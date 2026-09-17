--! ALU (arythmetic logic unit)
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity alu is
    port(
        --! Input
        i_clk : in std_logic;
        i_rst : in std_logic;
        i_val_1 : in std_logic_vector(31 downto 0);
        i_val_2 : in std_logic_vector(31 downto 0);
        i_opcode : in std_logic_vector(5 downto 0);
        --! Output
        o_flag : out std_logic;
        o_data : out std_logic_vector(31 downto 0)
    );
end entity alu;

architecture arch_alu of alu is
    --! Pour les différents flags
    signal flag_sub : std_logic := '0';
    signal flag_som : std_logic := '0';
    --! Pour les différentes data
    signal s_data_et   : std_logic_vector(31 downto 0);
    signal s_data_ou   : std_logic_vector(31 downto 0);
    signal s_data_som  : std_logic_vector(31 downto 0);
    signal s_data_sub  : std_logic_vector(31 downto 0);
begin
    --! Et logique
    P_et : entity work.et_logique
        port map(
            i_clk   => i_clk,
            i_rst   => i_rst,
            i_val_1 => i_val_1,
            i_val_2 => i_val_2,
            o_data  => s_data_et
        );
    --! Ou logique
    P_ou : entity work.ou_logique
        port map(
            i_clk   => i_clk,
            i_rst   => i_rst,
            i_val_1 => i_val_1,
            i_val_2 => i_val_2,
            o_data  => s_data_ou
        );
    --! Somme
    P_somme : entity work.somme
        port map(
            i_clk   => i_clk,
            i_rst   => i_rst,
            i_val_1 => i_val_1,
            i_val_2 => i_val_2,
            o_flag  => flag_som,
            o_data  => s_data_som
        );
    --! Soustraction
    P_soustraction : entity work.soustraction
        port map(
            i_clk   => i_clk,
            i_rst   => i_rst,
            i_val_1 => i_val_1,
            i_val_2 => i_val_2,
            o_flag  => flag_sub,
            o_data  => s_data_sub
        );
    
    --! Multiplexeur pour choisir qui l'on envoie
    P_Multiplexeur_opcode : process(i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst ='1' then
                o_flag <= '0';
                o_data <= (others => '0');
            else
                case i_opcode is
                    when "000000" => o_data <= s_data_et;
                                o_flag <= '0';

                    when "000001" => o_data <= s_data_ou;
                                o_flag <= '0';

                    when "000010" => o_data <= s_data_som;
                                o_flag <= flag_som;

                    when "000011" => o_data <= s_data_sub;
                                o_flag <= flag_sub;
                when others =>
                    end case;
                
            end if;
        end if;
    end process;
end architecture arch_alu;
