# Three-IQ profile with a standalone CORDIC plus CORDICs in IQ0 and IQ1.
# PID input pre-filters remain disabled to preserve placement/timing margin.
set profile_id cordic
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/cordic/red_pitaya_dsp.v]
set synth_generics {PID_DERIVATIVE=0 PID_FILTERSTAGES=0 PID_DERIVATIVE_FILTER_SHIFT=4}
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
set post_route_phys_opt_passes 2
# Vivado 2024.2 can terminate without an error while running parallel
# post-route AggressiveExplore on this dense profile.
set post_route_phys_opt_max_threads 1
