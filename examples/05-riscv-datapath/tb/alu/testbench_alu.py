import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

@cocotb.test()
async def alu_basic_test(dut):
    """Test de base pour notre ALU 32 bits - Version Finale Fixe"""

    # 1. Horloge (10 ns)
    clock = Clock(dut.i_clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    # 2. Reset initial
    dut.i_rst.value = 1
    dut.i_opcode.value = 0x0
    dut.i_val_1.value = 0x0
    dut.i_val_2.value = 0x0
    
    await RisingEdge(dut.i_clk)
    await RisingEdge(dut.i_clk)
    
    # 3. Libération du Reset
    dut.i_rst.value = 0 
    await RisingEdge(dut.i_clk) 

    # =========================================================================
    # TEST 1 : L'Additionneur
    # =========================================================================
    dut._log.info("--- Début Test 1 : Addition standard ---")
    
    dut.i_opcode.value = 0b10      # Opcode de l'addition
    dut.i_val_1.value = 0x00000000F       # 15
    dut.i_val_2.value = 0x00000001E      # 30
    
    # Attente des cycles pour le pipeline
    await RisingEdge(dut.i_clk) 
    await RisingEdge(dut.i_clk) 
    await RisingEdge(dut.i_clk)
    await RisingEdge(dut.i_clk)
    await RisingEdge(dut.i_clk)

    valeur_entiere = dut.o_data.value
    valeur_hexa = hex(valeur_entiere) # Donnera quelque chose comme '0x2d' ou '0x0'
    
    dut._log.info(f"Sortie Data lue en Hexa : {valeur_hexa}")
    
    # Comparaison directe en chaîne hexa (hex(45) donne '0x2d')
    assert valeur_hexa == "0x2d", f"Erreur ! Reçu {valeur_hexa} au lieu de 0x2d"
    dut._log.info("TEST 1 REUSSI ! 🚀")