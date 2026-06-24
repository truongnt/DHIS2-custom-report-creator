"""
DE Review dialog — shown before generate so user can verify/swap the DEs the LLM selected.

result = list[dict]  → confirmed (possibly swapped) DEs
result = None        → user skipped (use LLM planned list as-is)
"""
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

DHIS2_BLUE = "#1a6fa8"
_TYPE_LABELS = {
    "data_element":      "DE",
    "program_indicator": "PI",
    "indicator":         "IND",
}


class DEReviewDialog(ctk.CTkToplevel):
    def __init__(self, parent, planned_des: list[dict], metadata: dict,
                 verify_log: dict | None = None):
        super().__init__(parent)
        self.title("🔍 Review Data Elements before Generate")
        self.resizable(True, True)
        self.after(0, lambda: self.state("zoomed"))
        self.grab_set()

        self.result: list[dict] | None = None  # None = skipped
        self._rows: list[dict] = [dict(de) for de in planned_des]  # mutable copies
        self._row_frames: list[ctk.CTkFrame] = []
        self._metadata = metadata
        self._verify_log: dict = verify_log or {}
        # UIDs that failed verification before and were never valid
        self._known_bad: set[str] = {
            uid for uid, e in self._verify_log.items()
            if e.get("invalid", 0) > 0 and e.get("valid", 0) == 0
        }

        # Flat list of all DEs for search — deduplicated by UID so Treeview iid is unique
        _seen_uids: set[str] = set()
        self._all_des: list[dict] = [
            de for de in (
                metadata.get("data_elements", []) +
                metadata.get("program_stage_data_elements", []) +
                metadata.get("indicators", []) +
                metadata.get("program_indicators", [])
            )
            if de.get("id") and de.get("id") not in _seen_uids and not _seen_uids.add(de.get("id"))
        ]

        self._swap_target_idx: int | None = None
        self._build()
        self.lift()
        self.focus_force()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="#1e2d3d", corner_radius=0, height=52)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr,
                     text=f"🔍  LLM selected {len(self._rows)} data elements — review before generating",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="white").grid(row=0, column=0, padx=20, pady=14, sticky="w")
        ctk.CTkLabel(hdr,
                     text="Click 🔄 to swap a DE. Changes are applied for this run.",
                     font=ctk.CTkFont(size=11), text_color="#8aa3b8").grid(
            row=0, column=1, padx=10, pady=14, sticky="w")

        # Main split: left = DE list, right = swap picker
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=10)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        # ── Left: DE list ──
        left = ctk.CTkFrame(body, fg_color="white", corner_radius=8,
                            border_width=1, border_color="#d0dde8")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Data Elements to be used in the report",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#1e2d3d",
                     fg_color="#f0f4f8", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=0, pady=0, ipady=8, ipadx=12)

        self._list_frame = ctk.CTkScrollableFrame(left, fg_color="white")
        self._list_frame.grid(row=1, column=0, sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)
        self._render_de_rows()

        # ── Right: swap picker (hidden until swap clicked) ──
        self._picker_frame = ctk.CTkFrame(body, fg_color="white", corner_radius=8,
                                          border_width=1, border_color="#d0dde8")
        self._picker_frame.grid(row=0, column=1, sticky="nsew")
        self._picker_frame.grid_rowconfigure(2, weight=1)
        self._picker_frame.grid_columnconfigure(0, weight=1)
        self._picker_frame.grid_columnconfigure(1, weight=0)
        self._build_picker()
        self._picker_frame.grid_remove()  # hidden initially

        # ── Footer buttons ──
        foot = ctk.CTkFrame(self, fg_color="#f0f4f8", corner_radius=0, height=52)
        foot.grid(row=2, column=0, sticky="ew")
        foot.grid_propagate(False)
        foot.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            foot, text="Skip — Generate with DEs as listed", width=260, height=34,
            fg_color="transparent", border_width=1, border_color="#8aa3b8",
            text_color="#4a6278", hover_color="#e8f0f8",
            command=self._on_skip,
        ).grid(row=0, column=0, padx=20, pady=9, sticky="e")

        ctk.CTkButton(
            foot, text="✓  Confirm & Generate", width=200, height=34,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            command=self._on_confirm,
        ).grid(row=0, column=1, padx=(8, 20), pady=9)

    def _render_de_rows(self):
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._row_frames.clear()

        for i, de in enumerate(self._rows):
            bg = "#f8fbff" if i % 2 == 0 else "white"
            row = ctk.CTkFrame(self._list_frame, fg_color=bg, corner_radius=4)
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(0, weight=1)

            # type badge
            type_lbl = _TYPE_LABELS.get(de.get("type", ""), "?")
            badge_color = {"DE": "#e8f4ec", "PI": "#e8f0ff", "IND": "#fff8e0"}.get(type_lbl, "#eee")
            badge_fg    = {"DE": "#2d6a3f", "PI": "#4a1d96", "IND": "#856404"}.get(type_lbl, "#333")

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.grid(row=0, column=0, sticky="ew", padx=8, pady=6)
            info.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(info, text=type_lbl, width=34, height=20,
                         fg_color=badge_color, text_color=badge_fg, corner_radius=4,
                         font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, padx=(0, 8))

            uid = de.get("id", "")
            is_bad = uid in self._known_bad
            name_text = de.get("displayName", uid or "?")
            if de.get("_was_swapped"):
                name_text = "↔ " + name_text
            ctk.CTkLabel(info, text=name_text, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color="#c0392b" if is_bad else "#1e2d3d").grid(
                row=0, column=1, sticky="w")

            id_suffix = "  ⚠ known invalid" if is_bad else ""
            ctk.CTkLabel(info, text=uid + id_suffix, anchor="w",
                         font=ctk.CTkFont(family="Consolas", size=10),
                         text_color="#c0392b" if is_bad else "#8aa3b8").grid(
                row=1, column=1, sticky="w")

            reason = de.get("reason", "")
            if reason:
                ctk.CTkLabel(info, text=f"→ {reason}", anchor="w",
                             font=ctk.CTkFont(size=10, slant="italic"),
                             text_color="#6b8299").grid(row=2, column=1, sticky="w")

            swap_btn = ctk.CTkButton(
                row, text="🔄 Swap", width=70, height=28,
                fg_color="transparent", border_width=1, border_color="#c8d8e8",
                text_color="#4a6278", hover_color="#e8f4ff",
                font=ctk.CTkFont(size=11),
                command=lambda idx=i: self._on_swap_click(idx),
            )
            swap_btn.grid(row=0, column=1, padx=(6, 8), pady=6)

            self._row_frames.append(row)

    def _build_picker(self):
        p = self._picker_frame
        self._picker_title = ctk.CTkLabel(
            p, text="Select replacement DE", anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#1e2d3d",
            fg_color="#f0f4f8")
        self._picker_title.grid(row=0, column=0, columnspan=2, sticky="ew", ipady=8, ipadx=12)

        search_frame = ctk.CTkFrame(p, fg_color="transparent")
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(6, 2))
        search_frame.grid_columnconfigure(0, weight=1)
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(search_frame, textvariable=self._search_var,
                     placeholder_text="🔍 Search by name or ID…",
                     height=30, font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="ew")

        # ── Treeview table — use tk.Frame wrapper so ttk widgets render correctly
        # inside CTkFrame (CTkFrame's internal canvas overlay hides native ttk
        # widgets that are parented directly to it).
        tree_host = tk.Frame(p, bg="white", bd=0, highlightthickness=0)
        tree_host.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=6, pady=4)
        tree_host.grid_rowconfigure(0, weight=1)
        tree_host.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure("DE.Treeview",
                        rowheight=22, font=("Segoe UI", 10),
                        background="white", fieldbackground="white",
                        foreground="#1e2d3d")
        style.configure("DE.Treeview.Heading",
                        font=("Segoe UI", 10, "bold"),
                        background="#f0f4f8", foreground="#4a6278")
        style.map("DE.Treeview", background=[("selected", "#dbeafe")])

        self._tree = ttk.Treeview(
            tree_host, columns=("type", "name", "id"),
            show="headings", selectmode="browse",
            style="DE.Treeview",
        )
        self._tree.heading("type", text="Type", anchor="w")
        self._tree.heading("name", text="Display Name", anchor="w")
        self._tree.heading("id",   text="ID",           anchor="w")
        self._tree.column("type", width=46, minwidth=46, stretch=False)
        self._tree.column("name", width=260, minwidth=120)
        self._tree.column("id",   width=110, minwidth=80, stretch=False)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._tree.bind("<Double-1>", self._on_tree_double_click)

        vsb = ttk.Scrollbar(tree_host, orient="vertical", command=self._tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=vsb.set)

        # Footer buttons
        btn_frame = ctk.CTkFrame(p, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(2, 10), sticky="e")

        ctk.CTkButton(btn_frame, text="✓ Select", width=90, height=28,
                      fg_color=DHIS2_BLUE, hover_color="#155a8a",
                      font=ctk.CTkFont(size=11),
                      command=self._on_tree_select).pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="✕ Cancel", width=80, height=28,
                      fg_color="transparent", border_width=1, border_color="#c8d8e8",
                      text_color="#6b8299", hover_color="#fee",
                      command=self._on_cancel_swap).pack(side="left")

    def _populate_picker(self, query: str = ""):
        self._tree.delete(*self._tree.get_children())
        q = query.lower()
        for de in self._all_des:
            name = de.get("displayName", "")
            uid  = de.get("id", "")
            if q and q not in name.lower() and q not in uid.lower():
                continue
            type_lbl = _TYPE_LABELS.get(de.get("type", ""), "DE")
            tag = "bad" if uid in self._known_bad else ""
            self._tree.insert("", "end", iid=uid, values=(type_lbl, name, uid), tags=(tag,))
        self._tree.tag_configure("bad", foreground="#c0392b")

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_swap_click(self, idx: int):
        self._swap_target_idx = idx
        de = self._rows[idx]
        self._picker_title.configure(
            text=f"Swap: \"{de.get('displayName', '')}\"")
        self._search_var.set("")
        self._populate_picker()
        self._picker_frame.grid()

    def _on_search(self, *_):
        self._populate_picker(self._search_var.get())

    def _on_tree_double_click(self, event=None):
        self._on_tree_select()

    def _on_tree_select(self):
        sel = self._tree.selection()
        if not sel:
            return
        uid = sel[0]  # iid == uid
        de = next((d for d in self._all_des if d.get("id") == uid), None)
        if de:
            self._on_pick(de)

    def _on_pick(self, new_de: dict):
        if self._swap_target_idx is None:
            return
        idx = self._swap_target_idx
        old = self._rows[idx]
        self._rows[idx] = {
            "id":          new_de.get("id", ""),
            "displayName": new_de.get("displayName", ""),
            "type":        new_de.get("type", old.get("type", "data_element")),
            "reason":      old.get("reason", ""),
            "_swapped_from": old.get("id"),
        }
        self._swap_target_idx = None
        self._picker_frame.grid_remove()
        self._render_de_rows()

    def _on_cancel_swap(self):
        self._swap_target_idx = None
        self._picker_frame.grid_remove()

    def _on_skip(self):
        self.result = None
        self.destroy()

    def _on_confirm(self):
        self.result = list(self._rows)
        self.destroy()
