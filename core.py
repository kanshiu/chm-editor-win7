# -*- coding: utf-8 -*-
"""
CHM Editor - 核心模型 (Win7 兼容)
负责工程数据结构、全文搜索倒排索引、HHP/HHC/HHK 生成、hhc.exe 查找
"""

import os
import re
import sys
import json
import subprocess


# ============ 目录树节点 ============

class Topic:
    """目录树中的一个节点（对应 HHC 里的一个 <LI><OBJECT>...</OBJECT></LI>）"""
    def __init__(self, title="", file_path="", topic_id=None):
        self.title = title
        self.file_path = file_path  # 相对工程根目录的路径
        self.children = []          # [Topic, ...]
        self.parent = None
        self._topic_id = topic_id   # 可选：hhc 里的 <param name="ID">
        self._id_counter = 0

    def _next_id(self):
        self._id_counter += 1
        return "ID%d" % self._id_counter

    def add_child(self, title, file_path="", topic_id=None):
        """追加一个子节点，返回新节点"""
        node = Topic(title=title, file_path=file_path,
                     topic_id=topic_id or self._next_id())
        node.parent = self
        self.children.append(node)
        return node

    def move_child(self, node, target_parent, index=None):
        """把一个子节点移动到 target_parent 下（index=None 表示追加到末尾）"""
        if node is self:
            raise ValueError("不能把节点移动到自己下面")
        # 防环：target 不能是 node 的后代
        cur = target_parent
        while cur is not None:
            if cur is node:
                raise ValueError("不能移动到自身后代节点下")
            cur = cur.parent
        # 从原父节点移除
        if node.parent is not None:
            node.parent.children.remove(node)
        # 插入到新父节点
        if index is None or index >= len(target_parent.children):
            target_parent.children.append(node)
        else:
            target_parent.children.insert(index, node)
        node.parent = target_parent


# ============ 全文搜索索引 ============

class SearchIndex:
    """倒排索引：中文按字/2-gram、英文按词，带相关度打分"""
    def __init__(self):
        self.index = {}   # term -> {doc_id: [positions]}
        self.docs = {}    # doc_id -> {"title", "path", "content"}
        self._counter = 0

    def add_document(self, title, path, content):
        self._counter += 1
        doc_id = self._counter
        self.docs[doc_id] = {
            "title": title,
            "path": path,
            "content": (content or "")[:5000],
        }
        text = (title or "") + "\n" + (content or "")
        for pos, term in enumerate(self._tokenize(text)):
            self.index.setdefault(term, {})
            self.index[term].setdefault(doc_id, []).append(pos)

    def _tokenize(self, text):
        """英文单词 + 中文单字 + 中文 2-gram"""
        terms = []
        eng = re.findall(r"[A-Za-z]+", text)
        terms.extend(w.lower() for w in eng)
        cjk = re.findall(r"[\u4e00-\u9fff]", text)
        terms.extend(cjk)
        for i in range(len(cjk) - 1):
            terms.append(cjk[i] + cjk[i + 1])
        return terms

    def search(self, query, top_n=20):
        query = (query or "").strip()
        if not query:
            return []
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        scores = {}
        for term in query_terms:
            if term not in self.index:
                continue
            for doc_id, positions in self.index[term].items():
                scores[doc_id] = scores.get(doc_id, 0) + len(positions)
        results = []
        for doc_id in sorted(scores, key=lambda d: -scores[d])[:top_n]:
            doc = dict(self.docs[doc_id])
            doc["score"] = scores[doc_id]
            doc["highlight"] = self._make_snippet(doc["content"], query_terms)
            results.append(doc)
        return results

    def _make_snippet(self, content, terms, window=40):
        content = (content or "").replace("\n", " ")
        content = re.sub(r"<[^>]+>", "", content)
        content = re.sub(r"\s+", " ", content).strip()
        if not content:
            return ""
        lower = content.lower()
        # 找一个命中位置
        pos = -1
        for t in terms:
            idx = lower.find(t.lower())
            if idx >= 0:
                pos = idx
                break
        if pos < 0:
            return content[: 2 * window]
        start = max(0, pos - window)
        end = min(len(content), pos + window)
        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
        return snippet


# ============ 工程对象 ============

