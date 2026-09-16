# Three-IQ profile with the original four-stage PID input pre-filters and no IIR.
set profile_id no_iir
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/no_iir/red_pitaya_dsp.v \
    red_pitaya_pid_block.v rtl_profiles/no_iir/red_pitaya_pid_block.v]
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
# This profile closed a -0.012 ns setup violation only after a second pass.
set post_route_phys_opt_passes 2
