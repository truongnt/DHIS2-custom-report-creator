"""
ChartConfigPanel — structured chart configuration form.

User defines N charts (title, type, data element, description, AI notes),
then clicks Generate Dashboard to send the full spec to the LLM.
"""
from __future__ import annotations
import tkinter.messagebox as msgbox
import customtkinter as ctk

DHIS2_BLUE = "#1a6fa8"

CHART_TYPES = [
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
    "Map / choropleth",
]


class ChartCard(ctk.CTkFrame):
    """Single chart configuration card."""

    def __init__(self, parent, index: int, on_remove, **kwargs):
        super().__init__(parent, fg_color="#f8fafc", corner_radius=8,
                         border_width=1, border_color="#d0dde8", **kwargs)
        self._index  = index
        self._on_remove = on_remove
        self._build()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Header ──────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="#e8f0f8", corner_radius=6)
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        hdr.grid_columnconfigure(0, weight=1)

        self._hdr_lbl = ctk.CTkLabel(
            hdr, text=f"Chart {self._index}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=DHIS2_BLUE)
        self._hdr_lbl.grid(row=0, column=0, padx=10, pady=4, sticky="w")

        ctk.CTkButton(
            hdr, text="✕", width=24, height=24,
            fg_color="transparent", text_color="#e74c3c",
            hover_color="#fde8e8", corner_radius=4,
            command=self._on_remove,
        ).grid(row=0, column=1, padx=(0, 6), pady=4)

        # ── Row 1: Title + Type ─────────────────────────────────
        r1 = ctk.CTkFrame(self, fg_color="transparent")
        r1.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        r1.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(r1, text="Title:", font=ctk.CTkFont(size=11),
                     text_color="#5a6a7a").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(r1, text="Chart type:", font=ctk.CTkFont(size=11),
                     text_color="#5a6a7a").grid(row=0, column=1, padx=(12, 0), sticky="w")

        self.title_entry = ctk.CTkEntry(
            r1, height=30, font=ctk.CTkFont(size=12),
            placeholder_text="e.g. Monthly Malaria Cases by Province")
        self.title_entry.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.type_var = ctk.StringVar(value=CHART_TYPES[0])
        ctk.CTkOptionMenu(
            r1, variable=self.type_var, values=CHART_TYPES,
            width=170, height=30, font=ctk.CTkFont(size=11),
            fg_color="white", button_color="#b8cfe8",
            button_hover_color="#9abcd8", text_color="#1e2d3d",
            dropdown_fg_color="white", dropdown_text_color="#1e2d3d",
        ).grid(row=1, column=1, padx=(12, 0), pady=(2, 0))

        # ── Row 2: Data element / metric ────────────────────────
        ctk.CTkLabel(self, text="Data element / metric:",
                     font=ctk.CTkFont(size=11), text_color="#5a6a7a",
                     ).grid(row=2, column=0, sticky="w", padx=10)
        self.metric_entry = ctk.CTkEntry(
            self, height=30, font=ctk.CTkFont(size=12),
            placeholder_text="e.g. Confirmed malaria cases — aggregate sum per province")
        self.metric_entry.grid(row=3, column=0, sticky="ew", padx=10, pady=(2, 4))

        # ── Row 3: Description ──────────────────────────────────
        ctk.CTkLabel(self, text="Description:",
                     font=ctk.CTkFont(size=11), text_color="#5a6a7a",
                     ).grid(row=4, column=0, sticky="w", padx=10)
        self.desc_entry = ctk.CTkEntry(
            self, height=30, font=ctk.CTkFont(size=12),
            placeholder_text="e.g. Compare total cases across all provinces for selected period")
        self.desc_entry.grid(row=5, column=0, sticky="ew", padx=10, pady=(2, 4))

        # ── Row 4: Notes for AI ────────────────────────────────
        ctk.CTkLabel(self, text="Notes for AI:",
                     font=ctk.CTkFont(size=11), text_color="#5a6a7a",
                     ).grid(row=6, column=0, sticky="w", padx=10)
        self.notes_entry = ctk.CTkEntry(
            self, height=30, font=ctk.CTkFont(size=12),
            placeholder_text="e.g. Stacked by species (Pf/Pv), add a target line at 5000")
        self.notes_entry.grid(row=7, column=0, sticky="ew", padx=10, pady=(2, 10))

    def update_index(self, index: int):
        self._index = index
        self._hdr_lbl.configure(text=f"Chart {index}")

    def get_config(self) -> dict:
        return {
            "index":       self._index,
            "title":       self.title_entry.get().strip(),
            "chart_type":  self.type_var.get(),
            "metric":      self.metric_entry.get().strip(),
            "description": self.desc_entry.get().strip(),
            "notes":       self.notes_entry.get().strip(),
        }

    def is_valid(self) -> bool:
        return bool(self.title_entry.get().strip() and
                    self.metric_entry.get().strip())


class ChartConfigPanel(ctk.CTkFrame):
    """
    Panel where the user configures N charts before generating a dashboard.

    Callback: on_generate(configs: list[dict]) — called when user clicks Generate.
    """

    MIN_CHARTS     = 1
    MAX_CHARTS     = 10
    DEFAULT_CHARTS = 3

    def __init__(self, parent, on_generate, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._on_generate = on_generate
        self._cards: list[ChartCard] = []
        self._build()
        self._set_count(self.DEFAULT_CHARTS)

    # ── Build ─────────────────────────────────────────────────────

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar: count control + hint
        ctrl = ctk.CTkFrame(self, fg_color="#f0f4f8", corner_radius=8)
        ctrl.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ctk.CTkLabel(
            ctrl, text="Number of charts:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#1e2d3d",
        ).pack(side="left", padx=(16, 8), pady=10)

        ctk.CTkButton(
            ctrl, text="−", width=30, height=30,
            fg_color="#dde8f4", text_color=DHIS2_BLUE,
            hover_color="#c8d8e8", corner_radius=6,
            command=self._dec_count,
        ).pack(side="left")

        self._count_var = ctk.StringVar(value=str(self.DEFAULT_CHARTS))
        ctk.CTkLabel(
            ctrl, textvariable=self._count_var,
            width=40, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=DHIS2_BLUE,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            ctrl, text="+", width=30, height=30,
            fg_color="#dde8f4", text_color=DHIS2_BLUE,
            hover_color="#c8d8e8", corner_radius=6,
            command=self._inc_count,
        ).pack(side="left")

        ctk.CTkLabel(
            ctrl,
            text="Fill in each chart's details, then click Generate Dashboard.",
            font=ctk.CTkFont(size=11), text_color="#8aa3b8",
        ).pack(side="left", padx=16)

        # Scrollable cards area
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        # Footer: Generate button
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=2, column=0, sticky="e", pady=(10, 0))

        self._gen_btn = ctk.CTkButton(
            foot, text="Generate Dashboard ▶",
            width=210, height=38,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_generate_clicked,
        )
        self._gen_btn.pack()

    # ── Count management ──────────────────────────────────────────

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
        card = ChartCard(
            self._scroll, index=idx,
            on_remove=lambda c=None: self._remove_card(card))
        card.grid(row=idx - 1, column=0, sticky="ew", pady=(0, 10))
        self._cards.append(card)

    def _remove_card(self, card: ChartCard, _reindex: bool = True):
        if len(self._cards) <= self.MIN_CHARTS:
            return
        card.grid_forget()
        card.destroy()
        self._cards.remove(card)
        if _reindex:
            for i, c in enumerate(self._cards, 1):
                c.update_index(i)
                c.grid(row=i - 1, column=0, sticky="ew", pady=(0, 10))
        self._count_var.set(str(len(self._cards)))

    # ── Public API ────────────────────────────────────────────────

    def get_configs(self) -> list[dict]:
        return [c.get_config() for c in self._cards]

    def set_generating(self, generating: bool):
        if generating:
            self._gen_btn.configure(state="disabled", text="Generating…")
        else:
            self._gen_btn.configure(state="normal", text="Generate Dashboard ▶")

    def reset(self):
        for card in self._cards[:]:
            card.grid_forget()
            card.destroy()
        self._cards.clear()
        self._set_count(self.DEFAULT_CHARTS)

    # ── Internal ──────────────────────────────────────────────────

    def _on_generate_clicked(self):
        configs = self.get_configs()
        invalid = [c["index"] for c in configs
                   if not c["title"] or not c["metric"]]
        if invalid:
            names = ", ".join(f"Chart {i}" for i in invalid)
            msgbox.showwarning(
                "Missing required fields",
                f"{names}: Title and Data element/metric are required.")
            return
        self._on_generate(configs)
