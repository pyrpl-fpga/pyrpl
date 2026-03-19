# -*- mode: python -*-
block_cipher = None
import os
import sys

a = Analysis(['pyrpl/__main__.py'],
             pathex=['.'],
             binaries=[],
             datas=[('pyrpl/fpga/red_pitaya.bin', 'pyrpl/fpga'),
                    ('pyrpl/fpga/red_pitaya.dtbo', 'pyrpl/fpga'),
                    ('pyrpl/monitor_server/monitor_server*',
                     'pyrpl/monitor_server')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[
                 'scipy',
                 'cupy',
                 'cupy.cuda',
                 'cupy_backends',
                 'cupyx',
                 'pytest',
                 'numba',
                 'doctest',
                 'setuptools',
                 'pandas',
                 'pkg_resources',
                 'IPython',
                 'matplotlib',
                 'mpl_toolkits',
             ],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

# One directory exe type
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='pyrpl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pyrpl',
)
