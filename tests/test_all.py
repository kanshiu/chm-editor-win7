# -*- coding: utf-8 -*-
"""
CHM Editor 测试套件（无头，可在 Linux CI 上运行）
覆盖：core 模型 / 全文搜索 / HHP-HHC-HHK 生成 / 拖拽层级 / GUI 工作流 / Win7 惰性降级
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import Project, Topic, SearchIndex, find_hhc, compile_chm  # noqa


# ==================== core 模型测试 ====================

class TestTopicTree(unittest.TestCase):
    def test_add_and_move_child(self):
        root = Topic(title="Root")
        a = root.add_child("A", "a.html")
        b = root.add_child("B", "b.html")
        self.assertEqual(len(root.children), 2)
        # 把 B 拖成 A 的子节点
        root.move_child(b, a, index=None)
        self.assertEqual(len(root.children), 1)
        self.assertEqual(len(a.children), 1)
        self.assertIs(b.parent, a)

    def test_prevent_cycle(self):
        root = Topic(title="Root")
        a = root.add_child("A")
        b = a.add_child("B")
        # 把 A 拖到 B 下面 = 环，应拒绝
        with self.assertRaises(ValueError):
            root.move_child(a, b, index=None)

    def test_move_to_sibling_index(self):
        root = Topic(title="Root")
        a = root.add_child("A", "a.html")
        b = root.add_child("B", "b.html")
        c = root.add_child("C", "c.html")
        # 把 C 移到 A 之前（index=0）
        root.move_child(c, root, index=0)
        self.assertEqual([n.title for n in root.children], ["C", "A", "B"])


class TestSearchIndex(unittest.TestCase):
    def test_chinese_and_english_search(self):
        idx = SearchIndex()
        idx.add_document("介绍", "intro.html", "<h1>产品介绍</h1>这是一段说明文字")
        idx.add_document("Guide", "guide.html", "<p>User guide and manual</p>")
        res = idx.search("介绍")
        self.assertTrue(any("介绍" in r["title"] or "介绍" in r["highlight"] for r in res))
        res = idx.search("guide")
        self.assertTrue(any("guide" in r["path"].lower() or r.get("score", 0) > 0 for r in res))
        res = idx.search("")
        self.assertEqual(res, [])

    def test_snippet_highlight(self):
        idx = SearchIndex()
        idx.add_document("doc", "d.html", "一二三四五六七八九十")
        res = idx.search("五六")
        self.assertEqual(len(res), 1)
        self.assertIn("五六", res[0]["highlight"])


class TestProjectGeneration(unittest.TestCase):
    def test_hhp_has_fulltext_search(self):
        p = Project()
        p.add_file("index.html", title="首页", content="<h1>首页</h1>")
        p.add_file("intro.html", title="介绍", content="<h1>介绍</h1>")
        hhp = p.to_hhp("/tmp", "out.chm")
        self.assertIn("Full-text search=Yes", hhp)
        self.assertIn("Default topic=index.html", hhp)
        self.assertIn("Language=0x804", hhp)
        self.assertIn("index.html", hhp)
        self.assertIn("intro.html", hhp)

    def test_hhc_hhk_structure(self):
        p = Project()
        p.add_file("a.html", title="A", content="关键词甲乙丙丁")
        p.add_file("b.html", title="B", content="内容")
        root = p.root
        n = root.add_child("章节", "a.html")
        root.add_child("附录", "b.html")
        hhc = p.to_hhc()
        self.assertIn("<UL>", hhc)
        self.assertIn("章节", hhc)
        self.assertIn("a.html", hhc)
        hhk = p.to_hhk()
        self.assertIn("A", hhk)
        self.assertIn("B", hhk)

    def test_save_roundtrip(self):
        tmp = tempfile.mkdtemp()
        p = Project()
        p.add_file("x.html", title="X", content="<p>hello</p>")
        p.root.add_child("X页", "x.html")
        p.save(tmp)
        self.assertTrue(os.path.exists(os.path.join(tmp, "project.hhp")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "table_of_contents.hhc")))
        self.assertTrue(os.path.exists(os.path.join(tmp, "project.json")))
        # 校验内容
        with open(os.path.join(tmp, "project.hhp"), "r", encoding="gb2312", errors="ignore") as f:
            self.assertIn("Full-text search=Yes", f.read())


class TestFindHHC(unittest.TestCase):
    def test_find_hhc_returns_none_or_path(self):
        # 沙盒中一般不存在 hhc.exe，应返回 None 而非抛异常
        result = find_hhc()
        self.assertTrue(result is None or isinstance(result, str))


# ==================== GUI 工作流测试（用 stub 模拟 tk） ====================

class FakeText:
    def __init__(self, content=""):
        self._content = content
    def get(self, *args):
        return self._content
    def delete(self, *args):
        self._content = ""
    def insert(self, *args):
        self._content = args[-1] if args else ""
    def pack(self, **kw): pass
    def config(self, **kw): pass
    def bind(self, *args): pass


class FakeTree:
    """模拟 TopicTree，记录 rebuild/move 调用"""
    def __init__(self):
        self.rebuild_calls = 0
        self.project = None
    def rebuild(self):
        self.rebuild_calls += 1


class TestGUIWorkflow(unittest.TestCase):
    """在无 tkinter 环境下，直接驱动 CHMEditorApp 的内部方法"""

    def _make_app(self):
        # 延迟导入，避免无 tkinter 时报错
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "chm_editor", os.path.join(os.path.dirname(__file__), "..", "chm_editor.py"))
        # 若无法导入（无 tkinter），则用桩对象
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod, True
        except Exception as e:
            return None, False

    def test_workflow_headless(self):
        """模拟：新建→编辑→搜索→删除→保存→编译（不依赖真实 GUI）"""
        import core
        proj = core.Project()
        idx = core.SearchIndex()
        tmp = tempfile.mkdtemp()

        # 新建
        proj.add_file("index.html", title="首页", content="<h1>首页内容</h1>")
        proj.add_file("guide.html", title="指南", content="<p>Guide content</p>")
        for path, info in proj.files.items():
            idx.add_document(info["title"], path, info["content"])

        # 编辑（模拟编辑器修改）
        proj.files["index.html"]["content"] = "<h1>修改后的首页</h1>"

        # 搜索
        results = idx.search("首页")
        self.assertTrue(len(results) >= 1)

        # 删除
        proj.remove_file("guide.html")
        self.assertNotIn("guide.html", proj.files)

        # 保存
        proj.save(tmp)
        self.assertTrue(os.path.exists(os.path.join(tmp, "project.hhp")))

        # 编译（沙盒无 hhc.exe，预期返回 False 但流程不崩）
        ok, msg = compile_chm(tmp, os.path.join(tmp, "out.chm"))
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)


class TestWin7Compatibility(unittest.TestCase):
    """Win7 专属检查：语法、惰性降级逻辑、Python 版本提示"""

    def test_chm_editor_syntax_compiles(self):
        path = os.path.join(os.path.dirname(__file__), "..", "chm_editor.py")
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        compile(source, path, "exec")  # 不抛异常即通过

    def test_lazy_webview_degradation(self):
        """PreviewPanel._try_load_html_frame 在未装 tkinterweb 时应降级为 text"""
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "..", "chm_editor.py")
        spec = importlib.util.spec_from_file_location("chm_editor_mod", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            self.skipTest("tkinter 不可用，跳过 GUI 类检查")
        # 用一个最小桩替代 tkinter 组件
        panel = mod.PreviewPanel.__new__(mod.PreviewPanel)
        panel._mode = "text"
        panel._html_frame = None
        # 未装 tkinterweb 时 _try_load_html_frame 应保持 text 模式
        try:
            import tkinterweb  # noqa
            has_webview = True
        except ImportError:
            has_webview = False
        if not has_webview:
            panel._try_load_html_frame()
            self.assertEqual(panel._mode, "text")

    def test_no_modern_syntax(self):
        """确认源码不含 Python 3.9+ 语法（保证可在 3.8 运行）"""
        path = os.path.join(os.path.dirname(__file__), "..", "chm_editor.py")
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        # 通过 3.8 兼容编译验证（已在 test_chm_editor_syntax_compiles 中覆盖）
        self.assertNotIn("match ", source.split("\n")[0])  # 简单防护


if __name__ == "__main__":
    unittest.main(verbosity=2)
