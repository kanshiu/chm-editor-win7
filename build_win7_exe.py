# -*- coding: utf-8 -*-
"""
Build CHM Editor as Win7 portable exe
PyInstaller 5.13.2 + Python 3.8
"""

import os
import sys
import subprocess

APP_NAME = "CHMEditor"
MAIN_SCRIPT = "chm_editor.py"

WIN7_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker" uiAccess="false"/>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <supportedOS Id="{e2011457-1546-43c5-a5fe-008deee3d3f0}"/>
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}"/>
      <supportedOS Id="{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}"/>
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}"/>
    </application>
  </compatibility>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls"
        version="6.0.0.0" processorArchitecture="*" publicKeyToken="6595b64144ccf1df" language="*"/>
    </dependentAssembly>
  </dependency>
</assembly>"""

def check_python_version():
    major, minor = sys.version_info[:2]
    print("Python %d.%d.%d detected" % (major, minor, sys.version_info[2]))
    if major > 3 or (major == 3 and minor > 8):
        print("[WARN] Python %d.%d - consider using 3.8.x for Win7" % (major, minor))
    else:
        print("[OK] Python version is compatible")

def build():
    print("=" * 50)
    print("  CHM Editor - Win7 Build")
    print("=" * 50)

    check_python_version()

    manifest_path = "win7_build_temp.manifest"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(WIN7_MANIFEST)
    print("[OK] Manifest ready")

    if not os.path.exists(MAIN_SCRIPT):
        print("[ERROR] %s not found!" % MAIN_SCRIPT)
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--noupx",
        "--manifest", manifest_path,
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", ".",
        "--clean",
    ]

    hidden_imports = [
        "tkinter",
        "tkinter.scrolledtext",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "tkinter.simpledialog",
    ]
    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    if os.path.exists("hhc.exe"):
        cmd.extend(["--add-binary", "hhc.exe;."])
        print("[OK] hhc.exe will be bundled")

    if os.path.exists("README-编译CHM.txt"):
        cmd.extend(["--add-data", "README-编译CHM.txt;."])

    cmd.append(MAIN_SCRIPT)

    print("Running PyInstaller...")
    print("Command: %s" % " ".join(cmd[:8]) + " ...(truncated)")

    try:
        result = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("[ERROR] Build failed, code %d" % e.returncode)
        sys.exit(1)
    finally:
        if os.path.exists(manifest_path):
            os.remove(manifest_path)

    exe_path = os.path.join("dist", APP_NAME + ".exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / 1024.0 / 1024.0
        print("")
        print("=" * 50)
        print("  BUILD SUCCESSFUL")
        print("=" * 50)
        print("Output: %s" % os.path.abspath(exe_path))
        print("Size: %.1f MB" % size_mb)
    else:
        print("[ERROR] exe not found!")
        sys.exit(1)

if __name__ == '__main__':
    build()
