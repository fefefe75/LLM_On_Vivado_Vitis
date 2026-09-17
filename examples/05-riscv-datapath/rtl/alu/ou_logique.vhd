library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;


entity ou_logique is
    port(
        --! Input
        i_clk : in std_logic;
        i_rst : in std_logic;

        i_val_1 : in std_logic_vector(31 downto 0);
        i_val_2 : in std_logic_vector(31 downto 0);
        --! Output
        o_data : out std_logic_vector(31 downto 0)
    );
end entity ou_logique;

architecture arch_ou_logique of ou_logique is
begin
    
    P_ou_logique : process(i_clk)
    begin
        if rising_edge(i_clk) then
            if(i_rst = '1') then
                o_data <= (others => '0');
            else
                --! Renvoie de la valeur
                o_data <= i_val_1 or i_val_2;
        end if;
    end if;
    end process;
end architecture arch_ou_logique;
