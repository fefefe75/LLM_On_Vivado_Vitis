--------------------------------------------------------------------------------
--! @file    tb_word_parity_counter.vhd
--! @brief   Testbench VHDL pur, auto-verifiant, pour word_parity_counter.
--!
--! @details
--!   *Aucune* bibliotheque de verification proprietaire : ni OSVVM, ni UVVM,
--!   ni cocotb, ni std.env. Uniquement les paquets IEEE standards :
--!     ieee.std_logic_1164, ieee.numeric_std, ieee.math_real.
--!   Le meme fichier tourne tel quel sous Vivado XSim et sous GHDL.
--!
--!   Le testbench est *auto-verifiant* :
--!     - un modele de reference est tenu dans la procedure `cycle` (etat
--!       memorise, latence, compteur de mots) et compare aux sorties des
--!       deux DUT a chaque cycle ;
--!     - une fonction `parity_ref` recalcule la parite independamment du DUT ;
--!     - une table de reference figee (C_REF_PARITY_LOW) verifie la fonction
--!       de parite elle-meme ;
--!     - chaque echec incremente un compteur d'erreurs et emet un
--!       `report ... severity error` ;
--!     - la simulation se termine par `report "ALL TESTS PASSED" severity note`
--!       si et seulement si le compteur d'erreurs est nul.
--!
--!   Stimulation :
--!     (1)  reset synchrone (et preuve qu'il ne prend effet qu'au front) ;
--!     (2)  verification de la latence de 1 cycle ;
--!     (3)  balayage *exhaustif* des 2**C_DATA_WIDTH mots d'entree ;
--!     (4)  trous dans i_valid : le compteur ne doit compter que les mots
--!          reellement valides ;
--!     (5)  stimulation *aleatoire reproductible* (graine fixe, uniform de
--!          ieee.math_real) avec i_valid aleatoire ;
--!     (6)  reset synchrone en plein trafic.
--!
--! @note  Fichiers de sortie optionnels volontairement ecartes : ce testbench
--!        n'ecrit NI VCD/FST/GHW, NI fichier de reference externe. Il est
--!        auto-verifiant et ne depend d'aucun fichier sur disque. Le trace
--!        d'ondes est laisse au simulateur (xsim_wave.tcl sous XSim, ou
--!        `ghdl -r --wave=...` en option sous GHDL).
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.math_real.all;

--------------------------------------------------------------------------------
--! @brief Testbench du generateur de parite + compteur de mots.
--! @param C_DATA_WIDTH     Largeur des mots testes (8 par defaut).
--! @param C_CLK_PERIOD     Periode d'horloge (10 ns = 100 MHz).
--! @param C_SETTLE         Delai d'echantillonnage apres un front (1 ns).
--! @param C_SEED_VALID     Graine 1 du generateur aleatoire (i_valid).
--! @param C_SEED_DATA      Graine 2 du generateur aleatoire (i_data).
--! @param C_RANDOM_VECTORS Nombre de cycles aleatoires joues.
--! @param C_MAX_CYCLES     Garde-fou : nombre de cycles maximal autorise.
--------------------------------------------------------------------------------
entity tb_word_parity_counter is
  generic (
    C_DATA_WIDTH     : positive := 8;
    C_CLK_PERIOD     : time     := 10 ns;
    C_SETTLE         : time     := 1 ns;
    C_SEED_VALID     : positive := 12345;
    C_SEED_DATA      : positive := 6789;
    C_RANDOM_VECTORS : natural  := 500;
    C_MAX_CYCLES     : positive := 100000
  );
end entity tb_word_parity_counter;

