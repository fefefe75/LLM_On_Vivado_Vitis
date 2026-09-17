# =============================================================================
# Generation du programme RISC-V (examples/05-riscv-datapath).
#
# main.c est le programme C joue par le datapath dans le testbench
# tb/riscv/testbench_datapath.py. Le fichier main.bin produit ici est un
# ARTEFACT DERIVE : il n'est pas committe (il depend du compilateur croise).
#
#   make            genere main.elf + main.bin (chaine croisee detectee)
#   make clean      supprime main.elf et main.bin
#
# Deux chaines croisees sont acceptees, par ordre de preference :
#   1. riscv-none-embed-gcc     (xPack, bare-metal, utilisee a l'origine)
#   2. riscv64-unknown-elf-gcc  (GNU, bare-metal RV32)
# Le compilateur "riscv64-linux-gnu-gcc" (chaine Linux, presente sur Fedora)
# fonctionne aussi avec -nostdlib : voir la cible gnu-linux ci-dessous.
#
# L'adresse de chargement 0x100f8 doit rester identique a START_ADDRESS dans
# tb/riscv/testbench_datapath.py, sinon le testbench injecte des NOP.
# =============================================================================

TEXT_ADDR ?= 0x100f8
SRC       ?= main.c
OPT       ?= -O0

CC_ENV := $(shell command -v riscv-none-embed-gcc 2>/dev/null)
CC_GNU := $(shell command -v riscv64-unknown-elf-gcc 2>/dev/null)
CC_LNX := $(shell command -v riscv64-linux-gnu-gcc 2>/dev/null)

ifeq ($(CC_ENV),)
  ifeq ($(CC_GNU),)
    CC      := $(CC_LNX)
    TARGET  := linux
  else
    CC      := $(CC_GNU)
    TARGET  := gnu
  endif
else
  CC     := $(CC_ENV)
  TARGET := xpack
endif

OBJCOPY := $(patsubst %gcc,%objcopy,$(CC))

# --build-id=none est indispensable avec la chaine Linux : sinon ld place
# .note.gnu.build-id sous 0x100f8 et refuse la section .text.
TOOLCHAIN_FLAGS := -march=rv32i -mabi=ilp32 -nostdlib -nostartfiles -e main
ifeq ($(TARGET),gnu)
  TOOLCHAIN_FLAGS += -mno-relax
endif
ifeq ($(TARGET),linux)
  TOOLCHAIN_FLAGS += -mno-relax -Wl,--build-id=none
endif

CFLAGS := $(OPT) $(TOOLCHAIN_FLAGS) -Wl,-Ttext=$(TEXT_ADDR)

all: main.bin

main.bin: main.elf
	$(OBJCOPY) -O binary $< $@
	@echo "main.bin genere : `wc -c < $@` octets"

main.elf: $(SRC)
	@test -n "$(CC)" || { \
	  echo "ERREUR : aucune chaine croisee RISC-V trouvee."; \
	  echo "Installer riscv-none-embed-gcc ou riscv64-unknown-elf-gcc,"; \
	  echo "ou bien riscv64-linux-gnu-gcc (Fedora : dnf install gcc-riscv64-linux-gnu)."; \
	  exit 1; }
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f main.elf main.bin

.PHONY: all clean
