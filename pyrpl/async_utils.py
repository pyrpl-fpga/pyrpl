"""
This file provides the basic functions to perform asynchronous tasks.
It provides the 3 functions:
 * ensure_future(coroutine): schedules the task described by the coroutine and
                             returns a Future that can be used as argument of
                             the following functions:
 * sleep(time_s): blocks the commandline for time_s, without blocking other
                  tasks such as gui update...
 * wait(future, timeout=None): blocks the commandline until future is set or
                               timeout expires.

BEWARE: sleep() and wait() can be used behind a qt slot (for instance in
response to a QPushButton being pressed), however, they will fail if used
inside a coroutine. In this case, one should use the builtin await (in
place of wait) and the asynchronous sleep coroutine provided below (in
place of sleep):
  * async_sleep(time_s): await this coroutine to stall the execution for a
                         time time_s within a coroutine.

These functions are provided in place of the native asyncio functions in
order to integrate properly within the IPython (Jupyter) Kernel. For this,
Main loop of the application:
In an Ipython (Jupyter) notebook with qt integration:
    %gui qt
     fut = ensure_future(some_coroutine(), loop=LOOP) # executes anyway in
the background loop
#    LOOP.run_until_complete(fut) # only returns when fut is ready
# BEWARE ! inside some_coroutine, calls to asyncio.sleep_async() have to be
# made this way:
#    asyncio.sleep(sleep_time, loop=LOOP)
# Consequently, there is a coroutine async_utils.async_sleep(time_s)
# Finally this file provides a sleep() function that waits for the execution of
# sleep_async and that should be used in place of time.sleep.

"""

import logging
from qtpy import QtWidgets, QtCore
import asyncio
from asyncio import TimeoutError, futures, coroutines
from asyncio.tasks import __sleep0, _wait
from pyrpl_utils import isnotebook
import qasync
import math
import concurrent.futures

logger = logging.getLogger(name=__name__)


APP = QtWidgets.QApplication.instance()
if APP is None:
    # logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(["pyrpl"])

# Design note (Python 3.14+):
# `asyncio.get_event_loop()` no longer creates a loop implicitly in the main
# thread. Older PyRPL code relied on that behavior.
#
# Keep one module-level qasync loop as a fallback for code paths where no
# running/current asyncio loop is available (for example plain python.exe).
# Important: do not install it globally at import time because that can clash
# with loops created later by IPython/prompt_toolkit.
LOOP = qasync.QEventLoop(already_running=True)

FIRST_COMPLETED = concurrent.futures.FIRST_COMPLETED
FIRST_EXCEPTION = concurrent.futures.FIRST_EXCEPTION
ALL_COMPLETED = concurrent.futures.ALL_COMPLETED


INTERACTIVE = isnotebook()  # True if we are in an interactive IPython session

if INTERACTIVE:
    from IPython import get_ipython

    IPYTHON = get_ipython()
    # Make sure Qt events are integrated with the interactive shell event loop.
    # This avoids having to call `%gui qt` manually in normal notebook usage.
    IPYTHON.run_line_magic("gui", "qt")


