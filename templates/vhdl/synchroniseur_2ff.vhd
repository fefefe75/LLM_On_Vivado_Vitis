library ieee;
use ieee.std_logic_1164.all;

--! @brief Synchroniseur 2 bascules pour un signal asynchrone (bouton, entree externe).
--! @details A placer AVANT toute logique qui utilise un signal venant d'un autre
--!          domaine d'horloge. Ne transmet pas de bus (un bit seulement) : pour un bus,
--!          utiliser un handshake ou une FIFO asynchrone.
--!          Verifie : ghdl -a --std=08 synchroniseur_2ff.vhd
entity synchroniseur_2ff is
    port (
        i_clk     : in  std_logic;                --! horloge du domaine de destination
        i_rst     : in  std_logic;                --! reset synchrone actif haut
        i_async   : in  std_logic;                --! signal asynchrone (jamais lu ailleurs)
        o_sync    : out std_logic                 --! version synchronisee (2 cycles de latence)
    );
end entity synchroniseur_2ff;

architecture rtl of synchroniseur_2ff is
    -- Attribut utile pour la synthese : empeche Vivado d'optimiser le premier etage.
    signal s_meta  : std_logic := '0';
    signal s_sync  : std_logic := '0';

    attribute ASYNC_REG : string;
    attribute ASYNC_REG of s_meta : signal is "TRUE";
    attribute ASYNC_REG of s_sync : signal is "TRUE";
begin

    o_sync <= s_sync;

    p_sync : process (i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_meta <= '0';
                s_sync <= '0';
            else
                s_meta <= i_async;
                s_sync <= s_meta;
            end if;
        end if;
    end process p_sync;

end architecture rtl;
