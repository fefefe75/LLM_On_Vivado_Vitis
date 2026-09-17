library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Testbench VHDL AUTO-VERIFIANT, executable par XSim (Vivado) sans cocotb.
--! @details Modele a copier : c'est la seule facon de tester un design quand
--!          l'environnement est Vivado-only (cocotb ne supporte pas XSim).
--!          Ici le DUT est le compteur fourni dans le meme dossier.
--!
--!   XSim : xvhdl -2008 compteur.vhd tb_compteur.vhd
--!          xelab -debug typical -s tb_sim work.tb_compteur
--!          xsim tb_sim -R
--!   GHDL : ghdl -a --std=08 compteur.vhd tb_compteur.vhd
--!          ghdl -m --std=08 tb_compteur && ghdl -r --std=08 tb_compteur
--!
--! Regles apprises en compilant ce fichier (erreurs reelles corrigees ici) :
--!   * une procedure ne peut PAS etre declaree apres le 'begin' d'une
--!     architecture : elle va dans une partie declarative (ici, celle du process) ;
--!   * en VHDL-2008, une 'shared variable' ordinaire est refusee
--!     ("type of a shared variable must be a protected type") : on utilise donc
--!     des variables locales au process, lues par une procedure imbriquee ;
--!   * la simulation doit se terminer explicitement : std.env.finish, sinon
--!     elle tourne indefiniment (et le cycle CI avec).
entity tb_compteur is
    generic (
        C_WIDTH   : positive := 8;
        C_MAX     : natural  := 15;                   --! petit plafond pour aller vite
        C_PERIODE : time     := 10 ns
    );
end entity tb_compteur;

architecture bench of tb_compteur is

    -- signaux relies au DUT
    signal i_clk   : std_logic := '0';
    signal i_rst   : std_logic := '1';
    signal i_en    : std_logic := '0';
    signal i_clear : std_logic := '0';
    signal o_count : std_logic_vector(C_WIDTH - 1 downto 0);
    signal o_tick  : std_logic;

    signal s_fin : boolean := false;

begin

    -- 1) DUT
    u_dut : entity work.compteur
        generic map (
            C_WIDTH => C_WIDTH,
            C_MAX   => C_MAX
        )
        port map (
            i_clk   => i_clk,
            i_rst   => i_rst,
            i_en    => i_en,
            i_clear => i_clear,
            o_count => o_count,
            o_tick  => o_tick
        );

    -- 2) horloge (process dedie, jamais une porte logique)
    p_clk : process
    begin
        while not s_fin loop
            i_clk <= '0';
            wait for C_PERIODE / 2;
            i_clk <= '1';
            wait for C_PERIODE / 2;
        end loop;
        wait;
    end process p_clk;

    -- 3) scenario de test
    p_test : process
        variable v_checks  : integer := 0;
        variable v_erreurs : integer := 0;
        variable v_attendu : natural := 0;

        -- verifie une condition ; la procedure voit les variables du process
        procedure verifier(condition : boolean; message : string) is
        begin
            v_checks := v_checks + 1;
            if not condition then
                v_erreurs := v_erreurs + 1;
                report "ECHEC : " & message & " (t=" & time'image(now) & ")"
                    severity error;
            end if;
        end procedure verifier;

        -- reset synchrone reutilisable (l'appelant a deja pose ses entrees)
        procedure reset_dut(cycles : natural := 3) is
        begin
            i_rst <= '1';
            i_en  <= '0';
            for n in 1 to cycles loop
                wait until rising_edge(i_clk);
            end loop;
            i_rst <= '0';
        end procedure reset_dut;

        -- front d'horloge AVEC echantillonnage sur.
        -- Piege majeur (mesure a la trace) : juste apres `wait until rising_edge(clk)`,
        -- la sortie du DUT n'est pas encore mise a jour (cycles delta) et on lit
        -- l'ANCIENNE valeur -- meme avec `wait for 0 ns`. L'idiome fiable est
        -- d'echantillonner AU MILIEU de la periode, exactement comme on lit une
        -- sortie sur front descendant en cocotb.
        procedure front is
        begin
            wait until rising_edge(i_clk);
            wait for C_PERIODE / 4;
        end procedure front;

    begin
        report "=== debut du testbench compteur ===" severity note;

        -- (a) reset : la sortie doit etre a 0
        reset_dut;
        front;
        verifier(unsigned(o_count) = 0, "compteur non nul apres reset");

        -- (b) comptage : i_en = 1 pendant N cycles
        i_en <= '1';
        for n in 1 to 5 loop
            front;
            v_attendu := n;
        end loop;
        verifier(unsigned(o_count) = v_attendu,
                 "comptage : attendu " & integer'image(v_attendu) &
                 " recu " & integer'image(to_integer(unsigned(o_count))));

        -- (c) gel : i_en = 0, la valeur ne bouge plus
        i_en <= '0';
        for n in 1 to 3 loop
            front;
        end loop;
        verifier(unsigned(o_count) = v_attendu, "le compteur a avance sans i_en");

        -- (d) clear : remise a zero sans reset
        i_clear <= '1';
        front;
        i_clear <= '0';
        front;
        verifier(unsigned(o_count) = 0, "clear n'a pas remis le compteur a zero");

        -- (e) plafond + impulsion o_tick
        i_en <= '1';
        for n in 1 to C_MAX loop
            front;
        end loop;
        verifier(unsigned(o_count) = C_MAX, "le compteur n'a pas atteint le plafond");
        verifier(o_tick = '0', "o_tick actif trop tot");

        front;                                            -- front du plafond
        verifier(unsigned(o_count) = 0, "pas de rebouclage apres le plafond");
        verifier(o_tick = '1', "impulsion o_tick absente au plafond");

        front;                                            -- l'impulsion ne dure qu'un cycle
        verifier(o_tick = '0', "o_tick dure plus d'un cycle");

        -- (f) bilan
        report "*** " & integer'image(v_checks) & " verifications, " &
               integer'image(v_erreurs) & " erreur(s) ***" severity note;

        if v_erreurs = 0 then
            report "ALL TESTS PASSED" severity note;
        else
            report "TESTS FAILED" severity failure;      -- fait echouer la simulation
        end if;

        s_fin <= true;
        wait for C_PERIODE;                              -- laisser l'horloge s'arreter
        std.env.finish;                                  -- VHDL-2008 : termine proprement
    end process p_test;

end architecture bench;
