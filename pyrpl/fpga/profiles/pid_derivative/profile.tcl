# Full-featured PID profile: four input-filter stages and a band-limited
# derivative on all three PIDs.  Keep the no-IIR DSP topology but use the
# current shared PID block rather than no_iir's compatibility snapshot.
set profile_id pid_derivative
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/no_iir/red_pitaya_dsp.v]
set synth_generics {PID_DERIVATIVE=1 PID_FILTERSTAGES=4 PID_DERIVATIVE_FILTER_SHIFT=4}
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
# The three derivative DSP paths and input filters may need a second pass.
set post_route_phys_opt_passes 2
# Vivado 2024.2 can terminate without an error while running parallel
# post-route AggressiveExplore on this dense profile.
set post_route_phys_opt_max_threads 1
