# Additional clean files
cmake_minimum_required(VERSION 3.16)

if("${CONFIG}" STREQUAL "" OR "${CONFIG}" STREQUAL "")
  file(REMOVE_RECURSE
  "C:\\Users\\croquette\\GitHub\\pyrpl\\pyrpl\\fpga\\vitis_proj\\redpitaya\\ps7_cortexa9_0\\Full\\bsp\\include\\sleep.h"
  "C:\\Users\\croquette\\GitHub\\pyrpl\\pyrpl\\fpga\\vitis_proj\\redpitaya\\ps7_cortexa9_0\\Full\\bsp\\include\\xiltimer.h"
  "C:\\Users\\croquette\\GitHub\\pyrpl\\pyrpl\\fpga\\vitis_proj\\redpitaya\\ps7_cortexa9_0\\Full\\bsp\\include\\xtimer_config.h"
  "C:\\Users\\croquette\\GitHub\\pyrpl\\pyrpl\\fpga\\vitis_proj\\redpitaya\\ps7_cortexa9_0\\Full\\bsp\\lib\\libxiltimer.a"
  )
endif()
