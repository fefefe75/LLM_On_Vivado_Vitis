library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Un "lane" SIMT : calcule le nombre d'iterations d'echappement d'UN point
--!        du plan complexe (z <- z^2 + c) en virgule fixe Q(C_FRAC).
--!
--! Modele SIMT : chaque lane est un fil d'execution independant. Ils executent tous
--! le meme code (le meme automate), mais divergent naturellement : un point qui fuit
--! vite libere son lane pendant qu'un point de l'ensemble tourne jusqu'a C_MAX_ITER.
--! C'est exactement la "warp divergence" d'un GPU, avec les memes consequences : de
--! la puissance de calcul perdue si les points d'un lot n'ont pas la meme duree.
--!
--! Cout : 3 multiplications par lane (zr*zr, zi*zi, zr*zi, le facteur 2 est un
--! decalage), 3 cycles d'horloge par iteration (PROD -> DECIDE -> UPDATE).
--! Verifie : analyse GHDL --std=08 et synthese Vivado 2025.2 (voir README).

entity mandelbrot_lane is
    generic (
        C_WIDTH    : positive := 32;   -- largeur totale, format Q(C_FRAC)
        C_FRAC     : positive := 26;   -- bits fractionnaires : 1.0 = 2**C_FRAC
                                       -- 26 et non 28 : avec 32 bits, 28 bits fractionnaires
                                       -- donnent une plage de +/-8.0, or l'intermediaire
                                       -- 2*zr*zi atteint 8.0 pile au bord de la fuite ->
                                       -- 'bound check failure' (mesure sur GHDL).
        C_MAX_ITER : positive := 64;   -- iterations avant de conclure "dans l'ensemble"
        C_ITER_W   : positive := 8     -- largeur du compteur d'iterations
    );
    port (
        i_clk     : in  std_logic;
        i_rst     : in  std_logic;                            -- reset synchrone actif haut
        i_start   : in  std_logic;                            -- 1 cycle : un point a calculer
        i_cr      : in  signed(C_WIDTH - 1 downto 0);         -- partie reelle de c
        i_ci      : in  signed(C_WIDTH - 1 downto 0);         -- partie imaginaire de c
        o_free    : out std_logic;                            -- 1 = pret a recevoir un point
        o_done    : out std_logic;                            -- pulse 1 cycle : resultat valide
        o_iter    : out unsigned(C_ITER_W - 1 downto 0);      -- iterations avant fuite
        o_escaped : out std_logic                             -- 1 = point hors de l'ensemble
    );
end entity mandelbrot_lane;

architecture rtl of mandelbrot_lane is

    -- 1.0 et le seuil de fuite |z|^2 > 4, tous deux en Q(C_FRAC).
    constant C_ONE    : signed(C_WIDTH - 1 downto 0) := to_signed(2 ** C_FRAC, C_WIDTH);
    -- ATTENTION : ne PAS ecrire `to_signed(4 * 2**(2*C_FRAC), 2*C_WIDTH)`. GHDL evalue
    -- `2 ** 56` dans un entier 32 bits AVANT la conversion et echoue en "integer
    -- overflow" (erreur constatee). On construit donc la valeur en deux temps, dans le
    -- domaine large : 4.0 (Q_C_FRAC) puis decalage a gauche de C_FRAC bits.
    constant C_FUITE2 : signed(2 * C_WIDTH - 1 downto 0) :=
        shift_left(resize(to_signed(4 * (2 ** C_FRAC), C_WIDTH), 2 * C_WIDTH), C_FRAC);

    -- Domaines internes : les produits sont en Q(2*C_FRAC), on redescend en Q(C_FRAC)
    -- par un decalage a droite (division par 2**C_FRAC, arrondi vers -infini, ce que
    -- fait aussi >> en Python : le modele de reference reproduit exactement ceci).
    subtype t_wide is signed(2 * C_WIDTH - 1 downto 0);

    type t_etat is (S_IDLE, S_PROD, S_DECIDE, S_UPDATE, S_EMIT);

    signal etat    : t_etat := S_IDLE;
    signal zr, zi  : signed(C_WIDTH - 1 downto 0) := (others => '0');
    signal cr, ci  : signed(C_WIDTH - 1 downto 0) := (others => '0');
    signal iter    : unsigned(C_ITER_W - 1 downto 0) := (others => '0');
    signal escaped : std_logic := '0';

    signal p_rr, p_ii, p_ri : t_wide := (others => '0');   -- zr^2, zi^2, 2*zr*zi

