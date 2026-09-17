library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Squelette d'un module SEQUENTIEL : registre avec enable et reset synchrone.
--! @details Verifie : ghdl -a --std=08 registre_synchrone.vhd
--!          Un seul process sequentiel, un seul style de reset (synchrone, actif haut).
entity registre_synchrone is
    generic (
        C_WIDTH : positive := 8;
        C_RESET_VALUE : natural := 0             --! valeur apres reset
    );
    port (
        i_clk : in  std_logic;
        i_rst : in  std_logic;                   --! reset SYNCHRONE actif haut
        i_en  : in  std_logic;                   --! '1' = charge i_d
        i_d   : in  std_logic_vector(C_WIDTH - 1 downto 0);
        o_q   : out std_logic_vector(C_WIDTH - 1 downto 0)
    );
end entity registre_synchrone;

architecture rtl of registre_synchrone is
    signal s_q : std_logic_vector(C_WIDTH - 1 downto 0) := (others => '0');
begin

    o_q <= s_q;

    p_seq : process (i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_q <= std_logic_vector(to_unsigned(C_RESET_VALUE, C_WIDTH));
            elsif i_en = '1' then
                s_q <= i_d;
            end if;
        end if;
    end process p_seq;

end architecture rtl;
