"""
Testbench cocotb 2.x du datapath RV32I (examples/05-riscv-datapath).

Ce test n'est PAS autonome : il a besoin du programme RISC-V compile
(software/main.bin). Ce binaire n'est pas committe dans le depot (fichier
derive, dependant du compilateur croise). Voir README.md, section
"Programme RISC-V" : sans lui, le test ECHOUE avec un message explicite
plutot que de simuler un programme inexistant.

Portage cocotb 2.x : COCOTB_TOPLEVEL / COCOTB_TEST_MODULES cote Makefile, et
lecture du binaire via la variable d'environnement RISCV_BIN (chemin absolu
exporte par le Makefile, car cocotb execute le test depuis sim_build/).
"""

import os

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

# Adresse de chargement par defaut : le binaire d'origine est lie a 0x100f8
# (voir objdump). On fait comme si cette adresse correspondait a l'index 0 du
# tableau d'instructions.
START_ADDRESS = 0x100F8

MISSING_BIN_MSG = """
================================================================================
PROGRAMME RISC-V ABSENT : {path}

Ce testbench charge le code machine produit a partir de software/main.c
(adresse de chargement 0x{start:x}). Le fichier .bin n'est pas committe
(fichier derive) : il doit etre genere localement.

Commandes de generation (voir software/Makefile et README.md) :

  # 1. chaine croisee bare-metal xPack
  riscv-none-embed-gcc -march=rv32i -mabi=ilp32 -O1 -nostdlib -nostartfiles \\
      -Wl,-Ttext=0x{start:x} -o main.elf main.c
  riscv-none-embed-objcopy -O binary main.elf main.bin

  # 2. chaine croisee GNU
  riscv64-unknown-elf-gcc -march=rv32i -mabi=ilp32 -mno-relax -O1 \\
      -nostdlib -nostartfiles -Wl,-Ttext=0x{start:x} -o main.elf main.c
  riscv64-unknown-elf-objcopy -O binary main.elf main.bin

Le test est marque en ECHEC (et non simule a vide) tant que le binaire est
absent : voir "Ce qui est verifie / ce qui ne l'est pas" dans README.md.
================================================================================
"""


def resolve_bin_path():
    """Trouve le .bin : variable RISCV_BIN (Makefile) puis replis classiques."""
    candidates = []
    env = os.environ.get("RISCV_BIN")
    if env:
        candidates.append(env)
    # Replis si le test est lance hors du Makefile
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(here, "..", "..", "software", "main.bin"))
    candidates.append(os.path.join("software", "main.bin"))
    for cand in candidates:
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


# 1. Fonction pour charger le binaire compile
def load_binary(filename):
    instructions = {}
    with open(filename, "rb") as f:
        bytes_data = f.read()

    # On regroupe les octets 4 par 4 (32 bits)
    # Le RISC-V genere est en Little-Endian (octets de poids faible en premier)
    for i in range(0, len(bytes_data), 4):
        word = int.from_bytes(bytes_data[i : i + 4], byteorder="little")
        # On stocke l'instruction a son adresse memoire relative (0, 4, 8, 12...)
        instructions[i] = word
    return instructions


@cocotb.test()
async def test_datapath_c_code(dut):
    """Test du Datapath avec le programme main.bin compile"""

    # 2. Chargement du programme
    # Le .bin est indispensable : on echoue proprement s'il est absent.
    bin_path = resolve_bin_path()
    if bin_path is None:
        raise FileNotFoundError(
            MISSING_BIN_MSG.format(
                path=os.environ.get("RISCV_BIN", "software/main.bin"),
                start=START_ADDRESS,
            )
        )
    dut._log.info(f"Programme RISC-V charge depuis : {bin_path}")
    program = load_binary(bin_path)

    # 3. Demarrage de l'horloge (periode de 10 ns -> 100 MHz)
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())

    # 4. Initialisation des signaux et Reset
    dut.i_rst.value = 1
    dut.i_instruction.value = 0
    dut.i_ram_data.value = 0
    dut.i_pc.value = START_ADDRESS
    await Timer(20, unit="ns")
    dut.i_rst.value = 0
    await FallingEdge(dut.i_clk)

    # 5. Boucle d'execution du processeur
    # On fait tourner la simulation sur 50 cycles pour voir le if/else s'executer
    for cycle in range(50):
        # Permet de lire le PC meme s'il y a des 'U' ou 'X' au demarrage
        # (cocotb 2.x : str(logic_array) remplace le getter .binstr, deprecie)
        current_pc_binstr = str(dut.i_pc.value).lower()
        if "x" in current_pc_binstr or "u" in current_pc_binstr:
            current_pc = START_ADDRESS
        else:
            current_pc = dut.i_pc.value.to_unsigned()
        binary_offset = current_pc - START_ADDRESS

        # Injection de l'instruction
        if binary_offset in program:
            current_instruction = program[binary_offset]
            dut.i_instruction.value = current_instruction
        else:
            current_instruction = 0x00000013  # NOP
            dut.i_instruction.value = current_instruction

        # Detection de l'opcode pour savoir si l'ALU va travailler
        opcode = current_instruction & 0x7F

        # Si c'est une operation R (0x33), I (0x13) ou un branchement (0x63)
        # l'ALU a besoin de ses cycles de pipeline pour le flag ou le resultat.
        if opcode in [0x33, 0x13, 0x63, 0x03, 0x23]:
            dut._log.info(
                "--- Instruction necessitant l'ALU detectee. Attente de 5 cycles ---"
            )

            for alu_cycle in range(5):
                # Si le CPU ecrit en RAM, cela se produit generalement au dernier cycle
                if alu_cycle == 4 and dut.o_mem_write.value == 1:
                    addr = dut.o_ram_addr.value.to_unsigned()
                    data = dut.o_ram_data.value.to_unsigned()
                    dut._log.info(f"[RAM WRITE] Ecriture de {data} a {hex(addr)}")

                await RisingEdge(dut.i_clk)  # On avance d'un cycle d'horloge
        else:
            # Pour les instructions immediates simples ou hors ALU (si applicable)
            await RisingEdge(dut.i_clk)

        # On affiche le log une fois le calcul de l'ALU stabilise
        dut._log.info(
            f"PC actuel: {hex(current_pc)} | Instruction: {hex(current_instruction)}"
        )

        # L'ALU a fini : o_next_pc est maintenant stable et valide
        await Timer(1, unit="ns")

        # On applique le prochain PC pour le cycle suivant
        dut.i_pc.value = dut.o_next_pc.value

    dut._log.info("Fin de la simulation Cocotb !")
