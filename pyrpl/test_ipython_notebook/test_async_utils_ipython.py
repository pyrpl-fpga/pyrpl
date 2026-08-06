def test_scope_notebook(tmp_path):
    import importlib.util
    import json
    import os
    import subprocess
    import sys

    if importlib.util.find_spec("ipykernel") is None:
        import pytest

        pytest.skip("ipykernel is required to execute the notebook regression test")

    # Execute with the same interpreter as pytest. Relying on the global
    # ``python3`` kernelspec can silently run the test under another Python
    # version (this previously made the 3.14 test run under Python 3.13).
    kernel_name = "pyrpl-test-kernel"
    kernel_root = tmp_path / "jupyter" / "kernels" / kernel_name
    kernel_root.mkdir(parents=True)
    (kernel_root / "kernel.json").write_text(
        json.dumps(
            {
                "argv": [
                    sys.executable,
                    "-m",
                    "ipykernel_launcher",
                    "-f",
                    "{connection_file}",
                ],
                "display_name": "PyRPL test kernel",
                "language": "python",
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        JUPYTER_PATH=str(tmp_path / "jupyter"),
        JUPYTER_RUNTIME_DIR=str(tmp_path / "runtime"),
        IPYTHONDIR=str(tmp_path / "ipython"),
        QT_QPA_PLATFORM="offscreen",
        # nbconvert queues cells automatically; IPython's Qt ZMQ notifier is
        # intended for an interactive client waiting between cell requests.
        PYRPL_AUTO_GUI_QT="0",
    )
    script = f"""
import sys
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

with open('pyrpl/test_ipython_notebook/test_async.ipynb', encoding='utf-8') as f:
    nb = nbformat.read(f, as_version=4)
nb.cells.insert(0, nbformat.v4.new_code_cell(
    'import sys\\nassert sys.version_info[:2] == {sys.version_info[:2]!r}'
))
ExecutePreprocessor(
    # Fail a stalled cell quickly.  In particular, this catches event-loop
    # deadlocks instead of leaving the test session waiting indefinitely.
    timeout=10,
    startup_timeout=15,
    kernel_name={kernel_name!r},
).preprocess(nb, {{'metadata': {{'path': '.'}}}})
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
            timeout=25,
        )
    except subprocess.TimeoutExpired as exc:
        import pytest

        pytest.fail(
            "Notebook regression process exceeded its 25-second timeout.\n"
            f"stdout:\n{exc.stdout or ''}\n"
            f"stderr:\n{exc.stderr or ''}"
        )
    assert result.returncode == 0, result.stdout + result.stderr
