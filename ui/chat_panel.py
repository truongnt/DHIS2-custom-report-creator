"""Multi-turn chat widget for the Auto Report app."""
import customtkinter as ctk
import tkinter as tk

DHIS2_BLUE = "#1a6fa8"


class ChatPanel(ctk.CTkFrame):
    """
    Multi-turn chat widget.
    Stores messages as list[dict] with role/content.
    set_send_callback(cb) — called with (text: str) when user sends.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="white", corner_radius=8,
                         border_width=1, border_color="#d0dde8", **kwargs)
        self._messages: list[dict] = []
        self._send_cb = None
        self._generating = False
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._build()

    # ── Public API ──────────────────────────────────────────────────────────

    def set_send_callback(self, cb):
        self._send_cb = cb

    def add_user_message(self, text: str):
        self._messages.append({"role": "user", "content": text})
        self._append(text, "user")

    def add_assistant_message(self, text: str):
        self._messages.append({"role": "assistant", "content": text})
        self._append(text, "asst")

    def add_system_note(self, text: str):
        """Non-LLM note (e.g. 'HTML generated') — NOT added to messages list."""
        self._append(text, "note")

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def clear(self):
        self._messages.clear()
        self._txt.configure(state="normal")
        self._txt.delete("1.0", "end")
        self._txt.configure(state="disabled")

    def set_generating(self, flag: bool):
        self._generating = flag
        state = "disabled" if flag else "normal"
        self._entry.configure(state=state)
        self._send_btn.configure(state=state, text="…" if flag else "Gửi ↵")

    def set_hint(self, text: str):
        self._hint_lbl.configure(text=text)

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header row
        hdr = ctk.CTkFrame(self, fg_color="#f0f4f8", corner_radius=0, height=34)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="💬 Chat",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#1e2d3d").grid(row=0, column=0, padx=12, pady=6, sticky="w")

        self._hint_lbl = ctk.CTkLabel(
            hdr, text="Mô tả báo cáo → nhấn Generate",
            font=ctk.CTkFont(size=10), text_color="#8aa3b8")
        self._hint_lbl.grid(row=0, column=1, padx=6, sticky="w")

        ctk.CTkButton(
            hdr, text="Xóa", width=46, height=22,
            fg_color="transparent", border_width=1, border_color="#c8d8e8",
            text_color="#6b8299", hover_color="#e8f0f8",
            font=ctk.CTkFont(size=10),
            command=self.clear,
        ).grid(row=0, column=2, padx=8, pady=6, sticky="e")

        # Chat display — tk.Text with tag-based coloring
        txt_frame = tk.Frame(self, bg="#f8fbff")
        txt_frame.grid(row=1, column=0, sticky="nsew")
        txt_frame.grid_rowconfigure(0, weight=1)
        txt_frame.grid_columnconfigure(0, weight=1)

        self._txt = tk.Text(
            txt_frame,
            state="disabled",
            bg="#f8fbff",
            relief="flat",
            font=("Segoe UI", 11),
            wrap="word",
            bd=0,
            padx=10,
            pady=6,
            cursor="arrow",
            selectbackground="#dbeafe",
        )
        self._txt.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(txt_frame, command=self._txt.yview, width=10)
        sb.grid(row=0, column=1, sticky="ns")
        self._txt.configure(yscrollcommand=sb.set)

        # Tags
        self._txt.tag_configure("user_prefix",
            foreground=DHIS2_BLUE, font=("Segoe UI", 10, "bold"))
        self._txt.tag_configure("user_body",
            foreground="#1e2d3d", lmargin1=14, lmargin2=14)
        self._txt.tag_configure("asst_prefix",
            foreground="#374151", font=("Segoe UI", 10, "bold"))
        self._txt.tag_configure("asst_body",
            foreground="#374151", lmargin1=14, lmargin2=14)
        self._txt.tag_configure("note",
            foreground="#8aa3b8", font=("Segoe UI", 9, "italic"),
            justify="center")

        # Input row
        inp = ctk.CTkFrame(self, fg_color="#f0f4f8", corner_radius=0, height=42)
        inp.grid(row=2, column=0, sticky="ew")
        inp.grid_propagate(False)
        inp.grid_columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            inp, placeholder_text="Nhập yêu cầu hoặc câu hỏi…",
            font=ctk.CTkFont(size=12), height=30,
        )
        self._entry.grid(row=0, column=0, padx=(10, 6), pady=6, sticky="ew")
        self._entry.bind("<Return>", lambda e: self._on_send())

        self._send_btn = ctk.CTkButton(
            inp, text="Gửi ↵", width=78, height=30,
            fg_color=DHIS2_BLUE, hover_color="#155a8a",
            font=ctk.CTkFont(size=12),
            command=self._on_send,
        )
        self._send_btn.grid(row=0, column=1, padx=(0, 10), pady=6)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_send(self):
        text = self._entry.get().strip()
        if not text or self._generating:
            return
        self._entry.delete(0, "end")
        self.add_user_message(text)
        if self._send_cb:
            self._send_cb(text)

    def _append(self, text: str, kind: str):
        self._txt.configure(state="normal")
        if kind == "note":
            self._txt.insert("end", f"\n— {text} —\n", "note")
        elif kind == "user":
            self._txt.insert("end", "\nBạn:  ", "user_prefix")
            self._txt.insert("end", text + "\n", "user_body")
        else:
            self._txt.insert("end", "\nClaude:  ", "asst_prefix")
            self._txt.insert("end", text + "\n", "asst_body")
        self._txt.configure(state="disabled")
        self._txt.see("end")
