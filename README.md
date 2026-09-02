# CHM Editor (Win7 便携版)

可视化 CHM 文件编辑器，功能对标 CHM Editor 3.2.0 的核心操作，具备：

- 📂 **目录树编辑**：多级子主题，支持**鼠标拖拽调整层级与顺序**（自动防环）
- ✏️ **HTML 源码编辑**：内嵌编辑器，实时修改
- 🔍 **全文搜索**：内置倒排索引（中文 2-gram + 英文单词），相关度排序 + 结果摘要高亮；**编译出的 CHM 自带全文检索**（`Full-text search=Yes`）
- 📥 **导入现有 CHM**：一键解包为可编辑工程
- 📦 **编译 CHM**：调用 `hhc.exe` 生成标准 CHM
- 🖥️ **WYSIWYG 预览**：优先 WebView2 渲染，Win7 无 WebView2 时**自动降级为纯文本预览**

## 系统要求

- **Windows 7 SP1 及以上**（已通过 Win7 manifest + PyInstaller 4.10.1 锁定兼容）
- 目标机**无需 Python、无需联网**

## 方式一：直接下载成品（推荐）

1. 打开仓库的 **Actions** 标签页
2. 点最新一次 `Build Win7 CHM Editor` 运行记录
3. 底部 **Artifacts** 区域下载 `CHMEditor-Win7.zip`
4. 解压后整个文件夹拷到目标 Win7 机器，**双击 `CHMEditor.exe`** 即可运行

> 不需要你自己准备 Win7 机器、不需要装 Python、不需要联网。CI 用 `windows-2019` runner 自动构建。

## 方式二：本地运行（开发调试）

```cmd
pip install pychm           :: 可选，优化 CHM 导入
python chm_editor.py        :: 启动可视化窗口
```

## 方式三：本地打包 exe

> ⚠️ **必须在 Windows + Python 3.8.10 上运行**（PyInstaller 4.10.1 仅兼容到 3.8）。

```cmd
pip install "PyInstaller==4.10.1"
python build_win7_exe.py
```

产物：`dist\CHMEditor\CHMEditor.exe`，整个文件夹拷贝即免装运行。

## 编译 CHM 需要 hhc.exe

微软 HTML Help Workshop 的 `hhc.exe` 需用户自行获取（微软许可限制，不内置）：
- 把 `hhc.exe` 放到 `CHMEditor.exe` **同目录**最省事
- 或安装 [HTML Help Workshop](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/htmlhelp/microsoft-html-help-1-4-sdk-download)

## 项目结构

```
chm-editor-win7/
├── chm_editor.py                # GUI 主程序（三栏界面 + 拖拽 + 惰性 WebView 降级）
├── core.py                      # 核心模型（Project / Topic / SearchIndex / HHP-HHC-HHK 生成）
├── build_win7_exe.py            # Win7 打包脚本（PyInstaller 4.10.1 + manifest）
├── tests/
│   └── test_all.py              # 单元测试（core + GUI 工作流 + Win7 兼容检查）
├── .github/
│   └── workflows/
│       └── build-win7.yml        # GitHub Actions CI（windows-2019 runner）
└── README.md
```

## 开发说明

- `core.py` 与 GUI 完全解耦，方便无头测试与后续替换界面
- 全文搜索：中文按字符、英文按词分词建倒排索引，支持短语高亮摘要 + 相关度排序
- 编译出的 CHM 自带搜索框：通过 `Full-text search=Yes` 让微软编译器生成全文检索

## License

MIT
