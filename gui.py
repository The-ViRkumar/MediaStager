"""MediaStager GUI — Tkinter/ttk, themed with sv_ttk."""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

AUTHOR_URL = "https://github.com/The-ViRkumar"

import sv_ttk

import core

COLUMNS = ("include", "folder", "original", "proposed", "type")
HEADINGS = {
    "include": "Rename?", "folder": "Folder", "original": "Original Name",
    "proposed": "Proposed Name", "type": "Type",
}
QUEUE_COLUMNS = ("folder", "mode", "suggested", "status")
QUEUE_HEADINGS = {"folder": "Folder", "mode": "Mode", "suggested": "Suggested Folder Name", "status": "Status"}


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: "MediaStagerApp"):
        super().__init__(parent)
        self.title("TMDB Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="TMDB API Key:").grid(row=0, column=0, padx=12, pady=12, sticky="w")
        self.key_var = tk.StringVar(value=parent.tmdb_api_key)
        entry = ttk.Entry(self, textvariable=self.key_var, width=42, show="*")
        entry.grid(row=0, column=1, padx=(0, 12), pady=12)

        ttk.Label(self, text="Get a free key at themoviedb.org -> Settings -> API",
                  foreground="#888888").grid(row=1, column=0, columnspan=2, padx=12, sticky="w")
        ttk.Label(self, text="Used for this session only — not saved to disk.",
                  foreground="#888888").grid(row=2, column=0, columnspan=2, padx=12, sticky="w")

        btns = ttk.Frame(self)
        btns.grid(row=3, column=0, columnspan=2, pady=(6, 12))
        ttk.Button(btns, text="Save", command=self._save).pack(side="left", padx=6)
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=6)
        entry.focus_set()

    def _save(self):
        self.master.tmdb_api_key = self.key_var.get().strip()
        self.destroy()


class MediaStagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaStager")
        self.minsize(920, 600)
        self._set_icon()
        self._center_window(1200, 760)

        self.cfg = core.load_config()
        self.tmdb_api_key = ""  # session-only, never written to config.json
        self.dark = tk.BooleanVar(value=self.cfg.get("dark_mode", True))
        sv_ttk.set_theme("dark" if self.dark.get() else "light")

        self.queue_items: list[core.QueueItem] = []
        self.rows: list[core.Row] = []
        self._work_queue: "queue.Queue" = queue.Queue()

        self._build_top_bar()
        self._build_options_bar()
        self._build_queue_panel()
        self._build_action_bar()
        self._build_table()
        self._build_bottom_bar()

    def _center_window(self, width: int, height: int):
        x = (self.winfo_screenwidth() - width) // 2
        y = (self.winfo_screenheight() - height) // 2
        self.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")

    def _set_icon(self):
        base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
        assets = base / "assets"
        try:
            self.iconbitmap(str(assets / "icon.ico"))
        except tk.TclError:
            pass
        try:
            self._icon_image = tk.PhotoImage(file=str(assets / "icon.png"))
            self.iconphoto(True, self._icon_image)
        except tk.TclError:
            pass

    # -- layout -------------------------------------------------------

    def _build_top_bar(self):
        bar = ttk.Frame(self, padding=(12, 12, 12, 4))
        bar.pack(fill="x")

        ttk.Label(bar, text="Target Directory:").pack(side="left")
        self.path_var = tk.StringVar()
        self.path_combo = ttk.Combobox(bar, textvariable=self.path_var,
                                        values=self.cfg.get("recent_dirs", []), width=60)
        self.path_combo.pack(side="left", padx=8, fill="x", expand=True)

        ttk.Button(bar, text="Browse...", command=self._browse).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="+ Add to Queue", command=self._add_to_queue).pack(side="left", padx=(4, 4))
        ttk.Checkbutton(bar, text="Dark Mode", variable=self.dark, command=self._toggle_theme,
                         style="Switch.TCheckbutton").pack(side="left", padx=(12, 0))

    def _build_options_bar(self):
        bar = ttk.Frame(self, padding=(12, 4, 12, 4))
        bar.pack(fill="x")

        ttk.Label(bar, text="Mode:").pack(side="left")
        self.mode = tk.StringVar(value=core.MODE_SERIES)
        ttk.Radiobutton(bar, text="Series", variable=self.mode, value=core.MODE_SERIES).pack(side="left", padx=(4, 0))
        ttk.Radiobutton(bar, text="Movie", variable=self.mode, value=core.MODE_MOVIE).pack(side="left", padx=(4, 12))

        self.sync_sidecars = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Sync Sidecars (.srt, .nfo, ...)",
                         variable=self.sync_sidecars).pack(side="left")

        self.fetch_tmdb = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Fetch Titles (TMDB)", variable=self.fetch_tmdb,
                         command=self._on_tmdb_toggle).pack(side="left", padx=(16, 0))

        ttk.Label(bar, text="Title Override:").pack(side="left", padx=(16, 4))
        self.title_override = tk.StringVar()
        ttk.Entry(bar, textvariable=self.title_override, width=22).pack(side="left")

    def _build_queue_panel(self):
        frame = ttk.LabelFrame(self, text="Batch Queue", padding=(8, 4))
        frame.pack(fill="x", padx=12, pady=(4, 4))

        self.queue_tree = ttk.Treeview(frame, columns=QUEUE_COLUMNS, show="headings", height=4)
        for col in QUEUE_COLUMNS:
            self.queue_tree.heading(col, text=QUEUE_HEADINGS[col])
        self.queue_tree.column("folder", width=320)
        self.queue_tree.column("mode", width=70, anchor="center", stretch=False)
        self.queue_tree.column("suggested", width=320)
        self.queue_tree.column("status", width=140, anchor="center", stretch=False)
        self.queue_tree.pack(side="left", fill="x", expand=True)
        self.queue_tree.bind("<Double-1>", self._on_queue_double_click)

        btns = ttk.Frame(frame)
        btns.pack(side="left", padx=(8, 0), fill="y")
        ttk.Button(btns, text="Remove Selected", command=self._remove_from_queue).pack(fill="x", pady=1)
        ttk.Button(btns, text="Clear Queue", command=self._clear_queue).pack(fill="x", pady=1)
        self.rename_folders = tk.BooleanVar(value=False)
        ttk.Checkbutton(btns, text="Also rename folders", variable=self.rename_folders).pack(fill="x", pady=(6, 1))
        ttk.Label(frame, text="Double-click 'Suggested Folder Name' to copy it.",
                  foreground="#888888").pack(side="left", padx=(8, 0))

    def _build_action_bar(self):
        bar = ttk.Frame(self, padding=(12, 4, 12, 8))
        bar.pack(fill="x")

        ttk.Button(bar, text="Scan Directory", command=self._scan,
                   style="Accent.TButton").pack(side="left")

        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=140)
        self.progress.pack(side="left", padx=12)

        ttk.Label(bar, text="Filter:").pack(side="left", padx=(16, 4))
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._refresh_table())
        ttk.Entry(bar, textvariable=self.filter_var, width=24).pack(side="left")

    def _build_table(self):
        frame = ttk.Frame(self, padding=(12, 0, 12, 0))
        frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(frame, columns=COLUMNS, show="headings", selectmode="extended")
        for col in COLUMNS:
            self.tree.heading(col, text=HEADINGS[col])
        self.tree.column("include", width=70, anchor="center", stretch=False)
        self.tree.column("folder", width=150, stretch=False)
        self.tree.column("original", width=320)
        self.tree.column("proposed", width=360)
        self.tree.column("type", width=80, anchor="center", stretch=False)

        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("excluded", foreground="#888888")
        self.tree.tag_configure("sidecar", foreground="#9a9a9a")
        self.tree.tag_configure("error", foreground="#e06060")

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _build_bottom_bar(self):
        bar = ttk.Frame(self, padding=12)
        bar.pack(fill="x")

        ttk.Button(bar, text="Execute Rename", command=self._execute_rename,
                   style="Accent.TButton").pack(side="left")
        ttk.Button(bar, text="Undo Last Batch", command=self._undo).pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=16)

        author = ttk.Label(bar, text="The.ViRkumar", foreground="#3b82f6", cursor="hand2",
                           font=("TkDefaultFont", 9, "underline"))
        author.pack(side="right")
        author.bind("<Button-1>", lambda _e: webbrowser.open(AUTHOR_URL))
        ttk.Label(bar, text="MediaStager by ", foreground="#888888").pack(side="right")

    # -- helpers --------------------------------------------------------

    def _toggle_theme(self):
        sv_ttk.set_theme("dark" if self.dark.get() else "light")
        self.cfg["dark_mode"] = self.dark.get()
        core.save_config(self.cfg)

    def _on_tmdb_toggle(self):
        if self.fetch_tmdb.get() and not self.tmdb_api_key:
            SettingsDialog(self)
            if not self.tmdb_api_key:
                self.fetch_tmdb.set(False)

    def _browse(self):
        directory = filedialog.askdirectory()
        if directory:
            self.path_var.set(directory)

    # -- queue ------------------------------------------------------------

    def _queued_paths(self) -> set[str]:
        return {str(item.path.resolve()) for item in self.queue_items}

    def _add_to_queue(self) -> bool:
        directory = self.path_var.get().strip()
        if not directory:
            return False
        path = Path(directory)
        if not path.exists():
            messagebox.showerror("MediaStager", f"Directory not found:\n{directory}")
            return False
        if str(path.resolve()) in self._queued_paths():
            self.path_var.set("")
            return True

        self.cfg = core.remember_directory(self.cfg, directory)
        core.save_config(self.cfg)
        self.path_combo["values"] = self.cfg.get("recent_dirs", [])

        self.queue_items.append(core.QueueItem(
            path=path,
            mode=self.mode.get(),
            sync_sidecars=self.sync_sidecars.get(),
            use_tmdb=self.fetch_tmdb.get(),
            title_override=self.title_override.get().strip() or None,
        ))
        self.path_var.set("")
        self._refresh_queue_tree()
        return True

    def _remove_from_queue(self):
        selected = {int(i) for i in self.queue_tree.selection()}
        if not selected:
            return
        self.queue_items = [item for i, item in enumerate(self.queue_items) if i not in selected]
        self._refresh_queue_tree()

    def _clear_queue(self):
        self.queue_items = []
        self.rows = []
        self._refresh_queue_tree()
        self._refresh_table()
        self.status_var.set("Queue cleared.")

    def _refresh_queue_tree(self):
        self.queue_tree.delete(*self.queue_tree.get_children())
        for idx, item in enumerate(self.queue_items):
            mode_label = "Movie" if item.mode == core.MODE_MOVIE else "Series"
            self.queue_tree.insert("", "end", iid=str(idx), values=(
                str(item.path), mode_label, item.folder_name or "—", item.status,
            ))

    def _on_queue_double_click(self, event):
        region = self.queue_tree.identify_region(event.x, event.y)
        col = self.queue_tree.identify_column(event.x)
        item_id = self.queue_tree.identify_row(event.y)
        if region != "cell" or col != "#3" or not item_id:
            return
        text = self.queue_items[int(item_id)].folder_name
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.status_var.set(f"Copied '{text}' to clipboard.")

    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if not item_id or col != "#1":
            return
        idx = int(item_id)
        self.rows[idx].excluded = not self.rows[idx].excluded
        self._refresh_table()

    def _on_tree_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        col = self.tree.identify_column(event.x)
        item_id = self.tree.identify_row(event.y)
        if region != "cell" or col != "#4" or not item_id:
            return
        idx = int(item_id)
        self._edit_proposed_name(item_id, idx)

    def _edit_proposed_name(self, item_id: str, idx: int):
        x, y, width, height = self.tree.bbox(item_id, "proposed")
        var = tk.StringVar(value=self.rows[idx].proposed)
        entry = ttk.Entry(self.tree, textvariable=var)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        entry.select_range(0, "end")

        def commit(_event=None):
            new_name = var.get().strip()
            if new_name:
                self.rows[idx].proposed = new_name
            entry.destroy()
            self._refresh_table()

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", lambda _e: entry.destroy())

    def _folder_label(self, row: core.Row) -> str:
        for item in self.queue_items:
            try:
                row.original.relative_to(item.path)
                return item.path.name
            except ValueError:
                continue
        return ""

    # -- scan / rename / undo -------------------------------------------

    def _scan(self):
        self._add_to_queue()  # flush whatever's in the text field into the queue too

        pending = [item for item in self.queue_items if item.status == "Pending"]
        if not pending:
            messagebox.showinfo("MediaStager", "Nothing to scan. Paste a folder path and click Scan, "
                                                 "or add one or more folders to the queue first.")
            return

        self.status_var.set(f"Scanning {len(pending)} folder(s)...")
        self.progress.start(12)
        tmdb_key = self.tmdb_api_key

        def worker():
            for item in pending:
                try:
                    result = core.scan_directory(item.path, item.mode, item.sync_sidecars,
                                                  tmdb_key if item.use_tmdb else None, item.title_override)
                    item.rows = result.rows
                    item.folder_name = result.folder_name
                    item.status = f"Scanned ({len(result.rows)})"
                except Exception as exc:  # surfaced to the user, not swallowed
                    item.status = f"Error: {exc}"
            self._work_queue.put(("scan_done", None))

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll_queue)

    def _poll_queue(self):
        try:
            kind, payload = self._work_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_queue)
            return

        self.progress.stop()
        if kind == "scan_done":
            self.rows = [row for item in self.queue_items for row in item.rows]
            self._refresh_queue_tree()
            self._refresh_table()
            to_rename = sum(1 for r in self.rows if not r.excluded)
            self.status_var.set(f"Found {len(self.rows)} file(s) in {to_rename} to rename "
                                 f"across {len(self.queue_items)} folder(s).")
        elif kind == "scan_error":
            messagebox.showerror("MediaStager", f"Scan failed:\n{payload}")
            self.status_var.set("Scan failed.")

    def _refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        needle = self.filter_var.get().strip().lower()
        show_folder_col = len(self.queue_items) > 1
        self.tree.column("folder", width=150 if show_folder_col else 0, stretch=False)
        for idx, row in enumerate(self.rows):
            if needle and needle not in row.original.name.lower() and needle not in row.proposed.lower():
                continue
            mark = "✗" if row.excluded else "✓"
            tags = []
            if row.excluded:
                tags.append("excluded")
            if row.row_type == "Sidecar":
                tags.append("sidecar")
            if row.proposed.startswith("(could not"):
                tags.append("error")
            self.tree.insert("", "end", iid=str(idx),
                              values=(mark, self._folder_label(row), row.original.name, row.proposed, row.row_type),
                              tags=tags)

    def _execute_rename(self):
        if not self.rows:
            messagebox.showinfo("MediaStager", "Scan a directory first.")
            return
        included = [r for r in self.rows if not r.excluded]
        if not included:
            messagebox.showinfo("MediaStager", "Nothing selected to rename.")
            return

        preview = "\n".join(f"{r.original.name}  ->  {r.proposed}" for r in included[:15])
        more = f"\n... and {len(included) - 15} more" if len(included) > 15 else ""
        note = "\n\nFolders will also be renamed to their suggested names." if self.rename_folders.get() else ""
        if not messagebox.askyesno("Confirm Rename", f"Rename {len(included)} file(s)?\n\n{preview}{more}{note}"):
            return

        renamed_total = 0
        skipped_total: list[str] = []
        for item in self.queue_items:
            if not item.rows:
                continue
            target = item.folder_name if self.rename_folders.get() else None
            renamed, skipped, new_dir = core.apply_rename(item.rows, item.path, rename_folder_to=target)
            item.path = new_dir
            item.rows = [r for r in item.rows if r.excluded or r.original.exists()]
            item.status = f"Done ({renamed})" + (f", {len(skipped)} issue(s)" if skipped else "")
            renamed_total += renamed
            skipped_total.extend(skipped)

        self.rows = [row for item in self.queue_items for row in item.rows]
        self._refresh_queue_tree()
        self._refresh_table()

        msg = f"Renamed {renamed_total} file(s)."
        if skipped_total:
            msg += f"\n\nSkipped {len(skipped_total)}:\n" + "\n".join(skipped_total[:10])
        self.status_var.set(f"Renamed {renamed_total} file(s), {len(skipped_total)} skipped.")
        messagebox.showinfo("MediaStager", msg)

    def _undo(self):
        if self.queue_items:
            undone_total = 0
            errors_total: list[str] = []
            touched = 0
            for item in self.queue_items:
                try:
                    undone, errors, result_dir = core.undo_last_batch(item.path)
                except FileNotFoundError:
                    continue
                touched += 1
                item.path = result_dir
                item.status = "Pending"
                item.rows = []
                item.folder_name = None
                undone_total += undone
                errors_total.extend(errors)

            self.rows = []
            self._refresh_queue_tree()
            self._refresh_table()
            if touched == 0:
                messagebox.showinfo("MediaStager", "No ledger found for any queued folder.")
                return
            msg = f"Reverted {undone_total} file(s) across {touched} folder(s)."
            if errors_total:
                msg += f"\n\n{len(errors_total)} issue(s):\n" + "\n".join(errors_total[:10])
            self.status_var.set(f"Undo complete: {undone_total} reverted, {len(errors_total)} issue(s).")
            messagebox.showinfo("MediaStager", msg)
            return

        directory = filedialog.askdirectory(title="Select directory containing mediastager_ledger.json")
        if not directory:
            return
        try:
            undone, errors, _result_dir = core.undo_last_batch(Path(directory))
        except FileNotFoundError as exc:
            messagebox.showerror("MediaStager", str(exc))
            return

        msg = f"Reverted {undone} file(s)."
        if errors:
            msg += f"\n\n{len(errors)} issue(s):\n" + "\n".join(errors[:10])
        self.status_var.set(f"Undo complete: {undone} reverted, {len(errors)} issue(s).")
        messagebox.showinfo("MediaStager", msg)


def main():
    app = MediaStagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
