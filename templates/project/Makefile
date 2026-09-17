# =============================================================================
#  Makefile « boite a outils » - squelette de projet FPGA (VHDL)
#  Depot : LLM_On_Vivado_Vitis  .  modele : templates/project/
#
#  Ce Makefile ne connait AUCUN nom de module : il decouvre tout seul
#      - les sources VHDL      : rtl/**/*.vhd        (cible lint)
#      - les testbenches       : tb/*/               (cibles sim, sim-one, waves)
#      - les scripts Tcl       : **/*.tcl            (cible tcl-check)
#  Ajouter un module ou un test ne demande donc aucune modification ici.
#
#  Regle d'or du depot : aucune affirmation sans log. Une cible qui n'a pas pu
#  s'executer le dit et n'invente jamais un resultat.
#
#  Aide complete :  make help
# =============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# --- outils (tous surchargeables) -------------------------------------------
#   make sim SIM=questa
#   make vivado-build VIVADO=/outils/Xilinx/2024.1/Vivado/bin/vivado
SIM    ?= ghdl
GHDL   ?= ghdl
VIVADO ?= vivado
VITIS  ?= vitis
XSCT   ?= xsct
PYTHON ?= python3
TCLSH  ?= tclsh

# --- repertoires du projet ---------------------------------------------------
RTL_DIR     ?= rtl
TB_DIR      ?= tb
SCRIPTS_DIR ?= scripts
SIM_DIR     ?= sim
BUILD_DIR   ?= build

# --- parametres --------------------------------------------------------------
# WAVES=1 enregistre les traces (.ghw / .vcd / .fst)
# SEED est la graine cocotb : les tests doivent etre reproductibles
# TEST est le nom du dossier tb/<TEST> pour sim-one et waves
WAVES ?= 0
SEED  ?= 1234
TEST  ?=

# --- arguments passes aux outils EDA -----------------------------------------
# ex : make vivado-create VIVADO_ARGS="-tclargs --part xc7a35tcsg324-1"
VIVADO_ARGS ?=
VITIS_ARGS  ?=

# --- localisation des scripts EDA --------------------------------------------
# Les modeles Tcl/Python de Vivado et Vitis vivent dans templates/ du depot.
# Un projet copie peut aussi embarquer ses propres copies dans scripts/.
# Recherche, dans l'ordre : $(EDA_SCRIPT_DIR), ./scripts/, ./templates/...,
# puis les chemins relatifs au depot (../../templates/...).
EDA_SCRIPT_DIR  ?=
EDA_SCRIPT_DIRS ?= $(EDA_SCRIPT_DIR) $(CURDIR)/scripts $(CURDIR)/templates/vivado $(CURDIR)/templates/vitis $(CURDIR)/../templates/vivado $(CURDIR)/../templates/vitis $(CURDIR)/../../templates/vivado $(CURDIR)/../../templates/vitis

# Premier chemin existant pour un nom de fichier donne.
eda_script = $(firstword $(foreach d,$(EDA_SCRIPT_DIRS),$(if $(wildcard $(d)/$(1)),$(d)/$(1))))

VIVADO_CREATE  = $(call eda_script,create_project.tcl)
VIVADO_BUILD   = $(call eda_script,build.tcl)
VIVADO_PROGRAM = $(call eda_script,program.tcl)
# Vitis : noms non ambigus uniquement. Pas de build.py / build.tcl, sinon un
# build.tcl de Vivado range dans ./scripts/ serait lance avec xsct.
VITIS_SCRIPT   = $(firstword $(foreach f,create_app.py create_app.tcl vitis_build.py vitis_build.tcl build_app.py build_app.tcl,$(call eda_script,$(f))))

# --- chemins ou sont cherches ces scripts (pour les messages d'erreur) --------
EDA_SEARCH_LIST = $(foreach d,$(EDA_SCRIPT_DIRS),$(if $(d),$(d),.))

# =============================================================================
#  Messages des garde-fous (texte affiche quand un outil manque)
#  ATTENTION : GNU Make 4.4 tronque une variable multi-lignes utilisee dans une
#  recette (le texte est coupe au premier saut de ligne). Ces textes sont donc
#  sur UNE seule ligne, avec des \n interpretes par printf %b a l'affichage.
#  Meme contrainte : pas de caractere $ ni # dans ces chaines.
# =============================================================================

