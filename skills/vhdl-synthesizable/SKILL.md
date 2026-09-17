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
4. Un seul style de reset, et un reset **synchrone actif haut** par défaut :
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
5. Process combinatoire : **affecter une valeur par défaut à chaque sortie en tête**,
   sinon Vivado infère un latch (`WARNING: [Synth 8-327] inferring latch`).
6. Pas de `after`, pas de `wait for`, pas de variable qui porte une sortie, pas
   d'initialisation de signal en RTL (à part `:= (others => '0')` pour la simulation).
7. Conversions explicites : `std_logic_vector(s_count)`, `to_unsigned(n, W)`,
   `to_signed(n, W)`. Ne jamais comparer deux `std_logic_vector` de largeurs
   différentes.
8. Entiers et génériques : préférer `unsigned`/`signed` avec un générique `C_WIDTH`.

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
