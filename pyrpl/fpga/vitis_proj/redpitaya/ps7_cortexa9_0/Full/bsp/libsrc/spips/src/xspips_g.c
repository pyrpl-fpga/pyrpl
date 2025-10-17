#include "xspips.h"

XSpiPs_Config XSpiPs_ConfigTable[] __attribute__ ((section (".drvcfg_sec"))) = {

	{
		"xlnx,zynq-spi-r1p6", /* compatible */
		0xe0007000, /* reg */
		0x9ef21b0, /* xlnx,spi-clk-freq-hz */
		0x4031, /* interrupts */
		0xf8f01000 /* interrupt-parent */
	},
	 {
		 NULL
	}
};