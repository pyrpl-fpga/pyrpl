import contextlib
import logging
import time

import numpy as np
import pytest
from qtpy import QtCore, QtTest, QtWidgets

import pyrpl


def _pump_events(duration_s=0.2):
    app = QtWidgets.QApplication.instance()
    end = time.monotonic() + duration_s
    while time.monotonic() < end:
        if app is not None:
            app.processEvents(QtCore.QEventLoop.AllEvents, 50)
        time.sleep(0.005)


def _wait_until(predicate, timeout_s=5.0):
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        if predicate():
            return True
        _pump_events(0.05)
    return predicate()


def _click_button(button):
    QtCore.QTimer.singleShot(0, lambda: QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton))
    _pump_events(0.2)


def _count_calibration_success(records):
    return sum(
        1
        for rec in records
        if rec.name == "pyrpl.modules" and "calibration successful" in rec.getMessage()
    )


@pytest.fixture
def pyrpl_instance():
    p = pyrpl.Pyrpl(config="", hostname="_FAKE_")
    try:
        yield p
    finally:
        # Keep teardown best-effort to avoid masking test assertions with
        # unrelated config-file lock issues.
        with contextlib.suppress(Exception):
            p._clear()


@pytest.fixture
def qt_messages():
    messages = []

    def _handler(_msg_type, _context, message):
        messages.append(str(message))

    previous = QtCore.qInstallMessageHandler(_handler)
    try:
        yield messages
    finally:
        QtCore.qInstallMessageHandler(previous)


def test_scope_and_lockbox_buttons_work_without_loop_errors(pyrpl_instance, caplog, qt_messages):
    p = pyrpl_instance

    caplog.set_level(logging.INFO)

    # Use a lockbox model that exposes the "port1" input and calibrate routine
    # used in the regression scenario.
    p.lockbox.classname = "Interferometer"

    # 1) Direct blocking acquisition must return proper shape.
    curve = p.rp.scope.single(timeout=3.0)
    assert curve.shape == (2, 16384)
    assert p.rp.scope._last_run is not None
    assert p.rp.scope._last_run.done()

    scope = p.rp.scope
    scope.setup(duration=0.0001, trace_average=1)
    scope_widget = scope._create_widget()

    # 2) Scope run-single button should launch an acquisition and update data.
    _click_button(scope_widget.button_single)
    assert _wait_until(lambda: scope.running_state == "stopped", timeout_s=5.0)

    data1 = np.array(scope.data_avg, copy=True)
    assert data1.shape == (2, 16384)

    _click_button(scope_widget.button_single)
    assert _wait_until(lambda: scope.running_state == "stopped", timeout_s=5.0)

    data2 = np.array(scope.data_avg, copy=True)
    assert data2.shape == (2, 16384)
    assert not np.array_equal(data1, data2), "scope data should change between runs"

    # 3) Lockbox calibrate button should complete and update calibration data.
    input_mod = p.lockbox.inputs["port1"]
    input_widget = input_mod._create_widget()

    before = (
        float(input_mod.calibration_data.min),
        float(input_mod.calibration_data.max),
        float(input_mod.calibration_data.mean),
        float(input_mod.calibration_data.rms),
    )

    success_count = _count_calibration_success(caplog.records)
    _click_button(input_widget.button_calibrate)
    assert _wait_until(
        lambda: _count_calibration_success(caplog.records) > success_count,
        timeout_s=8.0,
    ), "calibration did not complete"

    after = (
        float(input_mod.calibration_data.min),
        float(input_mod.calibration_data.max),
        float(input_mod.calibration_data.mean),
        float(input_mod.calibration_data.rms),
    )
    assert after != before

    # 4) Stress repeated click paths to catch event-loop/timer regressions.
    for _ in range(8):
        _click_button(scope_widget.button_single)
        _click_button(input_widget.button_calibrate)
        _pump_events(0.2)

    # No qasync loop-affinity runtime errors should be logged.
    qasync_errors = [
        rec
        for rec in caplog.records
        if rec.name == "qasync._QEventLoop" and rec.levelno >= logging.ERROR
    ]
    assert not qasync_errors, [rec.getMessage() for rec in qasync_errors]

    module_failures = [
        rec.getMessage()
        for rec in caplog.records
        if rec.name == "pyrpl.modules"
        and rec.levelno >= logging.ERROR
        and ("Calibration failed" in rec.getMessage() or "Timeout exceeded" in rec.getMessage())
    ]
    assert not module_failures, module_failures

    bad_qt_messages = [
        message
        for message in qt_messages
        if (
            "registerTimer: Failed to create a timer" in message
            or "QEventLoop::exec: instance" in message
            or "The event loop is already running" in message
        )
    ]
    assert not bad_qt_messages, bad_qt_messages
