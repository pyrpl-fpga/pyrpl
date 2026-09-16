# Original datapaths: 32-bit/14-stage IIR and four PID input filters.
set profile_id legacy
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_legacy/red_pitaya_dsp.v \
    red_pitaya_iir_block.v rtl_legacy/red_pitaya_iir_block.v \
    red_pitaya_iq_modulator_block.v rtl_legacy/red_pitaya_iq_modulator_block.v \
    red_pitaya_pid_block.v rtl_legacy/red_pitaya_pid_block.v \
    red_pitaya_pwm.sv rtl_legacy/red_pitaya_pwm.sv]
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
# The legacy unpipelined datapaths remain several nanoseconds short of timing;
# this expensive pass cannot close them and needlessly prolongs compatibility builds.
set post_route_phys_opt_passes 0
