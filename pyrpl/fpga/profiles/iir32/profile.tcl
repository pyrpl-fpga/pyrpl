# Pipelined 32-bit/14-stage IIR profile with PID2 omitted and all three IQs kept.
set profile_id iir32
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/iir32/red_pitaya_dsp.v]
set synth_generics {PID_DERIVATIVE=0 PID_FILTERSTAGES=0 PID_DERIVATIVE_FILTER_SHIFT=4}
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
set post_route_phys_opt_passes 1
