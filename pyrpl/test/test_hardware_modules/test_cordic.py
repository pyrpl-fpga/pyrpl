import time

import numpy as np
import pytest

from pyrpl.redpitaya_client import DummyClient


@pytest.mark.requires_fpga("cordic")
def test_cordic_quadrants_and_independent_inputs(hardware_session):
    rp = hardware_session.rp
    if isinstance(rp.client, DummyClient):
        pytest.skip("requires real FPGA signal processing")
    cordic = rp.cordic
    asg_i = rp.asg0
    asg_q = rp.asg1
    original_cordic = cordic.setup_attributes.copy()
    original_i = asg_i.setup_attributes.copy()
    original_q = asg_q.setup_attributes.copy()

    def set_vector(i_value, q_value):
        asg_i.offset = i_value
        asg_q.offset = q_value
        # Allow more than the ten-cycle CORDIC latency plus network latency.
        time.sleep(0.01)
        return cordic.current_output_signal

    try:
        assert cordic.abi_version in (0x434F5201, 0x434F5202)
        asg_i.setup(amplitude=0, offset=0.25, waveform="dc", output_direct="off")
        asg_q.setup(amplitude=0, offset=0, waveform="dc", output_direct="off")
        cordic.setup(
            input_pair="independent",
            input="asg0",
            input_q="asg1",
            output_direct="off",
        )

        # Compare wrapped phase because the hardware intentionally unwraps
        # successive samples with its two-bit turn counter.
        for i_value, q_value, expected_turn in (
            (0.25, 0, 0.0),
            (0.25, 0.25, 0.125),
            (0, 0.25, 0.25),
            (-0.25, 0, 0.5),
            (0, -0.25, 0.75),
        ):
            measured = set_vector(i_value, q_value) % 1.0
            assert measured == pytest.approx(expected_turn, abs=2e-3)

        held_phase = cordic.current_output_signal
        assert set_vector(0, 0) == pytest.approx(held_phase, abs=1 / 4096)
    finally:
        cordic.setup_attributes = original_cordic
        asg_i.setup_attributes = original_i
        asg_q.setup_attributes = original_q


@pytest.mark.requires_fpga("iq_cordic")
def test_cordic_direct_iq_pairs(hardware_session):
    """Verify that IQ0 and IQ1 each feed their own integrated CORDIC.

    Both IQ modules demodulate the same DC value with a static oscillator. For
    each module, only that IQ receives a 90-degree phase step. A
    quarter-turn response from its phase register, while the other stays
    fixed, proves that the two CORDIC datapaths are independent.
    """
    rp = hardware_session.rp
    if isinstance(rp.client, DummyClient):
        pytest.skip("requires real FPGA signal processing")
    source = rp.asg0
    iqs = [rp.iq0, rp.iq1]
    original_source = source.setup_attributes.copy()
    original_iqs = [iq.setup_attributes.copy() for iq in iqs]

    try:
        assert all(iq.cordic_abi_version == 0x434F5203 for iq in iqs)
        source.setup(
            waveform="dc",
            amplitude=0,
            offset=0.4,
            output_direct="off",
            trigger_source="immediately",
        )
        for iq in iqs:
            iq.setup(
                input="asg0",
                frequency=0,
                trigger_source="immediately",
                bandwidth=0,
                quadrature_factor=10,
                output_signal="cordic",
                gain=0,
                amplitude=0,
                phase=0,
                output_direct="off",
            )
        iqs[0].synchronize_iqs()
        time.sleep(1e-3)

        phase_steps = []
        for index, iq in enumerate(iqs):
            phase_0 = iq.cordic_phase
            other_phase_0 = iqs[1 - index].cordic_phase
            iq.phase = 90
            time.sleep(1e-3)
            phase_90 = iq.cordic_phase
            other_phase_90 = iqs[1 - index].cordic_phase
            phase_steps.append(
                np.angle(np.exp(2j * np.pi * (phase_90 - phase_0))) / (2 * np.pi)
            )
            other_step = np.angle(
                np.exp(2j * np.pi * (other_phase_90 - other_phase_0))
            ) / (2 * np.pi)
            assert abs(other_step) < 5e-3
            iq.phase = 0
            time.sleep(1e-3)

        phase_steps = np.asarray(phase_steps)
        assert np.all(np.abs(np.abs(phase_steps) - 0.25) < 5e-3), phase_steps
    finally:
        source.setup_attributes = original_source
        for iq, setup in zip(iqs, original_iqs):
            iq.setup_attributes = setup