HINT_NO_VIVADO = \n  ============================================================================\n   ATTENTION : le binaire vivado est introuvable dans le PATH.\n   Cette cible n'a PAS ete executee : aucun projet, build ou bitstream n'a ete\n   cree. Ce message n'est pas un succes de build. Que faire :\n     1) sourcer une installation Vivado existante :\n          source /chemin/vers/Xilinx/2024.1/Vivado/settings64.sh\n     2) ou donner le chemin du binaire :\n          make vivado-build VIVADO=/chemin/vers/Vivado/2024.1/bin/vivado\n     3) ou verifier le design sans Vivado (suffisant pour valider) :\n          make lint          analyse VHDL (GHDL)\n          make sim           simulation cocotb\n  ============================================================================\n

HINT_NO_VITIS = \n  ============================================================================\n   ATTENTION : le binaire vitis (ou xsct) est introuvable dans le PATH.\n   Cette cible n'a PAS ete executee : aucun logiciel embarque n'a ete compile.\n   Que faire :\n     1) sourcer Vitis (version 2023.2 et plus : vitis / avant : xsct) :\n          source /chemin/vers/Xilinx/2024.1/Vitis/settings64.sh\n     2) ou donner le chemin du binaire :\n          make vitis-build VITIS=/chemin/vers/Vitis/2024.1/bin/vitis\n          make vitis-build XSCT=/chemin/vers/Vitis/2023.1/bin/xsct\n     3) verifier le nom du script attendu :  make check-tools\n  ============================================================================\n

HINT_NO_GHDL = \n  ============================================================================\n   ATTENTION : le binaire ghdl est introuvable dans le PATH.\n   Que faire :\n     - Fedora : sudo dnf install ghdl              (paquet officiel)\n     - ou binaire local : make lint GHDL=/opt/ghdl/bin/ghdl\n     - ou simulation     : make sim SIM=icarus     (Verilog seulement)\n  ============================================================================\n

HINT_NO_TCLSH = \n  ============================================================================\n   ATTENTION : tclsh est introuvable dans le PATH.\n   Il sert uniquement a verifier la syntaxe des scripts .tcl.\n     - Fedora : sudo dnf install tcl\n     - ou      : make tcl-check TCLSH=/usr/bin/tclsh8.6\n  ============================================================================\n

# =============================================================================
#  Aide
# =============================================================================

help: ## Affiche cette aide (cible par defaut)
	@echo "Makefile boite a outils - squelette de projet FPGA (LLM_On_Vivado_Vitis)"
	@echo ""
	@echo "Usage : make <cible> [VARIABLE=valeur]"
	@echo ""
	@echo "Cibles :"
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables courantes :"
	@echo "  SIM=ghdl|icarus|questa   simulateur cocotb            (defaut : $(SIM))"
	@echo "  TEST=<nom>               dossier tb/<nom>              (sim-one, waves)"
	@echo "  WAVES=1                  enregistrer les traces        (defaut : $(WAVES))"
	@echo "  SEED=1234                graine cocotb                 (defaut : $(SEED))"
	@echo "  GHDL=$(GHDL)  VIVADO=$(VIVADO)  VITIS=$(VITIS)  PYTHON=$(PYTHON)"
	@echo ""
	@echo "Exemples :"
	@echo "  make lint"
	@echo "  make sim"
	@echo "  make sim-one TEST=compteur"
	@echo "  make waves TEST=compteur"
	@echo "  make vivado-build VIVADO=/outils/Xilinx/2024.1/Vivado/bin/vivado"

# =============================================================================
#  Environnement : etat des outils (utile quand une cible EDA se plaint)
# =============================================================================

