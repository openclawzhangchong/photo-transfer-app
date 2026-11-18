# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本"""
import os
import subprocess
import sys

APP = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP)

name = "批量手机电脑传照片"
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onefile", "--noconsole",
    "--name", name,
    "--icon", "logo.ico",
    "--add-data", "logo.ico;.",
    "main.py",
]

print("Running:", " ".join(cmd))
r = subprocess.run(cmd, cwd=APP)
print("Exit code:", r.returncode)

exe = os.path.join(APP, "dist", name + ".exe")
if os.path.exists(exe):
    print("BUILD_OK:", exe, os.path.getsize(exe), "bytes")
else:
    print("BUILD_FAILED")
    sys.exit(1)
