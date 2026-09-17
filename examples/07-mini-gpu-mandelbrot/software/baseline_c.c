/* baseline_c.c - le MEME algorithme que le mini-GPU, en C sur un coeur CPU.
 *
 * Sert de point de comparaison honnete : meme format virgule fixe Q26, memes
 * operations entieres (donc memes resultats, pixel par pixel), meme fenetre du plan
 * complexe. Ce que l'on compare, c'est le debit : un coeur CPU sequentiel contre
 * N lanes FPGA en parallele.
 *
 * Compilation et execution :
 *   gcc -O2 -o baseline_c baseline_c.c && ./baseline_c 128 96 64
 *
 * Le total d'iterations imprime doit etre IDENTIQUE a `iterations_totales` du banc
 * cocotb : c'est un controle croise entre le C, le Python et le VHDL.
 */

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define FRAC 26
#define ONE (1 << FRAC)

/* Fenetre identique a mandelbrot_config.py : (-2.1..0.7) x (-1.2..1.2) */
static const double XMIN = -2.1, XMAX = 0.7, YMIN = -1.2, YMAX = 1.2;

static int32_t quantifier(double valeur) {
    double x = valeur * (double)ONE;
    return (int32_t)(x >= 0.0 ? x + 0.5 : x - 0.5);
}

/* Nombre d'iterations avant fuite (ou max_iter si le point est dans l'ensemble).
 * Reproduction exacte de mandelbrot_lane.vhd : le decalage a droite d'un entier
 * signe est arithmetique en C (implementation-defined, mais arithmetique sur toutes
 * les plateformes x86/ARM courantes et garanti par le modele VHDL). */
static int mandelbrot(int32_t cr, int32_t ci, int max_iter) {
    int32_t zr = 0, zi = 0;
    int n = 0;
    const int64_t seuil = 4LL * (int64_t)ONE * (int64_t)ONE;

    for (;;) {
        int64_t p_rr = (int64_t)zr * (int64_t)zr;
        int64_t p_ii = (int64_t)zi * (int64_t)zi;
        int64_t p_ri = 2LL * (int64_t)zr * (int64_t)zi;

        if (p_rr + p_ii > seuil) return n;
        if (n >= max_iter) return n;

        zr = (int32_t)(((p_rr - p_ii) >> FRAC) + cr);
        zi = (int32_t)((p_ri >> FRAC) + ci);
        n++;
    }
}

static double maintenant(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (double)t.tv_sec + 1e-9 * (double)t.tv_nsec;
}

int main(int argc, char **argv) {
    int largeur = (argc > 1) ? atoi(argv[1]) : 128;
    int hauteur = (argc > 2) ? atoi(argv[2]) : 96;
    int max_iter = (argc > 3) ? atoi(argv[3]) : 64;
    int repetitions = (argc > 4) ? atoi(argv[4]) : 3;

    int32_t x0 = quantifier(XMIN), y0 = quantifier(YMIN);
    int32_t dx = quantifier((XMAX - XMIN) / (double)largeur);
    int32_t dy = quantifier((YMAX - YMIN) / (double)hauteur);

    long long iterations = 0;
    volatile long long controle = 0;
    double meilleur = 1e30;

    for (int r = 0; r < repetitions; r++) {
        double t0 = maintenant();
        iterations = 0;
        for (int y = 0; y < hauteur; y++) {
            int32_t ci = y0 + dy * y;
            for (int x = 0; x < largeur; x++) {
                int32_t cr = x0 + dx * x;
                iterations += mandelbrot(cr, ci, max_iter);
            }
        }
        double dt = maintenant() - t0;
        controle += iterations;
        if (dt < meilleur) meilleur = dt;
    }

    double pixels = (double)largeur * (double)hauteur;
    printf("image            : %d x %d (%d pixels), max_iter=%d\n", largeur, hauteur, largeur * hauteur, max_iter);
    printf("iterations       : %lld\n", iterations);
    printf("meilleur temps   : %.6f s\n", meilleur);
    printf("debit CPU        : %.3f Mpixels/s\n", pixels / meilleur / 1e6);
    printf("iterations/s     : %.3f Miter/s\n", (double)iterations / meilleur / 1e6);
    printf("controle         : %lld\n", controle);
    return 0;
}
