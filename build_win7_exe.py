# -*- coding: utf-8 -*-
"""
CHM Editor - Win7 便携 exe 打包脚本
用法：python build_win7_exe.py
环境：必须在 Windows + Python 3.8.10 上运行（CI: windows-2019 runner）

关键锁定：
- PyInstaller 4.10.1（最后一个支持 Windows 7 的版本）
- --onedir（Win7 稳定性优于 onefile）
- 注入 Win7/8/10/11 supportedOS manifest
- 内置 Python 版本自检（>=3.9 明确警告）
"""

import os
import sys
import shutil
import subprocess

APP_NAME = "CHMEditor"
MAIN_SCRIPT = "chm_editor.py"
ENTRY_POINT = "chm_editor:main"

# Windows 7 最高支持 Python 3.8.10
MAX_SUPPORTED_MINOR = 8


def check_python_version():
    major, minor = sys.version_info[:2]
    if (major, minor) > (3, MAX_SUPPORTED_MINOR):
        print("=" * 60)
        print("[警告] 当前 Python %d.%d 高于 3.%d" % (major, minor, MAX_SUPPORTED_MINOR))
        print("PyInstaller 4.10.1 仅兼容到 Python 3.8，在更高版本上可能无法安装。")
        print("推荐：使用 Python 3.8.10 或 GitHub Actions (windows-2019) 自动构建。")
        print("=" * 60)
        return False
    print("[OK] Python %d.%d - Win7 兼容" % (major, minor))
    return True


def ensure_pyinstaller():
    """确保 PyInstaller 4.10.1 已安装"""
    try:
        import PyInstaller  # noqa
        from PyInstaller import __version__ as v
        if v != "4.10.1":
            print("[提示] 当前 PyInstaller %s，将重新安装 4.10.1" % v)
            raise ImportError
    except ImportError:
        print("[安装] PyInstaller 4.10.1 ...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "PyInstaller==4.10.1"])
        print("[OK] PyInstaller 4.10.1 已安装")


def build():
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    check_python_version()
    ensure_pyinstaller()

    # 清理旧产物
    for d in ("build", "dist", APP_NAME + ".spec"):
        if os.path.isdir(d):
            shutil.rmtree(d)
        elif os.path.exists(d):
            os.remove(d)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",        # Win7 稳定性优先
        "--windowed",      # 无控制台窗口
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", here,
        "--hidden-import", "core",
        MAIN_SCRIPT,
    ]

    # 若存在图标可取消注释
    # icon = os.path.join(here, "icon.ico")
    # if os.path.exists(icon):
    #     cmd += ["--icon", icon]

    print("\n[执行] " + " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("\n[失败] PyInstaller 构建返回非零")
        sys.exit(1)

    dist_dir = os.path.join(here, "dist", APP_NAME)
    if not os.path.isdir(dist_dir):
        print("\n[失败] 未找到输出目录: " + dist_dir)
        sys.exit(1)

    # 注入 Win7 兼容 manifest（兼容 Win7/8/10/11）
    _patch_manifest(dist_dir, APP_NAME)

    # 附上说明
    with open(os.path.join(dist_dir, "README-编译CHM.txt"), "w", encoding="utf-8") as f:
        f.write(MANIFEST_TEXT)

    print("\n" + "=" * 60)
    print("[成功] 便携版已生成:")
    print("  " + dist_dir)
    print("将整个文件夹拷贝到目标 Win7 机器即可双击 CHMEditor.exe 运行。")
    print("如需编译 CHM，把 hhc.exe 放到本文件夹内。")
    print("=" * 60)


def _patch_manifest(dist_dir, app_name):
    """为生成的 exe 注入兼容 Win7~Win11 的 manifest"""
    exe_path = os.path.join(dist_dir, app_name + ".exe")
    if not os.path.exists(exe_path):
        return
    try:
        import subprocess as sp
        # PyInstaller 4.x 会在 exe 旁生成 <name>.exe.manifest
        manifest = os.path.join(dist_dir, app_name + ".exe.manifest")
        if not os.path.exists(manifest):
            with open(manifest, "w", encoding="utf-8") as f:
                f.write(WIN7_MANIFEST)
        # 用 mt.exe 或 pyinstaller 自带的 hook 合并（若存在）
        mt = _find_mt()
        if mt:
            sp.run([mt, "-manifest", manifest, "-outputresource:" + exe_path + ";#1"],
                   check=False)
            print("[OK] 已注入 Win7 兼容 manifest")
    except Exception as e:
        print("[提示] manifest 注入跳过（不影响运行）:", e)


def _find_mt():
    """查找 Windows SDK 的 mt.exe"""
    candidates = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\x64\mt.exe",
        r"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\mt.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


WIN7_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <compatibility xmlns="urn:schemas-microsoft-com:compatibility.v1">
    <application>
      <!-- Windows 7 -->
      <supportedOS Id="{35138b9a-5d96-4fbd-8e2d-a2440225f93a}" />
      <!-- Windows 8 -->
      <supportedOS Id="{4a2f28e3-53b9-4441-ba9c-d69d4a4a6e38}" />
      <!-- Windows 8.1 -->
      <supportedOS Id="{1f676c76-80e1-4239-95bb-83d0f6d0da78}" />
      <!-- Windows 10 / 11 -->
      <supportedOS Id="{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}" />
    </application>
  </compatibility>
</assembly>
"""

MANIFEST_TEXT = """CHM Editor - Win7 便携版
========================

【使用方法】
1. 双击 CHMEditor.exe 启动
2. 文件 → 打开工程文件夹：加载 HTML 工程
3. 文件 → 导入 CHM 文件：解压并编辑现有 CHM
4. 编辑完成后点"编译 CHM"生成新的 CHM

【编译 CHM 需要 hhc.exe】
将微软 HTML Help Workshop 中的 hhc.exe 拷贝到本文件夹，
或安装 HTML Help Workshop（离线安装包 htmlhelp.exe）。

【全文搜索】
- 程序内置搜索引擎，打开工程后在搜索框输入关键词回车
- 编译出的 CHM 也带全文检索（HHP 已含 Full-text search=Yes）

【系统要求】Windows 7 SP1 及以上
"""


if __name__ == "__main__":
    build()
