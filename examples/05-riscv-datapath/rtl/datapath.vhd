library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity datapath is
    port(
        --! Input
        i_clk          : in std_logic;
        i_rst          : in std_logic;
        i_instruction  : in std_logic_vector(31 downto 0); -- L'instruction lue
        i_ram_data     : in std_logic_vector(31 downto 0); -- Donnée lue de la RAM
        i_pc           : in std_logic_vector(31 downto 0);
        --! Output
        o_next_pc      : out std_logic_vector(31 downto 0); -- Le PC calculé pour le prochain cycle
        o_ram_addr     : out std_logic_vector(31 downto 0); -- Adresse pour la RAM
        o_ram_data     : out std_logic_vector(31 downto 0); -- Donnée à écrire dans la RAM
        o_mem_read     : out std_logic;
        o_mem_write    : out std_logic;
        o_branch       : out std_logic
    );
end entity datapath;

architecture arch_datapath of datapath is

    -- Signaux de liaison Décodeur
    signal s_rs1_addr      : std_logic_vector(4 downto 0);
    signal s_rs2_addr      : std_logic_vector(4 downto 0);
    signal s_rd_addr       : std_logic_vector(4 downto 0);
    signal s_reg_write_en  : std_logic;
    signal s_immediat      : std_logic;
    signal s_alu_cmd       : std_logic_vector(5 downto 0);
    signal s_imm_extended  : std_logic_vector(31 downto 0);
    signal s_mem_read      : std_logic;
    signal s_mem_write     : std_logic;
    signal s_branch        : std_logic;

    -- Signaux de liaison Banc de Registres
    signal s_rs1_data      : std_logic_vector(31 downto 0);
    signal s_rs2_data      : std_logic_vector(31 downto 0);
    signal s_rd_data       : std_logic_vector(31 downto 0); -- Sortie du MUX écriture

    -- Signaux de liaison ALU
    signal s_alu_val2      : std_logic_vector(31 downto 0); -- Sortie du MUX ALU
    signal s_alu_result    : std_logic_vector(31 downto 0);
    signal s_alu_flag      : std_logic;

    -- Nouveaux signaux pour le calcul du PC
    signal s_pc_plus_4       : std_logic_vector(31 downto 0);
    signal s_pc_target       : std_logic_vector(31 downto 0);
    signal s_take_branch     : std_logic;

begin

    --! Instanciation du décodeur d'instructions
    P_u_decoder : entity work.decoder
        port map(
            i_clk          => i_clk,
            i_rst          => i_rst,
            i_pc           => i_instruction, -- i_pc reçoit l'instruction dans ton décodeur
            o_reg_rs1_addr => s_rs1_addr,
            o_reg_rs2_addr => s_rs2_addr,
            o_reg_rd_addr  => s_rd_addr,
            o_reg_write_en => s_reg_write_en,
            o_immediat     => s_immediat,
            o_alu_cmd      => s_alu_cmd,
            o_imm_extended => s_imm_extended,
            o_mem_read     => s_mem_read,
            o_mem_write    => s_mem_write,
            o_branch       => s_branch
        );

    --! Instanciation du banc de registres
    P_u_banc_registre : entity work.banc_registre
        port map(
            i_clk          => i_clk,
            i_rst          => i_rst,
            i_reg_write_en => s_reg_write_en,
            i_rs1_addr     => s_rs1_addr,
            i_rs2_addr     => s_rs2_addr,
            i_rd_addr      => s_rd_addr,
            i_rd_data      => s_rd_data,
            o_rs1_data     => s_rs1_data,
            o_rs2_data     => s_rs2_data
        );

    --! Multiplexeur pour l'entrée numéro 2 de l'ALU
    s_alu_val2 <= s_imm_extended when (s_immediat = '1') else s_rs2_data;

    --! Instanciation de l'ALU
    P_u_alu : entity work.alu
        port map(
            i_clk    => i_clk,
            i_rst    => i_rst,
            i_val_1  => s_rs1_data,
            i_val_2  => s_alu_val2,
            i_opcode => s_alu_cmd,
            o_flag   => s_alu_flag,
            o_data   => s_alu_result
        );

    --! CALCULS DES ADRESSES PC
    s_pc_plus_4 <= std_logic_vector(unsigned(i_pc) + 4);
    
    -- L'adresse cible d'un saut ou d'un branchement (PC + Immédiat étendu)
    s_pc_target <= std_logic_vector(unsigned(i_pc) + unsigned(s_imm_extended));

    --! LOGIQUE DE BRANCHEMENT (Pour ton if/else et ton BNE)
    s_take_branch <= '1' when (s_branch = '1' and s_alu_flag = '0') else '0';

    --! 3. MULTIPLEXEUR DU PROCHAIN PC
    -- Choix entre : Continuer tout droit (PC+4), Sauter (PC+Imm) ou JALR (Adresse absolue de l'ALU)
    P_MULT_NEXT_PC : process(s_take_branch, s_pc_plus_4, s_pc_target, s_alu_result, i_instruction)
    begin
        if (i_instruction(6 downto 0) = "1100111") then -- Si c'est un JALR (ret)
            o_next_pc <= s_alu_result;                  -- L'adresse est calculée directement par l'ALU
        elsif (s_take_branch = '1' or i_instruction(6 downto 0) = "1101111") then -- Si BNE valide ou JAL (j)
            o_next_pc <= s_pc_target;                   -- On prend la cible du saut
        else
            o_next_pc <= s_pc_plus_4;                   -- Sinon, instruction suivante classique
        end if;
    end process;

    --! 4. MULTIPLEXEUR D'ÉCRITURE DANS RD (Mis à jour pour sauvegarder l'adresse de retour des fonctions)
    P_MULT_RD : process(s_mem_read, i_instruction, i_ram_data, s_alu_result, s_pc_plus_4)
    begin
        if (s_mem_read = '1') then
            s_rd_data <= i_ram_data; -- Lecture RAM (LW)
        elsif (i_instruction(6 downto 0) = "1101111" or i_instruction(6 downto 0) = "1100111") then
            s_rd_data <= s_pc_plus_4; -- Sauvegarde de l'adresse de retour pour JAL/JALR
        else
            s_rd_data <= s_alu_result; -- Calcul ALU classique (ADD, ADDI...)
        end if;
    end process;

    --! Affectations physiques
    o_ram_addr   <= s_alu_result; 
    o_ram_data   <= s_rs2_data;   
    o_mem_read   <= s_mem_read;
    o_mem_write  <= s_mem_write;
    o_branch     <= s_branch;

end architecture arch_datapath;