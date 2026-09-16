# Timing-optimized production profile.
set profile_id default
set rtl_overrides [dict create]
set place_directive ExtraNetDelay_high
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
set post_route_phys_opt_passes 1
