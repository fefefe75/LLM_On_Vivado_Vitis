library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity somme is
    port(
        --! Input
        i_clk : in std_logic;
        i_rst : in std_logic;

        i_val_1 : in std_logic_vector(31 downto 0);
        i_val_2 : in std_logic_vector(31 downto 0);
        --! Output
        o_flag : out std_logic;
        o_data : out std_logic_vector(31 downto 0)
    );
end entity somme;

architecture arch_somme of somme is
    signal s_calc_tempo_1 : unsigned(31 downto 0) := (others => '0');
    signal s_calc_tempo_2 : unsigned(31 downto 0) := (others => '0');
    signal s_buff : unsigned(31 downto 0) := (others => '0');
begin 

    --! Somme de deux valeurs
    P_somme : process(i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1' ) then
                s_calc_tempo_1 <= (others => '0');
                s_calc_tempo_2 <= (others => '0');
                s_buff <= (others => '0');
                o_flag <= '0';
                o_data <= (others => '0');
            else

                --! Début du calcul
                s_calc_tempo_1 <= unsigned(i_val_1);
                s_calc_tempo_2 <= unsigned(i_val_2);

                s_buff <= s_calc_tempo_1 + s_calc_tempo_2;
                --! Overflow
                if ((x"FFFFFFFF" - s_calc_tempo_1) < s_calc_tempo_2) then
                    o_flag <= '1';
                else
                    o_flag <= '0';
                end if;

                --! Renvoie de la valeur
                o_data <= std_logic_vector(s_buff);

            end if;
        end if;
    end process;

end arch_somme;