check-tools: ## Montre les outils trouves et les scripts EDA detects
	@echo "Outils (recherche dans le PATH) :"
	@for t in $(GHDL) $(VIVADO) $(VITIS) $(XSCT) $(TCLSH) $(PYTHON); do \
	  p=$$(command -v $$t 2>/dev/null); \
	  if [ -n "$$p" ]; then echo "  [ok]    $$t -> $$p"; else echo "  [absent] $$t"; fi; \
	done
	@echo ""
	@echo "Scripts EDA detectes :"
	@printf '  %-24s %s\n' "create_project.tcl" "$(if $(VIVADO_CREATE),$(VIVADO_CREATE),introuvable)"
	@printf '  %-24s %s\n' "build.tcl"          "$(if $(VIVADO_BUILD),$(VIVADO_BUILD),introuvable)"
	@printf '  %-24s %s\n' "program.tcl"        "$(if $(VIVADO_PROGRAM),$(VIVADO_PROGRAM),introuvable)"
	@printf '  %-24s %s\n' "vitis (build.py/tcl)" "$(if $(VITIS_SCRIPT),$(VITIS_SCRIPT),introuvable)"
	@echo ""
	@echo "Repertoires fouilles : $(EDA_SEARCH_LIST)"
	@echo "Surcharge : make vivado-build EDA_SCRIPT_DIR=/chemin/vers/templates/vivado"

# =============================================================================
#  Analyse VHDL : ghdl -i puis ghdl -a sur tout rtl/**, VHDL-2008
# =============================================================================

lint: ## Analyse tout rtl/**/*.vhd avec GHDL (VHDL-2008)
	@if ! command -v $(GHDL) >/dev/null 2>&1; then \
	  printf '%b\n' "$(HINT_NO_GHDL)"; \
	  exit 1; \
	fi
	@$(SCRIPTS_DIR)/ghdl_lint.sh "$(RTL_DIR)" "$(BUILD_DIR)/lint" "$(GHDL)"

# =============================================================================
#  Simulation cocotb : boucle sur tb/*/ + agregation
# =============================================================================

sim: ## Lance TOUS les testbenches de tb/*/ et agrege les resultats
	@nb=0; ok=0; ko=0; ignores=0; en_echec=""; tbs=""; \
	for d in `ls -d $(TB_DIR)/*/ 2>/dev/null | sort`; do \
	  if [ -n "`ls -A $$d 2>/dev/null`" ]; then tbs="$$tbs $$d"; fi; \
	done; \
	if [ -z "$$tbs" ]; then \
	  echo "[sim] aucun testbench a lancer : $(TB_DIR)/ est vide (ou absent)."; \
	  echo "[sim] creez $(TB_DIR)/<mon_test>/ avec soit un Makefile cocotb,"; \
	  echo "[sim] soit un run_tests.py (voir $(TB_DIR)/README.md)."; \
	  exit 0; \
	fi; \
	for d in $$tbs; do \
	  name=`basename $$d`; nb=`expr $$nb + 1`; \
	  echo ""; \
	  echo "===================== [$$nb] $$name ====================="; \
	  if [ -f "$$d/Makefile" ] || [ -f "$$d/run_tests.py" ]; then \
	    if SIM=$(SIM) WAVES=$(WAVES) SEED=$(SEED) PYTHON=$(PYTHON) MAKE="$(MAKE)" \
	       $(SCRIPTS_DIR)/run_testbench.sh "$$d"; then \
	      ok=`expr $$ok + 1`; echo "----> $$name : OK"; \
	    else \
	      ko=`expr $$ko + 1`; en_echec="$$en_echec $$name"; echo "----> $$name : ECHEC"; \
	    fi; \
	  else \
	    echo "[sim] $$d ignore : ni Makefile ni run_tests.py (voir $(TB_DIR)/README.md)"; \
	    ignores=`expr $$ignores + 1`; \
	  fi; \
	done; \
	echo ""; \
	echo "=========== RESUME : $$nb testbench(s), $$ok OK, $$ko ECHEC, $$ignores ignore(s) ==========="; \
	if [ $$ko -ne 0 ]; then echo "en echec :$$en_echec"; exit 1; fi

sim-one: ## Lance UN testbench : make sim-one TEST=<dossier dans tb/>
	@d=""; \
	if [ -n "$(TEST)" ]; then d="$(TB_DIR)/$(TEST)"; \
	  if [ ! -d "$$d" ]; then \
	    echo "[sim-one] dossier $$d introuvable."; \
	    echo "[sim-one] disponibles : `ls -d $(TB_DIR)/*/ 2>/dev/null | sed 's:^.*/\([^/]*\)/$$:\1:' | tr '\n' ' '`"; \
	    exit 2; \
	  fi; \
	else \
	  d=`ls -d $(TB_DIR)/*/ 2>/dev/null | sort | head -1`; \
	  if [ -z "$$d" ]; then echo "[sim-one] $(TB_DIR)/ est vide : rien a lancer."; exit 0; fi; \
	  echo "[sim-one] TEST non fourni : utilisation de $$d"; \
	fi; \
	echo "===================== `basename $$d` ====================="; \
	if SIM=$(SIM) WAVES=$(WAVES) SEED=$(SEED) PYTHON=$(PYTHON) MAKE="$(MAKE)" \
	   $(SCRIPTS_DIR)/run_testbench.sh "$$d"; then \
	  echo "----> `basename $$d` : OK"; \
	else \
	  echo "----> `basename $$d` : ECHEC"; exit 1; \
	fi

