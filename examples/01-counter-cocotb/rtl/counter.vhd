library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Compteur synchrone avec enable et reset synchrone actif haut.
--! @details Exemple de reference du depot : style, conventions de nommage et
--!          squelette d'un module sequentiel simple.
entity counter is
    generic (
        C_WIDTH : positive := 8
    );
    port (
        i_clk   : in  std_logic;
        i_rst   : in  std_logic;                                    --! reset synchrone, actif haut
        i_en    : in  std_logic;                                    --! increment quand '1'
        o_count : out std_logic_vector(C_WIDTH - 1 downto 0)        --! valeur courante
    );
end entity counter;

architecture rtl of counter is
    signal s_count : unsigned(C_WIDTH - 1 downto 0) := (others => '0');
begin

    o_count <= std_logic_vector(s_count);

    p_count : process (i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_count <= (others => '0');
            elsif i_en = '1' then
                s_count <= s_count + 1;
            end if;
        end if;
    end process p_count;

end architecture rtl;
