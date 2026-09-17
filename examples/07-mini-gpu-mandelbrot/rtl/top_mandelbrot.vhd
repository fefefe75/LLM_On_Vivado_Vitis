library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

--! @brief Top de synthese du mini-GPU : enveloppe de `mandelbrot_gpu` avec des
--!        valeurs par defaut realistes pour une carte XC7Z020 (640x480).
--!
--! C'est CETTE entite que la synthese Vivado prend comme top. Les generateurs
--! (taille d'image, nombre de lanes) se changent soit ici, soit depuis la ligne
--! de commande de synth_design :
--!     synth_design -top top_mandelbrot -part xc7z020clg400-1 \
--!                  -generic C_LANES=16,C_IMG_W=640,C_IMG_H=480
--! Verifie : synthese reelle Vivado 2025.2 (voir README, section mesures).

entity top_mandelbrot is
    generic (
        C_LANES    : positive := 16;
        C_IMG_W    : positive := 640;
        C_IMG_H    : positive := 480;
        C_MAX_ITER : positive := 128
    );
    port (
        i_clk        : in  std_logic;        -- horloge, 100 MHz typique sur Zynq-7020
        i_rst        : in  std_logic;        -- reset synchrone actif haut
        i_start      : in  std_logic;        -- 1 cycle : lance le rendu d'une image
        o_px_valid   : out std_logic;        -- flot de sortie (valid/ready)
        i_px_ready   : in  std_logic;
        o_px_x       : out unsigned(9 downto 0);
        o_px_y       : out unsigned(8 downto 0);
        o_px_iter    : out unsigned(7 downto 0);
        o_px_escaped : out std_logic;
        o_busy       : out std_logic;
        o_done       : out std_logic;
        o_cycles     : out unsigned(31 downto 0)
    );
end entity top_mandelbrot;

architecture rtl of top_mandelbrot is
begin

    u_gpu : entity work.mandelbrot_gpu
        generic map (
            C_IMG_W    => C_IMG_W,
            C_IMG_H    => C_IMG_H,
            C_LANES    => C_LANES,
            C_MAX_ITER => C_MAX_ITER,
            C_XW       => 10,
            C_YW       => 9
        )
        port map (
            i_clk        => i_clk,
            i_rst        => i_rst,
            i_start      => i_start,
            o_px_valid   => o_px_valid,
            i_px_ready   => i_px_ready,
            o_px_x       => o_px_x,
            o_px_y       => o_px_y,
            o_px_iter    => o_px_iter,
            o_px_escaped => o_px_escaped,
            o_busy       => o_busy,
            o_done       => o_done,
            o_cycles     => o_cycles,
            o_cfg_lanes  => open,
            o_cfg_w      => open,
            o_cfg_h      => open,
            o_cfg_iter   => open,
            o_cfg_frac   => open,
            o_cfg_x0     => open,
            o_cfg_dx     => open,
            o_cfg_y0     => open,
            o_cfg_dy     => open
        );

end architecture rtl;
