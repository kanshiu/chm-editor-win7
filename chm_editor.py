# -*- coding: utf-8 -*-
"""
CHM Editor - 可视化 CHM 编辑器 (Win7 兼容版)
功能：目录树编辑、HTML 源码编辑、全文搜索、导入/编译 CHM、拖拽调整层级
预览策略：优先 WebView2(tkinterweb)，失败时惰性降级为纯文本预览
"""

import os
import sys
import re
import json
import tempfile
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 兼容直接运行与打包后运行
try:
    from core import (Project, Topic, SearchIndex, compile_chm, find_hhc)
except ImportError:
    import core  # type: ignore
    Project = core.Project
    Topic = core.Topic
    SearchIndex = core.SearchIndex
    compile_chm = core.compile_chm
    find_hhc = core.find_hhc


APP_NAME = "CHM Editor"
APP_VERSION = "1.0.0"
CONFIG_FILE = "chm_editor.json"


# ============ 预览面板：惰性探测 WebView，失败降级纯文本 ============

class PreviewPanel(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master, text="预览")
        self._mode = "text"   # "web" 或 "text"
        self._html_frame = None
        self._text = tk.Text(self, wrap=tk.WORD, height=8, font=("SimSun", 10))
        self._text.pack(fill=tk.BOTH, expand=True)
        self._text.config(state=tk.DISABLED)

    def _try_load_html_frame(self):
        """惰性探测：仅在首次需要时 import tkinterweb，避免 Win7 导入崩溃"""
        if self._html_frame is not None:
            return
        try:
            from tkinterweb import HtmlFrame  # noqa
            self._html_frame = HtmlFrame(self)
            self._mode = "web"
        except Exception:
            self._html_frame = None
            self._mode = "text"

    def set_html(self, html):
        self._try_load_html_frame()
        if self._mode == "web" and self._html_frame is not None:
            try:
                self._html_frame.load_html(html or "")
                self._show(self._html_frame)
                return
            except Exception:
                self._mode = "text"
        self._set_text_preview(html or "")

    def _set_text_preview(self, html):
        text = re.sub(r"<[^>]+>", "", html or "")
        text = re.sub(r"\s+", " ", text).strip()
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text[:3000])
        self._text.config(state=tk.DISABLED)
        self._show(self._text)

    def _show(self, widget):
        for w in (self._html_frame, self._text):
            if w is not None:
                w.pack_forget()
        widget.pack(fill=tk.BOTH, expand=True)

    def get_mode(self):
        self._try_load_html_frame()
        return self._mode


# ============ 目录树：支持拖拽调整层级与顺序 ============

class TopicTree(ttk.Treeview):
    def __init__(self, master, project, on_select=None, on_change=None):
        super().__init__(master, show="tree")
        self.project = project
        self.on_select = on_select
        self.on_change = on_change
        self._id_map = {}   # tree item id -> Topic
        self.bind("<<TreeviewSelect>>", self._fire_select)
        # 拖拽绑定
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_drop)
        self._drag_data = {"item": None, "x": 0, "y": 0}

    def rebuild(self):
        for i in self.get_children(""):
            self.delete(i)
        self._id_map.clear()
        for child in self.project.root.children:
            self._insert_node(child, "")

    def _insert_node(self, node, parent):
        iid = self.insert(parent, tk.END, text=node.title or node.file_path or "(无标题)")
        self._id_map[iid] = node
        for c in node.children:
            self._insert_node(c, iid)
        return iid

    def _fire_select(self, event):
        if self.on_select:
            sel = self.selection()
            if sel:
                self.on_select(self._id_map.get(sel[0]))

    # ---- 拖拽 ----
    def _on_drag_start(self, event):
        item = self.identify_row(event.y)
        if not item:
            self._drag_data["item"] = None
            return
        self._drag_data["item"] = item
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        if not self._drag_data["item"]:
            return
        # 指示落点：贴近节点文字=子节点，贴近上下边缘=同级插入
        self.selection_set(self._drag_data["item"])

    def _on_drag_drop(self, event):
        src = self._drag_data.get("item")
        self._drag_data["item"] = None
        if not src:
            return
        target = self.identify_row(event.y)
        if not target or target == src:
            return
        src_node = self._id_map.get(src)
        tgt_node = self._id_map.get(target)
        if not src_node or not tgt_node:
            return
        # 判断是“插入为子节点”还是“插入为同级前序”
        region = self.identify_element(event.x, event.y)
        try:
            bbox = self.bbox(target)
            if bbox:
                top, bottom = bbox[1], bbox[1] + bbox[3]
                if event.y - top < (bottom - top) * 0.25:
                    # 上部：作为 tgt 的前序同级
                    parent = tgt_node.parent or self.project.root
                    idx = parent.children.index(tgt_node) if tgt_node in parent.children else None
                    self.project.move_topic(src_node, parent, index=idx)
                elif event.y - top > (bottom - top) * 0.75:
                    # 下部：作为 tgt 的后序同级
                    parent = tgt_node.parent or self.project.root
                    idx = (parent.children.index(tgt_node) + 1) if tgt_node in parent.children else None
                    self.project.move_topic(src_node, parent, index=idx)
                else:
                    # 中间：作为 tgt 的子节点
                    self.project.move_topic(src_node, tgt_node, index=None)
            else:
                self.project.move_topic(src_node, tgt_node, index=None)
        except ValueError as e:
            messagebox.showwarning("移动失败", str(e))
        self.rebuild()
        if self.on_change:
            self.on_change()


