--------------------------------------------------------------------------------
--! @file alu_pkg.vhd
--! @brief Codes d'operation de l'ALU generique de l'exemple examples/02-alu.
--!
--! Les opcodes sont definis ici, et nulle part ailleurs dans le RTL. Le
--! testbench Python les recopie explicitement (tb/test_alu.py) : si les deux
--! listes divergent, l'interface a change et le test echoue, ce qui est le
--! comportement attendu d'un contrat d'interface.
--!
--! Regle de conception : tout code non defini est un code reserve, et l'ALU
--! renvoie zero. Une operation inconnue ne produit donc jamais un resultat
--! fantaisiste ; o_zero vaut alors '1'.
--------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;

package alu_pkg is

  --! Largeur du champ d'opcode. 4 bits donnent 16 codes, dont 12 definis et
  --! 4 reserves.
  constant C_OP_WIDTH : positive := 4;

  --! Type du port i_op.
  subtype t_op is std_logic_vector(C_OP_WIDTH - 1 downto 0);

  -- --- Arithmetique ----------------------------------------------------------
  --! Somme : o_y = (i_a + i_b) modulo 2**C_WIDTH, o_carry = retenue sortante.
  constant C_OP_ADD : t_op := "0000";
  --! Difference : o_y = (i_a - i_b) modulo 2**C_WIDTH, o_carry = '1' quand
  --! i_a >= i_b, soit l'absence d'emprunt (convention ARM et MIPS).
  constant C_OP_SUB : t_op := "0001";

  -- --- Logique bit a bit -----------------------------------------------------
  --! ET bit a bit.
  constant C_OP_AND : t_op := "0010";
  --! OU bit a bit.
  constant C_OP_OR : t_op := "0011";
  --! OU exclusif bit a bit.
  constant C_OP_XOR : t_op := "0100";
  --! Complement de i_a. i_b est ignore.
  constant C_OP_NOT : t_op := "0101";

  -- --- Comparaisons ----------------------------------------------------------
  --! o_y = 1 si i_a = i_b, 0 sinon.
  constant C_OP_EQ : t_op := "0110";
  --! o_y = 1 si i_a < i_b en non signe.
  constant C_OP_LT_U : t_op := "0111";
  --! o_y = 1 si i_a < i_b en signe (complement a deux).
  constant C_OP_LT_S : t_op := "1000";

  -- --- Decalages logiques ----------------------------------------------------
  --! i_a decale a gauche de i_b bits, zeros injectes a droite.
  constant C_OP_SLL : t_op := "1001";
  --! i_a decale a droite de i_b bits, zeros injectes a gauche.
  constant C_OP_SRL : t_op := "1010";

  -- --- Divers ----------------------------------------------------------------
  --! Recopie de i_b, derniere entree du multiplexeur d'operation.
  constant C_OP_PASS_B : t_op := "1011";

  --! Codes non definis, de "1100" a "1111". Voir la regle en tete de fichier.
  constant C_OP_RESERVED_FIRST : t_op := "1100";

end package alu_pkg;
