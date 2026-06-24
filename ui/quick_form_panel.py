"""
QuickFormPanel — report-request form shown when the chat is empty.

Flow:
  1. User selects Program / Dataset / Period / OU level.
  2. User configures N charts (title, type, data element, notes for AI).
  3. Click "Generate Dashboard" → on_generate(configs, scope, scope_text) callback.
"""
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk

DHIS2_BLUE = "#1a6fa8"
_SKIP = "— (skip) —"

_PERIOD_TYPES = ["Monthly", "Quarterly", "Yearly"]
_TIME_RANGES  = [
    "Last 12 months",
    "Current year",
    "Last quarter",
    "Last 6 months",
    "Last 2 years",
    "Custom…",
]

_CHART_TYPES = [
    "Bar chart",
    "Stacked bar chart",
    "Line chart",
    "Area chart",
    "Pie chart",
    "Donut chart",
    "Scorecard / KPI card",
    "Data table",
    "Bar + Line combo",
    "Horizontal bar",
]


# ── Compact chart card ─────────────────────────────────────────────────────────

class _ChartRow(ctk.CTkFrame):
    """Compact 2-row chart card: [#N | Title | Type | ✕] / [DE combo | Notes]."""

    def __init__(self, parent, index: int, on_remove, **kwargs):
        super().__init__(parent, fg_color="white", corner_radius=6,
                         border_width=1, border_color="#dde8f4", **kwargs)
        self._index     = index
        self._on_remove = on_remove
        self._de_map: dict[str, str] = {}   # displayName → UID
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=2)
        self.grid_columnconfigure(3, weight=1)

        ekw = dict(height=26, font=ctk.CTkFont(size=11))

        # ── Row 0: #N | Title | Type dropdown | ✕ ─────────────────────
        self._idx_lbl = ctk.CTkLabel(
            self, text=f"#{self._index}", width=26,
            font=ctk.CTkFont(size=11, weight="bold"), text_color=DHIS2_BLUE)
        self._idx_lbl.grid(row=0, column=0, padx=(6, 2), pady=(6, 2), sticky="w")

        self.title_entry = ctk.CTkEntry(self, placeholder_text="Title", **ekw)
        self.title_entry.grid(row=0, column=1, padx=(0, 6), pady=(6, 2), sticky="ew")

        self.type_var = ctk.StringVar(value=_CHART_TYPES[0])
        ctk.CTkOptionMenu(
            self, variable=self.type_var, values=_CHART_TYPES,
            width=148, height=26, font=ctk.CTkFont(size=10),
            fg_color="white", button_color="#b8cfe8",
            button_hover_color="#9abcd8", text_color="#1e2d3d",
            dropdown_fg_color="white", dropdown_text_color="#1e2d3d",
        ).grid(row=0, column=2, padx=(0, 6), pady=(6, 2))

        ctk.CTkButton(
            self, text="✕", width=22, height=22,
            fg_color="transparent", text_color="#cccccc",
            hover_color="#fde8e8", corner_radius=4,
            font=ctk.CTkFont(size=10), command=self._on_remove,
        ).grid(row=0, column=3, padx=(0, 6), pady=(6, 2), sticky="e")

        # ── Row 1: DE combobox | Notes entry ───────────────────────────
        self.metric_combo = ctk.CTkComboBox(
            self, values=[], height=26, font=ctk.CTkFont(size=11),
            fg_color="white", border_color="#b8cfe8",
            button_color="#b8cfe8", button_hover_color="#9abcd8",
            text_color="#1e2d3d", dropdown_fg_color="white",
            dropdown_text_color="#1e2d3d",
        )
        self.metric_combo.set("")
        self.metric_combo.grid(row=1, column=0, columnspan=2,
                               padx=(6, 6), pady=(0, 6), sticky="ew")

        self.notes_entry = ctk.CTkEntry(
            self, placeholder_text="Notes for AI", **ekw)
        self.notes_entry.grid(row=1, column=2, columnspan=2,
                              padx=(0, 6), pady=(0, 6), sticky="ew")

    def update_index(self, index: int):
        self._index = index
        self._idx_lbl.configure(text=f"#{index}")

    def update_de_options(self, des: list[tuple[str, str]]):
        """Populate DE combobox. des = [(displayName, uid), ...]"""
        self._de_map = {name: uid for name, uid in des}
        names = [name for name, _ in des]
        self.metric_combo.configure(values=names)
        # Keep current value if it's still valid, else clear placeholder
        cur = self.metric_combo.get()
        if cur and cur not in self._de_map:
            self.metric_combo.set("")

    def _metric_text(self) -> str:
        """Return 'Name (UID: xyz)' when UID known, else raw text."""
        name = self.metric_combo.get().strip()
        uid  = self._de_map.get(name, "")
        if uid:
            return f"{name} (UID: {uid})"
        return name

    def get_config(self) -> dict:
        return {
            "index":       self._index,
            "title":       self.title_entry.get().strip(),
            "chart_type":  self.type_var.get(),
            "metric":      self._metric_text(),
            "metric_uid":  self._de_map.get(self.metric_combo.get().strip(), ""),
            "description": "",
            "notes":       self.notes_entry.get().strip(),
        }

    def is_valid(self) -> bool:
        return bool(self.title_entry.get().strip() and
                    self.metric_combo.get().strip())

    def get_state(self) -> dict:
        return {
            "title":      self.title_entry.get(),
            "chart_type": self.type_var.get(),
            "metric":     self.metric_combo.get(),
            "notes":      self.notes_entry.get(),
        }

    def restore_state(self, state: dict):
        if not state:
            return
        if state.get("title"):
            self.title_entry.insert(0, state["title"])
        if state.get("chart_type") in _CHART_TYPES:
            self.type_var.set(state["chart_type"])
        if state.get("metric"):
            self.metric_combo.set(state["metric"])
        if state.get("notes"):
            self.notes_entry.insert(0, state["notes"])


