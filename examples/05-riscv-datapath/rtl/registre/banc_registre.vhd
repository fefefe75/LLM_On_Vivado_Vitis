--! Banc de Registres (Register File) pour processeur RV32I
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity banc_registre is
    port(
        --! Input Control
        i_clk          : in std_logic;
        i_rst          : in std_logic;
        i_reg_write_en : in std_logic; --! Autorisation d'écriture (Venu du décodeur)

        --! Input Addresses (5 bits pour pointer de x0 à x31)
        i_rs1_addr     : in std_logic_vector(4 downto 0); --! Source 1 (Venu du décodeur)
        i_rs2_addr     : in std_logic_vector(4 downto 0); --! Source 2 (Venu du décodeur)
        i_rd_addr      : in std_logic_vector(4 downto 0);  --! Destination (Venu du décodeur)

        --! Input Data (32 bits)
        i_rd_data      : in std_logic_vector(31 downto 0); --! Donnée à écrire (Venu de l'ALU ou RAM)

        --! Output Data (32 bits)
        o_rs1_data     : out std_logic_vector(31 downto 0); --! Donnée lue 1 (Va vers l'ALU)
        o_rs2_data     : out std_logic_vector(31 downto 0)  --! Donnée lue 2 (Va vers l'ALU ou Mux)
    );
end entity banc_registre;

architecture arch_banc_registre of banc_registre is
    --! Définition de la mémoire interne : un tableau de 32 lignes de 32 bits
    type t_banc_registres is array (0 to 31) of std_logic_vector(31 downto 0);
    signal regs : t_banc_registres := (others => (others => '0'));

begin

    -- =========================================================================
    -- 1. LECTURE COMBINATOIRE DIRECTE
    -- Conforme au PDF : x0 est câblé à zéro. Si on l'adresse, on sort "0".
    -- Pas besoin d'attendre l'horloge, la donnée sort dès que l'adresse change.
    -- =========================================================================
    
    -- Lecture du Registre Source 1
    o_rs1_data <= (others => '0') when (i_rs1_addr = "00000") else 
                  regs(to_integer(unsigned(i_rs1_addr)));

    -- Lecture du Registre Source 2
    o_rs2_data <= (others => '0') when (i_rs2_addr = "00000") else 
                  regs(to_integer(unsigned(i_rs2_addr)));


    -- =========================================================================
    -- 2. ÉCRITURE SYNCHRONE
    -- L'écriture se fait uniquement sur front d'horloge si elle est autorisée.
    -- Interdiction stricte d'écrire dans x0 (l'écriture est ignorée).
    -- =========================================================================
    P_Write_Register : process(i_clk)
    begin
        if rising_edge(i_clk) then
            if (i_rst = '1') then
                -- Réinitialisation de tous les registres à 0 
                regs <= (others => (others => '0'));
            else
                -- Si l'écriture est activée ET qu'on ne cible pas le registre x0
                if (i_reg_write_en = '1') and (i_rd_addr /= "00000") then
                    regs(to_integer(unsigned(i_rd_addr))) <= i_rd_data;
                end if;
            end if;
        end if;
    end process;

end architecture arch_banc_registre;