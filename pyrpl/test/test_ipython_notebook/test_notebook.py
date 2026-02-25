import pytest

def test_scope_notebook():
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor
    
    with open("pyrpl/test/test_ipython_notebook/test_notebook.ipynb") as f:
        nb = nbformat.read(f, as_version=4)
    
    ep = ExecutePreprocessor(timeout=300, kernel_name='python3')
    ep.preprocess(nb, {'metadata': {'path': './'}})