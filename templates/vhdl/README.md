# Templates VHDL

Squelettes à copier, volontairement courts et **compilés pour de vrai** (GHDL 6.0.0,
`--std=08`) :

| Fichier | Rôle |
|---|---|
| `entity_combinatoire.vhd` | module combinatoire : mux + comparateur, valeurs par défaut (pas de latch) |
| `registre_synchrone.vhd` | registre avec enable, reset synchrone, valeur de reset générique |
| `compteur.vhd` | compteur avec enable, clear, plafond générique et impulsion `o_tick` |
| `fsm_moore.vhd` | machine d'états : 1 process d'état + 1 process combinatoire |
| `synchroniseur_2ff.vhd` | synchronisation d'un signal asynchrone (bouton, entrée externe) |
| `package_utils.vhd` | package : types énumérés, conversion, fonction de saturation |
| `tb_compteur.vhd` | **testbench auto-vérifiant en VHDL** (XSim **et** GHDL), pour les environnements sans cocotb |

Compilation de contrôle :
```bash
ghdl -a --std=08 entity_combinatoire.vhd registre_synchrone.vhd compteur.vhd \
             fsm_moore.vhd synchroniseur_2ff.vhd package_utils.vhd
# testbench complet (9 vérifications) :
ghdl -a --std=08 compteur.vhd tb_compteur.vhd
ghdl -m --std=08 tb_compteur && ghdl -r --std=08 tb_compteur --assert-level=error
#   -> *** 9 verifications, 0 erreur(s) ***   ALL TESTS PASSED
```
Le même testbench, sous XSim :
```bash
xvhdl -2008 compteur.vhd tb_compteur.vhd
xelab -debug typical -s tb_sim work.tb_compteur
xsim tb_sim -R          # -> Note: *** 9 verifications, 0 erreur(s) *** / ALL TESTS PASSED
```
Les deux simulateurs donnent exactement le même verdict (c'est ce qui a permis de
piéger les erreurs ci-dessous).

## Trois règles apprises en écrivant ces fichiers (toutes vérifiées)

1. **Un testbench VHDL doit échantillonner au milieu de la période.**
   Juste après `wait until rising_edge(clk)`, la sortie du DUT n'est pas encore mise
   à jour (cycles delta) : on lit l'**ancienne** valeur — et `wait for 0 ns` ne
   suffit pas. Trace réelle du compteur, un front par ligne :
   ```
   front 1 : count=0   (mauvaise lecture)      front 1 : count=1   (lecture a +periode/4)
   front 2 : count=1                            front 2 : count=2
   ```
   D'où la procédure `front` du template : `rising_edge` puis `wait for C_PERIODE/4`.
   C'est le cousin VHDL du piège cocotb « lire sur `RisingEdge` sans `ReadOnly` ».

2. **Pas de `shared variable`** en VHDL-2008 : GHDL refuse avec
   `type of a shared variable must be a protected type`. Utiliser des variables
   locales au process, lues par une procédure imbriquée (comme dans `tb_compteur.vhd`).

3. **Les procédures vont dans une partie déclarative**, jamais après le `begin` d'une
   architecture (`error: unexpected token 'procedure' in a concurrent statement list`).
   Et `return (others => '0');` est refusé dans une fonction : passer par une variable
   locale (voir `saturer` dans `package_utils.vhd`).

## Convention de nommage

`i_*` entrées · `o_*` sorties · `s_*` signaux internes · `C_*` constantes ·
`p_*` labels de process · `t_*` types · `v_*` variables de process.
Un module par fichier, nom de fichier = nom d'entité.

## Vérifier un template après modification

```bash
python3 ../../scripts/check_tcl.py .      # sans rapport avec le VHDL, mais utile si tu ajoutes du Tcl
cd .. && ..                                     # puis, depuis ce dossier :
for f in *.vhd; do ghdl -a --std=08 "$f" || echo "ECHEC: $f"; done
```
