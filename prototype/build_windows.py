from pathlib import Path
from PyInstaller.__main__ import run

root = Path(__file__).resolve().parent
run(['--noconfirm', '--onefile', '--windowed', '--name', 'Tianwen-Prototype',
     '--distpath', str(root / 'dist'), '--workpath', str(root / 'build'),
     '--specpath', str(root / 'build'), '--paths', str(root),
     '--add-data', str(root / 'data') + ';data',
     '--exclude-module', 'numpy', '--exclude-module', 'matplotlib', '--exclude-module', 'tkinter',
     str(root / 'main.py')])
