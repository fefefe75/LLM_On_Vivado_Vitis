--------------------------------------------------------------------------------
-- fifo_sync.vhd
--
-- FIFO synchrone générique : une seule horloge, reset synchrone actif haut.
--
-- Conventions du dépôt : ports i_/o_, signaux s_, constantes C_, processus p_.
--
-- Choix de conception documentés (voir README.md du répertoire) :
--   * lecture NON « first word fall through » (mode standard) : o_data est
--     enregistré et n'est mis à jour que lors d'une lecture réussie ; il ne
--     dépend donc pas de façon combinatoire de la mémoire.
--   * la profondeur C_DEPTH est une puissance de 2 (vérifié à l'élaboration).
--   * o_full est un verrou dur : une écriture demandée quand o_full=1 est
--     ignorée, même si une lecture a lieu dans le même cycle (comportement des
--     FIFO « standard » Xilinx : le drapeau plein refuse l'écriture).
--   * écriture et lecture simultanées acceptées dès que la FIFO n'est ni pleine
--     ni vide : une entrée et une sortie dans le même cycle, o_level inchangé.
--
-- Largeur de o_level (points d'attention) :
--   la VHDL n'a pas de fonction log2 dans la bibliothèque standard ; la largeur
--   du compteur de remplissage ne peut donc pas être calculée dans la clause
--   de ports. Elle est fournie par le générique C_LEVEL_W, et C_DEPTH vaut par
--   défaut 2**(C_LEVEL_W-1). Les deux génériques sont vérifiés à l'élaboration :
--   une profondeur non puissance de 2 ou un C_LEVEL_W trop petit provoque une
--   erreur explicite (severity failure) au lieu d'une troncature silencieuse.
--------------------------------------------------------------------------------
library ieee;
  use ieee.std_logic_1164.all;
  use ieee.numeric_std.all;

entity fifo_sync is
  generic (
    C_WDATA   : positive := 8;                    -- largeur d'un mot (bits)
    C_LEVEL_W : positive := 4;                    -- largeur binaire de o_level
    C_DEPTH   : positive := 2 ** (C_LEVEL_W - 1)  -- profondeur (puissance de 2)
  );
  port (
    i_clk   : in  std_logic;
    i_rst   : in  std_logic;                                  -- reset synchrone, actif haut
    i_wr_en : in  std_logic;                                  -- demande d'écriture
    i_rd_en : in  std_logic;                                  -- demande de lecture
    i_data  : in  std_logic_vector(C_WDATA - 1 downto 0);     -- mot à écrire
    o_data  : out std_logic_vector(C_WDATA - 1 downto 0);     -- mot lu (valide après une lecture)
    o_full  : out std_logic;                                  -- FIFO pleine
    o_empty : out std_logic;                                  -- FIFO vide
    o_level : out std_logic_vector(C_LEVEL_W - 1 downto 0)    -- nombre de mots stockés
  );
end entity fifo_sync;

architecture rtl of fifo_sync is

  -- log2 exact d'une puissance de 2 (nb de divisions par 2 nécessaires).
  -- Fonction locale : la VHDL standard n'en fournit pas.
  function log2_pow2(v : positive) return natural is
    variable v_x : positive := v;
    variable v_n : natural := 0;
  begin
    while v_x > 1 loop
      v_x := v_x / 2;
      v_n := v_n + 1;
    end loop;
    return v_n;
  end function log2_pow2;

  function is_pow2(v : positive) return boolean is
  begin
    return v = 2 ** log2_pow2(v);
  end function is_pow2;

  constant C_PTR_W : positive := log2_pow2(C_DEPTH);  -- largeur des pointeurs
  constant C_CNT_W : positive := C_PTR_W + 1;         -- largeur minimale de o_level

  type t_mem is array (0 to C_DEPTH - 1) of std_logic_vector(C_WDATA - 1 downto 0);

  signal s_mem    : t_mem := (others => (others => '0'));
  signal s_wr_ptr : unsigned(C_PTR_W - 1 downto 0) := (others => '0');
  signal s_rd_ptr : unsigned(C_PTR_W - 1 downto 0) := (others => '0');
  signal s_count  : natural range 0 to C_DEPTH := 0;
  signal s_data   : std_logic_vector(C_WDATA - 1 downto 0) := (others => '0');

begin

  -- Vérifications d'élaboration (assertions concurrentes, évaluées au temps 0) :
  -- échec immédiat et message explicite plutôt qu'un débordement silencieux du
  -- compteur de remplissage.
  assert is_pow2(C_DEPTH)
    report "fifo_sync : C_DEPTH doit etre une puissance de 2 (C_DEPTH="
           & integer'image(C_DEPTH) & ")"
    severity failure;

  assert C_LEVEL_W >= C_CNT_W
    report "fifo_sync : C_LEVEL_W=" & integer'image(C_LEVEL_W)
           & " est trop petit pour C_DEPTH=" & integer'image(C_DEPTH)
           & " ; utilisez C_LEVEL_W >= " & integer'image(C_CNT_W)
    severity failure;

  p_fifo : process (i_clk) is
    variable v_wr_ok : boolean;
    variable v_rd_ok : boolean;
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        -- reset synchrone : pointeurs et compteur remis à zéro
        s_wr_ptr <= (others => '0');
        s_rd_ptr <= (others => '0');
        s_count  <= 0;
        s_data   <= (others => '0');
      else
        -- acceptation des demandes : o_full et o_empty sont des verrous durs,
        -- une écriture quand plein ou une lecture quand vide est ignorée
        v_wr_ok := (i_wr_en = '1') and (s_count < C_DEPTH);
        v_rd_ok := (i_rd_en = '1') and (s_count > 0);

        if v_wr_ok then
          s_mem(to_integer(s_wr_ptr)) <= i_data;
          s_wr_ptr <= s_wr_ptr + 1;          -- rebouclage modulo C_DEPTH
        end if;

        if v_rd_ok then
          s_data   <= s_mem(to_integer(s_rd_ptr));  -- lecture enregistrée (mode standard)
          s_rd_ptr <= s_rd_ptr + 1;
        end if;

        -- compteur de remplissage : inchangé si écriture et lecture simultanées
        if v_wr_ok and not v_rd_ok then
          s_count <= s_count + 1;
        elsif v_rd_ok and not v_wr_ok then
          s_count <= s_count - 1;
        end if;
      end if;
    end if;
  end process p_fifo;

  o_data  <= s_data;
  o_full  <= '1' when s_count = C_DEPTH else '0';
  o_empty <= '1' when s_count = 0 else '0';
  o_level <= std_logic_vector(to_unsigned(s_count, C_LEVEL_W));

end architecture rtl;
