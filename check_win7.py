# -*- coding: utf-8 -*-
"""
Win7 兼容性自动检查（CI 中作为额外关卡）
1. 所有源码用 Python 3.8 兼容方式编译
2. build_win7_exe.py 锁定 PyInstaller 4.10.1
3. chm_editor.py 存在惰性 WebView 降级逻辑
4. workflow 使用 windows-2019 runner
5. HHP 生成含 Full-text search=Yes
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def check(condition, msg):
    status = "[OK]   " if condition else "[FAIL] "
    print(status + msg)
    return condition


def main():
    results = []

    # 1. 源码语法（用当前解释器编译，配合 test_chm_editor_syntax_compiles 覆盖）
    py_files = []
    for dirpath, _, files in os.walk(ROOT):
        if ".git" in dirpath:
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(dirpath, f))
    for path in py_files:
        with open(path, "r", encoding="utf-8") as fh:
            source = fh.read()
        try:
            compile(source, path, "exec")
            results.append(check(True, "语法编译通过: " + os.path.relpath(path, ROOT)))
        except SyntaxError as e:
            results.append(check(False, "语法错误 %s: %s" % (os.path.relpath(path, ROOT), e)))

    # 2. PyInstaller 版本锁定
    build_script = os.path.join(ROOT, "build_win7_exe.py")
    with open(build_script, "r", encoding="utf-8") as f:
        build_src = f.read()
    results.append(check(
        "PyInstaller==4.10.1" in build_src,
        "build_win7_exe.py 锁定 PyInstaller 4.10.1"))
    results.append(check(
        "MAX_SUPPORTED_MINOR = 8" in build_src,
        "build_win7_exe.py 限制 Python <= 3.8"))

    # 3. 惰性 WebView 降级
    gui = os.path.join(ROOT, "chm_editor.py")
    with open(gui, "r", encoding="utf-8") as f:
        gui_src = f.read()
    results.append(check(
        "_try_load_html_frame" in gui_src,
        "chm_editor.py 存在惰性 WebView 探测 (_try_load_html_frame)"))
    results.append(check(
        "tkinterweb" in gui_src,
        "chm_editor.py 引用 tkinterweb（失败时降级）"))

    # 4. workflow runner
    wf = os.path.join(ROOT, ".github", "workflows", "build-win7.yml")
    with open(wf, "r", encoding="utf-8") as f:
        wf_src = f.read()
    results.append(check("runs-on: windows-2019" in wf_src, "workflow 使用 windows-2019 runner"))
    results.append(check("python-version: \"3.8.10\"" in wf_src, "workflow 使用 Python 3.8.10"))
    results.append(check("PyInstaller==4.10.1" in wf_src, "workflow 安装 PyInstaller 4.10.1"))

    # 5. HHP 全文搜索
    core_path = os.path.join(ROOT, "core.py")
    with open(core_path, "r", encoding="utf-8") as f:
        core_src = f.read()
    results.append(check("Full-text search=Yes" in core_src, "core.py HHP 含 Full-text search=Yes"))
    results.append(check("find_hhc" in core_src, "core.py 含 find_hhc 多路径查找"))

    # 6. Python 版本提示
    print("\n--- 环境信息 ---")
    print("Python:", sys.version.split()[0])
    print("Platform:", sys.platform)

    failed = [r for r in results if not r]
    print("\n=== 结果: %d/%d 通过 ===" % (len(results) - len(failed), len(results)))
    if failed:
        print("存在失败项，退出码 1")
        sys.exit(1)
    print("全部通过 ✓")


if __name__ == "__main__":
    main()
