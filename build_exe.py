#!/usr/bin/env python3
"""
build_exe.py
Helper to build a one-file executable with PyInstaller and bundle fonts.

Usage:
    python build_exe.py

What it does:
- Ensures there is a local `./fonts/` directory. If empty, it will try to copy common system fonts
  (DejaVuSans, LiberationSans, FreeSans, Arial) into `./fonts/`.
- Runs PyInstaller with `--add-data` to include `fonts/*` into the packaged executable.

Notes:
- On Windows the add-data separator is ';' while on macOS/Linux it is ':'. This script handles that.
- To bundle your preferred font(s), you can also manually put .ttf/.otf files into `./fonts/`.
- Building a Windows exe on Linux may require Wine and a suitable Python environment; this script
  does not perform cross-compilation beyond invoking PyInstaller on the current host.
"""

import os
import sys
import shutil
import glob
import subprocess


def find_system_fonts():
    candidates = []
    if sys.platform.startswith('linux'):
        candidates += [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
        ]
    elif sys.platform.startswith('win'):
        windir = os.environ.get('WINDIR', r'C:\Windows')
        candidates += [
            os.path.join(windir, 'Fonts', 'arial.ttf'),
            os.path.join(windir, 'Fonts', 'DejaVuSans.ttf'),
            os.path.join(windir, 'Fonts', 'LiberationSans-Regular.ttf'),
        ]
    elif sys.platform.startswith('darwin'):
        candidates += [
            '/System/Library/Fonts/Helvetica.ttc',
            '/Library/Fonts/Arial.ttf',
        ]
    return [p for p in candidates if os.path.isfile(p)]


def ensure_fonts_dir(fonts_dir):
    os.makedirs(fonts_dir, exist_ok=True)
    existing = glob.glob(os.path.join(fonts_dir, '*.ttf')) + glob.glob(os.path.join(fonts_dir, '*.otf'))
    if existing:
        return existing
    found = find_system_fonts()
    for f in found:
        try:
            shutil.copy(f, fonts_dir)
            print('Copied font:', f)
        except Exception as e:
            print('Failed to copy', f, e)
    return glob.glob(os.path.join(fonts_dir, '*.ttf')) + glob.glob(os.path.join(fonts_dir, '*.otf'))


def build():
    fonts_dir = os.path.abspath('fonts')
    fonts = ensure_fonts_dir(fonts_dir)
    if not fonts:
        print('Warning: no fonts were found or copied into ./fonts. Place desired .ttf/.otf under ./fonts before building.')

    sep = ';' if sys.platform.startswith('win') else ':'
    add_data = f"{fonts_dir}/*{sep}fonts"

    cmd = [
        'pyinstaller',
        '--onefile',
        '--add-data', add_data,
        '--name', 'analyze_gui',
        'analyze_gui.py',
    ]

    print('Running PyInstaller:')
    print(' '.join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print('PyInstaller failed:', e)
        sys.exit(1)

    print('\nBuild finished. Check the `dist/` directory for the executable.')


if __name__ == '__main__':
    build()
