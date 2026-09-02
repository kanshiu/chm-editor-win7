# -*- coding: utf-8 -*-
"""
本地一键验证：运行测试 + Win7 兼容性检查
用法：python run_checks.py
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def step(title):
    print("\n" + "=" * 60)
    print("  " + title)
    print("=" * 60)


def main():
    step("1. 运行单元测试")
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    if result.returncode != 0:
        print("[错误] 测试失败，停止")
        sys.exit(1)

    step("2. Win7 兼容性检查")
    from check_win7 import main as check_main
    check_main()

    step("3. 冒烟测试：导入 + 全文搜索 + HHP 生成")
    from core import Project, SearchIndex, Topic  # noqa
    proj = Project()
    proj.add_file("index.html", title="首页", content="<h1>欢迎使用 CHM 编辑器</h1>")
    proj.add_file("help.html", title="帮助", content="<p>全文搜索功能说明</p>")
    idx = SearchIndex()
    for path, info in proj.files.items():
        idx.add_document(info["title"], path, info["content"])
    results = idx.search("搜索")
    assert len(results) >= 1, "搜索应返回结果"
    hhp = proj.to_hhp(ROOT, "out.chm")
    assert "Full-text search=Yes" in hhp, "HHP 必须含全文搜索"
    # 拖拽防环
    root = Topic(title="Root")
    a = root.add_child("A")
    b = a.add_child("B")
    try:
        root.move_child(a, b)
        print("[错误] 防环未生效")
        sys.exit(1)
    except ValueError:
        pass
    print("[OK] 冒烟测试通过: 导入 + 搜索 + HHP + 防环")

    print("\n" + "#" * 60)
    print("  所有检查通过 ✓")
    print("  项目已准备好推送到 GitHub 触发 CI 构建。")
    print("#" * 60)


if __name__ == "__main__":
    main()
