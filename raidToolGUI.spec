# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['raidToolGUI.py'],
             pathex=['E:\\WPy64-3830\\raidToolGUI'],
             binaries=[],
             datas=[('icons\\*.png', 'icons'), ('config.yml', '.')],
             hiddenimports=['win32api'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='raidGUI',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False , icon='icons\\agoraIcon.ico')
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='agoraGUI')
