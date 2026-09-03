# -*- coding: utf-8 -*-
"""
打包 CHM Editor 为 Win7 便携 exe
使用 PyInstaller 5.13.2 + Python 3.8
兼容 Windows 7 SP1
"""

import os
import sys
import shutil
import subprocess
import tempfile

APP_NAME = "CHMEditor"
MAIN_SCRIPT = "chm_editor.py"

# Win7 兼容 manifest
WIN7_MANIFEST = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
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
</assembly>'''

def check_python_version():
    """检查 Python 版本，警告但不阻止"""
    major, minor = sys.version_info[:2]
    print("检测到 Python %d.%d.%d" % (major, minor, sys.version_info[2]))
    if major > 3 or (major == 3 and minor > 8):
        print("[WARN] Python %d.%d 可能不完全兼容 Win7，建议使用 3.8.x" % (major, minor))
    else:
        print("[OK] Python 版本适合 Win7 兼容构建")

def build():
    print("=" * 50)
    print("  CHM Editor - Win7 便携版构建脚本")
    print("=" * 50)
    
    check_python_version()
    
    # 写入 manifest 文件
    manifest_path = "win7.manifest"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(WIN7_MANIFEST)
    print("[OK] 已生成 win7.manifest")
    
    # 检查主脚本
    if not os.path.exists(MAIN_SCRIPT):
        print("[ERROR] 找不到 %s" % MAIN_SCRIPT)
        sys.exit(1)
    
    # 构建 PyInstaller 命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--noupx",          # 禁用 UPX，避免 Win7 闪退
        "--manifest", manifest_path,
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", ".",
    ]
    
    # 添加隐藏导入（确保 tkinter 和相关模块被打包）
    hidden_imports = [
        "tkinter",
        "tkinter.scrolledtext",
        "tkinter.ttk",
        "sqlite3",  # 如果搜索索引用了 sqlite
    ]
    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])
    
    # 如果有 hhc.exe，添加为二进制数据
    if os.path.exists("hhc.exe"):
        cmd.extend(["--add-binary", "hhc.exe;."])
        print("[OK] 将 hhc.exe 打包进 exe")
    
    # 如果有 README，添加
    if os.path.exists("README-编译CHM.txt"):
        cmd.extend(["--add-data", "README-编译CHM.txt;."])
    
    cmd.append(MAIN_SCRIPT)
    
    print("\n执行打包命令...")
    print(" ".join(cmd[:8]) + " ...")  # 简略显示
    
    try:
        result = subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("\n[ERROR] 打包失败，返回码: %d" % e.returncode)
        sys.exit(1)
    finally:
        # 清理 manifest 临时文件
        if os.path.exists(manifest_path):
            os.remove(manifest_path)
    
    # 检查产物
    exe_path = os.path.join("dist", APP_NAME + ".exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / 1024 / 1024
        print("\n" + "=" * 50)
        print("  构建成功！")
        print("=" * 50)
        print("输出文件: %s" % os.path.abspath(exe_path))
        print("文件大小: %.1f MB" % size_mb)
        print("\n将 dist 目录下的文件拷贝到目标 Win7 机器即可运行。")
        print("如需编译 CHM，确保 hhc.exe 在 exe 同目录。")
    else:
        print("\n[ERROR] 未找到输出文件，打包可能失败")
        sys.exit(1)

if __name__ == '__main__':
    build()
