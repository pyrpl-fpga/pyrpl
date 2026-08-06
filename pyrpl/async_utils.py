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

import asyncio
import concurrent.futures
import logging
from asyncio import TimeoutError

import qasync
from qtpy import QtCore, QtWidgets
import threading

logger = logging.getLogger(name=__name__)

APP = QtWidgets.QApplication.instance()
if APP is None:
    # logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(["pyrpl"])


def _ipython_shell_name():
    try:
        from IPython import get_ipython
    except Exception:
        return None
    ip = get_ipython()
    if ip is None:
        return None
    return ip.__class__.__name__


IPYTHON_SHELL = _ipython_shell_name()
INTERACTIVE = IPYTHON_SHELL == "ZMQInteractiveShell"
TERMINAL_IPYTHON = IPYTHON_SHELL == "TerminalInteractiveShell"
ZMQ_IPYTHON = IPYTHON_SHELL == "ZMQInteractiveShell"

_NOTEBOOK_LOOP = None
_NOTEBOOK_LOOP_READY = threading.Event()
_NOTEBOOK_LOOP_LOCK = threading.Lock()


def _notebook_loop_main(loop):
    asyncio.set_event_loop(loop)
    _NOTEBOOK_LOOP_READY.set()
    loop.run_forever()


def _get_notebook_loop():
    """Return the persistent asyncio loop used by notebook background jobs."""
    global _NOTEBOOK_LOOP
    if _NOTEBOOK_LOOP is None:
        with _NOTEBOOK_LOOP_LOCK:
            if _NOTEBOOK_LOOP is None:
                _NOTEBOOK_LOOP_READY.clear()
                _NOTEBOOK_LOOP = asyncio.new_event_loop()
                threading.Thread(
                    target=_notebook_loop_main,
                    args=(_NOTEBOOK_LOOP,),
                    name="pyrpl-notebook",
                    daemon=True,
                ).start()
                _NOTEBOOK_LOOP_READY.wait()
    return _NOTEBOOK_LOOP


def _submit_notebook(coroutine):
    return asyncio.run_coroutine_threadsafe(coroutine, _get_notebook_loop())

# Design note (Python 3.14+):
# `asyncio.get_event_loop()` no longer creates a loop implicitly in the main
# thread. Older PyRPL code relied on that behavior.
#
# Keep one module-level qasync loop as a fallback for code paths where no
# running/current asyncio loop is available (for example plain python.exe).
# Important: do not install it globally at import time because that can clash
# with loops created later by IPython/prompt_toolkit.
#
# Keep a dedicated qasync loop fallback for synchronous call paths.
# In plain python (non-IPython), Qt callbacks often rely on a loop that acts
# as already-running while Qt is pumping events.
# In IPython shells, forcing already_running=True is harmful (prompt_toolkit
# in terminal IPython; kernel message flow in notebooks), so keep it False.
if IPYTHON_SHELL is None:
    LOOP = qasync.QEventLoop(already_running=True)
else:
    LOOP = qasync.QEventLoop(already_running=False)

FIRST_COMPLETED = asyncio.FIRST_COMPLETED
FIRST_EXCEPTION = asyncio.FIRST_EXCEPTION
ALL_COMPLETED = asyncio.ALL_COMPLETED

