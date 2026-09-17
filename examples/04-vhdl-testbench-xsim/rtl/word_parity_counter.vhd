--------------------------------------------------------------------------------
--! @file    word_parity_counter.vhd
--! @brief   Generateur de parite + compteur de mots (design de test generique).
--!
--! @details
--!   Design *non trivial* volontairement petit, mais avec etage de registre,
--!   generique et reset synchrone : il sert de DUT aux exemples de
--!   verification (testbench VHDL pur sous XSim, co-simulation cocotb).
--!
--!   Pipeline a 1 etage :
--!     - front 1 : i_data / i_valid sont memorises dans des bascules ;
--!     - front 2 : o_valid / o_parity presentent le mot memorise et o_words
--!                 compte les mots deja presentes.
--!
--!   Latence : 1 cycle d'horloge entre i_valid/i_data et o_valid/o_parity.
--!   o_words est incremente a chaque front ou o_valid etait actif au cycle
--!   precedent : o_words = nombre de mots deja presentes (donc decale d'un
--!   cycle par rapport au mot affiche sur o_parity).
--!
--! @note  Reset synchrone, actif haut, une seule horloge (conventions du
--!        depot). Aucune dependance : ieee.std_logic_1164 + ieee.numeric_std.
--------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--------------------------------------------------------------------------------
--! @brief Generateur de parite serie + compteur de mots valides.
--! @param C_DATA_WIDTH Largeur en bits des mots d'entree (>= 1).
--! @param C_ODD_PARITY  false = parite paire (defaut), true = parite impaire.
--------------------------------------------------------------------------------
entity word_parity_counter is
  generic (
    C_DATA_WIDTH : positive := 8;
    C_ODD_PARITY : boolean  := false
  );
  port (
    i_clk    : in  std_logic;                                    --! horloge
    i_rst    : in  std_logic;                                    --! reset synchrone actif haut
    i_valid  : in  std_logic;                                    --! i_data est un mot valide
    i_data   : in  std_logic_vector(C_DATA_WIDTH - 1 downto 0);   --! mot d'entree
    o_valid  : out std_logic;                                    --! mise en forme : 1 apres i_valid
    o_parity : out std_logic;                                    --! bit de parite du mot memorise
    o_words  : out std_logic_vector(15 downto 0)                 --! nombre de mots presentes
  );
end entity word_parity_counter;

--------------------------------------------------------------------------------
--! @brief Architecture RTL : etage de registre + arbre XOR de parite.
--------------------------------------------------------------------------------
architecture rtl of word_parity_counter is

  -- Etat des bascules (reset synchrone : valeurs initiales utiles au simulateur)
  signal s_data_r  : std_logic_vector(C_DATA_WIDTH - 1 downto 0) := (others => '0');
  signal s_valid_r : std_logic                                    := '0';
  signal s_words_r : unsigned(15 downto 0)                        := (others => '0');

  -- Resultat de l'arbre XOR (combinatoire)
  signal s_xor : std_logic;

begin

  ------------------------------------------------------------------------------
  --! @brief Etage de registre : mise en forme de i_data / i_valid + comptage.
  --! @details Reset synchrone : i_rst n'est pris en compte qu'au front montant.
  ------------------------------------------------------------------------------
  p_pipeline : process (i_clk)
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_data_r  <= (others => '0');
        s_valid_r <= '0';
        s_words_r <= (others => '0');
      else
        s_valid_r <= i_valid;
        if i_valid = '1' then
          s_data_r <= i_data;
        end if;
        if s_valid_r = '1' then
          s_words_r <= s_words_r + 1;
        end if;
      end if;
    end if;
  end process p_pipeline;

  ------------------------------------------------------------------------------
  --! @brief Arbre XOR combinatoire sur le mot memorise.
  --! @details Ecrit sous forme de boucle (VHDL-93/2008) pour rester lisible
  --!          et portable sur tous les simulateurs.
  ------------------------------------------------------------------------------
  p_xor : process (s_data_r)
    variable v_xor : std_logic;
  begin
    v_xor := '0';
    for i in s_data_r'range loop
      v_xor := v_xor xor s_data_r(i);
    end loop;
    s_xor <= v_xor;
  end process p_xor;

  ------------------------------------------------------------------------------
  -- Sorties : parite paire ou impaire selon le generique
  ------------------------------------------------------------------------------
  o_valid  <= s_valid_r;
  o_parity <= not s_xor when C_ODD_PARITY else s_xor;
  o_words  <= std_logic_vector(s_words_r);

end architecture rtl;
