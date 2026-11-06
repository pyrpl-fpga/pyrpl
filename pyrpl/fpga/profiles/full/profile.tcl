# All optional DSP features in one image, for Zynq 7020 boards only:
#  - 3 PIDs with four input-filter stages and a band-limited derivative
#  - pipelined 32-bit / 14-stage IIR
#  - 3 IQs with VCO inputs, IQ0/IQ1 with integrated CORDICs
#  - standalone CORDIC (slot 16) and two-input arithmetic module (slot 17),
#    whose registers live in system-bus region 5 (0x40500000)
set profile_id full
set supported_fpga_parts {z7020}
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/full/red_pitaya_dsp.v]
set synth_generics {PID_DERIVATIVE=1 PID_FILTERSTAGES=4 PID_DERIVATIVE_FILTER_SHIFT=4 IQ_VCO=1 ARITHMETIC=1 DSP_HIGH_SLOTS=1}
set place_directive ExtraTimingOpt
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
set post_route_phys_opt_passes 2
# Vivado 2024.2 can terminate without an error while running parallel
# post-route AggressiveExplore on dense profiles.
set post_route_phys_opt_max_threads 1
