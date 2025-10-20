#include "xsysmon.h"

XSysMon_Config XSysMon_ConfigTable[] __attribute__ ((section (".drvcfg_sec"))) = {

	{
		"xlnx,xadc-wiz-3.3", /* compatible */
		0x83c00000, /* reg */
		0x1, /* xlnx,include-intr */
		0x0 /* xlnx,ip-type */
	},
	 {
		 NULL
	}
};