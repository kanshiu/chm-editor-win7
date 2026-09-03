# -*- coding: utf-8 -*-
"""
CHM Editor - Win7 Portable
Visual CHM editor with full-text search
"""

import os
import sys
import json
import re
import tkinter as tk
import tkinter.simpledialog
from tkinter import ttk, filedialog, messagebox, scrolledtext
import tempfile
import subprocess
import shutil
import zipfile

# ============ Constants ============
APP_NAME = "CHM Editor"
APP_VERSION = "1.0.0"

# ============ Utility ============

def resource_path(relative_path):
    """Get absolute path to resource (compatible with PyInstaller)"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def extract_chm(chm_path, output_dir):
    """Extract CHM file using hhc.exe or fallback to zipfile"""
    hhc_path = resource_path("hhc.exe")
    if os.path.exists(hhc_path):
        cmd = [hhc_path, "-decompile", output_dir, chm_path]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            return True
        except:
            pass
    try:
        with zipfile.ZipFile(chm_path, 'r') as z:
            z.extractall(output_dir)
        return True
    except:
        pass
    return False

def build_chm(project_dir, output_chm, hhp_content):
    """Compile CHM using hhc.exe"""
    hhc_path = resource_path("hhc.exe")
    if not os.path.exists(hhc_path):
        return False, "hhc.exe not found. Put hhc.exe in the same folder as the program."
    
    hhp_path = os.path.join(project_dir, "project.hhp")
    with open(hhp_path, 'w', encoding='gb2312') as f:
        f.write(hhp_content)
    
    try:
        result = subprocess.run(
            [hhc_path, hhp_path],
            capture_output=True, text=True, timeout=120,
            encoding='gb2312', errors='ignore'
        )
        # hhc.exe returns non-zero even on success, so check file existence instead
        if os.path.exists(output_chm) and os.path.getsize(output_chm) > 0:
            return True, "Compilation successful"
        else:
            output = result.stdout + result.stderr
            return False, output[-500:] if output else "Unknown error"
    except subprocess.TimeoutExpired:
        return False, "Compilation timed out (120s)"
    except Exception as e:
        return False, str(e)

# ============ Full-text Search ============

class SearchIndex:
    def __init__(self):
        self.index = {}
        self.docs = {}
        self.doc_counter = 0

    def add_document(self, title, path, content):
        self.doc_counter += 1
        doc_id = self.doc_counter
        self.docs[doc_id] = {
            'title': title,
            'path': path,
            'content': content[:5000]
        }
        text = title + " " + content
        words = self._tokenize(text)
        for pos, word in enumerate(words):
            if word not in self.index:
                self.index[word] = {}
            if doc_id not in self.index[word]:
                self.index[word][doc_id] = []
            self.index[word][doc_id].append(pos)

    def _tokenize(self, text):
        words = []
        eng_words = re.findall(r'[a-zA-Z]+', text)
        words.extend([w.lower() for w in eng_words])
        chinese = re.findall(r'[\u4e00-\u9fff]', text)
        for i in range(len(chinese) - 1):
            words.append(chinese[i] + chinese[i+1])
        words.extend(chinese)
        return words

    def search(self, query, top_n=20):
        query_words = self._tokenize(query)
        scores = {}
        for word in query_words:
            if word in self.index:
                for doc_id, positions in self.index[word].items():
                    if doc_id not in scores:
                        scores[doc_id] = 0
                    scores[doc_id] += len(positions)
        results = []
        for doc_id, score in sorted(scores.items(), key=lambda x: -x[1])[:top_n]:
            doc = self.docs[doc_id].copy()
            doc['score'] = score
            results.append(doc)
        return results

# ============ Main App ============

class CHMEditorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1100x700")
        
        self.current_project = None
        self.current_file = None
        self.files_tree = {}
        self.search_index = SearchIndex()
        
        self._build_ui()
        
    def _build_ui(self):
        # Menu
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open CHM", command=self._open_chm)
        file_menu.add_command(label="Open Project Folder", command=self._open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Compile CHM", command=self._compile_chm)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="New File", command=self._new_file)
        edit_menu.add_command(label="Delete File", command=self._delete_file)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        self.root.config(menu=menubar)
        
        # Toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        ttk.Button(toolbar, text="Open CHM", command=self._open_chm).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Compile CHM", command=self._compile_chm).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill=tk.Y)
        
        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT, padx=2)
        search_entry.bind('<Return>', lambda e: self._do_search())
        ttk.Button(toolbar, text="Go", command=self._do_search).pack(side=tk.LEFT, padx=2)
        
        # Three-pane layout
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left: Tree
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)
        ttk.Label(left_frame, text="Directory").pack(anchor=tk.W)
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_frame, show='tree')
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=tree_scroll.set)
        
        # Middle: File list
        mid_frame = ttk.Frame(paned)
        paned.add(mid_frame, weight=1)
        ttk.Label(mid_frame, text="Files").pack(anchor=tk.W)
        self.file_listbox = tk.Listbox(mid_frame)
        self.file_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.file_listbox.bind('<<ListboxSelect>>', self._on_file_select)
        mid_scroll = ttk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        mid_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=mid_scroll.set)
        
        # Right: Editor + Preview
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        edit_label_frame = ttk.Frame(right_frame)
        edit_label_frame.pack(fill=tk.X)
        ttk.Label(edit_label_frame, text="Editor").pack(side=tk.LEFT)
        ttk.Button(edit_label_frame, text="Save", command=self._save_current).pack(side=tk.RIGHT, padx=2)
        self.editor = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=('Consolas', 10))
        self.editor.pack(fill=tk.BOTH, expand=True, pady=(2, 5))
        ttk.Label(right_frame, text="Preview").pack(anchor=tk.W)
        self.preview = scrolledtext.ScrolledText(right_frame, wrap=tk.WORD, font=('SimSun', 10), state=tk.DISABLED)
        self.preview.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        
        # Status bar
        self.status = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.search_results_window = None
        
    def _open_chm(self):
        path = filedialog.askopenfilename(title="Select CHM", filetypes=[("CHM", "*.chm")])
        if not path:
            return
        self.status.config(text="Extracting...")
        self.root.update()
        extract_dir = tempfile.mkdtemp(prefix="chm_import_")
        ok = extract_chm(path, extract_dir)
        if ok:
            self.current_project = extract_dir
            self._load_project(extract_dir)
            self.status.config(text="Opened: %s" % path)
        else:
            messagebox.showerror("Error", "Failed to extract CHM.")
            self.status.config(text="Failed")
    
    def _open_project(self):
        path = filedialog.askdirectory(title="Select Project Folder")
        if not path:
            return
        self.current_project = path
        self._load_project(path)
        self.status.config(text="Loaded: %s" % path)
    
    def _load_project(self, project_dir):
        self.files_tree.clear()
        self.search_index = SearchIndex()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.file_listbox.delete(0, tk.END)
        
        html_files = []
        for root_dir, dirs, files in os.walk(project_dir):
            for f in files:
                if f.lower().endswith(('.html', '.htm', '.txt')):
                    full = os.path.join(root_dir, f)
                    rel = os.path.relpath(full, project_dir)
                    html_files.append((rel, full))
        
        for rel, full in sorted(html_files):
            self.file_listbox.insert(tk.END, rel)
            try:
                with open(full, 'r', encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
            except:
                content = ""
            self.files_tree[rel] = {'title': os.path.basename(rel), 'content': content}
            self.search_index.add_document(os.path.basename(rel), rel, content)
        
        for rel, _ in sorted(html_files):
            parts = rel.split(os.sep)
            parent = ''
            for i, part in enumerate(parts):
                item_id = os.sep.join(parts[:i+1])
                if not self.tree.exists(item_id):
                    self.tree.insert(parent if parent else '', tk.END, text=part, values=[item_id])
                parent = item_id
    
    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item = self.tree.item(sel[0])
        values = item.get('values', [])
        if values:
            path = values[0]
            for i in range(self.file_listbox.size()):
                if self.file_listbox.get(i) == path:
                    self.file_listbox.selection_clear(0, tk.END)
                    self.file_listbox.selection_set(i)
                    self.file_listbox.see(i)
                    self._load_file_to_editor(path)
                    break
    
    def _on_file_select(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        self._load_file_to_editor(self.file_listbox.get(sel[0]))
    
    def _load_file_to_editor(self, path):
        if path in self.files_tree:
            self.current_file = path
            content = self.files_tree[path]['content']
            self.editor.delete('1.0', tk.END)
            self.editor.insert('1.0', content)
            self._update_preview(content)
    
    def _update_preview(self, html_content):
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text).strip()
        self.preview.config(state=tk.NORMAL)
        self.preview.delete('1.0', tk.END)
        self.preview.insert('1.0', text[:3000])
        self.preview.config(state=tk.DISABLED)
    
    def _save_current(self):
        if not self.current_file:
            return
        content = self.editor.get('1.0', tk.END).rstrip()
        self.files_tree[self.current_file]['content'] = content
        if self.current_project:
            full = os.path.join(self.current_project, self.current_file)
            try:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status.config(text="Saved: %s" % self.current_file)
            except Exception as e:
                messagebox.showerror("Error", str(e))
    
    def _new_file(self):
        name = tkinter.simpledialog.askstring("New File", "Filename:")
        if not name:
            return
        if self.current_project:
            full = os.path.join(self.current_project, name)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'w', encoding='utf-8') as f:
                f.write('<html><head><title></title></head><body></body></html>')
            self.file_listbox.insert(tk.END, name)
            self.files_tree[name] = {'title': name, 'content': '<html><head><title></title></head><body></body></html>'}
    
    def _delete_file(self):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        path = self.file_listbox.get(sel[0])
        if messagebox.askyesno("Confirm", "Delete %s?" % path):
            if self.current_project:
                full = os.path.join(self.current_project, path)
                try:
                    os.remove(full)
                except:
                    pass
            self.file_listbox.delete(sel[0])
            del self.files_tree[path]
            self.current_file = None
            self.editor.delete('1.0', tk.END)
    
    def _do_search(self):
        query = self.search_var.get().strip()
        if not query:
            return
        results = self.search_index.search(query)
        if not results:
            messagebox.showinfo("Search", "No results found")
            return
        if self.search_results_window:
            self.search_results_window.destroy()
        self.search_results_window = tk.Toplevel(self.root)
        self.search_results_window.title("Search Results: %s" % query)
        self.search_results_window.geometry("500x400")
        listbox = tk.Listbox(self.search_results_window)
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(self.search_results_window, orient=tk.VERTICAL, command=listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scrollbar.set)
        for r in results:
            listbox.insert(tk.END, "[%d] %s  (%s)" % (r['score'], r['title'], r['path']))
        def on_select(event):
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                path = results[idx]['path']
                for i in range(self.file_listbox.size()):
                    if self.file_listbox.get(i) == path:
                        self.file_listbox.selection_clear(0, tk.END)
                        self.file_listbox.selection_set(i)
                        self.file_listbox.see(i)
                        self._load_file_to_editor(path)
                        break
                self.search_results_window.destroy()
        listbox.bind('<Double-1>', on_select)
    
    def _compile_chm(self):
        if not self.current_project:
            messagebox.showwarning("Warning", "Please open a project first")
            return
        output = filedialog.asksaveasfilename(title="Save CHM", defaultextension=".chm", filetypes=[("CHM", "*.chm")])
        if not output:
            return
        hhp = self._generate_hhp()
        self.status.config(text="Compiling...")
        self.root.update()
        ok, msg = build_chm(self.current_project, output, hhp)
        if ok:
            self.status.config(text="Compiled: %s" % output)
            messagebox.showinfo("Success", "CHM saved to:\n%s" % output)
        else:
            self.status.config(text="Failed")
            messagebox.showerror("Failed", msg)
    
    def _generate_hhp(self):
        files = list(self.files_tree.keys())
        default = files[0] if files else "index.html"
        hhp = "[OPTIONS]\n"
        hhp += "Compatibility=1.1 or later\n"
        hhp += "Compiled file=output.chm\n"
        hhp += "Default topic=%s\n" % default
        hhp += "Full-text search=Yes\n"
        hhp += "Language=0x804 Chinese (Simplified)\n\n"
        hhp += "[FILES]\n"
        for f in files:
            hhp += "%s\n" % f
        hhp += "\n[INFOTYPES]\n"
        return hhp
    
    def run(self):
        self.root.mainloop()

# ============ Entry Point ============

if __name__ == '__main__':
    app = CHMEditorApp()
    app.run()
