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
import qasync
import math
import concurrent.futures

logger = logging.getLogger(name=__name__)

# enable ipython QtGui support if needed
try:
    from IPython import get_ipython
    IPYTHON = get_ipython()
    IPYTHON.run_line_magic("gui","qt")
except BaseException as e:
    logger.debug('Could not enable IPython gui support: %s.' % e)

APP = QtWidgets.QApplication.instance()
if APP is None:
    # logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(['pyrpl'])

LOOP = qasync.QEventLoop(already_running=False)  # Since tasks scheduled in this loop seem to
# fall in the standard QEventLoop, and we never explicitly ask to run this
# loop, it might seem useless to send all tasks to LOOP, however, a task
# scheduled in the default loop seem to never get executed with IPython
# kernel integration.
asyncio.set_event_loop(LOOP)

FIRST_COMPLETED = concurrent.futures.FIRST_COMPLETED
FIRST_EXCEPTION = concurrent.futures.FIRST_EXCEPTION
ALL_COMPLETED = concurrent.futures.ALL_COMPLETED


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

    future = LOOP.create_future()
    h = LOOP.call_later(delay,
                        futures._set_result_unless_cancelled,
                        future, result)
    try:
        return await future
    finally:
        h.cancel()


def ensure_future(coroutine):
    """
    Schedules the task described by the coroutine. Deals properly with
    IPython kernel integration.
    """
    return asyncio.ensure_future(coroutine, loop=LOOP)

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
        raise ValueError('Set of Tasks/Futures is empty.')
    if return_when not in (FIRST_COMPLETED, FIRST_EXCEPTION, ALL_COMPLETED):
        raise ValueError(f'Invalid return_when value: {return_when}')

    fs = set(fs)

    if any(coroutines.iscoroutine(f) for f in fs):
        raise TypeError("Passing coroutines is forbidden, use tasks explicitly.")

    # loop = events.get_running_loop()  
    # Here we send the right qasync LOOP
    return await _wait(fs, timeout, return_when, LOOP)


def wait(future, timeout=None):
    loop = asyncio.get_event_loop()
    if asyncio.iscoroutine(future):
        future = asyncio.ensure_future(future, loop=loop)

    app = QtCore.QCoreApplication.instance()
    deadline = loop.time() + timeout if timeout is not None else None

    if app is None:
        print("[wait] no Qt app → run_until_complete")
        loop.run_until_complete(future)
    else:
        print("[wait] Qt app detected → hybrid polling")
        iteration = 0
        while not future.done():
            iteration += 1
            print(f"[wait] iter {iteration}: pumping events, done={future.done()}")

            # pump Qt
            app.processEvents(QtCore.QEventLoop.AllEvents, 50)

            # pump asyncio
            loop.call_soon(loop.stop)
            loop.run_forever()

            if deadline is not None:
                remaining = deadline - loop.time()
                print(f"[wait] iter {iteration}: remaining {remaining:.3f} s")
                if remaining <= 0:
                    break

    if not future.done():
        print("[wait] timeout exceeded after polling")
        raise TimeoutError("Timeout exceeded")

    print("[wait] success: returning result")
    return future.result()




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
