# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('templates',       'templates'),
    ('static',          'static'),
    ('database',        'database'),
    ('helpers',         'helpers'),
    ('bots',            'bots'),
    ('lexview.db',      '.'),
    ('IMPORTAR_AQUI',   'IMPORTAR_AQUI'),
]

datas += collect_data_files('flask')
datas += collect_data_files('flask_sqlalchemy')
datas += collect_data_files('flask_login')
datas += collect_data_files('flask_socketio')
datas += collect_data_files('fpdf2')

hidden_imports = [
    'flask',
    'flask_sqlalchemy',
    'flask_login',
    'flask_socketio',
    'flask_migrate',
    'engineio',
    'socketio',
    'werkzeug',
    'werkzeug.security',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'fpdf',
    'fitz',
    'selenium',
    'webdriver_manager',
    'webdriver_manager.chrome',
    'PIL',
    'requests',
    'qrcode',
    'qrcode.image.pil',
    'docx',
    'docx.oxml',
    'bots.clasificador',
    'bots.actualizador',
    'bots.sincronizador',
    'bots.migrador',
    'bots.forum_driver',
    'bots.auditor',
    'helpers.expte_parser',
    'helpers.migrador_old',
    'helpers.features',
    'helpers.cedulas',
    'database.models',
    'engineio.async_drivers.threading',
    'socketio.async_drivers.threading',
    'engineio.async_drivers',
    'socketio.async_drivers',
    'selenium.webdriver.chrome.options',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.chrome.webdriver',
    'selenium.webdriver.common.by',
    'selenium.webdriver.common.keys',
    'selenium.webdriver.common.action_chains',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'selenium.webdriver.remote.webelement',
    'selenium.webdriver.remote.command',
    'wmi',
    'uuid',
    'hashlib',
    'subprocess',
]

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
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
    name='LexView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LexView',
)
