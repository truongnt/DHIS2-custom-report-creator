"""
FilterConfigDialog — cấu hình bộ lọc metadata, layout phân cấp 2 tầng:

  ┌─────────────────────────────────────────────────────────┐
  │  TẦNG 1 — SCOPE  (Programs bên trái | Datasets bên phải)│
  │  Chọn programs/datasets xác định phạm vi dữ liệu sẽ dùng│
  ├─────────────────────────────────────────────────────────┤
  │  TẦNG 2 — THU HẸP THÊM  (tabs: Indicators | DE)        │
  │  Tùy chọn — bỏ qua = lấy tất cả từ scope trên          │
  ├─────────────────────────────────────────────────────────┤
  │  [Clear All]  [Cancel]  [Apply & Load Metadata]         │
  └─────────────────────────────────────────────────────────┘
"""
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk

DHIS2_BLUE = "#1a6fa8"
BORDER     = "#d0dde8"


class FilterConfigDialog(ctk.CTkToplevel):

    def __init__(self, parent, filter_options: dict, current_cfg: dict):
        super().__init__(parent)
        self.title("Configure Metadata Filters")
        self.minsize(800, 580)
        self.grab_set()
        self.focus_force()
        self.after(0, lambda: self.state("zoomed"))

        self._opts = filter_options
        self._cfg  = dict(current_cfg)
        self.result: dict | None = None

        # Checkbox vars — tầng 1
        self._prg_vars: dict[str, tk.BooleanVar] = {}
        self._ds_vars:  dict[str, tk.BooleanVar] = {}
        # Checkbox vars — tầng 2
        self._de_vars:  dict[str, tk.BooleanVar] = {}
        # Keyword vars
        self._de_name_var   = tk.StringVar(value=self._cfg.get("de_name", ""))
        self._prog_name_var = tk.StringVar(value=self._cfg.get("program_name", ""))

        self._build()
        self._restore_selection()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        outer = ctk.CTkFrame(self, fg_color="white", corner_radius=0)
        outer.grid(sticky="nsew")
        outer.grid_rowconfigure(1, weight=2)   # scope section
        outer.grid_rowconfigure(3, weight=1)   # refine section
        outer.grid_columnconfigure(0, weight=1)

        # ── Section label helper ───────────────────────────────────────────
        def section_header(parent, row, text, sub=""):
            f = ctk.CTkFrame(parent, fg_color="#1a3a52", corner_radius=0, height=36)
            f.grid(row=row, column=0, sticky="ew")
            f.grid_propagate(False)
            f.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(f, text=text,
                          font=ctk.CTkFont(size=12, weight="bold"),
                          text_color="white").grid(row=0, column=0, padx=14, sticky="w")
            if sub:
                ctk.CTkLabel(f, text=sub,
                              font=ctk.CTkFont(size=10),
                              text_color="#8aa3b8").grid(row=0, column=1, padx=8, sticky="w")

        # ── TẦNG 1: Scope ─────────────────────────────────────────────────
        section_header(outer, 0,
                        "① SCOPE — Programs & Datasets",
                        "Xác định phạm vi dữ liệu sẽ tải")

        scope_frame = ctk.CTkFrame(outer, fg_color="#f4f8fc", corner_radius=0)
        scope_frame.grid(row=1, column=0, sticky="nsew")
        scope_frame.grid_rowconfigure(0, weight=1)
        scope_frame.grid_columnconfigure(0, weight=1)
        scope_frame.grid_columnconfigure(1, weight=1)

        self._build_scope_panel(
            scope_frame, col=0,
            icon="🗂", title="Programs",
            hint="PI + Data Elements của program sẽ tự động được tải",
            items=self._opts.get("programs", []),
            var_dict=self._prg_vars,
            col3_key="type", col3_label="Loại",
        )
        # Divider
        ctk.CTkFrame(scope_frame, width=1, fg_color=BORDER,
                      corner_radius=0).grid(row=0, column=0,
                                             sticky="ns", padx=0,
                                             ipadx=0)
        self._build_scope_panel(
            scope_frame, col=1,
            icon="📋", title="Datasets",
            hint="Data Elements của dataset sẽ tự động được tải",
            items=self._opts.get("datasets", []),
            var_dict=self._ds_vars,
            col3_key="periodType", col3_label="Period",
        )

        # ── TẦNG 2: Thu hẹp ───────────────────────────────────────────────
        section_header(outer, 2,
                        "② THU HẸP THÊM  (tùy chọn)",
                        "Bỏ qua = lấy tất cả từ scope trên")

        refine_frame = ctk.CTkFrame(outer, fg_color="white", corner_radius=0)
        refine_frame.grid(row=3, column=0, sticky="nsew")
        refine_frame.grid_rowconfigure(0, weight=1)
        refine_frame.grid_columnconfigure(0, weight=1)

        tabs = ctk.CTkTabview(
            refine_frame, fg_color="white",
            segmented_button_fg_color="#e8f0f8",
            segmented_button_selected_color=DHIS2_BLUE,
            segmented_button_selected_hover_color="#155a8a",
            height=220,
        )
        tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=(4, 2))

        t_de  = tabs.add("🔢 Data Element Groups")
        t_kw  = tabs.add("🔍 Keyword Filters")

        self._build_refine_groups(
            t_de, self._opts.get("de_groups", []),
            self._de_vars, "Data Element Groups", "count")
        self._build_keywords(t_kw)

        # ── Bottom bar ─────────────────────────────────────────────────────
        self._summary_lbl = ctk.CTkLabel(
            outer, text="",
            font=ctk.CTkFont(size=11), text_color="#6b8299", anchor="w")
        self._summary_lbl.grid(row=4, column=0, sticky="ew", padx=16, pady=(4, 0))

        bottom = ctk.CTkFrame(outer, fg_color="#f0f4f8", corner_radius=0, height=52)
        bottom.grid(row=5, column=0, sticky="ew")
        bottom.grid_propagate(False)

        ctk.CTkButton(bottom, text="Clear All", width=84, height=34,
                      fg_color="transparent", border_width=1,
                      border_color="#e74c3c", text_color="#e74c3c",
                      hover_color="#fdecea",
                      command=self._clear_all).pack(side="left", padx=16, pady=8)

        ctk.CTkButton(bottom, text="Cancel", width=80, height=34,
                      fg_color="transparent", border_width=1,
                      border_color=BORDER, text_color="#4a6278",
                      hover_color="#e8f0f8",
                      command=self._on_cancel).pack(side="right", padx=(0, 16), pady=8)

        ctk.CTkButton(bottom, text="Apply & Load Metadata ▶", width=200, height=34,
                      fg_color=DHIS2_BLUE, hover_color="#155a8a",
                      command=self._on_apply).pack(side="right", padx=(0, 8), pady=8)

        self._update_summary()

    # ── Scope panel (Programs hoặc Datasets) ─────────────────────────────────

    def _build_scope_panel(self, parent, col, icon, title, hint,
                            items, var_dict, col3_key, col3_label):
        frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        frame.grid(row=0, column=col, sticky="nsew", padx=(0 if col else 0, 0))
        frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        # Panel header
        hdr = ctk.CTkFrame(frame, fg_color="#e8f0f8", height=52, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text=f"{icon}  {title}",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      text_color="#1e2d3d").grid(
            row=0, column=0, padx=14, pady=(8, 2), sticky="w")
        ctk.CTkLabel(hdr, text=hint,
                      font=ctk.CTkFont(size=10), text_color="#6b8299").grid(
            row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        # Column sub-header
        col_hdr = ctk.CTkFrame(frame, fg_color="#dde8f0", height=24, corner_radius=0)
        col_hdr.grid(row=1, column=0, sticky="ew")
        col_hdr.grid_columnconfigure(1, weight=1)
        col_hdr.grid_propagate(False)

        # Quick select inside col_hdr
        qs_frame = ctk.CTkFrame(col_hdr, fg_color="transparent")
        qs_frame.grid(row=0, column=0, padx=6, pady=2)
        ctk.CTkButton(qs_frame, text="All", width=36, height=18,
                       fg_color="transparent", border_width=1,
                       border_color=DHIS2_BLUE, text_color=DHIS2_BLUE,
                       font=ctk.CTkFont(size=9),
                       command=lambda vd=var_dict: self._select_all(vd, True)
                       ).pack(side="left", padx=(0, 3))
        ctk.CTkButton(qs_frame, text="None", width=40, height=18,
                       fg_color="transparent", border_width=1,
                       border_color="#8aa3b8", text_color="#4a6278",
                       font=ctk.CTkFont(size=9),
                       command=lambda vd=var_dict: self._select_all(vd, False)
                       ).pack(side="left")

        ctk.CTkLabel(col_hdr, text=col3_label,
                      font=ctk.CTkFont(size=9), text_color="#4a6278",
                      width=64, anchor="e").grid(row=0, column=2, padx=(0, 8))

        # Scrollable list
        scroll = ctk.CTkScrollableFrame(frame, fg_color="white",
                                         border_width=1, border_color=BORDER,
                                         corner_radius=0)
        scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
        scroll.grid_columnconfigure(0, weight=1)

        if not items:
            ctk.CTkLabel(scroll, text="Không có dữ liệu.",
                          text_color="#8aa3b8",
                          font=ctk.CTkFont(size=11)).pack(padx=12, pady=12)
            return

        for i, item in enumerate(items):
            uid  = item["id"]
            name = item["displayName"]
            val  = str(item.get(col3_key, ""))

            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: self._update_summary())
            var_dict[uid] = var

            bg = "#f8fbff" if i % 2 == 0 else "white"
            row_f = ctk.CTkFrame(scroll, fg_color=bg, height=26, corner_radius=0)
            row_f.pack(fill="x")
            row_f.grid_columnconfigure(1, weight=1)
            row_f.grid_propagate(False)

            ctk.CTkCheckBox(row_f, text="", variable=var,
                             width=28, height=26,
                             checkbox_width=14, checkbox_height=14
                             ).grid(row=0, column=0, padx=(4, 2))
            ctk.CTkLabel(row_f, text=name, font=ctk.CTkFont(size=11),
                          text_color="#1e2d3d", anchor="w"
                          ).grid(row=0, column=1, sticky="w", padx=2)
            ctk.CTkLabel(row_f, text=val, font=ctk.CTkFont(size=10),
                          text_color="#8aa3b8", width=64, anchor="e"
                          ).grid(row=0, column=2, padx=(0, 6))

    # ── Refine groups tab ─────────────────────────────────────────────────────

    def _build_refine_groups(self, parent, items, var_dict, label, count_key):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Quick select
        qs = ctk.CTkFrame(parent, fg_color="transparent")
        qs.grid(row=0, column=0, sticky="w", pady=(2, 4))
        ctk.CTkButton(qs, text="Select All", width=85, height=22,
                       fg_color="transparent", border_width=1,
                       border_color=DHIS2_BLUE, text_color=DHIS2_BLUE,
                       font=ctk.CTkFont(size=10),
                       command=lambda vd=var_dict: self._select_all(vd, True)
                       ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(qs, text="Clear", width=60, height=22,
                       fg_color="transparent", border_width=1,
                       border_color="#8aa3b8", text_color="#4a6278",
                       font=ctk.CTkFont(size=10),
                       command=lambda vd=var_dict: self._select_all(vd, False)
                       ).pack(side="left")

        scroll = ctk.CTkScrollableFrame(parent, fg_color="white",
                                         border_width=1, border_color=BORDER,
                                         corner_radius=4)
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        if not items:
            ctk.CTkLabel(scroll, text="Không có groups trên DHIS2 này.",
                          text_color="#8aa3b8",
                          font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=12, pady=8)
            return

        for i, item in enumerate(items):
            uid  = item["id"]
            name = item["displayName"]
            cnt  = str(item.get(count_key, ""))

            var = tk.BooleanVar(value=False)
            var.trace_add("write", lambda *_: self._update_summary())
            var_dict[uid] = var

            bg = "#f8fbff" if i % 2 == 0 else "white"
            row_f = ctk.CTkFrame(scroll, fg_color=bg, height=26, corner_radius=0)
            row_f.grid(row=i, column=0, sticky="ew")
            row_f.grid_columnconfigure(1, weight=1)
            row_f.grid_propagate(False)
            scroll.grid_columnconfigure(0, weight=1)

            ctk.CTkCheckBox(row_f, text="", variable=var,
                             width=28, height=26,
                             checkbox_width=14, checkbox_height=14
                             ).grid(row=0, column=0, padx=(4, 2))
            ctk.CTkLabel(row_f, text=name, font=ctk.CTkFont(size=11),
                          text_color="#1e2d3d", anchor="w"
                          ).grid(row=0, column=1, sticky="w", padx=2)
            ctk.CTkLabel(row_f, text=cnt, font=ctk.CTkFont(size=10),
                          text_color="#8aa3b8", width=56, anchor="e"
                          ).grid(row=0, column=2, padx=(0, 8))

    # ── Keyword filters tab ───────────────────────────────────────────────────

    def _build_keywords(self, parent):
        parent.grid_columnconfigure(1, weight=1)

        rows = [
            ("Program name:",      self._prog_name_var,
             "Lọc tên program khi fetch (stage DEs + TEAs)"),
            ("Data Element name:", self._de_name_var,
             "Lọc tên data element khi fetch"),
        ]
        for i, (lbl, var, hint) in enumerate(rows):
            ctk.CTkLabel(parent, text=lbl,
                          font=ctk.CTkFont(size=12), text_color="#4a6278",
                          anchor="e", width=180).grid(
                row=i, column=0, padx=(0, 10), pady=8, sticky="e")
            ctk.CTkEntry(parent, textvariable=var,
                          placeholder_text=hint,
                          height=32, font=ctk.CTkFont(size=12)).grid(
                row=i, column=1, sticky="ew", pady=8)

        ctk.CTkLabel(parent,
                      text="Để trống = lấy tất cả (không lọc theo tên)",
                      font=ctk.CTkFont(size=10), text_color="#8aa3b8").grid(
            row=len(rows), column=0, columnspan=2, pady=(0, 8))

    # ─── Summary ─────────────────────────────────────────────────────────────

    def _update_summary(self):
        prg = sum(1 for v in self._prg_vars.values() if v.get())
        ds  = sum(1 for v in self._ds_vars.values()  if v.get())
        de  = sum(1 for v in self._de_vars.values()  if v.get())

        scope_parts = []
        if prg: scope_parts.append(f"{prg} program{'s' if prg>1 else ''}")
        if ds:  scope_parts.append(f"{ds} dataset{'s' if ds>1 else ''}")

        refine_parts = []
        if de:  refine_parts.append(f"{de} DE group{'s' if de>1 else ''}")

        if not scope_parts and not refine_parts:
            self._summary_lbl.configure(
                text="⚠  Chưa chọn gì — sẽ tải TOÀN BỘ metadata (chậm hơn)",
                text_color="#e67e22")
        else:
            txt = ""
            if scope_parts:
                txt += "Scope: " + ", ".join(scope_parts)
            if refine_parts:
                txt += ("  |  Thu hẹp: " if scope_parts else "Thu hẹp: ") + ", ".join(refine_parts)
            self._summary_lbl.configure(text=txt, text_color=DHIS2_BLUE)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _select_all(self, var_dict: dict, value: bool):
        for v in var_dict.values():
            v.set(value)

    def _restore_selection(self):
        for uid in self._cfg.get("program_ids", []):
            if uid in self._prg_vars: self._prg_vars[uid].set(True)
        for uid in self._cfg.get("dataset_ids", []):
            if uid in self._ds_vars:  self._ds_vars[uid].set(True)
        for uid in self._cfg.get("de_group_ids", []):
            if uid in self._de_vars:  self._de_vars[uid].set(True)
        self._update_summary()

    def _clear_all(self):
        for vd in (self._prg_vars, self._ds_vars, self._de_vars):
            for v in vd.values(): v.set(False)
        self._de_name_var.set("")
        self._prog_name_var.set("")

    # ─── Apply / Cancel ──────────────────────────────────────────────────────

    def _on_apply(self):
        self.result = {
            "program_ids":  [uid for uid, v in self._prg_vars.items() if v.get()],
            "program_name":  self._prog_name_var.get().strip(),
            "dataset_ids":  [uid for uid, v in self._ds_vars.items()  if v.get()],
            "de_group_ids": [uid for uid, v in self._de_vars.items()  if v.get()],
            "de_name":       self._de_name_var.get().strip(),
            "domain_type":  "AGGREGATE",
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
