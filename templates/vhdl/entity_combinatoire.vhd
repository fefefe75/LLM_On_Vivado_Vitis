library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Squelette d'un module COMBINATOIRE (sans horloge).
--! @details A copier tel quel : renommer l'entite 'mon_module', adapter les ports.
--!          Regle : aucune horloge ici. Si ce module doit memoriser quelque
--!          chose, c'est un module sequentiel (voir registre_synchrone.vhd).
--!          Verifie : ghdl -a --std=08 entity_combinatoire.vhd
entity mon_module is
    generic (
        C_WIDTH : positive := 8                 --! largeur des donnees
    );
    port (
        i_a    : in  std_logic_vector(C_WIDTH - 1 downto 0);
        i_b    : in  std_logic_vector(C_WIDTH - 1 downto 0);
        i_sel  : in  std_logic;                                  --! 0 = a, 1 = a+b
        o_y    : out std_logic_vector(C_WIDTH - 1 downto 0);
        o_egal : out std_logic                                   --! '1' si a = b
    );
end entity mon_module;

architecture rtl of mon_module is
    -- signaux internes : prefixe s_
    signal s_somme : unsigned(C_WIDTH - 1 downto 0);
begin

    -- logique combinatoire : un seul process(..) avec toutes les entrees lues.
    -- IMPORTANT : on affecte une valeur par DEFAUT a chaque sortie en tete de
    -- process, sinon Vivado infere un latch (WARNING: [Synth 8-327]).
    p_comb : process (i_a, i_b, i_sel)
    begin
        s_somme <= unsigned(i_a) + unsigned(i_b);   -- defaut
        o_y     <= i_a;
        o_egal  <= '0';

        if i_sel = '1' then
            o_y <= std_logic_vector(s_somme);
        end if;

        if i_a = i_b then
            o_egal <= '1';
        end if;
    end process p_comb;

end architecture rtl;
