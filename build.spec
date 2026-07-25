# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# 收集 Playwright 的所有数据和子模块（含 driver/node.exe ~83MB）
playwright_datas = collect_data_files('playwright', include_py_files=True, subdir=None)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 包含前端打包后的静态文件
        ('dist', 'dist'),
        # 包含默认配置模板
        ('config.default.ini', '.'),
        # 包含托盘图标（PNG 优先，ICO 回退）
        ('app_icon.png', '.'),
        ('app_icon.ico', '.'),
        # Playwright driver（node.exe + package/）
    ] + playwright_datas,
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'apscheduler.triggers.cron',
        'apscheduler.triggers.interval',
        'pystray._win32',
        'PIL._tkinter_finder',
        'zoneinfo',
        'openpyxl',
        'openpyxl.cell',
        'openpyxl.styles',
        # Playwright 全家桶
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
        'playwright._impl',
        'playwright._impl._api_structures',
        'playwright._impl._browser',
        'playwright._impl._browser_context',
        'playwright._impl._browser_type',
        'playwright._impl._cdp_session',
        'playwright._impl._connection',
        'playwright._impl._console_message',
        'playwright._impl._dialog',
        'playwright._impl._download',
        'playwright._impl._element_handle',
        'playwright._impl._event_context_manager',
        'playwright._impl._fetch',
        'playwright._impl._file_chooser',
        'playwright._impl._frame',
        'playwright._impl._helper',
        'playwright._impl._input',
        'playwright._impl._js_handle',
        'playwright._impl._locator',
        'playwright._impl._network',
        'playwright._impl._object_factory',
        'playwright._impl._page',
        'playwright._impl._playwright',
        'playwright._impl._selectors',
        'playwright._impl._stream',
        'playwright._impl._tracing',
        'playwright._impl._video',
        'playwright._impl._waiter',
        'playwright._impl._web_error',
        'playwright._impl._worker',
        'playwright._impl._writable_stream',
        'greenlet',
        'pyee',
        'typing_extensions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'unittest',
        'pydoc',
        'doctest',
        'matplotlib',
        'scipy',
        'numpy.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='酒店数据分析系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 隐藏控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.ico'  # 酒店建筑图标
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='酒店数据分析系统'  # 数据目录已移至项目根，COLLECT 可安全覆盖
)