class Project:
    """一个 CHM 工程：根节点 + 文件内容映射"""

    def __init__(self, root_title="Table of Contents"):
        self.root = Topic(title=root_title)
        self.files = {}        # path -> {"title", "content"}
        self.default_topic = None

    # ---- 文件管理 ----
    def add_file(self, path, title=None, content=""):
        self.files[path] = {
            "title": title or os.path.basename(path),
            "content": content,
        }
        if self.default_topic is None:
            self.default_topic = path
        return self.files[path]

    def remove_file(self, path):
        if path in self.files:
            del self.files[path]
        if self.default_topic == path:
            self.default_topic = next(iter(self.files), None)

    # ---- 目录树操作（供拖拽使用）----
    def move_topic(self, node, target_parent, index=None):
        """移动目录节点，含防环校验"""
        self.root.move_child(node, target_parent, index)

    # ---- 序列化：生成 HHP / HHC / HHK ----
    def to_hhp(self, project_dir, output_chm="output.chm"):
        files = sorted(self.files.keys())
        default = self.default_topic or (files[0] if files else "index.html")
        lines = []
        lines.append("[OPTIONS]")
        lines.append("Compatibility=1.1 or later")
        lines.append("Compiled file=" + output_chm)
        lines.append("Contents file=table_of_contents.hhc")
        lines.append("Index file=table_of_contents.hhk")
        lines.append("Default topic=" + default)
        lines.append("Full-text search=Yes")
        lines.append("Language=0x804 中文(中国)")
        lines.append("")
        lines.append("[FILES]")
        for f in files:
            lines.append(f)
        lines.append("")
        lines.append("[INFOTYPES]")
        lines.append("")
        return "\n".join(lines)

    def to_hhc(self):
        """生成目录文件（HHC）XML"""
        parts = []
        parts.append('<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">')
        parts.append("<HTML>")
        parts.append("<HEAD></HEAD>")
        parts.append('<BODY><OBJECT type="text/site properties">')
        parts.append('<param name="FrameName" value="right">')
        parts.append("</OBJECT>")
        parts.append("<UL>")
        for child in self.root.children:
            parts.append(self._topic_to_hhc(child))
        parts.append("</UL></BODY></HTML>")
        return "\n".join(parts)

    def _topic_to_hhc(self, node):
        out = ["<LI><OBJECT type=\"text/sitemap\">"]
        out.append('<param name="Name" value="%s">' % _esc(node.title))
        if node.file_path:
            out.append('<param name="Local" value="%s">' % _esc(node.file_path))
        if node._topic_id:
            out.append('<param name="ID" value="%s">' % _esc(str(node._topic_id)))
        out.append("</OBJECT>")
        if node.children:
            out.append("<UL>")
            for c in node.children:
                out.append(self._topic_to_hhc(c))
            out.append("</UL>")
        out.append("</LI>")
        return "\n".join(out)

    def to_hhk(self):
        """生成索引文件（HHK）：基于文件标题与关键词"""
        parts = []
        parts.append('<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">')
        parts.append("<HTML><HEAD></HEAD><BODY>")
        parts.append("<UL>")
        entries = []
        for path, info in self.files.items():
            title = info.get("title") or os.path.basename(path)
            entries.append((title, path))
            # 抽取前几个中文词作为关键词
            words = set(re.findall(r"[\u4e00-\u9fff]{2,}", info.get("content", ""))[:5])
            for w in words:
                entries.append((w, path))
        for title, path in sorted(entries):
            parts.append('<LI><OBJECT type="text/sitemap">')
            parts.append('<param name="Name" value="%s">' % _esc(title))
            parts.append('<param name="Local" value="%s">' % _esc(path))
            parts.append("</OBJECT></LI>")
        parts.append("</UL></BODY></HTML>")
        return "\n".join(parts)

    def save(self, project_dir):
        """把工程落盘：文件内容 + project.json + hhp/hhc/hhk"""
        os.makedirs(project_dir, exist_ok=True)
        for path, info in self.files.items():
            full = os.path.join(project_dir, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", errors="ignore") as fh:
                fh.write(info.get("content", ""))
        # 工程元数据
        meta = {
            "root_title": self.root.title,
            "default_topic": self.default_topic,
            "toc": self._serialize_toc(self.root),
            "files": {p: {"title": info.get("title")} for p, info in self.files.items()},
        }
        with open(os.path.join(project_dir, "project.json"), "w", encoding="utf-8") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=2)
        # 标准工程文件
        with open(os.path.join(project_dir, "project.hhp"), "w", encoding="gb2312",
                  errors="ignore") as fh:
            fh.write(self.to_hhp(project_dir))
        with open(os.path.join(project_dir, "table_of_contents.hhc"), "w",
                  encoding="gb2312", errors="ignore") as fh:
            fh.write(self.to_hhc())
        with open(os.path.join(project_dir, "table_of_contents.hhk"), "w",
                  encoding="gb2312", errors="ignore") as fh:
            fh.write(self.to_hhk())

    def _serialize_toc(self, node):
        return {
            "title": node.title,
            "file_path": node.file_path,
            "topic_id": node._topic_id,
            "children": [self._serialize_toc(c) for c in node.children],
        }


def _esc(s):
    """XML 属性转义"""
    s = (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = s.replace('"', "&quot;").replace("\n", " ")
    return s


# ============ hhc.exe 查找（Win7 兼容路径） ============

def find_hhc():
    """
    按优先级查找 hhc.exe：
    1) 程序同目录 / htmlhelp 子目录（便携，推荐）
    2) C:\Program Files (x86)\HTML Help Workshop\
    3) C:\Program Files (x86)\Microsoft HTML Help\  (Win7 常见)
    """
    candidates = []
    # 1. 脚本/EXE 所在目录
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    candidates.append(os.path.join(base, "hhc.exe"))
    candidates.append(os.path.join(base, "htmlhelp", "hhc.exe"))
    # 2 & 3. 系统安装路径
    candidates.append(os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "HTML Help Workshop", "hhc.exe"))
    candidates.append(os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Microsoft HTML Help", "hhc.exe"))
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def compile_chm(project_dir, output_chm):
    """调用 hhc.exe 编译工程，返回 (ok, message)"""
    hhc = find_hhc()
    if not hhc:
        return False, ("未找到 hhc.exe。请将 HTML Help Workshop 的 hhc.exe "
                       "放到程序同目录，或安装 HTML Help Workshop。")
    hhp_path = os.path.join(project_dir, "project.hhp")
    if not os.path.exists(hhp_path):
        return False, "工程目录下不存在 project.hhp"
    try:
        result = subprocess_run([hhc, hhp_path])
        if os.path.exists(output_chm):
            return True, "编译成功"
        return False, (result.get("stderr") or result.get("stdout") or "未知错误")
    except Exception as e:
        return False, str(e)


def subprocess_run(cmd, timeout=120):
    """兼容 Python 2/3 的 subprocess 调用"""
    import subprocess
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {"stdout": r.stdout or "", "stderr": r.stderr or ""}
    except TypeError:
        # 老版本没有 text= 参数
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        def dec(b):
            try:
                return b.decode("gb2312", "ignore")
            except Exception:
                return ""
        return {"stdout": dec(r.stdout), "stderr": dec(r.stderr)}