waves: ## Lance un test en enregistrant les traces (WAVES=1) : make waves [TEST=<nom>]
	@echo "[waves] WAVES=1 : les traces (.ghw / .vcd) sont ecrites dans le dossier du testbench."
	@$(MAKE) --no-print-directory sim-one WAVES=1 TEST=$(TEST)
	@echo ""
	@echo "[waves] traces trouvees :"
	@find $(TB_DIR) -maxdepth 2 \( -name '*.ghw' -o -name '*.vcd' -o -name '*.fst' \) -printf '  %p  (%s octets)\n' 2>/dev/null | sort \
	  || echo "  (aucune : le simulateur n'a peut-etre pas d'option de trace)"

# =============================================================================
#  Verifications statiques hors GHDL
# =============================================================================

tcl-check: ## Verifie la syntaxe de tous les scripts .tcl (tclsh, sans execution)
	@if ! command -v $(TCLSH) >/dev/null 2>&1; then \
	  printf '%b\n' "$(HINT_NO_TCLSH)"; \
	  exit 1; \
	fi
	@files=`find . -path ./.git -prune -o -type f -name '*.tcl' -print 2>/dev/null \
	  | grep -vE '/(build|sim_build|\.Xil|\.runs|\.sim|\.cache|\.hw|\.ip_user_files|\.vitest|__pycache__)/' \
	  | sort`; \
	if [ -z "$$files" ]; then echo "[tcl-check] aucun script .tcl a verifier."; exit 0; fi; \
	echo "[tcl-check] fichiers :"; echo "$$files" | sed 's/^/  /'; \
	echo ""; \
	$(TCLSH) $(SCRIPTS_DIR)/check_tcl_syntax.tcl $$files

# =============================================================================
#  Vivado (scripts de templates/vivado/) : mode batch, non interactif
# =============================================================================

vivado-create: ## Cree le projet Vivado (script create_project.tcl, mode batch)
	@if ! command -v $(VIVADO) >/dev/null 2>&1; then \
	  printf '%b\n' "$(HINT_NO_VIVADO)"; \
	  echo "  [vivado-create] cible ignoree : rien n'a ete fait."; \
	elif [ -z "$(VIVADO_CREATE)" ]; then \
	  printf '%b\n' "$(HINT_NO_VIVADO)"; \
	  echo "  [vivado-create] script create_project.tcl introuvable."; \
	  echo "  Cherche dans : $(EDA_SEARCH_LIST)"; \
	  exit 1; \
	else \
	  echo "+ $(VIVADO) -mode batch -nojournal -nolog -source $(VIVADO_CREATE) $(VIVADO_ARGS)"; \
	  $(VIVADO) -mode batch -nojournal -nolog -source $(VIVADO_CREATE) $(VIVADO_ARGS); \
	fi

vivado-build: ## Synthese + implementation + bitstream (script build.tcl)
	@if ! command -v $(VIVADO) >/dev/null 2>&1; then \
	  printf '%b\n' "$(HINT_NO_VIVADO)"; \
	  echo "  [vivado-build] cible ignoree : rien n'a ete fait."; \
	elif [ -z "$(VIVADO_BUILD)" ]; then \
	  printf '%b\n' "$(HINT_NO_VIVADO)"; \
	  echo "  [vivado-build] script build.tcl introuvable."; \
	  echo "  Cherche dans : $(EDA_SEARCH_LIST)"; \
	  exit 1; \
	else \
	  echo "+ $(VIVADO) -mode batch -nojournal -nolog -source $(VIVADO_BUILD) $(VIVADO_ARGS)"; \
	  $(VIVADO) -mode batch -nojournal -nolog -source $(VIVADO_BUILD) $(VIVADO_ARGS); \
	fi