--------------------------------------------------------------------------------
--! @brief Architecture de simulation.
--------------------------------------------------------------------------------
architecture sim of tb_word_parity_counter is

  -- Nombre de mots du balayage exhaustif
  constant C_NB_WORDS : natural := 2 ** C_DATA_WIDTH;

  -- Table de reference figee : parite PAIRE des valeurs 0 a 15
  -- (index 0 = valeur 0). Verifiee par le test 4.5 ci-dessous.
  constant C_REF_PARITY_LOW : std_logic_vector(0 to 15) := "0110100110010110";

  constant C_ZERO16 : std_logic_vector(15 downto 0) := (others => '0');

  -- Horloge et commandes communes aux deux instances
  signal s_clk     : std_logic := '0';
  signal s_clk_en  : boolean   := true;   --! coupe l'horloge en fin de test
  signal s_rst     : std_logic := '1';    --! reset synchrone actif haut
  signal s_valid   : std_logic := '0';
  signal s_data    : std_logic_vector(C_DATA_WIDTH - 1 downto 0) := (others => '0');

  -- Instance 1 : parite paire (C_ODD_PARITY = false)
  signal s_valid_even  : std_logic;
  signal s_parity_even : std_logic;
  signal s_words_even  : std_logic_vector(15 downto 0);

  -- Instance 2 : parite impaire (C_ODD_PARITY = true) -> teste le generique
  signal s_valid_odd  : std_logic;
  signal s_parity_odd : std_logic;
  signal s_words_odd  : std_logic_vector(15 downto 0);

  -- Observation / resultats (visibles dans la trace d'ondes)
  signal s_errors : natural := 0;
  signal s_checks : natural := 0;
  signal s_done   : boolean := false;

begin

  ------------------------------------------------------------------------------
  --! @brief Generateur d'horloge. S'arrete quand s_clk_en passe a false, ce
  --!        qui permet a `xsim -R` (run all) et a GHDL de terminer d'eux-memes.
  ------------------------------------------------------------------------------
  p_clk : process
  begin
    while s_clk_en loop
      s_clk <= '0';
      wait for C_CLK_PERIOD / 2;
      s_clk <= '1';
      wait for C_CLK_PERIOD / 2;
    end loop;
    wait;
  end process p_clk;

  ------------------------------------------------------------------------------
  --! @brief Garde-fou : surveille le nombre de cycles et non le temps simule,
  --!        afin de ne pas maintenir de transaction en file d'attente.
  ------------------------------------------------------------------------------
  p_watchdog : process
    variable v_cycles : natural := 0;
  begin
    while not s_done loop
      wait until rising_edge(s_clk);
      v_cycles := v_cycles + 1;
      if v_cycles > C_MAX_CYCLES then
        report "TIMEOUT : le testbench n'a pas termine en "
               & integer'image(C_MAX_CYCLES) & " cycles" severity failure;
      end if;
    end loop;
    wait;
  end process p_watchdog;

  ------------------------------------------------------------------------------
  -- DUT : deux instances, meme stimulus, seul le generique C_ODD_PARITY change
  ------------------------------------------------------------------------------
  dut_even : entity work.word_parity_counter
    generic map (
      C_DATA_WIDTH => C_DATA_WIDTH,
      C_ODD_PARITY => false
    )
    port map (
      i_clk    => s_clk,
      i_rst    => s_rst,
      i_valid  => s_valid,
      i_data   => s_data,
      o_valid  => s_valid_even,
      o_parity => s_parity_even,
      o_words  => s_words_even
    );

  dut_odd : entity work.word_parity_counter
    generic map (
      C_DATA_WIDTH => C_DATA_WIDTH,
      C_ODD_PARITY => true
    )
    port map (
      i_clk    => s_clk,
      i_rst    => s_rst,
      i_valid  => s_valid,
      i_data   => s_data,
      o_valid  => s_valid_odd,
      o_parity => s_parity_odd,
      o_words  => s_words_odd
    );

  ------------------------------------------------------------------------------
  --! @brief Processus de test (stimulus + verification).
  ------------------------------------------------------------------------------
  p_test : process

    -- Compteurs
    variable v_errors : natural := 0;
    variable v_checks : natural := 0;

    -- Modele de reference de l'etat memorise du DUT
    variable v_ref_valid : std_logic := '0';
    variable v_ref_data  : std_logic_vector(C_DATA_WIDTH - 1 downto 0) := (others => '0');
    variable v_ref_words : natural := 0;

    -- Generateur pseudo-aleatoire (graine fixe => reproductible)
    variable v_seed_a : positive := C_SEED_VALID;
    variable v_seed_b : positive := C_SEED_DATA;
    variable v_rand   : real;
    variable v_valid  : std_logic;
    variable v_data   : std_logic_vector(C_DATA_WIDTH - 1 downto 0);

    ----------------------------------------------------------------------------
    --! @brief Modele de reference de la parite (recalcul independant du DUT).
    --! @param data Mot dont on veut la parite.
    --! @param odd  true = parite impaire, false = parite paire.
    ----------------------------------------------------------------------------
    function parity_ref (constant data : std_logic_vector; constant odd : boolean)
      return std_logic is
      variable v_xor : std_logic := '0';
    begin
      for i in data'range loop
        v_xor := v_xor xor data(i);
      end loop;
      if odd then
        return not v_xor;
      else
        return v_xor;
      end if;
    end function parity_ref;

    ----------------------------------------------------------------------------
    --! @brief Verification d'une condition : compte les verifications et
    --!        incremente le compteur d'erreurs avec un report severity error.
    --! @param cond Condition attendue vraie.
    --! @param msg  Message lisible decrivant la verification.
    --! @param err  Compteur d'erreurs (inout).
    --! @param nb   Compteur de verifications (inout).
    ----------------------------------------------------------------------------
    procedure check (constant cond : boolean;
                     constant msg  : string;
                     variable err  : inout natural;
                     variable nb   : inout natural) is
    begin
      nb := nb + 1;
      if not cond then
        err := err + 1;
        report "ECHEC : " & msg severity error;
      end if;
    end procedure check;

    ----------------------------------------------------------------------------
    --! @brief Joue un cycle d'horloge complet et verifie les sorties.
    --!
    --! 1. applique (i_valid, i_data) ;
    --! 2. avant le front, compare les sorties des deux DUT au modele de
    --!    reference (etat memorise au cycle precedent) ;
    --! 3. attend le front montant, laisse passer C_SETTLE ;
    --! 4. met a jour le modele avec ce que les bascules viennent de memoriser.
    --!
    --! @param valid_in Niveau applique sur i_valid pendant ce cycle.
    --! @param data_in  Mot applique sur i_data (utilise si valid_in = '1').
    ----------------------------------------------------------------------------
    procedure cycle (constant valid_in : std_logic;
                     constant data_in  : std_logic_vector;
                     variable err      : inout natural;
                     variable nb       : inout natural) is
    begin
      s_valid <= valid_in;
      if valid_in = '1' then
        s_data <= data_in;
      end if;

      -- (2) etat memorise attendu, echantillonne juste avant le front
      check(s_valid_even  = v_ref_valid,
            "DUT_pair  : o_valid (etat memorise, mot#" & integer'image(v_ref_words) & ")", err, nb);
      check(s_parity_even = parity_ref(v_ref_data, false),
            "DUT_pair  : o_parity (mot memorise, mot#" & integer'image(v_ref_words) & ")", err, nb);
      check(s_words_even  = std_logic_vector(to_unsigned(v_ref_words, 16)),
            "DUT_pair  : o_words (mot memorise, mot#" & integer'image(v_ref_words) & ")", err, nb);
      check(s_valid_odd  = v_ref_valid,
            "DUT_impair: o_valid (etat memorise, mot#" & integer'image(v_ref_words) & ")", err, nb);
      check(s_parity_odd = parity_ref(v_ref_data, true),
            "DUT_impair: o_parity (mot memorise, mot#" & integer'image(v_ref_words) & ")", err, nb);
      check(s_words_odd  = std_logic_vector(to_unsigned(v_ref_words, 16)),
            "DUT_impair: o_words (mot memorise, mot#" & integer'image(v_ref_words) & ")", err, nb);

      wait until rising_edge(s_clk);
      wait for C_SETTLE;

      -- (4) mise a jour du modele : compteur de mots puis etage d'entree
      if v_ref_valid = '1' then
        v_ref_words := v_ref_words + 1;
      end if;
      v_ref_valid := valid_in;
      if valid_in = '1' then
        v_ref_data := data_in;
      end if;
    end procedure cycle;

  begin
    ----------------------------------------------------------------------------
    report "=== tb_word_parity_counter : debut de simulation ===" severity note;
    report "    C_DATA_WIDTH     = " & integer'image(C_DATA_WIDTH) severity note;
    report "    C_RANDOM_VECTORS = " & integer'image(C_RANDOM_VECTORS) severity note;

    check(C_DATA_WIDTH >= 4, "hypothese : C_DATA_WIDTH >= 4", v_errors, v_checks);

    ----------------------------------------------------------------------------
    -- (1) ETAT INITIAL : reset synchrone actif haut
    ----------------------------------------------------------------------------
    report "-- (1) reset synchrone --" severity note;
    s_rst   <= '1';
    s_valid <= '0';
    s_data  <= (others => '0');
    wait until rising_edge(s_clk);
    wait for C_SETTLE;
    wait until rising_edge(s_clk);
    wait for C_SETTLE;

    check(s_valid_even  = '0',     "DUT_pair  : o_valid = 0 pendant le reset",      v_errors, v_checks);
    check(s_words_even  = C_ZERO16,"DUT_pair  : o_words = 0 pendant le reset",      v_errors, v_checks);
    check(s_parity_even = '0',     "DUT_pair  : parite paire de 0x00 = 0",          v_errors, v_checks);
    check(s_valid_odd   = '0',     "DUT_impair: o_valid = 0 pendant le reset",      v_errors, v_checks);
    check(s_words_odd   = C_ZERO16,"DUT_impair: o_words = 0 pendant le reset",      v_errors, v_checks);
    check(s_parity_odd  = '1',     "DUT_impair: parite impaire de 0x00 = 1",        v_errors, v_checks);

    ----------------------------------------------------------------------------
    -- (1b) LATENCE et caractere SYNCHRONE du reset
    ----------------------------------------------------------------------------
    report "-- (1b) latence de 1 cycle + reset synchrone --" severity note;
    s_rst <= '0';
    v_ref_valid := '0';
    v_ref_data  := (others => '0');
    v_ref_words := 0;

    -- un mot avec un seul bit a 1 -> parite = 1 dans les deux conventions
    v_data  := std_logic_vector(to_unsigned(1, C_DATA_WIDTH));
    s_valid <= '1';
    s_data  <= v_data;

    -- juste avant le front : aucune sortie ne doit encore bouger (latence = 1)
    check(s_valid_even = '0', "DUT_pair  : pas de o_valid avant le front (latence = 1 cycle)",
          v_errors, v_checks);
    check(s_parity_even = '0', "DUT_pair  : o_parity encore nulle avant le front",
          v_errors, v_checks);

    wait until rising_edge(s_clk);
    wait for C_SETTLE;
    check(s_valid_even  = '1', "DUT_pair  : o_valid = 1 un cycle apres i_valid", v_errors, v_checks);
    check(s_parity_even = '1', "DUT_pair  : parite paire du mot 0x01 = 1",       v_errors, v_checks);
    check(s_parity_odd  = '0', "DUT_impair: parite impaire du mot 0x01 = 0",     v_errors, v_checks);
    check(s_words_even  = C_ZERO16,
          "DUT_pair  : o_words = 0 (le compteur retarde d'un cycle sur o_valid)", v_errors, v_checks);

    -- reset arme *entre* deux fronts : les sorties ne doivent pas changer
    s_rst <= '1';
    check(s_valid_even  = '1', "DUT_pair  : reset synchrone inactif entre deux fronts (o_valid)",
          v_errors, v_checks);
    check(s_parity_even = '1', "DUT_pair  : reset synchrone inactif entre deux fronts (o_parity)",
          v_errors, v_checks);
    wait until rising_edge(s_clk);
    wait for C_SETTLE;
    check(s_valid_even  = '0',     "DUT_pair  : o_valid = 0 apres un front de reset", v_errors, v_checks);
    check(s_parity_even = '0',     "DUT_pair  : parite remise a 0 par le reset",      v_errors, v_checks);
    check(s_words_even  = C_ZERO16,"DUT_pair  : o_words remis a 0 par le reset",      v_errors, v_checks);

    -- etat de reference remis a zero apres le reset
    s_rst <= '0';
    v_ref_valid := '0';
    v_ref_data  := (others => '0');
    v_ref_words := 0;

    ----------------------------------------------------------------------------
    -- (3) BALAYAGE EXHAUSTIF des 2**C_DATA_WIDTH mots (verifie par `cycle`)
    ----------------------------------------------------------------------------
    report "-- (3) balayage exhaustif : " & integer'image(C_NB_WORDS) & " mots --" severity note;
    for i in 0 to C_NB_WORDS - 1 loop
      cycle('1', std_logic_vector(to_unsigned(i, C_DATA_WIDTH)), v_errors, v_checks);
    end loop;
    check(unsigned(s_words_even) = C_NB_WORDS - 1,
          "DUT_pair  : o_words = nb_mots-1 apres le balayage (dernier mot affiche)", v_errors, v_checks);

    ----------------------------------------------------------------------------
    -- (4) TROUS DANS i_valid : seuls les mots valides sont comptes
    ----------------------------------------------------------------------------
    report "-- (4) i_valid a 0 : le compteur se fige --" severity note;
    cycle('0', v_data, v_errors, v_checks);   -- purge la derniere pulse o_valid
    check(s_valid_even = '0', "DUT_pair  : o_valid = 0 un cycle apres i_valid = 0", v_errors, v_checks);
    check(unsigned(s_words_even) = C_NB_WORDS,
          "DUT_pair  : o_words = nb total de mots presentes", v_errors, v_checks);
    for k in 0 to 2 loop
      cycle('0', v_data, v_errors, v_checks);
      check(unsigned(s_words_even) = C_NB_WORDS,
            "DUT_pair  : o_words fige tant que i_valid = 0 (cycle#" & integer'image(k) & ")",
            v_errors, v_checks);
    end loop;

    -- reprise : 4 mots espaces d'un cycle vide
    report "-- (4b) reprise apres des trous --" severity note;
    for k in 0 to 3 loop
      cycle('0', v_data, v_errors, v_checks);
      v_data := std_logic_vector(to_unsigned(16#A0# + k, C_DATA_WIDTH));
      cycle('1', v_data, v_errors, v_checks);
    end loop;

    ----------------------------------------------------------------------------
    -- (4.5) TABLE DE REFERENCE FIGEE : verifie la fonction de parite elle-meme
    ----------------------------------------------------------------------------
    report "-- (4.5) table de reference figee (parite paire de 0 a 15) --" severity note;
    for i in 0 to 15 loop
      check(parity_ref(std_logic_vector(to_unsigned(i, 4)), false) = C_REF_PARITY_LOW(i),
            "modele    : parite paire de la valeur " & integer'image(i)
            & " = bit#" & integer'image(i) & " de " & "0110100110010110", v_errors, v_checks);
    end loop;

    ----------------------------------------------------------------------------
    -- (5) STIMULATION ALEATOIRE REPRODUCTIBLE (graine fixe)
    ----------------------------------------------------------------------------
    report "-- (5) " & integer'image(C_RANDOM_VECTORS)
           & " cycles aleatoires (graines " & integer'image(C_SEED_VALID)
           & "/" & integer'image(C_SEED_DATA) & ") --" severity note;
    for k in 1 to C_RANDOM_VECTORS loop
      -- i_valid aleatoire : environ 80 % de mots valides
      uniform(v_seed_a, v_seed_b, v_rand);
      if v_rand < 0.8 then
        v_valid := '1';
      else
        v_valid := '0';
      end if;
      -- donnee aleatoire sur toute la largeur du mot
      uniform(v_seed_a, v_seed_b, v_rand);
      v_data := std_logic_vector(to_unsigned(integer(v_rand * real(2 ** C_DATA_WIDTH - 1)),
                                             C_DATA_WIDTH));
      cycle(v_valid, v_data, v_errors, v_checks);
    end loop;

    ----------------------------------------------------------------------------
    -- (6) RESET SYNCHRONE EN PLEIN TRAFIC
    ----------------------------------------------------------------------------
    report "-- (6) reset en plein trafic --" severity note;
    cycle('1', std_logic_vector(to_unsigned(16#3C#, C_DATA_WIDTH)), v_errors, v_checks);
    cycle('1', std_logic_vector(to_unsigned(16#C3#, C_DATA_WIDTH)), v_errors, v_checks);

    -- reset arme entre deux fronts : rien ne bouge avant le front
    s_rst <= '1';
    check(s_valid_even = '1', "DUT_pair  : le reset n'agit pas entre deux fronts (en trafic)",
          v_errors, v_checks);
    wait until rising_edge(s_clk);
    wait for C_SETTLE;
    check(s_valid_even  = '0',     "DUT_pair  : o_valid = 0 apres reset en trafic", v_errors, v_checks);
    check(s_words_even  = C_ZERO16,"DUT_pair  : o_words remis a 0 par le reset en trafic", v_errors, v_checks);
    check(s_parity_even = '0',     "DUT_pair  : o_parity remise a 0 par le reset en trafic", v_errors, v_checks);
    check(s_words_odd   = C_ZERO16,"DUT_impair: o_words remis a 0 par le reset en trafic", v_errors, v_checks);
    s_rst <= '0';
    v_ref_valid := '0';
    v_ref_data  := (others => '0');
    v_ref_words := 0;

    -- la sortie doit repartir proprement apres le reset
    report "-- (6b) reprise apres reset --" severity note;
    for k in 0 to 4 loop
      cycle('1', std_logic_vector(to_unsigned(16#11# * (k + 1), C_DATA_WIDTH)), v_errors, v_checks);
    end loop;

    ----------------------------------------------------------------------------
    -- FIN : rapport et arret propre de la simulation
    ----------------------------------------------------------------------------
    s_errors <= v_errors;
    s_checks <= v_checks;
    s_done   <= true;

    report "*** " & integer'image(v_checks) & " verifications effectuees, "
           & integer'image(v_errors) & " erreur(s) ***" severity note;

    if v_errors = 0 then
      report "ALL TESTS PASSED" severity note;
    else
      report "TESTS FAILED : " & integer'image(v_errors) & " erreur(s)" severity failure;
    end if;

    -- on coupe l'horloge : plus aucun evenement programme, donc `xsim -R`
    -- (run all) et GHDL se terminent sans temps d'arret explicite.
    s_clk_en <= false;
    wait;
  end process p_test;

end architecture sim;