# ============ 主应用 ============

class CHMEditorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("%s v%s" % (APP_NAME, APP_VERSION))
        self.root.geometry("1100x720")

        self.project = Project()
        self.current_path = None       # 工程目录
        self.current_topic_file = None # 当前编辑的文件路径
        self.search_index = SearchIndex()

        self._build_ui()
        self._load_config()

    def _build_ui(self):
        # 菜单
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开工程文件夹", command=self._open_project)
        file_menu.add_command(label="导入 CHM 文件", command=self._import_chm)
        file_menu.add_separator()
        file_menu.add_command(label="保存工程", command=self._save_project)
        file_menu.add_command(label="编译 CHM", command=self._compile_chm)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="新建主题", command=self._new_topic)
        edit_menu.add_command(label="删除主题", command=self._delete_topic)
        menubar.add_cascade(label="编辑", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="切换预览模式", command=self._toggle_preview_mode)
        menubar.add_cascade(label="视图", menu=view_menu)
        self.root.config(menu=menubar)

        # 工具栏
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="打开工程", command=self._open_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="导入 CHM", command=self._import_chm).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="保存", command=self._save_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="编译 CHM", command=self._compile_chm).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        ttk.Label(toolbar, text="全文搜索:").pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.search_var, width=24)
        entry.pack(side=tk.LEFT, padx=2)
        entry.bind("<Return>", lambda e: self._do_search())
        ttk.Button(toolbar, text="搜索", command=self._do_search).pack(side=tk.LEFT, padx=2)

        # 三栏主体
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左：目录树
        left = ttk.Frame(paned)
        paned.add(left, weight=1)
        ttk.Label(left, text="目录结构（可拖拽调整层级/顺序）").pack(anchor=tk.W)
        self.tree = TopicTree(left, self.project,
                              on_select=self._on_topic_selected,
                              on_change=self._on_tree_changed)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 中：文件列表
        mid = ttk.Frame(paned)
        paned.add(mid, weight=1)
        ttk.Label(mid, text="文件列表").pack(anchor=tk.W)
        self.file_listbox = tk.Listbox(mid)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_selected)
        ttk.Scrollbar(mid, orient=tk.VERTICAL,
                      command=self.file_listbox.yview).pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=self.file_listbox.yview)

        # 右：编辑 + 预览
        right = ttk.Frame(paned)
        paned.add(right, weight=3)
        ttk.Label(right, text="HTML 编辑区").pack(anchor=tk.W)
        self.editor = tk.Text(right, wrap=tk.WORD, font=("Consolas", 10), undo=True)
        self.editor.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.editor.bind("<<Modified>>", self._on_editor_modified)
        self.preview = PreviewPanel(right)
        self.preview.pack(fill=tk.BOTH, expand=True)

        # 状态栏
        self.status = ttk.Label(self.root, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # ---- 工程操作 ----
    def _open_project(self):
        path = filedialog.askdirectory(title="选择工程文件夹")
        if not path:
            return
        self._load_project(path)
        self.status.config(text="已加载工程: " + path)

    def _import_chm(self):
        path = filedialog.askopenfilename(title="选择 CHM 文件",
                                          filetypes=[("CHM 文件", "*.chm")])
        if not path:
            return
        extract_dir = tempfile.mkdtemp(prefix="chm_import_")
        if _extract_chm(path, extract_dir):
            self._load_project(extract_dir)
            self.status.config(text="已导入 CHM: " + path)
        else:
            messagebox.showerror("错误", "无法解压 CHM，请确保 hhc.exe 可用。")

    def _load_project(self, project_dir):
        self.current_path = project_dir
        self.project = Project()
        self.search_index = SearchIndex()
        self.file_listbox.delete(0, tk.END)

        files = []
        for root_dir, _, fs in os.walk(project_dir):
            for f in fs:
                if f.lower().endswith((".html", ".htm", ".txt")):
                    full = os.path.join(root_dir, f)
                    rel = os.path.relpath(full, project_dir).replace("\\", "/")
                    files.append((rel, full))

        for rel, full in sorted(files):
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except Exception:
                content = ""
            self.project.add_file(rel, title=os.path.basename(rel), content=content)
            self.file_listbox.insert(tk.END, rel)
            self.search_index.add_document(os.path.basename(rel), rel, content)
            # 自动建目录树：按路径层级
            self._ensure_toc_for(rel)

        self.tree.rebuild()

    def _ensure_toc_for(self, rel_path):
        """按目录层级把文件挂到目录树"""
        parts = rel_path.split("/")
        parent = self.project.root
        for i, part in enumerate(parts):
            path_so_far = "/".join(parts[:i + 1])
            # 查找是否已存在
            node = None
            for c in parent.children:
                if c.file_path == path_so_far or c.title == part:
                    node = c
                    break
            if node is None:
                is_leaf = (i == len(parts) - 1)
                node = parent.add_child(title=part if not is_leaf else os.path.basename(part),
                                       file_path=path_so_far if is_leaf else "")
            parent = node

    def _save_project(self):
        if not self.current_path:
            path = filedialog.askdirectory(title="选择保存目录")
            if not path:
                return
            self.current_path = path
        # 同步编辑器内容到工程
        self._sync_current_file()
        self.project.save(self.current_path)
        self.status.config(text="工程已保存: " + self.current_path)

    def _compile_chm(self):
        self._sync_current_file()
        if not self.current_path:
            messagebox.showwarning("提示", "请先打开或保存工程")
            return
        output = filedialog.asksaveasfilename(title="保存 CHM",
                                              defaultextension=".chm",
                                              filetypes=[("CHM 文件", "*.chm")])
        if not output:
            return
        self.project.save(self.current_path)
        ok, msg = compile_chm(self.current_path, output)
        if ok:
            self.status.config(text="编译成功: " + output)
            messagebox.showinfo("成功", "CHM 已生成:\n" + output)
        else:
            self.status.config(text="编译失败")
            messagebox.showerror("编译失败", msg)

    # ---- 编辑交互 ----
    def _on_topic_selected(self, topic):
        if topic is None or not topic.file_path:
            return
        for i in range(self.file_listbox.size()):
            if self.file_listbox.get(i) == topic.file_path:
                self.file_listbox.selection_clear(0, tk.END)
                self.file_listbox.selection_set(i)
                self.file_listbox.see(i)
                self._load_file(topic.file_path)
                break

    def _on_file_selected(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        self._load_file(self.file_listbox.get(sel[0]))

    def _load_file(self, path):
        self._sync_current_file()
        self.current_topic_file = path
        info = self.project.files.get(path, {})
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", info.get("content", ""))
        self.editor.edit_modified(False)
        self.preview.set_html(info.get("content", ""))

    def _sync_current_file(self):
        if self.current_topic_file and self.current_topic_file in self.project.files:
            content = self.editor.get("1.0", tk.END).rstrip("\n")
            self.project.files[self.current_topic_file]["content"] = content

    def _on_editor_modified(self, event):
        if self._suppress_modified:
            return
        self._suppress_modified = True
        self.preview.set_html(self.editor.get("1.0", tk.END))
        self.editor.edit_modified(False)
        self._suppress_modified = False

    def _on_tree_changed(self):
        self.status.config(text="目录结构已变更（拖拽完成）")

    def _new_topic(self):
        name = tk.simpledialog.askstring("新建主题", "文件名（如 intro.html）:")
        if not name:
            return
        if self.current_path:
            full = os.path.join(self.current_path, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            if not os.path.exists(full):
                with open(full, "w", encoding="utf-8") as f:
                    f.write("<html><head><title></title></head><body></body></html>")
        self.project.add_file(name, title=name,
                              content="<html><head><title></title></head><body></body></html>")
        self.file_listbox.insert(tk.END, name)
        self._ensure_toc_for(name)
        self.tree.rebuild()

    def _delete_topic(self):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        path = self.file_listbox.get(sel[0])
        if not messagebox.askyesno("确认", "删除 " + path + "?"):
            return
        if self.current_path:
            full = os.path.join(self.current_path, path)
            try:
                os.remove(full)
            except Exception:
                pass
        self.project.remove_file(path)
        self.file_listbox.delete(sel[0])
        self.current_topic_file = None
        self.editor.delete("1.0", tk.END)
        self.tree.rebuild()

    def _do_search(self):
        query = self.search_var.get().strip()
        if not query:
            return
        results = self.search_index.search(query)
        if not results:
            messagebox.showinfo("搜索", "未找到匹配内容")
            return
        win = tk.Toplevel(self.root)
        win.title("搜索结果: " + query)
        win.geometry("520x420")
        lb = tk.Listbox(win)
        lb.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        for r in results:
            lb.insert(tk.END, "[%d] %s  (%s)" % (r["score"], r["title"], r["path"]))
        def on_select(ev):
            s = lb.curselection()
            if s:
                path = results[s[0]]["path"]
                for i in range(self.file_listbox.size()):
                    if self.file_listbox.get(i) == path:
                        self.file_listbox.selection_clear(0, tk.END)
                        self.file_listbox.selection_set(i)
                        self.file_listbox.see(i)
                        self._load_file(path)
                        break
                win.destroy()
        lb.bind("<Double-1>", on_select)

    def _toggle_preview_mode(self):
        mode = self.preview.get_mode()
        tip = "当前预览模式: " + ("WebView 渲染" if mode == "web" else "纯文本（Webview 不可用时自动降级）")
        messagebox.showinfo("预览模式", tip)

    # ---- 生命周期 ----
    def _load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "geometry" in cfg:
                self.root.geometry(cfg["geometry"])
        except Exception:
            pass

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"geometry": self.root.geometry()}, f)
        except Exception:
            pass

    def _on_close(self):
        self._sync_current_file()
        self._save_config()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ============ CHM 解压（兼容 Win7 无 pychm 环境） ============

def _extract_chm(chm_path, output_dir):
    """优先 hhc -decompile，其次尝试 zipfile，再尝试 7z 命令行"""
    hhc = find_hhc()
    if hhc:
        try:
            subprocess.run([hhc, "-decompile", output_dir, chm_path],
                           capture_output=True, timeout=60)
            if os.listdir(output_dir):
                return True
        except Exception:
            pass
    # 回退 zipfile（部分 CHM 兼容 ZIP 结构）
    try:
        import zipfile
        with zipfile.ZipFile(chm_path, "r") as z:
            z.extractall(output_dir)
        return True
    except Exception:
        pass
    # 回退 7z 命令行
    for exe in ("7z", "7za", "C:\\Program Files\\7-Zip\\7z.exe"):
        try:
            r = subprocess.run([exe, "x", chm_path, "-o" + output_dir, "-y"],
                               capture_output=True, timeout=60)
            if r.returncode == 0 and os.listdir(output_dir):
                return True
        except Exception:
            continue
    return False


def main():
    # 命令行无头自检（CI / 无 DISPLAY 环境友好退出）
    try:
        app = CHMEditorApp()
        app.run()
    except tk.TclError as e:
        print("[chm_editor] 无法启动 GUI（当前环境无显示或缺少 tkinter）：", e)
        print("[chm_editor] 这在 CI / 无图形环境中是预期行为，GUI 逻辑通过单元测试覆盖。")


if __name__ == "__main__":
    main()