vivado-program: ## Programme le FPGA / la flash (script program.tcl, materiel requis)
	@if ! command -v $(VIVADO) >/dev/null 2>&1; then \
	  printf '%b\n' "$(HINT_NO_VIVADO)"; \
	  echo "  [vivado-program] cible ignoree : rien n'a ete fait."; \
	elif [ -z "$(VIVADO_PROGRAM)" ]; then \
	  printf '%b\n' "$(HINT_NO_VIVADO)"; \
	  echo "  [vivado-program] script program.tcl introuvable."; \
	  echo "  Cherche dans : $(EDA_SEARCH_LIST)"; \
	  exit 1; \
	else \
	  echo "+ $(VIVADO) -mode batch -nojournal -nolog -source $(VIVADO_PROGRAM) $(VIVADO_ARGS)"; \
	  $(VIVADO) -mode batch -nojournal -nolog -source $(VIVADO_PROGRAM) $(VIVADO_ARGS); \
	fi

# =============================================================================
#  Vitis (logiciel embarque) : vitis -s (>= 2023.2) ou xsct (<= 2023.1)
# =============================================================================

vitis-build: ## Compile le logiciel embarque (create_app.py via vitis -s, ou .tcl via xsct)
	@tool="$(VITIS)"; \
	if [ -z "$(VITIS_SCRIPT)" ]; then \
	  if ! command -v $(VITIS) >/dev/null 2>&1 && ! command -v $(XSCT) >/dev/null 2>&1; then \
	    printf '%b\n' "$(HINT_NO_VITIS)"; \
	  else \
	    echo "[vitis-build] script Vitis introuvable (create_app.py, create_app.tcl, vitis_build.py, vitis_build.tcl)."; \
	    echo "  Cherche dans : $(EDA_SEARCH_LIST)"; \
	    echo "  Surcharge possible : make vitis-build VITIS_SCRIPT=software/mon_script.py"; \
	  fi; \
	  echo "  [vitis-build] cible ignoree : rien n'a ete fait."; \
	  exit 0; \
	fi; \
	case "$(VITIS_SCRIPT)" in \
	  *.py) \
	    if ! command -v $(VITIS) >/dev/null 2>&1; then \
	      printf '%b\n' "$(HINT_NO_VITIS)"; \
	      echo "  [vitis-build] cible ignoree : rien n'a ete fait."; exit 0; \
	    fi; \
	    tool="$(VITIS) -s"; \
	    ;; \
	  *.tcl) \
	    if ! command -v $(XSCT) >/dev/null 2>&1; then \
	      printf '%b\n' "$(HINT_NO_VITIS)"; \
	      echo "  [vitis-build] cible ignoree : rien n'a ete fait."; exit 0; \
	    fi; \
	    tool="$(XSCT)"; \
	    ;; \
	esac; \
	echo "+ $$tool $(VITIS_SCRIPT) $(VITIS_ARGS)"; \
	$$tool $(VITIS_SCRIPT) $(VITIS_ARGS)

# =============================================================================
#  Menage : uniquement des artefacts generes (jamais une source, jamais un README)
# =============================================================================

clean: ## Supprime les artefacts generes (simulation, lint, traces) et rien d'autre
	@echo "[clean] artefacts generes uniquement (sources et README conserves)"
	@rm -rf "$(BUILD_DIR)" sim_build
	@find . -path ./.git -prune -o -type d -name sim_build -print -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./.git -prune -o -type d -name __pycache__ -print -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./.git -prune -o -type d -name work -print -exec rm -rf {} + 2>/dev/null || true
	@find . -path ./.git -prune -o -type f \
	    \( -name 'results.xml' -o -name '*.ghw' -o -name '*.vcd' -o -name '*.fst' \
	       -o -name '*.wdb' -o -name '*.asdb' -o -name '*.qwave.db' \
	       -o -name '*.cf' -o -name '*.o' -o -name '*.pyc' \) \
	    -print -exec rm -f {} + 2>/dev/null || true
	@echo "[clean] termine"
	@echo "[clean] (les sources rtl/, tb/, constraints/, scripts/, software/ et les"
	@echo "[clean]  README sont intacts ; verifiez avec git status)"

.PHONY: help check-tools lint sim sim-one waves tcl-check \
        vivado-create vivado-build vivado-program vitis-build clean