begin

    -- Garde-fous d'elaboration : un format mal dimensionne doit echouer tout de suite,
    -- pas produire un resultat faux.
    assert C_WIDTH > C_FRAC + 3
        report "C_WIDTH doit laisser au moins 3 bits a la partie entiere (|z| monte a 2)."
        severity failure;
    assert C_MAX_ITER < (2 ** C_ITER_W)
        report "C_ITER_W est trop petit pour C_MAX_ITER."
        severity failure;

    o_free    <= '1' when etat = S_IDLE else '0';
    o_done    <= '1' when etat = S_EMIT else '0';
    o_iter    <= iter;
    o_escaped <= escaped;

    p_process : process (i_clk)
        variable v_m2 : t_wide;
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                etat    <= S_IDLE;
                zr      <= (others => '0');
                zi      <= (others => '0');
                cr      <= (others => '0');
                ci      <= (others => '0');
                iter    <= (others => '0');
                escaped <= '0';
                p_rr    <= (others => '0');
                p_ii    <= (others => '0');
                p_ri    <= (others => '0');
            else
                case etat is

                    -- Attente d'un point. z = 0, n = 0 (boucle du manuel).
                    when S_IDLE =>
                        escaped <= '0';
                        if i_start = '1' then
                            cr   <= i_cr;
                            ci   <= i_ci;
                            zr   <= (others => '0');
                            zi   <= (others => '0');
                            iter <= (others => '0');
                            etat <= S_PROD;
                        end if;

                    -- Trois multiplications, independantes des donnees suivantes.
                    -- PIEGE MESURE : ne PAS ecrire `resize(zr * zi, 2*C_WIDTH) * 2`.
                    -- GHDL leve "bound check failure" des que le 2e operande est un
                    -- litteral entier multiplie a un vecteur large (repro minimale dans
                    -- l'historique de ce projet). `shift_left` est l'idiome correct :
                    -- pas de controle de debordement, et le MSB est simplement perdu.
                    when S_PROD =>
                        p_rr <= zr * zr;
                        p_ii <= zi * zi;
                        p_ri <= shift_left(zr * zi, 1);   -- 2*zr*zi
                        etat <= S_DECIDE;

                    -- Test de fuite : |z|^2 > 4 ?  et fin de boucle si n = C_MAX_ITER.
                    when S_DECIDE =>
                        v_m2 := p_rr + p_ii;
                        if (v_m2 > C_FUITE2) then
                            escaped <= '1';
                            etat    <= S_EMIT;
                        elsif (iter >= to_unsigned(C_MAX_ITER, C_ITER_W)) then
                            escaped <= '0';                             -- dans l'ensemble
                            etat    <= S_EMIT;
                        else
                            etat <= S_UPDATE;
                        end if;

                    -- z <- z^2 + c, n <- n + 1
                    when S_UPDATE =>
                        zr   <= resize(shift_right(p_rr - p_ii, C_FRAC), C_WIDTH) + cr;
                        zi   <= resize(shift_right(p_ri, C_FRAC), C_WIDTH) + ci;
                        iter <= iter + 1;
                        etat <= S_PROD;

                    -- Resultat tenu 1 cycle sur les sorties.
                    when S_EMIT =>
                        etat <= S_IDLE;
                end case;
            end if;
        end if;
    end process p_process;

end architecture rtl;
