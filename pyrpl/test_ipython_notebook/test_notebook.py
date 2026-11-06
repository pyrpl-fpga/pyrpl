from pathlib import Path


def test_scope_notebook():
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    with Path(__file__).with_name("test_notebook.ipynb").open() as f:
        nb = nbformat.read(f, as_version=4)

    ep = ExecutePreprocessor(timeout=300, kernel_name="python3")
    ep.preprocess(nb, {"metadata": {"path": "./"}})
