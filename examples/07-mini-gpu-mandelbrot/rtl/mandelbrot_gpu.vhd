library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.mandelbrot_pkg.all;

--! @brief Mini-GPU SIMT : C_LANES lanes en parallele + un repartiteur de pixels.
--!
--! Analogie GPU, terme par terme :
--!   * lane                <-> thread / CUDA core           (execute z <- z^2 + c)
--!   * repartiteur         <-> distributeur de blocs        (un point libre -> un lane libre)
--!   * divergence          <-> un point qui fuit vite libere son lane ; s'il tourne
--!                              jusqu'a C_MAX_ITER il bloque ce lane (warp divergence)
--!   * generation de c     <-> unites partagees du SM       (2 multiplications pour TOUS
--!                              les lanes : elles ne sont pas dans le lane)
--!   * tampon de resultats <-> file de sortie du SM         (2 creneaux par lane, avec
--!                              contre-pression : un resultat ne peut pas etre ecrase)
--!
--! POURQUOI DEUX CRENEAUX PAR LANE (bug reel corrige ici, mesure avant/apres) : un lane
--! peut terminer son point et en recevoir un AUTRE avant que le collecteur ait pris le
--! resultat. Avec un seul creneau, le second resultat ecrasait le premier : sur une image
--! 96x64, 351 pixels sur 6144 n'etaient jamais emis (simulation bloquee, o_done jamais
--! arme). Le nombre de creneaux occupes par un lane conditionne desormais l'emission d'un
--! nouveau point : c'est de la contre-pression, et la perte devient impossible.
--!
--! Verifie a l'execution : GHDL + cocotb, comparaison exacte de 6144 puis 76800 pixels
--! contre un modele Python, et mesures de debit par nombre de lanes (voir README).

entity mandelbrot_gpu is
    generic (
        C_IMG_W    : positive := 640;         -- largeur de l'image, en pixels
        C_IMG_H    : positive := 480;         -- hauteur de l'image, en pixels
        C_LANES    : positive := 16;          -- nombre de lanes SIMT en parallele
        C_WIDTH    : positive := 32;          -- format Q(C_FRAC) : 32 bits dont 26 fractionnaires
        C_FRAC     : positive := 26;          -- 26 et non 28 : voir la note dans mandelbrot_lane.vhd
        C_MAX_ITER : positive := 128;         -- iterations max avant "dans l'ensemble"
        C_ITER_W   : positive := 8;
        -- Largeur des coordonnees de pixel. Ce sont des generiques et non des constantes
        -- calculees : une plage de port doit etre localement statique, donc
        -- `unsigned(f_bits(C_IMG_W-1)-1 downto 0)` serait refuse par GHDL et par Vivado.
        C_XW       : positive := 10;          -- 640  pixels < 2**10
        C_YW       : positive := 9;           -- 480  pixels < 2**9
        -- Fenetre du plan complexe, en Q(C_FRAC) : c = (C_X0 + x*C_DX) + i*(C_Y0 + y*C_DY)
        C_X0       : integer  := -140928614;  -- -2.1  en Q26
        C_Y0       : integer  := -80530637;   -- -1.2  en Q26
        C_DX       : integer  := 293601;      --  2.8 / 640  en Q26
        C_DY       : integer  := 335544       --  2.4 / 480  en Q26
    );
    port (
        i_clk        : in  std_logic;
        i_rst        : in  std_logic;                          -- reset synchrone actif haut
        i_start      : in  std_logic;                          -- 1 cycle : lance une image
        o_px_valid   : out std_logic;                          -- flot de pixels de sortie
        i_px_ready   : in  std_logic;                          -- 0 = consommateur occupe
        o_px_x       : out unsigned(C_XW - 1 downto 0);
        o_px_y       : out unsigned(C_YW - 1 downto 0);
        o_px_iter    : out unsigned(C_ITER_W - 1 downto 0);
        o_px_escaped : out std_logic;                          -- 1 = point hors de l'ensemble
        o_busy       : out std_logic;                          -- image en cours
        o_done       : out std_logic;                          -- pulse : image terminee
        o_cycles     : out unsigned(31 downto 0);              -- duree mesuree, en cycles
        -- "device properties" : la configuration reelle du moteur, lisible par le logiciel.
        -- Le banc de test s'en sert au lieu de supposer les parametres.
        o_cfg_lanes  : out unsigned(15 downto 0);
        o_cfg_w      : out unsigned(15 downto 0);
        o_cfg_h      : out unsigned(15 downto 0);
        o_cfg_iter   : out unsigned(15 downto 0);
        o_cfg_frac   : out unsigned(7 downto 0);               -- format Q utilise
        -- Fenetre du plan complexe REELLEMENT utilisee, en Q(C_FRAC). Le banc de test
        -- reconstruit son modele de reference a partir de CES valeurs : il verifie donc
        -- l'arithmetique du design, et non une constante recopiee a la main.
        o_cfg_x0     : out signed(C_WIDTH - 1 downto 0);
        o_cfg_dx     : out signed(C_WIDTH - 1 downto 0);
        o_cfg_y0     : out signed(C_WIDTH - 1 downto 0);
        o_cfg_dy     : out signed(C_WIDTH - 1 downto 0)
    );
