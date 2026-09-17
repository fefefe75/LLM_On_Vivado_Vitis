# Toolchain — installation, versions, licences (cible **Linux**)

Ce dépôt cible **Linux** exclusivement : les commandes, les chemins et les scripts
sont écrits pour bash. Vivado/Vitis existent aussi sous Windows, mais rien ici n'est
testé ni maintenu pour Windows (pas de `.bat`, pas de `settings64.bat`, pas de
chemins `C:\`). Pour Linux, tout est couvert — installation, source de
l'environnement, batch, simulation, programmation.

Version de référence : **Vivado / Vitis 2025.2 (lin64)**, layout « par version ».
Les commandes marquées *(2020.2+)* ou *(2023.2+)* changent selon la version ; les
différences sont signalées au fil du texte.

---

## 1. Ce qui doit être installé

| Outil | Rôle | Licence | Taille |
|---|---|---|---|
| Vivado | synthèse, implémentation, bitstream, XSim, IP Integrator | gratuite pour les petites puces (WebPACK), sinon licence | ~35–70 Go |
| Vitis | logiciel embarqué (Zynq PS), plateformes, BSP | gratuite | ~10–20 Go |
| GHDL | simulation VHDL libre (utilisée par les tests de ce dépôt) | GPL, libre | ~25 Mo |
| Icarus Verilog / Verilator | simulation Verilog/SystemVerilog libre | GPL/LGPL | quelques Mo |
| cocotb | framework de test Python (testbenches en Python) | BSD | quelques Mo |
| GTKWave ou Surfer | visualisation d'ondes (`.ghw`, `.vcd`, `.fst`) | libre | ~10 Mo |
| Model Composer | optionnel (Simulink) — pas nécessaire ici | — | ~2,5 Go |

## 2. Arborescences d'installation rencontrées

Deux dispositions existent. Le serveur MCP et les scripts de ce dépôt gèrent les deux.

```
# A. installation "par version" (celle de la machine de référence)
~/vivado/2025.2/Vivado/bin/vivado
~/vivado/2025.2/Vitis/bin/vitis
~/vivado/2025.2/Vitis/bin/xsct

# B. installation AMD standard
/tools/Xilinx/Vivado/2025.2/bin/vivado
/tools/Xilinx/Vitis/2025.2/bin/vitis
```

Pour un agent, la question « où est Vivado ? » se répond ainsi :

```bash
ls -d /tools/Xilinx /opt/Xilinx ~/vivado 2>/dev/null     # candidats
find ~ /tools -maxdepth 4 -name settings64.sh 2>/dev/null # le plus fiable
```

## 3. Activer l'environnement (l'équivalent Linux de `settings64.bat`)

```bash
source /home/<user>/vivado/2025.2/Vivado/settings64.sh     # Vivado
source /home/<user>/vivado/2025.2/Vitis/settings64.sh      # xsct, vitis, bootgen
```
Ce script définit `PATH`, `XILINX_VIVADO`, `XILINX_VITIS`, `XILINX_HLS`, `LD_LIBRARY_PATH`.
Sans lui : `vivado: command not found`, ou des erreurs de bibliothèques partagées.

Pour un agent qui relance des commandes sans shell persistant, deux options :
sourcer dans la même commande (`bash -lc "source ... && vivado -mode batch ..."`),
ou passer la racine d'installation au serveur MCP (`FPGA_MCP_TOOL_ROOT=/home/<user>/vivado/2025.2`),
qui reconstruit l'équivalent (PATH + variables) sans sourcer.

Vérifications utiles :
```bash
vivado -version        # -> vivado v2025.2 (64-bit), Tool Version Limit: 2025.11
vitis --version        # -> Vitis v2025.2
xsim --version         # -> Vivado Simulator v2025.2
xsct -version          # encore présent en 2025.2 (déprécié depuis 2023.2)
```

> `Tool Version Limit` affiché par `vivado -version` est la **limite de version du
> fichier de licence** (pas la date du jour). Un design qui « marchait » peut
> échouer après une mise à jour de Vivado si la licence ne couvre pas la version.

## 4. Licences

- **Pièces gratuites (WebPACK)** : Artix-7 35T et inférieurs, Spartan-7,
  Zynq-7000 jusqu'à 7020, Kintex-7 70T… Ce sont les familles utilisées dans les
  exemples et les cartes pédagogiques. Aucun fichier de licence à demander.
- **Gros composants** (Kintex UltraScale+, Versal, gros Virtex) : licence
  flottante/node-locked à demander chez AMD (gratuite en version « device-locked »).
- **Vivado Lab Edition** : gratuite, pour programmer et déboguer sur du matériel,
  sans synthèse — utile si seul le programmeur est nécessaire.
- Emplacement classique d'une licence locale : `~/.Xilinx/*.lic`,
  `XILINX_LOCAL_USER_DATA`, ou `/usr/local/flexlm` (le dossier existe sur la machine
  de référence pour un serveur flottant).

## 5. Câbles JTAG et udev (obligatoire pour programmer)

```bash
lsusb | grep -i xilinx                      # le câble est-il vu ?
# pilotes fournis avec Vivado (à relancer après mise à jour du noyau) :
sudo bash /tools/Xilinx/Vivado/2025.2/data/xicom/cable_drivers/lin64/install_script/install_drivers/install_drivers
```
Sans ces règles, `program_hw_devices` renvoie « aucun câble détecté » ou un
`hw_server` qui ne voit rien. (Le chemin est identique dans une installation
`~/vivado/<version>/Vivado/data/...`.)

## 6. Chemin 100 % libre (aucune licence, aucun compte)

Indispensable pour un agent qui doit vérifier du VHDL tout de suite, et c'est ce
qui est utilisé par les tests de ce dépôt :

```bash
# GHDL : binaire précompilé, aucune installation système nécessaire
curl -sL -o /tmp/ghdl.tgz \
  https://github.com/ghdl/ghdl/releases/download/v6.0.0/ghdl-mcode-6.0.0-ubuntu24.04-x86_64.tar.gz
mkdir -p /tmp/ghdl_tool && tar xzf /tmp/ghdl.tgz -C /tmp/ghdl_tool --strip-components=1
/tmp/ghdl_tool/bin/ghdl --version          # GHDL 6.0.0, backend mcode

# cocotb 2.x dans un venv Python
python3 -m venv ~/.venv-fpga && . ~/.venv-fpga/bin/activate
pip install cocotb>=2.0,<3

# Fedora : ghdl/iverilog/verilator/gtkwave sont dans les dépôts
sudo dnf install -y ghdl iverilog verilator gtkwave
# Debian/Ubuntu : sudo apt install -y ghdl iverilog verilator gtkwave
```

Limite importante : **GHDL ne simule que du VHDL**, Icarus/Verilator que du
Verilog/SystemVerilog — et **cocotb ne pilote pas XSim** (voir
`docs/03-simulation.md`). Pour un projet Vivado 100 % VHDL sans carte, la
combinaison qui marche est : *cocotb + GHDL pour vérifier, Vivado pour synthétiser
et implémenter*.

## 7. Raccourcis de batch Vivado à connaître

```bash
vivado -mode batch -source script.tcl -nolog -nojournal -notrace -tclargs --xpr prj.xpr
```
| Option | Effet |
|---|---|
| `-mode batch` | pas d'IHM (avec `DISPLAY=""` : jamais d'ouverture de fenêtre) |
| `-nolog` / `-nojournal` | ne pas écrire `vivado.log` / `vivado.jou` dans le dossier courant |
| `-notrace` | journal moins verbeux (utile dans un pipeline) |
| `-tclargs ...` | arguments accessibles via `$argv` dans le script |
| `-tempdir DIR` | dossier temporaire (utile sur disque lent) |

Le **code retour** de `vivado` est non nul quand une commande échoue : c'est ce
qu'un agent doit tester. Un `ERROR:` dans le script interrompt l'exécution du
script (comportement observé en mode batch).

## 8. Ce que la machine de référence a réellement

Vérifié lors de l'écriture de ce dépôt :

```
Vivado v2025.2 (64-bit)   Tool Version Limit: 2025.11   (+ XSim, xsct, Vitis v2025.2)
GHDL 6.0.0 (mcode, JIT)   cocotb 2.0.1 (Python 3.12)     tclsh 8.6
Pièces dispo. : xc7z020*, xc7z010*, xc7z007s*, xc7a35t* (30 variantes), xc7a100t*
Commande absente de 2025.2 : write_hw_def  (remplacée par write_hw_platform)
```
