library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Compteur synchrone avec enable, reset, remise a zero et plafond.
--! @details Sert de base a tout compteur : diviser une horloge, compter des evenements,
--!          adresser une memoire. Verifie : ghdl -a --std=08 compteur.vhd
entity compteur is
    generic (
        C_WIDTH : positive := 8;
        C_MAX   : natural  := 255                --! plafond : reboucle a 0 apres C_MAX
    );
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                 --! reset synchrone actif haut
        i_en    : in  std_logic;                 --! increment quand '1'
        i_clear : in  std_logic;                 --! remise a zero sans reset
        o_count : out std_logic_vector(C_WIDTH - 1 downto 0);
        o_tick  : out std_logic                  --! impulsion d'un cycle a chaque plafond
    );
end entity compteur;

architecture rtl of compteur is
    signal s_count : unsigned(C_WIDTH - 1 downto 0) := (others => '0');
    signal s_tick  : std_logic := '0';
begin

    o_count <= std_logic_vector(s_count);
    o_tick  <= s_tick;

    p_count : process (i_clk)
    begin
        if rising_edge(i_clk) then
            s_tick <= '0';                       -- impulsion d'un seul cycle
            if i_rst = '1' or i_clear = '1' then
                s_count <= (others => '0');
            elsif i_en = '1' then
                if s_count = to_unsigned(C_MAX, C_WIDTH) then
                    s_count <= (others => '0');
                    s_tick  <= '1';
                else
                    s_count <= s_count + 1;
                end if;
            end if;
        end if;
    end process p_count;

end architecture rtl;
