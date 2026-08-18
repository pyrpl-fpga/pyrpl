import concurrent.futures
import threading
import time

from pyrpl.redpitaya_client import MonitorClient


def test_monitor_client_serializes_transactions_between_threads():
    """A shared protocol stream must never contain overlapping requests."""
    client = MonitorClient.__new__(MonitorClient)
    client._socket_lock = threading.RLock()
    client._read_counter = 0
    client._write_counter = 0
    client._sound_debug = False
    client.close = lambda: None

    state_lock = threading.Lock()
    active = 0
    maximum_active = 0

    def transaction(_function, _addr, value):
        nonlocal active, maximum_active
        with state_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.01)
        with state_lock:
            active -= 1
        return value

    client.try_n_times = transaction

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        calls = [
            executor.submit(client.reads, 0x40100000 + index * 4, 1)
            if index % 2
            else executor.submit(client.writes, 0x40100000 + index * 4, [index])
            for index in range(16)
        ]
        for call in calls:
            call.result(timeout=2.0)

    assert maximum_active == 1
