import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Checks that PyRPL's asynchronous calls work in a Jupyter kernel. The notebook
# uses a simulated (_FAKE_) Red Pitaya, so the test needs no hardware.
NOTEBOOK = Path(__file__).with_name("test_notebook.ipynb")


def test_scope_notebook():
    # Run nbconvert in a separate process, with a kernel of this interpreter:
    # starting the kernel from inside the pytest process hangs on Windows (the
    # kernel never starts and Ctrl+C does not stop pytest), and the global
    # "python3" kernel may run another Python.
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        kernel_name = "pyrpl-test-kernel"
        kernel_root = tmp / "jupyter" / "kernels" / kernel_name
        kernel_root.mkdir(parents=True)
        (kernel_root / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": "PyRPL test kernel",
                    "language": "python",
                }
            ),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            JUPYTER_PATH=str(tmp / "jupyter"),
            JUPYTER_RUNTIME_DIR=str(tmp / "runtime"),
            IPYTHONDIR=str(tmp / "ipython"),
            QT_QPA_PLATFORM="offscreen",
        )
        script = f"""
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

with open({str(NOTEBOOK)!r}, encoding="utf-8") as f:
    nb = nbformat.read(f, as_version=4)
ExecutePreprocessor(
    # fail a stalled cell instead of waiting indefinitely
    timeout=60,
    startup_timeout=30,
    kernel_name={kernel_name!r},
).preprocess(nb, {{"metadata": {{"path": {str(NOTEBOOK.parent)!r}}}}})
"""
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                env=env,
                text=True,
                capture_output=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            pytest.fail(
                "Notebook process exceeded its 120-second timeout.\n"
                f"stdout:\n{exc.stdout or ''}\nstderr:\n{exc.stderr or ''}"
            )
    assert result.returncode == 0, result.stdout + result.stderr
