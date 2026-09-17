--! RV32I Type de processeur donc on suit ces instructions pour le decodeur
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity decoder is
    port(
        --! Input
        i_clk : in std_logic;
        i_rst : in std_logic;
        i_pc : in std_logic_vector(31 downto 0);

        --! Output.
        o_reg_rs1_addr : out std_logic_vector(4 downto 0);
        o_reg_rs2_addr : out std_logic_vector(4 downto 0);
        o_reg_rd_addr  : out std_logic_vector(4 downto 0);
        o_reg_write_en : out std_logic;
        o_immediat : out std_logic;                             --! Indique si l'instruction utilise un immédiat (1) ou non (0)
        o_alu_cmd : out std_logic_vector(5 downto 0);
        o_imm_extended : out std_logic_vector(31 downto 0);     --! Pour certaines instructions, l'immédiat est étendu à 32 bits pour l'ALU
        --! Sorties supplémentaires minimales pour le support du C
        o_mem_read     : out std_logic;                         --! Commande de lecture de la mémoire de données
        o_mem_write    : out std_logic;                         --! Commande d'écriture dans la mémoire de données
        o_branch       : out std_logic                          --! Indique une instruction de branchement (if/loops)
    );
end entity decoder;


architecture arch_decoder of decoder is
    signal fct7 : unsigned(6 downto 0) := (others => '0');
    signal rs2 : unsigned(4 downto 0) := (others => '0');
    signal rs1 : unsigned(4 downto 0) := (others => '0');
    signal fct3 : unsigned(2 downto 0) := (others => '0');
    signal rd : unsigned(4 downto 0) := (others => '0');
    signal opcode : unsigned(6 downto 0) := (others => '0');

