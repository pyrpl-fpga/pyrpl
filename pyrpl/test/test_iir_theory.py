import numpy as np
import pytest

from pyrpl.hardware_modules.iir.iir import IIR, IirListProperty
from pyrpl.hardware_modules.iir.iir_theory import IirFilter, residues_discrete


def _evaluate_zpk_q(zeros, poles, gain, q):
    numerator = np.prod(1.0 - zeros[None, :] * q[:, None], axis=1)
    denominator = np.prod(1.0 - poles[None, :] * q[:, None], axis=1)
    return gain * numerator / denominator


def _evaluate_residues_q(residues, poles, direct, q):
    response = np.full(len(q), direct, dtype=np.complex128)
    for residue, pole in zip(residues, poles):
        response += residue / (1.0 - pole * q)
    return response


@pytest.mark.parametrize(
    ("zeros", "poles"),
    [
        # Equal degree exercises the direct term.
        (
            np.array([0.8 + 0.1j, 0.8 - 0.1j]),
            np.array([0.9 + 0.2j, 0.9 - 0.2j]),
        ),
        # Relative degree three exercises the residue scaling that ordinary
        # polynomial residues do not provide.
        (
            np.array([0.7 + 0.1j, 0.7 - 0.1j]),
            np.array([0.8, 0.85, 0.9, 0.92, 0.95]),
        ),
    ],
)
def test_discrete_residues_reconstruct_z_inverse_transfer_function(zeros, poles):
    gain = 0.37
    q = np.exp(-1j * np.linspace(0.01, 2.8, 101))
    residues, direct = residues_discrete(zeros, poles, gain)

    expected = _evaluate_zpk_q(zeros, poles, gain, q)
    actual = _evaluate_residues_q(residues, poles, direct, q)
    np.testing.assert_allclose(actual, expected, rtol=1e-9, atol=1e-10)


def test_medium_filter_is_representable_and_has_requested_dc_gain():
    filt = IirFilter(
        zeros=[4e4j - 300, 2e5j - 3000],
        poles=[5e4j - 300, 1e5j - 3000, 1e6j - 30000, -5e5],
        gain=1.0,
        loops=None,
        minloops=4,
        iirstages=8,
        totalbits=24,
        shiftbits=21,
        inputfilter=0,
        moduledelay=0,
    )

    assert len(filt.coefficients) == 4
    assert np.max(np.abs(filt.coefficients)) < 2.0
    response_at_dc = filt.tf_coefficients_numpy(frequencies=np.array([0.0]))
    np.testing.assert_allclose(response_at_dc, [1.0], rtol=1e-9, atol=1e-9)


def test_discrete_diagnostic_matches_generated_coefficients():
    frequencies = np.geomspace(1e3, 1e6, 101)
    filt = IirFilter(
        zeros=[1e5j - 3e3],
        poles=[5e4j - 3e3],
        gain=0.5,
        loops=8,
        minloops=4,
        iirstages=8,
        totalbits=24,
        shiftbits=21,
        frequencies=frequencies,
        inputfilter=0,
        moduledelay=0,
    )

    expected = filt.tf_coefficients_numpy(frequencies=frequencies)
    expected *= filt.tf_inputfilter(frequencies=frequencies)
    np.testing.assert_allclose(filt.tf_discrete(), expected, rtol=1e-9, atol=1e-9)
    # The continuous diagnostic used to fail because rp_continuous was never set.
    assert np.all(np.isfinite(filt.tf_partialfraction()))


def test_finite_precision_rejects_unrepresentable_coefficient():
    filt = IirFilter([], [], 1.0, totalbits=24, shiftbits=21)
    with pytest.raises(ValueError, match="outside the Q"):
        filt.finiteprecision(np.array([[4.0, 0.0, 0.0, 1.0, 0.0, 0.0]]))


def test_fixed_point_encoding_rejects_wraparound_and_round_trips_24_bits():
    iir = object.__new__(IIR)
    hi, lo = iir._from_double(-1.25, bitlength=24, shift=21)
    assert iir._to_double(hi, lo, bitlength=24, shift=21) == -1.25
    with pytest.raises(ValueError, match="does not fit"):
        iir._from_double(4.0, bitlength=24, shift=21)


class _IntegerSimulator:
    _IIRBITS = 24
    _IIRSHIFT = 21
    coefficients = np.array([[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]])
    _product_sat = IIR._product_sat
    _saturate = IIR._saturate


def test_integer_simulator_unity_and_signed_saturation():
    simulator = _IntegerSimulator()
    samples = np.array([-8192, -123, 0, 456, 8191], dtype=np.int64)
    result = IIR.simulate_filter_int(simulator, samples)
    np.testing.assert_array_equal(result, samples)
    assert simulator._saturate(200, bits=8) == 127
    assert simulator._saturate(-200, bits=8) == -128


@pytest.mark.parametrize("setup_was_ongoing", [False, True])
def test_iir_list_setter_preserves_outer_setup_state(setup_was_ongoing):
    class DummyIir:
        _setup_ongoing = setup_was_ongoing
        complex_zeros = []
        real_zeros = []

    attribute = IirListProperty()
    attribute.name = "zeros"
    dummy = DummyIir()
    attribute.set_value(dummy, [1e3j - 10, -20])

    assert dummy._setup_ongoing is setup_was_ongoing
    assert dummy.complex_zeros == [1e3j - 10]
    assert dummy.real_zeros == [-20]