def _get_preferred_loop():
    """
    Return the loop that should own newly-created tasks/futures.

    Priority:
    1. Current running loop (strongest ownership signal)
    2. Current event loop when available and suitable
    3. Module-level qasync fallback (sync/Qt-slot code paths)
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        try:
            # In IPython/QtConsole, this may return a shell-owned loop.
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # Python 3.14+: no implicit loop in this thread.
            # In interactive kernels, do not globally replace the shell loop.
            if INTERACTIVE:
                return LOOP
            asyncio.set_event_loop(LOOP)
            return LOOP
        # Plain python.exe commonly returns a non-qasync default loop here.
        # For PyRPL Qt callbacks we prefer the qasync fallback loop in that
        # case to keep timer/future ownership consistent with Qt integration.
        if isinstance(loop, qasync.QEventLoop):
            return loop
        if not loop.is_running():
            # Avoid clobbering IPython kernel loop ownership.
            if INTERACTIVE:
                return LOOP
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

    # asyncio.sleep binds its timer to the caller's running loop. Reimplementing
    # it with private asyncio internals caused loop-affinity problems and broke
    # whenever those internals changed.
    return await asyncio.sleep(delay, result)


def ensure_future(coroutine, force_background=False):
    """
    Schedules the task described by the coroutine. Deals properly with
    IPython kernel integration.
    """
    if ZMQ_IPYTHON:
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        notebook_loop = _get_notebook_loop()
        if running_loop is notebook_loop:
            return asyncio.ensure_future(coroutine, loop=notebook_loop)
        concurrent_future = _submit_notebook(coroutine)
        if running_loop is not None and not force_background:
            # Preserve support for `await module.method_async()` in cells.
            return asyncio.wrap_future(concurrent_future, loop=running_loop)
        return concurrent_future

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
    if asyncio.isfuture(fs) or asyncio.iscoroutine(fs):
        raise TypeError(f"expect a list of futures, not {type(fs).__name__}")
    if not fs:
        raise ValueError("Set of Tasks/Futures is empty.")
    if return_when not in (FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED):
        raise ValueError(f"Invalid return_when value: {return_when}")

    fs = set(fs)

    if any(asyncio.iscoroutine(f) for f in fs):
        raise TypeError("Passing coroutines is forbidden, use tasks explicitly.")

    return await asyncio.wait(fs, timeout=timeout, return_when=return_when)


def wait(future, timeout=None):
    """
    Bridge async futures/coroutines to synchronous call sites.

    Important constraint:
    - `future` must be awaited on its owning loop.
    - We must not blindly call `run_until_complete` on a loop that is already
      running (typical in Qt/IPython), otherwise nested-loop/runtime errors can
      appear.
    """
    if isinstance(future, concurrent.futures.Future):
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise TimeoutError("Timeout exceeded") from None

    if asyncio.iscoroutine(future):
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if ZMQ_IPYTHON and running_loop is not None:
            worker_future = _submit_notebook(future)
            try:
                return worker_future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                worker_future.cancel()
                raise TimeoutError("Timeout exceeded") from None
        future = ensure_future(future)

    if INTERACTIVE:
        if not asyncio.isfuture(future):
            raise TypeError("wait() expects a Future/Task or coroutine.")
        # Interactive path. Never recursively drive ipykernel's running loop:
        # Python 3.14 rejects re-entering its currently executing shell task.
        target_loop = future.get_loop()
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if ZMQ_IPYTHON and running_loop is target_loop:
            raise RuntimeError(
                "Cannot synchronously wait for a task explicitly created on "
                "the notebook kernel loop. Use pyrpl.async_utils.ensure_future "
                "so the task is owned by PyRPL's Qt loop."
            )

        # Fallback:
        # Use a nested Qt event loop as a local waiter while the async task is
        # executed by its owning asyncio loop.
        #
        # In modern ipykernel/Python, calling run_until_complete from inside
        # the kernel task can trigger loop re-entry failures such as:
        # "Cannot enter into task ... while another task ... is being executed."
        # Therefore, do not call run_until_complete in this branch.
        # assert isinstance(future, Future) or iscoroutine(future)
        new_future = asyncio.ensure_future(
            asyncio_wait({future}, timeout=timeout), loop=target_loop
        )
        # if sys.version>='3.7':
        # # this way, it was not possible to execute wait behind a qt slot !!!

        #   LOOP.run_until_complete(new_future)
        #   done, pending = new_future.result()
        # else:

        loop = QtCore.QEventLoop()
        new_future.add_done_callback(lambda *args: loop.quit())
        timed_out = [False]
        timeout_timer = None
        if timeout is not None:
            timeout_timer = QtCore.QTimer(loop)
            timeout_timer.setSingleShot(True)

            def on_timeout():
                timed_out[0] = True
                loop.quit()

            timeout_timer.timeout.connect(on_timeout)
            timeout_timer.start(max(0, int(float(timeout) * 1000)))

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
    wait(sleep_async(time_s))


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
        super().__init__()

    def _get_loop(self):
        return LOOP
