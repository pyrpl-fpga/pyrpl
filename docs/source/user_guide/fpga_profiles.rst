FPGA profiles and hardware tests
********************************

An FPGA profile binds a bitstream to its Python hardware contract: available
modules, capabilities, register-map constants, and timing metadata. The
``default`` profile remains the normal production profile. Specialized images
such as ``legacy``, ``no_iir``, ``iir32``, ``cordic``, and the experimental
``pid_derivative`` profile must be selected explicitly. The ``cordic`` profile
replaces the IIR with a standalone two-input phase detector and disables the
PID input prefilters.

Selecting a profile
===================

Applications can select a published profile directly::

    from pyrpl import Pyrpl

    pyrpl = Pyrpl(
        hostname="169.254.101.38",
        fpga_profile="pid_derivative",
        reloadfpga="auto",
    )

With ``reloadfpga="auto"``, PyRPL compares the requested profile with the
per-boot marker written after a successful load. It reloads the packaged image
when the marker is absent or names another profile. Startup then validates
hardware constants against the selected manifest.

External PID sample-and-hold
============================

In the ``default`` profile, each PID can use a synchronized expansion pin as
an active-high enable. For example::

    rp.pid0.pause_source = "external"
    rp.pid0.pause_pin = "P0"

The PID runs while P0 is high. While P0 is low, its controller state and
complete output are held rather than reset; they resume when P0 returns high.
Profile-specific input prefilters continue tracking the input while held.
Set ``pause_source="off"`` to disable this external control. The existing
``paused`` and ``pause_gains`` properties remain available independently.
The selected expansion pin should be configured as an input through ``rp.hk``.

Pytest profile behavior
=======================

Hardware pytest sessions use one FPGA profile at a time. The session fixture
currently passes ``reloadfpga=True``, so it loads the selected packaged image
at the start of every test process. It does not merely inspect the previously
loaded image and adapt to it.

The ``REDPITAYA_FPGA_PROFILE`` environment variable selects the profile. For
PowerShell::

    $env:REDPITAYA_HOSTNAME = "169.254.101.38"
    $env:REDPITAYA_FPGA_PROFILE = "pid_derivative"
    pytest pyrpl/test/test_hardware_modules/test_pid_na_iq.py

For ``cmd.exe``::

    set REDPITAYA_HOSTNAME=169.254.101.38
    set REDPITAYA_FPGA_PROFILE=pid_derivative
    pytest pyrpl\test\test_hardware_modules\test_pid_na_iq.py

There must be no spaces around ``=`` in the ``cmd.exe`` form.

Tests declare optional hardware requirements with a marker such as::

    @pytest.mark.requires_fpga("pid_derivative")

After loading the selected profile, an autouse fixture compares these markers
with the capabilities in its manifest. Tests with missing capabilities are
reported as skipped; unmarked tests run normally. For example, run only the
derivative tests with::

    pytest pyrpl/test/test_hardware_modules/test_pid_na_iq.py -k pid_derivative

Because the connection and FPGA profile are session-scoped, testing several
profiles requires separate pytest invocations. PowerShell can run them in
sequence::

    foreach ($profile in @("default", "legacy", "no_iir", "iir32", "pid_derivative", "cordic")) {
        $env:REDPITAYA_FPGA_PROFILE = $profile
        pytest pyrpl/test/test_hardware_modules
    }

Development builds
==================

Only profiles staged under ``pyrpl/fpga/bitstreams`` are selectable at
runtime. After compiling a development profile, create its manifest and stage
its binary before testing::

    cd pyrpl/fpga
    make_bin.bat pid_derivative
    python publish_fpga_profile.py pid_derivative

For the CORDIC profile, use ``make_bin.bat cordic`` and then
``python publish_fpga_profile.py cordic``. Once loaded, ``rp.cordic.input``
selects I and ``rp.cordic.input_q`` independently selects Q. The routed output
is ``atan2(Q, I)`` expressed in turns.

Publishing makes the build selectable and records checksums. The staged
bitstream should still pass timing and hardware tests before its generated
artifacts are committed.

Result labels
=============

Frequency-response artifacts use the selected profile ID by default. Override
only their directory label with, for example::

    $env:PYRPL_BITSTREAM_LABEL = "pid_derivative_candidate_1"

``PYRPL_BITSTREAM_LABEL`` does not select, load, or identify the FPGA profile.
Use ``REDPITAYA_FPGA_PROFILE`` for that purpose.

Derivative cutoff cache
=======================

The ``pid_derivative`` Python model numerically calculates the exact discrete
3 dB roll-off frequency associated with each shift-filter setting. The helper uses
``@lru_cache(maxsize=None)`` so a shift value is calculated only once in a
Python process. Although the cache has no eviction limit, the hardware exposes
only 24 shift values, so it contains at most 24 practical entries. The cache
stores calculated Python values only; it never represents or replaces FPGA
state.
