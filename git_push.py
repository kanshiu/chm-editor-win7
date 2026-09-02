# -*- coding: utf-8 -*-
"""
辅助：在【你自己的电脑】上执行此脚本，把项目推送到 GitHub。
（沙盒无法直接认证你的 GitHub，故改为生成可复制粘贴的命令。）

用法：
    python git_push.py                  # 使用默认仓库地址
    python git_push.py --repo https://github.com/你的用户名/仓库名.git
"""

import argparse
import os
import subprocess
import sys

DEFAULT_REPO = "https://github.com/kanshiu/chm-editor-win7.git"


def run(cmd):
    print("  $ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="推送 CHM Editor 到 GitHub 并触发 CI")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub 仓库地址")
    parser.add_argument("--branch", default="main", help="主分支名")
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    # 生成可直接复制执行的命令清单（避免沙盒权限问题）
    cmds = [
        ["git", "init"],
        ["git", "add", "."],
        ["git", "commit", "-m", "CHM Editor: Win7 portable with CI build"],
        ["git", "branch", "-M", args.branch],
        ["git", "remote", "add", "origin", args.repo],
        ["git", "push", "-u", "origin", args.branch],
    ]

    print("\n请在【你自己的电脑】上、本项目根目录下，依次执行以下命令：\n")
    for c in cmds:
        print("  " + " ".join(c))
    print("\n推送成功后，GitHub Actions 会自动：")
    print("  1) 运行 tests/test_all.py 单元测试")
    print("  2) 用 windows-2019 runner + Python 3.8.10 + PyInstaller 4.10.1 构建")
    print("  3) 在 Actions → Artifacts 提供 CHMEditor-Win7.zip 下载")
    print("\n提示：首次推送若要求认证，请使用 GitHub Personal Access Token (classic)，")
    print("scope 勾选 repo + workflow。")


if __name__ == "__main__":
    main()
