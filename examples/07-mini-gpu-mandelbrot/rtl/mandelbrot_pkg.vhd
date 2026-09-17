library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Fonctions utilitaires du mini-GPU (aucune dependance, purs calculs).
--! @details Separees dans un package pour etre reutilisees par le banc de test VHDL
--!          et par le top. Verifie par analyse GHDL --std=08.

package mandelbrot_pkg is

    -- Nombre de bits necessaires pour representer `valeur` (>= 1).
    function f_bits(valeur : natural) return natural;

    -- Nombre de cycles d'horloge qu'un lane met pour UN point, au pire cas
    -- (3 cycles par iteration + 1 cycle d'emission). Utile pour verifier les mesures.
    function f_cycles_pire_cas(max_iter : natural) return natural;

end package mandelbrot_pkg;

package body mandelbrot_pkg is

    function f_bits(valeur : natural) return natural is
        variable v_reste : natural := valeur;
        variable v_bits  : natural := 1;
    begin
        while v_reste > 1 loop
            v_reste := v_reste / 2;
            v_bits  := v_bits + 1;
        end loop;
        return v_bits;
    end function f_bits;

    function f_cycles_pire_cas(max_iter : natural) return natural is
    begin
        return 3 * max_iter + 2;
    end function f_cycles_pire_cas;

end package body mandelbrot_pkg;
