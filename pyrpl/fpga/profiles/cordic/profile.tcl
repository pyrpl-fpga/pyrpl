# Three-IQ profile with a standalone two-input CORDIC in place of the IIR.
# PID input pre-filters remain disabled to preserve placement/timing margin.
set profile_id cordic
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/cordic/red_pitaya_dsp.v]
set synth_generics {PID_DERIVATIVE=0 PID_FILTERSTAGES=0 PID_DERIVATIVE_FILTER_SHIFT=4}
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
set post_route_phys_opt_passes 2