@pytest.mark.requires_fpga("cordic")
def test_cordic_dynamic_latency(hardware_session):
    """Measure the CORDIC pipeline latency using two simultaneous scope traces.

    ASG0 supplies a constant positive I value while ASG1 alternates Q between
    positive and negative values.  The expected CORDIC phase therefore
    alternates around zero with the same rising edges as Q, delayed only by
    the CORDIC pipeline.  Capturing Q and the phase output in the same scope
    acquisition removes network timing and trigger alignment from the
    measurement.  At scope decimation 1, one trace sample is one 125 MHz FPGA
    clock cycle.
    """
    rp = hardware_session.rp
    if isinstance(rp.client, DummyClient):
        pytest.skip("requires real FPGA signal processing")
    cordic = rp.cordic
    asg_i = rp.asg0
    asg_q = rp.asg1
    scope = rp.scope
    original_cordic = cordic.setup_attributes.copy()
    original_i = asg_i.setup_attributes.copy()
    original_q = asg_q.setup_attributes.copy()
    original_scope = scope.setup_attributes.copy()
    edge_search_margin_cycles = 2
    allowed_latency_error_cycles = 1
    minimum_matched_edges = 10

    def rising_edges(values):
        """Return indices of the first samples at or above the mid-level."""
        low, high = np.percentile(values, [10, 90])
        threshold = 0.5 * (low + high)
        # A true element at index n describes the transition between samples
        # n and n + 1.  Report n + 1, the first sample on the new/high side of
        # the edge, for both traces so their index difference is the latency.
        return np.flatnonzero((values[:-1] < threshold) & (values[1:] >= threshold)) + 1

    try:
        asg_i.setup(
            waveform="dc",
            amplitude=0,
            offset=0.25,
            output_direct="off",
            trigger_source="immediately",
        )
        asg_q.setup(
            waveform="square",
            frequency=1e6,
            amplitude=0.125,
            offset=0,
            output_direct="off",
            trigger_source="immediately",
        )
        cordic.setup(
            input_pair="independent",
            input="asg0",
            input_q="asg1",
            output_direct="off",
        )
        scope.setup(
            input1="asg1",
            input2="cordic",
            duration=scope.durations[0],
            trigger_source="immediately",
            trace_average=1,
            average=False,
        )
        q_trace, phase_trace = scope.single(timeout=4)

        q_edges = rising_edges(q_trace)
        phase_edges = rising_edges(phase_trace)
        measured_lags = []
        for q_edge in q_edges:
            # Search slightly more widely than the final one-cycle tolerance.
            # This makes a real latency mismatch visible in the assertion and
            # its diagnostic list instead of silently treating every edge as
            # unmatched.  Centering the window on the expected latency also
            # prevents an unrelated earlier edge from being paired with Q.
            expected_phase_edge = q_edge + cordic._delay
            candidates = phase_edges[
                (phase_edges >= expected_phase_edge - edge_search_margin_cycles)
                & (phase_edges <= expected_phase_edge + edge_search_margin_cycles)
            ]
            if len(candidates):
                measured_lags.append(int(candidates[0] - q_edge))

        # Use several periods so a single acquisition-boundary glitch cannot
        # make a coincidental edge pair look like a valid latency measurement.
        assert len(measured_lags) >= minimum_matched_edges, (
            f"Only {len(measured_lags)} CORDIC edges could be matched; "
            f"expected at least {minimum_matched_edges}"
        )
        assert np.median(measured_lags) == pytest.approx(
            cordic._delay, abs=allowed_latency_error_cycles
        ), f"CORDIC edge lags were {measured_lags}; expected {cordic._delay} cycles"
        assert (
            np.max(np.abs(np.asarray(measured_lags) - cordic._delay))
            <= allowed_latency_error_cycles
        ), f"CORDIC edge lags were {measured_lags}; expected {cordic._delay} cycles"
    finally:
        scope.stop()
        scope.setup_attributes = original_scope
        cordic.setup_attributes = original_cordic
        asg_i.setup_attributes = original_i
        asg_q.setup_attributes = original_q
