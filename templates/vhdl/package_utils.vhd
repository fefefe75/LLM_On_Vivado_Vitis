library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Package de types/fonctions partages entre plusieurs modules.
--! @details A utiliser quand deux modules doivent parler la meme langue (largeur,
--!          encodage, conversion). Verifie : ghdl -a --std=08 package_utils.vhd
package utils_pkg is

    constant C_WIDTH : positive := 8;

    --! Codes d'operation : un type enumerE evite les '0'/'1' magiques.
    type t_op is (OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR);

    --! Etats d'une FSM partagee (si plusieurs modules suivent la meme machine).
    type t_etat is (IDLE, RUN, DONE);

    --! Conversion d'un code d'operation vers une chaine (utile pour les rapports de test).
    function op_to_string(op : t_op) return string;

    --! Saturation : borne une valeur entiere sur C_WIDTH bits.
    function saturer(valeur : integer) return std_logic_vector;

end package utils_pkg;


package body utils_pkg is

    function op_to_string(op : t_op) return string is
    begin
        case op is
            when OP_ADD => return "ADD";
            when OP_SUB => return "SUB";
            when OP_AND => return "AND";
            when OP_OR  => return "OR";
            when OP_XOR => return "XOR";
        end case;
    end function op_to_string;

    function saturer(valeur : integer) return std_logic_vector is
        constant C_MAXI : integer := (2 ** C_WIDTH) - 1;
        variable v_res : std_logic_vector(C_WIDTH - 1 downto 0);
    begin
        if valeur > C_MAXI then
            v_res := std_logic_vector(to_unsigned(C_MAXI, C_WIDTH));
        elsif valeur < 0 then
            v_res := (others => '0');
        else
            v_res := std_logic_vector(to_unsigned(valeur, C_WIDTH));
        end if;
        return v_res;
    end function saturer;

end package body utils_pkg;
