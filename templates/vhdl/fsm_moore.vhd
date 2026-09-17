library ieee;
use ieee.std_logic_1164.all;

--! @brief Machine d'etats de Moore : 1 process sequentiel (etat) + 1 process combinatoire
--!        (prochain etat ET sorties). Ce decoupage evite les sorties qui glissent
--!        d'un cycle et les avertissements de latch.
--! @details Verifie : ghdl -a --std=08 fsm_moore.vhd
--!          Regle : une FSM = un fichier. Si elle pilote plus de 6 sorties,
--!          envisager un etat de plus plutot que plus de logique combinatoire.
entity fsm_moore is
    port (
        i_clk    : in  std_logic;
        i_rst    : in  std_logic;                 --! reset synchrone actif haut
        i_start  : in  std_logic;
        i_done   : in  std_logic;                 --! acquittement venant du chemin de donnees
        o_busy   : out std_logic;                 --! sorties (Moore : fonction de l'etat seul)
        o_finish : out std_logic
    );
end entity fsm_moore;

architecture rtl of fsm_moore is
    type t_etat is (IDLE, RUN, DONE);
    signal s_etat  : t_etat := IDLE;
    signal s_next  : t_etat := IDLE;
begin

    -- 1) etat : le seul process qui touche l'horloge
    p_etat : process (i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_etat <= IDLE;
            else
                s_etat <= s_next;
            end if;
        end if;
    end process p_etat;

    -- 2) prochain etat ET sorties : combinatoire, valeurs par defaut en tete
    p_comb : process (s_etat, i_start, i_done)
    begin
        s_next   <= s_etat;                       -- defaut : on reste
        o_busy   <= '0';
        o_finish <= '0';

        case s_etat is
            when IDLE =>
                if i_start = '1' then
                    s_next <= RUN;
                end if;

            when RUN =>
                o_busy <= '1';
                if i_done = '1' then
                    s_next <= DONE;
                end if;

            when DONE =>
                o_finish <= '1';
                s_next   <= IDLE;

            when others =>                        -- obligatoire en VHDL : jamais atteint
                s_next <= IDLE;
        end case;
    end process p_comb;

end architecture rtl;
