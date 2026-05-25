import customtkinter as ctk
import tkinter as tk
import tempfile, os, webbrowser

BORDER   = "#d0dde8"
DHIS2_BLUE = "#1a6fa8"


class ReportView(ctk.CTkFrame):
    """
    Shows the generated HTML source and provides:
      - Preview in Browser
      - Deploy to DHIS2  (wired in by AppWindow via set_deploy_callback)
      - Copy HTML
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="white", corner_radius=8,
                         border_width=1, border_color=BORDER, **kwargs)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._html: str | None = None
        self._deploy_cb = None
        self._edit_cb = None
        self._build()

    def set_deploy_callback(self, cb):
        """AppWindow calls this to wire up the Deploy button."""
        self._deploy_cb = cb

    def set_edit_callback(self, cb):
        """Pass a callable to show the Edit Dashboard button; pass None to hide it."""
        self._edit_cb = cb
        if cb:
            self._edit_btn.grid()
        else:
            self._edit_btn.grid_remove()

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        # ── Toolbar ──
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

        self._deploy_btn = ctk.CTkButton(
            toolbar, text="Deploy to DHIS2 ▲", width=155, height=28,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            command=self._on_deploy,
        )
        self._deploy_btn.grid(row=0, column=5, padx=(0, 16), pady=8, sticky="e")

        # Hide action buttons until HTML is ready
        self._preview_btn.grid_remove()
        self._copy_btn.grid_remove()
        self._edit_btn.grid_remove()
        self._deploy_btn.grid_remove()

        # ── HTML source textbox ──
        self._code_box = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#1e1e2e",
            text_color="#cdd6f4",
            border_width=0,
            corner_radius=0,
            wrap="none",
        )
        self._code_box.grid(row=1, column=0, sticky="nsew")
        self._code_box.configure(state="disabled")

        # ── Empty state ──
        self._empty_lbl = ctk.CTkLabel(
            self,
            text="HTML report sẽ xuất hiện ở đây sau khi Generate.\n"
                 "Sau đó bạn có thể Preview và Deploy lên DHIS2.",
            font=ctk.CTkFont(size=12),
            text_color="#b0c0d0",
            justify="center",
        )
        self._empty_lbl.grid(row=1, column=0)

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
        self._deploy_btn.grid()
        # edit button visibility is controlled by set_edit_callback()

    def clear(self):
        self._html = None
        self._code_box.configure(state="normal")
        self._code_box.delete("1.0", "end")
        self._code_box.configure(state="disabled")
        self._preview_btn.grid_remove()
        self._copy_btn.grid_remove()
        self._edit_btn.grid_remove()
        self._deploy_btn.grid_remove()
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

    def _on_deploy(self):
        if self._deploy_cb:
            self._deploy_cb()
