---
name: vhdl-synthesizable
description: Use when writing or reviewing VHDL for an FPGA (entity, process, FSM, counter, register, FIFO, top-level) that must synthesize in Vivado.
---

# Écrire du VHDL qui synthétise

Squelettes prêts : `templates/vhdl/`. Conventions et pièges étendus :
`docs/06-constraints-xdc.md` (contraintes) et `docs/10-troubleshooting.md` §2 (erreurs
de synthèse réelles). Exemples complets : `examples/01`, `02`, `03`, `05`.

## Règles

1. Un module par fichier, nom de fichier = nom d'entité (minuscules, `_`).
2. Ports : `i_*` entrées, `o_*` sorties, `s_*` signaux internes, `C_*` constantes,
   `p_*` labels de process.
3. `ieee.std_logic_1164` + `ieee.numeric_std` **uniquement**. Jamais
   `std_logic_arith` / `std_logic_unsigned` (non standard, source de bugs de largeur).
4. **Ne jamais relire un port `out` dans l'architecture.** C'est une facilité
   VHDL-2008 : GHDL l'accepte en `--std=08`, mais **un projet Vivado lit les sources
   en VHDL-93 par défaut** et rejette alors le fichier avec
   `ERROR: [Synth 8-10557] cannot read from 'out' object 'o_x'; use 'buffer' or 'inout' instead`.
   Écrire dans un signal interne et câbler le port en concurrence :
   ```vhdl
   signal s_px_valid : std_logic := '0';
   o_px_valid <= s_px_valid;          -- le port n'est jamais lu
   ```
   Le module s'analyse alors en **VHDL-93 comme en VHDL-2008** : à préférer pour tout
   code destiné à être ouvert dans un projet Vivado.
5. Un seul style de reset, et un reset **synchrone actif haut** par défaut :
   ```vhdl
   p_seq : process (i_clk) is
   begin
       if rising_edge(i_clk) then
           if i_rst = '1' then
               s_val <= (others => '0');
           else
               s_val <= s_next;
           end if;
       end if;
   end process p_seq;
   ```
6. Process combinatoire : **affecter une valeur par défaut à chaque sortie en tête**,
   sinon Vivado infère un latch (`WARNING: [Synth 8-327] inferring latch`).
7. Pas de `after`, pas de `wait for`, pas de variable qui porte une sortie, pas
   d'initialisation de signal en RTL (à part `:= (others => '0')` pour la simulation).
8. Conversions explicites : `std_logic_vector(s_count)`, `to_unsigned(n, W)`,
   `to_signed(n, W)`. Ne jamais comparer deux `std_logic_vector` de largeurs
   différentes.
9. Entiers et génériques : préférer `unsigned`/`signed` avec un générique `C_WIDTH`.

## Virgule fixe : dimensionner sur le pire intermédiaire

Trois `bound check failure` **mesurés** (GHDL) qui n'ont rien à voir avec les signaux
finaux :

1. **Le format Q doit couvrir l'intermédiaire le plus grand.** Q28 sur 32 bits porte
   ±8,0 ; dans `z ← z² + c`, l'intermédiaire `2·zr·zi` atteint exactement 8,0 au bord
   de la fuite → dépassement. Dimensionner sur le pire cas, pas sur la sortie
   (exemple : Q26 → ±32, et le format est passé en générique + déclaré par un port).
2. **Pas de multiplication d'un vecteur large par un littéral entier** :
   `resize(x, 64) * 2` échoue même pour de petites valeurs → `shift_left(x, 1)`.
3. **`unsigned + delta` avec un delta signé** échoue : l'opérateur numeric_std prend
   en réalité un **NATURAL**. Écrire les cas en branches explicites (`+1`, `-1`,
   inchangé) au lieu d'additionner un delta signé.

Exemple complet et synthétisé : `examples/07-mini-gpu-mandelbrot/`.

## Erreurs de synthèse fréquentes (messages réels)

| Message | Cause | Correctif |
|---|---|---|
| `[Synth 8-36] 'o_q' is not declared` | port/signal non déclaré | déclarer, ou corriger la faute de frappe |
| `[Synth 8-2716] syntax error near 'process'` | `end if;`/`end process;` manquant | vérifier l'imbrication |
| `[Synth 8-5826] no such design unit 'x'` | entité instanciée absente ou ordre de compilation | `add_files` + `update_compile_order -fileset sources_1` |
| `[Synth 8-327] inferring latch` | branche non couverte | valeur par défaut en tête de process |

## Vérification obligatoire

Aucun module ne part en synthèse sans un testbench cocotb qui passe
(`skills/cocotb-testbench/SKILL.md`, via `docs/04-cocotb-recipes.md`) :

```bash
cd tb/<module> && PATH=/tmp/ghdl_tool/bin:$PATH make
```

## Découpage recommandé

- Un fichier = une entité. Un `top` qui ne fait qu'instancier et câbler.
- Une FSM par fichier, `type t_etat is (IDLE, RUN, DONE);` + un process séquentiel
  (état) et un process combinatoire (sorties et prochain état).
- Les bus et registres partagés vont dans un `package` (`templates/vhdl/vhdl_pkg_template.vhd`).
- Chronologie : d'abord le chemin de données, puis la FSM, puis le testbench.