# ── Main form panel ────────────────────────────────────────────────────────────

class QuickFormPanel(ctk.CTkFrame):
    """
    Compact form: scope selectors (top) + per-chart config (bottom).
    Callback: on_generate(configs: list[dict], scope: tuple[str, list[str]], scope_text: str)
    """

    MIN_CHARTS     = 1
    MAX_CHARTS     = 8
    DEFAULT_CHARTS = 3

    def __init__(self, master, on_generate=None, **kwargs):
        super().__init__(master,
                         fg_color="#f0f6fc",
                         corner_radius=8,
                         border_width=1,
                         border_color="#c8ddf0",
                         **kwargs)
        self._on_generate = on_generate
        self._metadata    = {}
        self._collapsed   = False
        self._cards: list[_ChartRow] = []
        self._de_options: list[tuple[str, str]] = []   # [(displayName, uid)]

        self._prog_names: list[str]      = []
        self._ds_names:   list[str]      = []
        self._ou_levels:  list[dict]     = []
        self._prog_map:   dict[str, dict] = {}

        self._build()

    # ── Public ────────────────────────────────────────────────────────────────

    def set_metadata(self, metadata: dict):
        self._metadata = metadata or {}
        programs  = self._metadata.get("programs", [])
        datasets  = self._metadata.get("datasets", [])
        ou_levels = self._metadata.get("org_unit_levels", [])

        self._prog_names = [p.get("displayName", p.get("id", "?")) for p in programs]
        self._ds_names   = [d.get("displayName", d.get("id", "?")) for d in datasets]
        self._ou_levels  = ou_levels
        self._prog_map   = {p.get("displayName", p.get("id", "?")): p for p in programs}

        prog_opts = [_SKIP] + (["(all)"] + self._prog_names if self._prog_names else [])
        ds_opts   = [_SKIP] + (["(all)"] + self._ds_names   if self._ds_names   else [])
        ou_opts   = ["(all)"] + [
            f"Level {l.get('level')}: {l.get('displayName', l.get('name',''))}"
            for l in ou_levels
        ]

        self._prog_var.set(prog_opts[0])
        self._ds_var.set(ds_opts[0])
        self._ou_var.set(ou_opts[0])

        self._prog_menu.configure(values=prog_opts)
        self._ds_menu.configure(values=ds_opts)
        self._ou_menu.configure(values=ou_opts)

        if self._prog_names:
            self._prog_row.grid()
        else:
            self._prog_row.grid_remove()
        if self._ds_names:
            self._ds_row.grid()
        else:
            self._ds_row.grid_remove()

        self._update_stage_row(prog_opts[0])

    def get_scope(self) -> tuple[str, list[str]]:
        """Return (program_name, [stage_names]) for metadata filtering."""
        _none = (_SKIP, "(none)", "(all)", "")
        prog   = self._prog_var.get()
        stages = [self._stage_lb.get(i) for i in self._stage_lb.curselection()]
        return ("" if prog in _none else prog, stages)

    def get_analytics_params(self) -> dict:
        """Return period / org-unit params for DHIS2 analytics API calls."""
        return {
            "time_range":  self._range_var.get(),
            "period_type": self._period_var.get(),
            "ou_level":    self._ou_var.get(),
        }

    def reset(self):
        self.set_metadata(self._metadata)
        self._period_var.set(_PERIOD_TYPES[0])
        self._range_var.set(_TIME_RANGES[0])
        # Reset cards to defaults
        for card in self._cards[:]:
            card.grid_forget()
            card.destroy()
        self._cards.clear()
        self._set_count(self.DEFAULT_CHARTS)
        self._count_var.set(str(self.DEFAULT_CHARTS))

    def get_state(self) -> dict:
        return {
            "program":     self._prog_var.get(),
            "stages":      [self._stage_lb.get(i) for i in self._stage_lb.curselection()],
            "dataset":     self._ds_var.get(),
            "period_type": self._period_var.get(),
            "time_range":  self._range_var.get(),
            "ou_level":    self._ou_var.get(),
            "charts":      [c.get_state() for c in self._cards],
        }

    def restore_state(self, state: dict):
        if not state:
            return
        prog = state.get("program", "")
        if prog and prog in self._prog_names:
            self._prog_var.set(prog)
            self._update_stage_row(prog)
            saved_stages = set(state.get("stages", []))
            for i in range(self._stage_lb.size()):
                if self._stage_lb.get(i) in saved_stages:
                    self._stage_lb.selection_set(i)
        ds = state.get("dataset", "")
        if ds and ds in self._ds_names:
            self._ds_var.set(ds)
        if state.get("period_type") in _PERIOD_TYPES:
            self._period_var.set(state["period_type"])
        if state.get("time_range") in _TIME_RANGES:
            self._range_var.set(state["time_range"])
        ou = state.get("ou_level", "")
        ou_vals = list(self._ou_menu.cget("values"))
        if ou and ou in ou_vals:
            self._ou_var.set(ou)
        # Restore chart cards
        saved_charts = state.get("charts", [])
        if saved_charts:
            # Rebuild cards to match saved count
            for card in self._cards[:]:
                card.grid_forget()
                card.destroy()
            self._cards.clear()
            for i, cs in enumerate(saved_charts, 1):
                self._add_card()
                self._cards[-1].restore_state(cs)
            self._count_var.set(str(len(self._cards)))

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="#dbeaf8", corner_radius=0, height=28)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="📝  Report Settings",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#1e2d3d").grid(row=0, column=0, padx=10, pady=4, sticky="w")

        self._collapse_btn = ctk.CTkButton(
            hdr, text="▲", width=28, height=20,
            fg_color="transparent", text_color="#4a6278",
            hover_color="#c8ddf0", font=ctk.CTkFont(size=10),
            command=self._toggle_collapse)
        self._collapse_btn.grid(row=0, column=2, padx=6, pady=4, sticky="e")

        # Content frame
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 8))
        self._content.grid_columnconfigure((0, 1, 2, 3), weight=1)

        lbl_kw = dict(font=ctk.CTkFont(size=10), text_color="#4a6278", anchor="w")
        opt_kw = dict(font=ctk.CTkFont(size=11), height=28,
                      fg_color="white", button_color="#b8cfe8",
                      button_hover_color="#9abcd8", text_color="#1e2d3d",
                      dropdown_fg_color="white", dropdown_text_color="#1e2d3d")

        # ── Row 0: Program ─────────────────────────────────────────────────
        self._prog_row = ctk.CTkFrame(self._content, fg_color="transparent")
        self._prog_row.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        self._prog_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self._prog_row, text="Program:", **lbl_kw).grid(
            row=0, column=0, padx=(0, 6), sticky="w")
        self._prog_var = ctk.StringVar(value="(none)")
        self._prog_menu = ctk.CTkOptionMenu(
            self._prog_row, variable=self._prog_var,
            values=["(none)"], width=360, command=self._on_program_change, **opt_kw)
        self._prog_menu.grid(row=0, column=1, sticky="ew")

        # ── Row 1: Stage ───────────────────────────────────────────────────
        self._stage_row = ctk.CTkFrame(self._content, fg_color="transparent")
        self._stage_row.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        self._stage_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self._stage_row, text="Stage:", **lbl_kw).grid(
            row=0, column=0, padx=(0, 6), sticky="nw", pady=(2, 0))
        stage_host = tk.Frame(self._stage_row, bg="#f0f4f8", bd=1, relief="solid")
        stage_host.grid(row=0, column=1, sticky="ew")
        stage_host.grid_columnconfigure(0, weight=1)
        self._stage_lb = tk.Listbox(
            stage_host, selectmode=tk.MULTIPLE, height=3,
            font=("Segoe UI", 10), bg="white", fg="#1e2d3d",
            selectbackground="#dbeafe", selectforeground="#1e2d3d",
            borderwidth=0, highlightthickness=0, activestyle="none")
        self._stage_lb.grid(row=0, column=0, sticky="ew")
        stage_sb = tk.Scrollbar(stage_host, orient="vertical", command=self._stage_lb.yview)
        stage_sb.grid(row=0, column=1, sticky="ns")
        self._stage_lb.configure(yscrollcommand=stage_sb.set)
        self._stage_lb.bind("<<ListboxSelect>>", lambda e: self._on_stage_select())
        self._stage_row.grid_remove()

        # ── Row 2: Dataset ─────────────────────────────────────────────────
        self._ds_row = ctk.CTkFrame(self._content, fg_color="transparent")
        self._ds_row.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        self._ds_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self._ds_row, text="Dataset:", **lbl_kw).grid(
            row=0, column=0, padx=(0, 6), sticky="w")
        self._ds_var = ctk.StringVar(value="(none)")
        self._ds_menu = ctk.CTkOptionMenu(
            self._ds_row, variable=self._ds_var,
            values=["(none)"], width=360, **opt_kw)
        self._ds_menu.grid(row=0, column=1, sticky="ew")

        # ── Row 3: Period + Time range ─────────────────────────────────────
        r3 = ctk.CTkFrame(self._content, fg_color="transparent")
        r3.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        r3.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(r3, text="Period type:", **lbl_kw).grid(row=0, column=0, padx=(0, 6), sticky="w")
        self._period_var = ctk.StringVar(value=_PERIOD_TYPES[0])
        ctk.CTkOptionMenu(r3, variable=self._period_var, values=_PERIOD_TYPES,
                          width=110, **opt_kw).grid(row=0, column=1, sticky="ew", padx=(0, 16))
        ctk.CTkLabel(r3, text="Time range:", **lbl_kw).grid(row=0, column=2, padx=(0, 6), sticky="w")
        self._range_var = ctk.StringVar(value=_TIME_RANGES[0])
        ctk.CTkOptionMenu(r3, variable=self._range_var, values=_TIME_RANGES,
                          width=180, **opt_kw).grid(row=0, column=3, sticky="ew")

        # ── Row 4: OU level ────────────────────────────────────────────────
        r4 = ctk.CTkFrame(self._content, fg_color="transparent")
        r4.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        r4.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(r4, text="Org unit level:", **lbl_kw).grid(row=0, column=0, padx=(0, 6), sticky="w")
        self._ou_var = ctk.StringVar(value="(all)")
        self._ou_menu = ctk.CTkOptionMenu(
            r4, variable=self._ou_var, values=["(all)"], width=240, **opt_kw)
        self._ou_menu.grid(row=0, column=1, sticky="w")

        # ── Divider ────────────────────────────────────────────────────────
        ctk.CTkFrame(self._content, fg_color="#c8ddf0", height=1).grid(
            row=5, column=0, columnspan=4, sticky="ew", pady=(0, 8))

        # ── Row 6: Chart count control ─────────────────────────────────────
        cnt_row = ctk.CTkFrame(self._content, fg_color="transparent")
        cnt_row.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(0, 6))

        ctk.CTkLabel(cnt_row, text="Charts:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#1e2d3d").pack(side="left", padx=(0, 8))

        ctk.CTkButton(cnt_row, text="−", width=26, height=26,
                      fg_color="#dde8f4", text_color=DHIS2_BLUE,
                      hover_color="#c8d8e8", corner_radius=5,
                      command=self._dec_count).pack(side="left")

        self._count_var = ctk.StringVar(value=str(self.DEFAULT_CHARTS))
        ctk.CTkLabel(cnt_row, textvariable=self._count_var,
                     width=32, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=DHIS2_BLUE).pack(side="left", padx=4)

        ctk.CTkButton(cnt_row, text="+", width=26, height=26,
                      fg_color="#dde8f4", text_color=DHIS2_BLUE,
                      hover_color="#c8d8e8", corner_radius=5,
                      command=self._inc_count).pack(side="left")

        # ── Row 7: Scrollable chart cards ─────────────────────────────────
        self._cards_frame = ctk.CTkScrollableFrame(
            self._content, fg_color="transparent", height=110)
        self._cards_frame.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(0, 4))
        self._cards_frame.grid_columnconfigure(0, weight=1)

        # Initialise default cards
        self._set_count(self.DEFAULT_CHARTS)

    # ── Chart card management ─────────────────────────────────────────────────

    def _inc_count(self):
        self._set_count(len(self._cards) + 1)

    def _dec_count(self):
        self._set_count(max(self.MIN_CHARTS, len(self._cards) - 1))

    def _set_count(self, n: int):
        n = max(self.MIN_CHARTS, min(self.MAX_CHARTS, n))
        while len(self._cards) < n:
            self._add_card()
        while len(self._cards) > n:
            self._remove_card(self._cards[-1], _reindex=False)
        self._count_var.set(str(len(self._cards)))

    def _add_card(self):
        idx  = len(self._cards) + 1
        card = _ChartRow(
            self._cards_frame, index=idx,
            on_remove=lambda c=None: self._remove_card(card))
        card.grid(row=idx - 1, column=0, sticky="ew", pady=(0, 6))
        card.update_de_options(self._de_options)
        self._cards.append(card)

    def _remove_card(self, card: _ChartRow, _reindex: bool = True):
        if len(self._cards) <= self.MIN_CHARTS:
            return
        card.grid_forget()
        card.destroy()
        self._cards.remove(card)
        if _reindex:
            for i, c in enumerate(self._cards, 1):
                c.update_index(i)
                c.grid(row=i - 1, column=0, sticky="ew", pady=(0, 6))
        self._count_var.set(str(len(self._cards)))

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_program_change(self, value: str):
        self._update_stage_row(value)
        self._on_stage_select()

    def _update_stage_row(self, prog_value: str):
        if prog_value in (_SKIP, "(none)", "(all)", ""):
            self._stage_lb.delete(0, tk.END)
            self._stage_row.grid_remove()
            self._de_options = []
            self._update_card_de_options()
            return
        prog   = self._prog_map.get(prog_value)
        stages = (prog or {}).get("programStages", [])
        if not stages:
            self._stage_lb.delete(0, tk.END)
            self._stage_row.grid_remove()
            self._de_options = []
            self._update_card_de_options()
            return
        self._stage_lb.delete(0, tk.END)
        for s in stages:
            self._stage_lb.insert(tk.END, s.get("displayName", s.get("id", "?")))
        self._stage_row.grid()

    def _on_stage_select(self):
        """Rebuild DE list from selected stages using pre-fetched metadata."""
        prog_value = self._prog_var.get()
        sel_stages = {self._stage_lb.get(i) for i in self._stage_lb.curselection()}

        # program_stage_data_elements already has {id, displayName, program, stage}
        all_stage_des = self._metadata.get("program_stage_data_elements", [])

        seen: set[str] = set()
        des:  list[tuple[str, str]] = []
        for de in all_stage_des:
            # Filter by program
            if prog_value not in (_SKIP, "(none)", "(all)", ""):
                if de.get("program", {}).get("displayName") != prog_value:
                    continue
            # Filter by stage (if any selected; if none selected → all stages)
            if sel_stages:
                if de.get("stage", {}).get("displayName") not in sel_stages:
                    continue
            uid  = de.get("id", "")
            name = de.get("displayName", "?")
            if uid and uid not in seen:
                seen.add(uid)
                des.append((name, uid))

        des.sort(key=lambda x: x[0])
        self._de_options = des
        self._update_card_de_options()

    def _update_card_de_options(self):
        for card in self._cards:
            card.update_de_options(self._de_options)

    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._content.grid_remove()
            self._collapse_btn.configure(text="▼")
        else:
            self._content.grid()
            self._collapse_btn.configure(text="▲")

    def _build_scope_text(self) -> str:
        """Human-readable context description for the LLM prompt."""
        parts: list[str] = []
        prog = self._prog_var.get()
        ds   = self._ds_var.get()
        if prog and prog not in (_SKIP, "(none)"):
            label = "all programs" if prog == "(all)" else f'program "{prog}"'
            sel_stages = [self._stage_lb.get(i) for i in self._stage_lb.curselection()]
            if sel_stages and prog != "(all)":
                label += ", stages: " + ", ".join(f'"{s}"' for s in sel_stages)
            parts.append(label)
        if ds and ds not in (_SKIP, "(none)"):
            parts.append("all datasets" if ds == "(all)" else f'dataset "{ds}"')
        parts.append(f"period: {self._period_var.get().lower()}, {self._range_var.get().lower()}")
        ou = self._ou_var.get()
        if ou and ou != "(all)":
            parts.append(f"org unit: {ou}")
        return "Context: " + "; ".join(parts) if parts else ""

    def _on_generate_click(self):
        import tkinter.messagebox as msgbox
        configs = [c.get_config() for c in self._cards]
        invalid = [c["index"] for c in configs
                   if not c["title"] or not c["metric"]]
        if invalid:
            names = ", ".join(f"Chart {i}" for i in invalid)
            msgbox.showwarning(
                "Missing required fields",
                f"{names}: Title and Data element/metric are required.")
            return
        if self._on_generate:
            scope      = self.get_scope()
            scope_text = self._build_scope_text()
            self._on_generate(configs, scope, scope_text)

    def set_generating(self, generating: bool):
        pass  # generate button is managed by app_window
