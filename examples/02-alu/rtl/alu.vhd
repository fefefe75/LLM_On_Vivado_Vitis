--------------------------------------------------------------------------------
--! @file alu.vhd
--! @brief ALU combinatoire generique : arithmetique, logique, comparaisons et
--!        decalages logiques, avec multiplexeur d'operation.
--!
--! @param C_WIDTH largeur des operandes et du resultat, en bits (defaut 8).
--! @param i_op    code d'operation, voir work.alu_pkg.
--! @param i_a     operande A.
--! @param i_b     operande B, aussi utilise comme nombre de bits de decalage.
--! @param o_y     resultat, largeur C_WIDTH.
--! @param o_zero  '1' quand o_y vaut 0, quelle que soit l'operation.
--! @param o_carry retenue ou emprunt, voir les conventions ci-dessous.
--!
--! Le module est volontairement combinatoire : ni horloge, ni reset. Le
--! multiplexeur d'operation appartient au chemin de donnees, et le sequentiel
--! reste dans le registre d'instruction du design appelant. Pour inserer l'ALU
--! dans un chemin cadence, enregistrer o_y, o_zero et o_carry en sortie.
--!
--! Conventions de drapeaux :
--!   ADD : o_carry = retenue sortante de la somme, '1' si le resultat depasse
--!         C_WIDTH bits ;
--!   SUB : o_carry = '1' quand i_a >= i_b. La soustraction est calculee comme
--!         i_a + (not i_b) + 1, donc la retenue sortante est l'inverse de
--!         l'emprunt, comme sur ARM et MIPS ;
--!   toutes les autres operations : o_carry = '0' ;
--!   o_zero ne depend que de o_y.
--------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.alu_pkg.all;

entity alu is
  generic (
    C_WIDTH : positive := 8   --! largeur des operandes et du resultat
  );
  port (
    i_op    : in  t_op;                                    --! code d'operation
    i_a     : in  std_logic_vector(C_WIDTH - 1 downto 0);  --! operande A
    i_b     : in  std_logic_vector(C_WIDTH - 1 downto 0);  --! operande B
    o_y     : out std_logic_vector(C_WIDTH - 1 downto 0);  --! resultat
    o_zero  : out std_logic;                               --! '1' si o_y = 0
    o_carry : out std_logic                                --! retenue ou emprunt
  );
end entity alu;

architecture rtl of alu is

  --! Largeur du resultat etendu : C_WIDTH bits plus le bit de retenue.
  constant C_EXT_WIDTH : positive := C_WIDTH + 1;

  --! Convertit i_b en nombre de bits de decalage, sature a C_WIDTH.
  --! La saturation rend la conversion sure pour toute largeur de donnees : un
  --! decalage d'au moins C_WIDTH bits vide le resultat, on n'a donc jamais
  --! besoin de la valeur exacte au dela de C_WIDTH. La boucle part du bit de
  --! poids fort et sort des que la saturation est atteinte.
  function f_shift_amount (b : std_logic_vector) return natural is
    variable v_amount : natural := 0;
  begin
    for i in b'range loop
      v_amount := v_amount * 2;
      if b(i) = '1' then
        v_amount := v_amount + 1;
      end if;
      if v_amount >= C_WIDTH then
        return C_WIDTH;
      end if;
    end loop;
    return v_amount;
  end function f_shift_amount;

begin

  ------------------------------------------------------------------------------
  --! @brief Multiplexeur d'operation : chemin combinatoire pur.
  --! Chaque branche affecte le resultat local v_y, puis o_y et o_zero en
  --! sortent en fin de processus. Aucun verrou n'est infere. Le cas others
  --! couvre les codes reserves.
  --!
  --! o_zero est calcule a partir de la variable v_y et non du signal o_y :
  --! cela evite de comparer a zero un signal encore non initialise en debut de
  --! simulation, ce qui declencherait un avertissement "metavalue detected"
  --! dans ieee.numeric_std.
  ------------------------------------------------------------------------------
  p_mux : process (i_op, i_a, i_b) is
    variable v_a_ext  : unsigned(C_EXT_WIDTH - 1 downto 0);
    variable v_res    : unsigned(C_EXT_WIDTH - 1 downto 0);
    variable v_y      : std_logic_vector(C_WIDTH - 1 downto 0);
    variable v_amount : natural;
  begin
    v_a_ext := resize(unsigned(i_a), C_EXT_WIDTH);
    v_res   := (others => '0');
    v_y     := (others => '0');

    case i_op is

      when C_OP_ADD =>
        v_res   := v_a_ext + resize(unsigned(i_b), C_EXT_WIDTH);
        v_y     := std_logic_vector(v_res(C_WIDTH - 1 downto 0));
        o_carry <= v_res(C_WIDTH);

      when C_OP_SUB =>
        -- i_a - i_b = i_a + (not i_b) + 1, en complement a deux.
        -- La retenue sortante vaut donc l'inverse de l'emprunt.
        v_res   := v_a_ext + resize(not unsigned(i_b), C_EXT_WIDTH) + 1;
        v_y     := std_logic_vector(v_res(C_WIDTH - 1 downto 0));
        o_carry <= v_res(C_WIDTH);

      when C_OP_AND =>
        v_y     := i_a and i_b;
        o_carry <= '0';

      when C_OP_OR =>
        v_y     := i_a or i_b;
        o_carry <= '0';

      when C_OP_XOR =>
        v_y     := i_a xor i_b;
        o_carry <= '0';

      when C_OP_NOT =>
        v_y     := not i_a;
        o_carry <= '0';

      when C_OP_EQ =>
        if unsigned(i_a) = unsigned(i_b) then
          v_y(0) := '1';
        end if;
        o_carry <= '0';

      when C_OP_LT_U =>
        if unsigned(i_a) < unsigned(i_b) then
          v_y(0) := '1';
        end if;
        o_carry <= '0';

      when C_OP_LT_S =>
        if signed(i_a) < signed(i_b) then
          v_y(0) := '1';
        end if;
        o_carry <= '0';

      when C_OP_SLL =>
        v_amount := f_shift_amount(i_b);
        if v_amount < C_WIDTH then
          v_y := std_logic_vector(shift_left(unsigned(i_a), v_amount));
        end if;
        o_carry <= '0';

      when C_OP_SRL =>
        v_amount := f_shift_amount(i_b);
        if v_amount < C_WIDTH then
          v_y := std_logic_vector(shift_right(unsigned(i_a), v_amount));
        end if;
        o_carry <= '0';

      when C_OP_PASS_B =>
        v_y     := i_b;
        o_carry <= '0';

      when others =>
        -- Codes reserves : resultat nul, drapeau de retenue au repos.
        o_carry <= '0';

    end case;

    --! Resultat et drapeau de zero, tous deux derives de v_y.
    --! La comparaison porte sur la variable et non sur le signal o_y, pour ne
    --! pas comparer a zero une valeur encore non initialisee en debut de
    --! simulation. Le if explicite evite l'affectation conditionnelle de
    --! signal, que GHDL accepte mais que d'autres analyseurs refusent.
    o_y <= v_y;
    if unsigned(v_y) = 0 then
      o_zero <= '1';
    else
      o_zero <= '0';
    end if;
  end process p_mux;

end architecture rtl;
