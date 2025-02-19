################################################################################
# XSCT / HSI tcl script for building pyrpl device tree blob
#
# Usage:
# xsct xsct_hsi_dtb.tcl
################################################################################


set prj_name pyrpl

set path_sdk sdk

hsi open_hw_design $path_sdk/red_pitaya.xsa

set ver 2023.2
foreach item $argv {
  puts "Input arfguments: $argv"
  if {[lsearch -all $item "*DTG_VER*"] >= 0} {
    set param [split $item "="]
    if {[lindex $param 1] ne ""} {
      set ver [lindex $param 1]
    }
  }
}
puts "DTG version: $ver"

hsi set_repo_path ../../../device-tree-xlnx-xilinx-v$ver/

hsi create_sw_design device-tree -os device_tree -proc ps7_cortexa9_0

hsi set_property CONFIG.kernel_version $ver [hsi get_os]
hsi set_property CONFIG.dt_overlay true [hsi get_os]

hsi generate_target -dir $path_sdk/dts

exit