begin
    --!                             31        25        20         15           12      7         0  
    --! Decode d'une structure en R [   fct7   |  rs2   |   rs1     |   fct3    |   rd  |   opcode]
    opcode <= unsigned(i_pc(6 downto 0));
    rd     <= unsigned(i_pc(11 downto 7));
    fct3   <= unsigned(i_pc(14 downto 12));
    rs1    <= unsigned(i_pc(19 downto 15));
    rs2    <= unsigned(i_pc(24 downto 20));
    fct7   <= unsigned(i_pc(31 downto 25));

    P_Decoder : process(i_clk)
    begin
        if rising_edge(i_clk) then

            if (i_rst= '1') then
                o_reg_rs1_addr <= (others => '0');
                o_reg_rs2_addr <= (others => '0');
                o_reg_rd_addr <= (others => '0');
                o_alu_cmd <= (others => '0');
                o_immediat <= '0';
                o_reg_write_en <= '0';
                o_mem_read <= '0';
                o_mem_write <= '0';
                o_branch <= '0';
                o_imm_extended <= (others => '0');
            else
                
                case opcode is
                    when "0110011" => --! Registre to Registre R (ADD, SUB, OR, ET)
                            o_reg_rs1_addr <= std_logic_vector(rs1);
                            o_reg_rs2_addr <= std_logic_vector(rs2);
                            o_reg_rd_addr  <= std_logic_vector(rd);
                            o_reg_write_en <= '1';
                            o_immediat     <= '0';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '0';

                            if fct3 = "000" and fct7 = "0000000" then
                                o_alu_cmd <= "000010"; -- Add
                            elsif fct3 = "000" and fct7 = "0100000" then
                                o_alu_cmd <= "000011"; -- Sub
                            elsif fct3 = "110" and fct7 = "0000000" then
                                o_alu_cmd <= "000001"; -- OR
                            elsif fct3 = "111" and fct7 = "0000000" then
                                o_alu_cmd <= "000000"; -- ET
                            end if;
                        
                    when "0010011" => --! Registre Immediat I (ADDI, LI, MV)
                            o_reg_rs1_addr <= std_logic_vector(rs1);
                            o_reg_rd_addr  <= std_logic_vector(rd);
                            o_reg_write_en <= '1';
                            o_immediat     <= '1';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '0';
                            o_alu_cmd      <= "000010"; -- Par défaut ADD pour ADDI
                            
                            -- Extension de signe propre sur 12 bits (Type I)
                            o_imm_extended(11 downto 0)  <= i_pc(31 downto 20);
                            o_imm_extended(31 downto 12) <= (others => i_pc(31));

                    when "0000011" => --! Chargement mémoire (LW)
                            o_reg_rs1_addr <= std_logic_vector(rs1);
                            o_reg_rd_addr  <= std_logic_vector(rd);
                            o_reg_write_en <= '1';
                            o_immediat     <= '1';
                            o_mem_read     <= '1';
                            o_mem_write    <= '0';
                            o_branch       <= '0';
                            o_alu_cmd      <= "000010"; -- Base + Offset via l'ALU
                            
                            o_imm_extended(11 downto 0)  <= i_pc(31 downto 20);
                            o_imm_extended(31 downto 12) <= (others => i_pc(31));

                    when "0100011" => --! Sauvegarde mémoire (SW)
                            o_reg_rs1_addr <= std_logic_vector(rs1);
                            o_reg_rs2_addr <= std_logic_vector(rs2);
                            o_reg_write_en <= '0';
                            o_immediat     <= '1';
                            o_mem_read     <= '0';
                            o_mem_write    <= '1';
                            o_branch       <= '0';
                            o_alu_cmd      <= "000010";
                            
                            -- Reconstruction propre de l'immédiat Type S
                            o_imm_extended(4 downto 0)   <= i_pc(11 downto 7);
                            o_imm_extended(11 downto 5)  <= i_pc(31 downto 25);
                            o_imm_extended(31 downto 12) <= (others => i_pc(31));

                    when "1100011" => --! Branchements (BEQ/BNE)
                            o_reg_rs1_addr <= std_logic_vector(rs1);
                            o_reg_rs2_addr <= std_logic_vector(rs2);
                            o_reg_write_en <= '0';
                            o_immediat     <= '1';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '1'; -- Active le calcul de saut dans l'unité PC
                            o_alu_cmd      <= "000011"; -- Soustraction pour comparer rs1 et rs2
                            
                            -- Reconstruction de l'immédiat Type B (signé et multiple de 2)
                            o_imm_extended(0)            <= '0';
                            o_imm_extended(4 downto 1)   <= i_pc(11 downto 8);
                            o_imm_extended(10 downto 5)  <= i_pc(30 downto 25);
                            o_imm_extended(11)           <= i_pc(7);
                            o_imm_extended(31 downto 12) <= (others => i_pc(31));

                    when "1101111" => --! AJOUT : Saut inconditionnel JAL (utilisé par 'j')
                            o_reg_rd_addr  <= std_logic_vector(rd); -- Souvent x0 dans ton cas
                            o_reg_write_en <= '1'; -- Écrit l'adresse de retour PC+4 (si rd /= x0)
                            o_immediat     <= '1';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '1'; -- On force le saut
                            o_alu_cmd      <= "000010"; 
                            
                            -- Reconstruction de l'immédiat Type J
                            o_imm_extended(0)            <= '0';
                            o_imm_extended(10 downto 1)  <= i_pc(30 downto 21);
                            o_imm_extended(11)           <= i_pc(20);
                            o_imm_extended(19 downto 12) <= i_pc(19 downto 12);
                            o_imm_extended(31 downto 20) <= (others => i_pc(31));

                    when "1100111" => --! AJOUT : Retour de fonction JALR (utilisé par 'ret')
                            o_reg_rs1_addr <= std_logic_vector(rs1); -- Contient l'adresse de retour (ra)
                            o_reg_rd_addr  <= std_logic_vector(rd);
                            o_reg_write_en <= '1';
                            o_immediat     <= '1';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '1'; -- C'est un saut
                            o_alu_cmd      <= "000010"; -- L'ALU calcule rs1 + imm
                            
                            o_imm_extended(11 downto 0)  <= i_pc(31 downto 20);
                            o_imm_extended(31 downto 12) <= (others => i_pc(31));
                    
                        when "0010111" => -- AUIPC
                            o_reg_rd_addr  <= std_logic_vector(rd);
                            o_reg_write_en <= '1';
                            o_immediat     <= '1';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '0';
                            o_alu_cmd      <= "000010"; -- Base + Offset via l'ALU
                            
                            -- Extension de signe propre sur 20 bits (Type U)
                            o_imm_extended(19 downto 0)  <= i_pc(31 downto 12); -- Récupèretation de l'immidiate
                            o_imm_extended(31 downto 20) <= (others => i_pc(31));

                    when others =>
                            o_reg_write_en <= '0';
                            o_mem_read     <= '0';
                            o_mem_write    <= '0';
                            o_branch       <= '0';
                            o_imm_extended <= (others => '0');
                end case;
                
            end if;
        end if;
    end process;
end architecture arch_decoder;