end entity mandelbrot_gpu;

architecture rtl of mandelbrot_gpu is

    constant C_TOTAL : positive := C_IMG_W * C_IMG_H;
    constant C_PXW   : positive := f_bits(C_TOTAL);
    constant C_SLOTS : positive := 2;          -- creneaux de resultat par lane

    subtype t_px_x is unsigned(C_XW - 1 downto 0);
    subtype t_px_y is unsigned(C_YW - 1 downto 0);
    subtype t_val  is signed(C_WIDTH - 1 downto 0);

    type t_val_tab  is array (0 to C_LANES - 1) of t_val;
    type t_x_tab    is array (0 to C_LANES - 1) of t_px_x;
    type t_y_tab    is array (0 to C_LANES - 1) of t_px_y;
    type t_iter_tab is array (0 to C_LANES - 1) of unsigned(C_ITER_W - 1 downto 0);
    type t_occ_tab  is array (0 to C_LANES - 1) of unsigned(f_bits(C_SLOTS) - 1 downto 0);

    -- un resultat complet, pret a etre emis
    type t_resultat is record
        x    : t_px_x;
        y    : t_px_y;
        iter : unsigned(C_ITER_W - 1 downto 0);
        esc  : std_logic;
    end record t_resultat;
    type t_slots_tab is array (natural range <>) of t_resultat;

    -- vers les lanes
    signal lane_start : std_logic_vector(C_LANES - 1 downto 0) := (others => '0');
    signal lane_cr    : t_val_tab;
    signal lane_ci    : t_val_tab;
    -- depuis les lanes
    signal lane_free    : std_logic_vector(C_LANES - 1 downto 0);
    signal lane_done    : std_logic_vector(C_LANES - 1 downto 0);
    signal lane_iter    : t_iter_tab;
    signal lane_escaped : std_logic_vector(C_LANES - 1 downto 0);

    -- tampon de resultats : C_SLOTS creneaux par lane, pointeurs circulaires.
    -- Deux pointeurs par lane au lieu d'un deplacement de donnees : aucune affectation
    -- concurrente au meme signal, donc aucun risque d'ecraser un resultat.
    signal s_slot    : t_slots_tab(0 to C_SLOTS * C_LANES - 1);
    signal s_w       : std_logic_vector(C_LANES - 1 downto 0) := (others => '0');  -- ecriture
    signal s_r       : std_logic_vector(C_LANES - 1 downto 0) := (others => '0');  -- lecture
    signal s_occ     : t_occ_tab := (others => (others => '0'));                   -- creneaux occupes

    -- suivi des points en vol : coordonnees du point confie au lane
    signal px_x_saved : t_x_tab;
    signal px_y_saved : t_y_tab;

    -- repartiteur
    signal s_lane_sel  : natural range 0 to C_LANES - 1 := 0;
    signal s_next_x    : t_px_x := (others => '0');
    signal s_next_y    : t_px_y := (others => '0');
    signal s_issued    : unsigned(C_PXW - 1 downto 0) := (others => '0');
    signal s_rendering : std_logic := '0';

    -- collecteur
    signal s_res_sel : natural range 0 to C_LANES - 1 := 0;
    signal s_emitted : unsigned(C_PXW - 1 downto 0) := (others => '0');

    -- etat global
    signal s_active : std_logic := '0';

    -- Sorties LUES A L'INTERIEUR de l'architecture : on passe par des signaux
    -- internes et on cable les ports en concurrence. Lire directement un port `out`
    -- est une facilite VHDL-2008 : en mode projet, Vivado lit les sources en VHDL-93
    -- par defaut et refuse alors le fichier --
    --   ERROR: [Synth 8-10557] cannot read from 'out' object 'o_px_valid';
    --                          use 'buffer' or 'inout' instead
    -- (erreur reellement rencontree en ouvrant le projet dans l'IHM). Avec ce cablage,
    -- le design s'analyse en VHDL-93 COMME en VHDL-2008 : verifie sur les deux.
    signal s_px_valid : std_logic := '0';
    signal s_cycles   : unsigned(31 downto 0) := (others => '0');

    -- c = point de depart + index * pas (calcul entier, en Q(C_FRAC)).
    function f_cr(x : t_px_x) return t_val is
    begin
        return to_signed(C_X0 + C_DX * to_integer(x), C_WIDTH);
    end function f_cr;

    function f_ci(y : t_px_y) return t_val is
    begin
        return to_signed(C_Y0 + C_DY * to_integer(y), C_WIDTH);
    end function f_ci;

    -- Un pointeur de creneau tient sur 1 bit : la conversion explicite evite
    -- `to_integer` sur un `std_logic` (qui n'existe pas dans numeric_std, erreur vue
    -- a l'analyse : "no overloaded function found matching to_integer").
    function f_bit_vers_int(b : std_logic) return natural is
    begin
        if b = '1' then
            return 1;
        else
            return 0;
        end if;
    end function f_bit_vers_int;

begin

    assert C_SLOTS >= 2
        report "Il faut au moins 2 creneaux de resultat par lane, sinon un resultat est ecrase."
        severity failure;
    assert C_TOTAL <= (2 ** C_PXW) - 1
        report "C_PXW ne peut pas representer C_IMG_W * C_IMG_H."
        severity failure;
    assert (C_IMG_W <= (2 ** C_XW)) and (C_IMG_H <= (2 ** C_YW))
        report "C_XW/C_YW sont trop petits pour C_IMG_W/C_IMG_H."
        severity failure;
    assert (C_X0 + C_DX * (C_IMG_W - 1)) < 2147483647
        report "Le calcul de la partie reelle deborde un entier 32 bits : reduire C_DX."
        severity failure;

    -- Configuration exposee (constantes a l'elaboration).
    o_cfg_lanes <= to_unsigned(C_LANES, 16);
    o_cfg_w     <= to_unsigned(C_IMG_W, 16);
    o_cfg_h     <= to_unsigned(C_IMG_H, 16);
    o_cfg_iter  <= to_unsigned(C_MAX_ITER, 16);
    o_cfg_frac  <= to_unsigned(C_FRAC, 8);
    o_cfg_x0    <= to_signed(C_X0, C_WIDTH);
    o_cfg_dx    <= to_signed(C_DX, C_WIDTH);
    o_cfg_y0    <= to_signed(C_Y0, C_WIDTH);
    o_cfg_dy    <= to_signed(C_DY, C_WIDTH);

    o_px_valid <= s_px_valid;
    o_cycles   <= s_cycles;

    -- ---------------------------------------------------------------- les lanes
    g_lanes : for k in 0 to C_LANES - 1 generate
        u_lane : entity work.mandelbrot_lane
            generic map (
                C_WIDTH    => C_WIDTH,
                C_FRAC     => C_FRAC,
                C_MAX_ITER => C_MAX_ITER,
                C_ITER_W   => C_ITER_W
            )
            port map (
                i_clk     => i_clk,
                i_rst     => i_rst,
                i_start   => lane_start(k),
                i_cr      => lane_cr(k),
                i_ci      => lane_ci(k),
                o_free    => lane_free(k),
                o_done    => lane_done(k),
                o_iter    => lane_iter(k),
                o_escaped => lane_escaped(k)
            );
    end generate g_lanes;

    -- ------------------------------------------------------------ repartiteur
    -- Un point est distribue par cycle au premier lane libre rencontre (balayage
    -- circulaire). Un lane n'accepte un nouveau point que s'il lui reste au moins un
    -- creneau libre : c'est la contre-pression qui rend la perte de resultat impossible.
    p_dispatch : process (i_clk)
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                lane_start  <= (others => '0');
                s_lane_sel  <= 0;
                s_next_x    <= (others => '0');
                s_next_y    <= (others => '0');
                s_issued    <= (others => '0');
                s_rendering <= '0';
            else
                lane_start <= (others => '0');   -- impulsion de 1 cycle par defaut

                if (i_start = '1') then
                    s_rendering <= '1';
                    s_issued    <= (others => '0');
                    s_next_x    <= (others => '0');
                    s_next_y    <= (others => '0');
                end if;

                if (s_rendering = '1') and (s_issued < C_TOTAL)
                   and (lane_free(s_lane_sel) = '1')
                   and (s_occ(s_lane_sel) < C_SLOTS) then
                    lane_cr(s_lane_sel)    <= f_cr(s_next_x);
                    lane_ci(s_lane_sel)    <= f_ci(s_next_y);
                    px_x_saved(s_lane_sel) <= s_next_x;
                    px_y_saved(s_lane_sel) <= s_next_y;
                    lane_start(s_lane_sel) <= '1';
                    s_issued               <= s_issued + 1;

                    -- pixel suivant : balayage ligne par ligne
                    if (s_next_x = C_IMG_W - 1) then
                        s_next_x <= (others => '0');
                        s_next_y <= s_next_y + 1;
                    else
                        s_next_x <= s_next_x + 1;
                    end if;
                end if;

                -- selection circulaire du lane candidat
                if (s_lane_sel = C_LANES - 1) then
                    s_lane_sel <= 0;
                else
                    s_lane_sel <= s_lane_sel + 1;
                end if;
            end if;
        end if;
    end process p_dispatch;

    -- -------------------------------------------------------------- collecteur
    p_collect : process (i_clk)
        variable v_lane_choisi   : natural range 0 to C_LANES - 1 := 0;
        variable v_lane_candidat : natural range 0 to C_LANES - 1;
        variable v_trouve : boolean;
        variable v_push   : boolean;
        variable v_pop    : boolean;
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_occ      <= (others => (others => '0'));
                s_w        <= (others => '0');
                s_r        <= (others => '0');
                s_px_valid <= '0';
                s_res_sel  <= 0;
                s_emitted  <= (others => '0');
            else
                -- (1) Choisir le lane dont on prend un resultat (balayage circulaire).
                --     Ce choix est fait AVANT les ecritures : la boucle suivante peut
                --     alors appliquer arrivee et depart sur le meme compteur en une seule
                --     affectation, ce qui supprime toute ambiguite de priorite.
                v_trouve := false;
                for j in 0 to C_LANES - 1 loop
                    if not v_trouve then
                        v_lane_candidat := (s_res_sel + j) mod C_LANES;
                        if (s_occ(v_lane_candidat) > 0) then
                            v_lane_choisi := v_lane_candidat;
                            v_trouve      := true;
                        end if;
                    end if;
                end loop;

                -- (2) Mise a jour par lane : une seule affectation par signal.
                for k in 0 to C_LANES - 1 loop
                    v_push  := (lane_done(k) = '1') and (s_occ(k) < C_SLOTS);
                    v_pop   := v_trouve and (s_px_valid = '0') and (k = v_lane_choisi);

                    if v_push then
                        s_slot(C_SLOTS * k + f_bit_vers_int(s_w(k))) <=
                            (x    => px_x_saved(k),
                             y    => px_y_saved(k),
                             iter => lane_iter(k),
                             esc  => lane_escaped(k));
                        s_w(k) <= not s_w(k);
                    end if;

                    if v_pop then
                        s_r(k) <= not s_r(k);
                    end if;

                    -- Compteur unique : 0 (vide) a C_SLOTS (plein).
                    -- PIEGE MESURE : `s_occ(k) + v_delta` avec v_delta entier signe
                    -- echoue en "bound check failure", car l'operateur numeric_std
                    -- `unsigned + INTEGER` attend en realite un NATURAL : une valeur
                    -- negative viole le sous-type avant tout calcul. On l'ecrit donc
                    -- en branches explicites.
                    if v_push and v_pop then
                        s_occ(k) <= s_occ(k);             -- un resultat entre, un sort
                    elsif v_push then
                        s_occ(k) <= s_occ(k) + 1;
                    elsif v_pop then
                        s_occ(k) <= s_occ(k) - 1;         -- impossible si s_occ = 0
                    end if;
                end loop;

                -- (3) Presenter le resultat choisi sur la sortie.
                if (s_px_valid = '0') and v_trouve then
                    o_px_x       <= s_slot(C_SLOTS * v_lane_choisi + f_bit_vers_int(s_r(v_lane_choisi))).x;
                    o_px_y       <= s_slot(C_SLOTS * v_lane_choisi + f_bit_vers_int(s_r(v_lane_choisi))).y;
                    o_px_iter    <= s_slot(C_SLOTS * v_lane_choisi + f_bit_vers_int(s_r(v_lane_choisi))).iter;
                    o_px_escaped <= s_slot(C_SLOTS * v_lane_choisi + f_bit_vers_int(s_r(v_lane_choisi))).esc;
                    s_px_valid   <= '1';
                elsif (s_px_valid = '1') and (i_px_ready = '1') then
                    -- accepte par le consommateur : c'est ICI qu'un pixel compte comme livre
                    s_px_valid <= '0';
                    s_emitted  <= s_emitted + 1;
                end if;

                if (s_res_sel = C_LANES - 1) then
                    s_res_sel <= 0;
                else
                    s_res_sel <= s_res_sel + 1;
                end if;
            end if;
        end if;
    end process p_collect;

    -- ------------------------------------------------------------------ etat
    p_status : process (i_clk)
        variable v_fini : boolean;
    begin
        if rising_edge(i_clk) then
            if i_rst = '1' then
                s_active <= '0';
                o_busy   <= '0';
                o_done   <= '0';
                s_cycles <= (others => '0');
            else
                o_done <= '0';

                if (i_start = '1') then
                    s_active <= '1';
                    o_busy   <= '1';
                    s_cycles <= (others => '0');
                end if;

                if (s_active = '1') then
                    s_cycles <= s_cycles + 1;

                    -- fin = tous les pixels livres, aucun resultat en attente,
                    --       aucun lane occupe
                    v_fini := (s_emitted = C_TOTAL);
                    for k in 0 to C_LANES - 1 loop
                        if (lane_free(k) = '0') or (s_occ(k) > 0) then
                            v_fini := false;
                        end if;
                    end loop;

                    if v_fini and (s_px_valid = '0') then
                        o_done   <= '1';
                        o_busy   <= '0';
                        s_active <= '0';
                    end if;
                end if;
            end if;
        end if;
    end process p_status;

end architecture rtl;
