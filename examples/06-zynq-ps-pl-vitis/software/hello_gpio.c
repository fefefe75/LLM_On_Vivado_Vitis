/*
 * hello_gpio.c - application baremetal Zynq : pilote le GPIO du PL cree dans
 * le block design (exemple 06). A compiler dans Vitis, pas ici.
 *
 * ATTENTION : ce code n'a PAS ete execute (aucune carte Zynq disponible).
 * Les identifiants (XPAR_GPIO_0_DEVICE_ID, adresses) viennent de xparameters.h,
 * genere par le BSP a partir de l'XSA : ne JAMAIS ecrire d'adresse en dur.
 */

#include <stdio.h>
#include "xparameters.h"     /* identifiants et adresses generes par le BSP */
#include "xgpio.h"
#include "xil_printf.h"
#include "sleep.h"

/* XPAR_AXI_GPIO_0_DEVICE_ID est defini dans xparameters.h.
 * Si le nom differe, le rechercher avec :
 *     grep -i gpio xparameters.h
 */
#ifndef XPAR_AXI_GPIO_0_DEVICE_ID
#define XPAR_AXI_GPIO_0_DEVICE_ID XPAR_GPIO_0_DEVICE_ID
#endif

int main(void)
{
    XGpio gpio;
    int status;
    u8 motif;
    int i;

    xil_printf("\r\n=== hello_gpio : PS -> PL ===\r\n");

    status = XGpio_Initialize(&gpio, XPAR_AXI_GPIO_0_DEVICE_ID);
    if (status != XST_SUCCESS) {
        xil_printf("ERREUR : XGpio_Initialize a echoue (%d)\r\n", status);
        return XST_FAILURE;
    }

    /* canal 1 = premiers 32 bits ; le GPIO fait 4 bits de large (voir le BD) */
    XGpio_SetDataDirection(&gpio, 1, 0x0);              /* 0 = sortie */

    /* chenillard : 4 LED, un motif different toutes les 500 ms */
    for (i = 0; i < 16; i++) {
        motif = (u8)(i & 0x0F);
        XGpio_DiscreteWrite(&gpio, 1, motif);
        xil_printf("motif = 0x%x\r\n", motif);
        sleep(1);                                        /* 1 s (sleep de Xilinx) */
    }

    XGpio_DiscreteWrite(&gpio, 1, 0x0);
    xil_printf("fin : LED eteintes\r\n");
    return XST_SUCCESS;
}