def _get_preferred_loop():
    """
    Return the loop that should own newly-created tasks/futures.

    Priority:
    1. current running loop (strongest signal of loop ownership)
    2. module-level qasync loop fallback (for sync/slot code paths)
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        try:
            # In IPython/QtConsole, this may return a shell-owned loop.
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Python 3.14+: no implicit loop in this thread.
            asyncio.set_event_loop(LOOP)
            return LOOP
        # Plain python.exe commonly returns a non-qasync default loop here.
        # For PyRPL Qt callbacks we prefer the qasync fallback loop in that
        # case to keep timer/future ownership consistent with Qt integration.
        if isinstance(loop, qasync.QEventLoop):
            return loop
        if not loop.is_running():
            asyncio.set_event_loop(LOOP)
            return LOOP
        return loop


async def sleep_async(delay, result=None):
    """
    Replaces asyncio.sleep(time_s) inside coroutines. Deals properly with
    IPython kernel integration. The standard asyncio function get the loop
    by calling get_event_loop which doesn't return the proper loop with
    IPython.
    """

    if delay <= 0:
        await __sleep0()
        return result

    if math.isnan(delay):
        raise ValueError("Invalid delay: NaN (not a number)")

    # Create the timer future on the same loop used by the caller/task.
    # Cross-loop futures are the main source of "attached to a different loop"
    # runtime errors.
    loop = _get_preferred_loop()
    future = loop.create_future()
    h = loop.call_later(delay, futures._set_result_unless_cancelled, future, result)
    try:
        return await future
    finally:
        h.cancel()


def ensure_future(coroutine):
    """
    Schedules the task described by the coroutine. Deals properly with
    IPython kernel integration.
    """
    # Always bind new tasks to the selected loop explicitly so task creation
    # from synchronous callbacks cannot accidentally bind to another loop.
    return asyncio.ensure_future(coroutine, loop=_get_preferred_loop())


async def asyncio_wait(fs, *, timeout=None, return_when=ALL_COMPLETED):
    """
    (This is the asyncio.wait() function rewritten here to work on the qasync LOOP)

    Wait for the Futures or Tasks given by fs to complete.

    The fs iterable must not be empty.

    Returns two sets of Future: (done, pending).

    Usage:

        done, pending = await asyncio.wait(fs)

    Note: This does not raise TimeoutError! Futures that aren't done
    when the timeout occurs are returned in the second set.
    """
    if futures.isfuture(fs) or coroutines.iscoroutine(fs):
        raise TypeError(f"expect a list of futures, not {type(fs).__name__}")
    if not fs:
        raise ValueError("Set of Tasks/Futures is empty.")
    if return_when not in (FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED):
        raise ValueError(f"Invalid return_when value: {return_when}")

    fs = set(fs)

    if any(coroutines.iscoroutine(f) for f in fs):
        raise TypeError("Passing coroutines is forbidden, use tasks explicitly.")

    # Run asyncio.wait on the same loop as the futures.
    # If we let asyncio pick implicitly, it may pick the wrong loop in mixed
    # Qt/IPython contexts and trigger cross-loop errors.
    loop = None
    for f in fs:
        if asyncio.isfuture(f):
            loop = f.get_loop()
            break
    if loop is None:
        loop = _get_preferred_loop()
    return await _wait(fs, timeout, return_when, loop)


def wait(future, timeout=None):
    """
    Bridge async futures/coroutines to synchronous call sites.

    Important constraint:
    - `future` must be awaited on its owning loop.
    - We must not blindly call `run_until_complete` on a loop that is already
      running (typical in Qt/IPython), otherwise nested-loop/runtime errors can
      appear.
    """
    if coroutines.iscoroutine(future):
        future = ensure_future(future)

    if INTERACTIVE:
        # Interactive (IPython/Jupyter) path:
        # Use a nested Qt event loop as a local waiter. This keeps GUI events
        # flowing while the caller blocks, and avoids `run_until_complete` on a
        # loop that may already be integrated/running under IPython.
        # assert isinstance(future, Future) or iscoroutine(future)
        new_future = ensure_future(asyncio_wait({future}, timeout=timeout))
        # if sys.version>='3.7':
        # # this way, it was not possible to execute wait behind a qt slot !!!

        #   LOOP.run_until_complete(new_future)
        #   done, pending = new_future.result()
        # else:

        # Keep waiting local to this call by running a short-lived nested Qt
        # loop that exits when the waiter finishes.
        loop = QtCore.QEventLoop()

        def quit(*args):
            loop.quit()

        new_future.add_done_callback(quit)
        timed_out = [False]
        timeout_timer = None
        if timeout is not None:
            timeout_ms = max(0, int(float(timeout) * 1000))
            timeout_timer = QtCore.QTimer(loop)
            timeout_timer.setSingleShot(True)

            def on_timeout():
                timed_out[0] = True
                loop.quit()

            timeout_timer.timeout.connect(on_timeout)
            timeout_timer.start(timeout_ms)

        while not new_future.done() and not timed_out[0]:
            loop.exec_()

        if timeout_timer is not None and timeout_timer.isActive():
            timeout_timer.stop()

        if not new_future.done():
            new_future.cancel()
            raise TimeoutError("Timeout exceeded")

        done, pending = new_future.result()
        if future in done:
            return future.result()
        raise TimeoutError("Timeout exceeded")
    else:
        # Non-interactive mode:
        # - coroutine objects are normalized to Task/Future above.
        # - Task/Future objects must be awaited on their owning loop.
        if asyncio.isfuture(future):
            target_loop = future.get_loop()
            if target_loop.is_running():
                # Future belongs to a loop that is already running. We cannot
                # call `run_until_complete` on it here.
                #
                # Instead, schedule a small waiter task *on that same loop* and
                # block this sync caller with a nested Qt loop until the waiter
                # completes or timeout fires.
                waiter = asyncio.ensure_future(
                    asyncio_wait({future}, timeout=timeout),
                    loop=target_loop,
                )
                qloop = QtCore.QEventLoop()
                timed_out = [False]
                timeout_timer = None

                def quit_wait(*args):
                    qloop.quit()

                waiter.add_done_callback(quit_wait)

                if timeout is not None:
                    timeout_ms = max(0, int(float(timeout) * 1000))
                    # Single dedicated timer avoids accumulating many transient
                    # timers in repeated wait calls.
                    timeout_timer = QtCore.QTimer(qloop)
                    timeout_timer.setSingleShot(True)

                    def on_timeout():
                        timed_out[0] = True
                        qloop.quit()

                    timeout_timer.timeout.connect(on_timeout)
                    timeout_timer.start(timeout_ms)

                while not waiter.done() and not timed_out[0]:
                    qloop.exec_()

                if timeout_timer is not None and timeout_timer.isActive():
                    timeout_timer.stop()

                if not waiter.done():
                    waiter.cancel()
                    raise TimeoutError("Timeout exceeded")

                done, pending = waiter.result()
                if future in done:
                    return future.result()
                raise TimeoutError("Timeout exceeded")

            if timeout is None:
                # Owning loop is not running: we can drive it directly.
                return target_loop.run_until_complete(future)
            return target_loop.run_until_complete(
                asyncio.wait_for(asyncio.shield(future), timeout)
            )

        raise TypeError("wait() expects a Future/Task or coroutine.")


def sleep(time_s):
    """
    Blocks the commandline for time_s. This function doesn't block the
    eventloop while executing.
    BEWARE: never sleep in a coroutine (use await sleep_async(time_s) instead)
    """
    wait(ensure_future(sleep_async(time_s)))


class Event(asyncio.Event):
    """
    Use this Event instead of asyncio.Event() to signal an event. This
    version deals properly with IPython kernel integration.
    Example: Resuming scope acquisition after a pause (acquisition_module.py)
        def pause(self):
            if self._running_state=='single_async':
                self._running_state=='paused_single'
            _resume_event = Event()

        async def _single_async(self):
            for self.current_avg in range(1, self.trace_average):
                if self._running_state=='paused_single':
                    await self._resume_event.wait()
            self.data_avg = (self.data_avg * (self.current_avg-1) + \
                             await self._trace_async(0)) / self.current_avg

    """

    def __init__(self):
        super(Event, self).__init__()

    def _get_loop(self):
        # Keep Event internals on the same preferred loop as the rest of this
        # module helpers.
        return _get_preferred_loop()
