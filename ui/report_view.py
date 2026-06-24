import customtkinter as ctk
import tkinter as tk
import tempfile, os, webbrowser

BORDER     = "#d0dde8"
DHIS2_BLUE = "#1a6fa8"


class ReportView(ctk.CTkFrame):
    """
    Shows the generated HTML source and provides:
      - Preview in Browser
      - Verify DEs (cross-check analytics call IDs against metadata)
      - Deploy to DHIS2  (wired in by AppWindow via set_deploy_callback)
      - Copy HTML
    Report name is entered here — required before deploy.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="white", corner_radius=8,
                         border_width=1, border_color=BORDER, **kwargs)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._html: str | None = None
        self._deploy_cb  = None
        self._verify_cb  = None
        self._edit_cb    = None
        self._build()

    def set_deploy_callback(self, cb):
        self._deploy_cb = cb

    def set_verify_callback(self, cb):
        self._verify_cb = cb

    def set_edit_callback(self, cb):
        self._edit_cb = cb
        if cb:
            self._edit_btn.grid()
        else:
            self._edit_btn.grid_remove()

    def get_report_name(self) -> str:
        return self._name_entry.get().strip()

    def focus_report_name(self):
        self._name_entry.focus_set()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        # ── Row 0: action toolbar ──
        toolbar = ctk.CTkFrame(self, fg_color="#f0f4f8", corner_radius=0,
                               border_width=0, height=44)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)
        toolbar.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            toolbar, text="Generated HTML Report",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#1e2d3d",
        ).grid(row=0, column=0, padx=16, pady=10, sticky="w")

        self._preview_btn = ctk.CTkButton(
            toolbar, text="Preview in Browser", width=140, height=28,
            fg_color="transparent", border_width=1, border_color=DHIS2_BLUE,
            text_color=DHIS2_BLUE, hover_color="#e8f0f8",
            command=self._on_preview,
        )
        self._preview_btn.grid(row=0, column=1, padx=(0, 8), pady=8)

        self._copy_btn = ctk.CTkButton(
            toolbar, text="Copy HTML", width=100, height=28,
            fg_color="transparent", border_width=1, border_color="#8aa3b8",
            text_color="#4a6278", hover_color="#e8f0f8",
            command=self._on_copy,
        )
        self._copy_btn.grid(row=0, column=2, padx=(0, 8), pady=8)

        self._edit_btn = ctk.CTkButton(
            toolbar, text="✏ Edit Dashboard", width=140, height=28,
            fg_color="transparent", border_width=1, border_color="#f39c12",
            text_color="#f39c12", hover_color="#fff8e8",
            command=self._on_edit,
        )
        self._edit_btn.grid(row=0, column=4, padx=(0, 8), pady=8, sticky="e")

        # Hide until HTML ready
        self._preview_btn.grid_remove()
        self._copy_btn.grid_remove()
        self._edit_btn.grid_remove()

        # ── Row 1: deploy bar (name + verify + deploy) ──
        deploy_bar = ctk.CTkFrame(self, fg_color="#e8f4ec", corner_radius=0,
                                  border_width=0, height=40)
        deploy_bar.grid(row=1, column=0, sticky="ew")
        deploy_bar.grid_propagate(False)
        deploy_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            deploy_bar, text="Report name:",
            font=ctk.CTkFont(size=11), text_color="#2d6a3f",
        ).grid(row=0, column=0, padx=(14, 6), pady=8, sticky="w")

        self._name_entry = ctk.CTkEntry(
            deploy_bar,
            placeholder_text="Enter report name… (required to deploy)",
            height=28, font=ctk.CTkFont(size=11),
        )
        self._name_entry.grid(row=0, column=1, padx=(0, 10), pady=6, sticky="ew")

        self._verify_btn = ctk.CTkButton(
            deploy_bar, text="🔍 Verify DEs", width=130, height=28,
            fg_color="transparent", border_width=1, border_color="#2d8a5f",
            text_color="#2d6a3f", hover_color="#d4edda",
            font=ctk.CTkFont(size=11),
            command=self._on_verify,
        )
        self._verify_btn.grid(row=0, column=2, padx=(0, 8), pady=6)

        self._deploy_btn = ctk.CTkButton(
            deploy_bar, text="Deploy to DHIS2 ▲", width=155, height=28,
            fg_color="#27ae60", hover_color="#1e8449",
            font=ctk.CTkFont(size=11),
            command=self._on_deploy,
        )
        self._deploy_btn.grid(row=0, column=3, padx=(0, 14), pady=6)

        # Hide deploy bar until HTML ready
        deploy_bar.grid_remove()
        self._deploy_bar = deploy_bar

        # ── Row 2: HTML source textbox ──
        self._code_box = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#1e1e2e",
            text_color="#cdd6f4",
            border_width=0,
            corner_radius=0,
            wrap="none",
        )
        self._code_box.grid(row=2, column=0, sticky="nsew")
        self._code_box.configure(state="disabled")

        # ── Empty state ──
        self._empty_lbl = ctk.CTkLabel(
            self,
            text="The HTML report will appear here after Generate.\n"
                 "You can then Preview and Deploy to DHIS2.",
            font=ctk.CTkFont(size=12),
            text_color="#b0c0d0",
            justify="center",
        )
        self._empty_lbl.grid(row=2, column=0)

    # ─── Public API ──────────────────────────────────────────────────────────

    def show(self, html: str):
        self._html = html
        self._code_box.configure(state="normal")
        self._code_box.delete("1.0", "end")
        self._code_box.insert("1.0", html)
        self._code_box.configure(state="disabled")

        self._empty_lbl.grid_remove()
        self._preview_btn.grid()
        self._copy_btn.grid()
        self._deploy_bar.grid()

    def clear(self):
        self._html = None
        self._code_box.configure(state="normal")
        self._code_box.delete("1.0", "end")
        self._code_box.configure(state="disabled")
        self._preview_btn.grid_remove()
        self._copy_btn.grid_remove()
        self._edit_btn.grid_remove()
        self._deploy_bar.grid_remove()
        self._empty_lbl.grid()

    def get_html(self) -> str | None:
        return self._html

    # ─── Actions ─────────────────────────────────────────────────────────────

    def _on_preview(self):
        if not self._html:
            return
        from llm.html_utils import fix_cdn_links
        html = fix_cdn_links(self._html)
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w", encoding="utf-8"
        )
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file:///{tmp.name.replace(os.sep, '/')}")

    def _on_copy(self):
        if not self._html:
            return
        self.clipboard_clear()
        self.clipboard_append(self._html)
        self._copy_btn.configure(text="Copied ✓")
        self.after(2000, lambda: self._copy_btn.configure(text="Copy HTML"))

    def _on_edit(self):
        if self._edit_cb:
            self._edit_cb()

    def _on_verify(self):
        if self._verify_cb and self._html:
            self._verify_cb(self._html)

    def _on_deploy(self):
        if self._deploy_cb:
            self._deploy_cb()
