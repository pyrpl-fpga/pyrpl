# note to the developer
# do not forget to make source distribution with
# python setup.py sdist

# much of the code here is from
# https://jeffknupp.com/blog/2013/08/16/open-sourcing-a-python-project-the-right-way/

# !/usr/bin/env python
from setuptools import setup, find_packages
import os
import sys

# Path to the directory that contains the setup.py script
SETUP_PATH = os.path.dirname(os.path.abspath(__file__))


def read(fname):
    return open(os.path.join(SETUP_PATH, fname)).read()


# Version info -- read without importing
_locals = {}
exec(read(os.path.join('pyrpl', '_version.py')), None, _locals)
version = _locals['__version__']

# Base requirements
requirements = [
    'scp',
    'scipy',
    'pyyaml',
    'pandas',
    'pyqtgraph',
    'numpy>=1.9',
    'paramiko>=2.0',
    'PyQt5',
    'qtpy',
    'nbconvert',
    'jupyter-client',
    'qasync',
    'ipykernel<6.30' 
]


# Environment specific requirements
if os.environ.get('READTHEDOCS') == 'True':
    requirements.extend(['sphinx', 'sphinx_bootstrap_theme'])
    # Filter out packages that RTD can't install
    filtered_requirements = []
    for req in requirements:
        if not any(req.startswith(pkg) for pkg in
                   ['numpy', 'scipy', 'pandas', 'scp', 'paramiko',
                   'qasync', 'qtpy', 'pyqtgraph']):
            filtered_requirements.append(req)
    requirements = filtered_requirements

# Try to read long description
try:
    long_description = read('README.rst')
except:
    try:
        import pypandoc
        long_description = pypandoc.convert_file('README.md', 'rst')
    except:
        long_description = read('README.md')

setup(
    name='pyrpl',
    version=version,
    description='DSP servo controller for quantum optics with the RedPitaya',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Leonhard Neuhaus, Michaël Croquette',
    author_email='neuhaus@lkb.upmc.fr ,michael.croquette@gmail.com',
    url='https://github.com/pyrpl-fpga/pyrpl',
    license='MIT',
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: C',
        'Natural Language :: English',
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Scientific/Engineering :: Physics'
    ],
    keywords='RedPitaya DSP FPGA IIR PDH synchronous detection filter PID '
             'control lockbox servo feedback lock quantum optics',
    packages=find_packages(),
    package_data={
        'pyrpl': [
            'fpga/*',
            'monitor_server/*',
            'config/*',
            'widgets/images/*'
        ]
    },
    install_requires=requirements,
    python_requires='>=3.8',
    extras_require={
        'dev': ['pytest', 'pytest-cov', 'sphinx', 'sphinx_bootstrap_theme'],
        'test': ['pytest', 'pytest-cov']
    }
)