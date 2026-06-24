"""Multi-turn chat widget for the Auto Report app — PySide6 version."""
from PySide6.QtWidgets import (
    QFrame, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QHBoxLayout, QVBoxLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QColor

DHIS2_BLUE = "#1a6fa8"


class ChatPanel(QFrame):
    """
    Multi-turn chat widget.
    Stores messages as list[dict] with role/content.
    set_send_callback(cb) — called with (text: str) when user sends.
    """

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setStyleSheet(
            "ChatPanel { border: 1px solid #d0dde8; border-radius: 8px; background: white; }"
        )

        self._messages: list[dict] = []
        self._send_cb = None
        self._clear_cb = None
        self._generating = False
        self._locked = False

        self._build()

    # ── Public API ──────────────────────────────────────────────────────────

    def set_send_callback(self, cb):
        self._send_cb = cb

    def set_clear_callback(self, cb):
        """Called when user clicks the 'Clear' button — app can run cleanup + show template."""
        self._clear_cb = cb

    def add_user_message(self, text: str):
        self._messages.append({"role": "user", "content": text})
        self._append(text, "user")

    def add_assistant_message(self, text: str):
        self._messages.append({"role": "assistant", "content": text})
        self._append(text, "asst")

    def add_system_note(self, text: str):
        """Non-LLM note (e.g. 'HTML generated') — NOT added to messages list."""
        self._append(text, "note")

    def add_welcome_message(self, text: str):
        """Display assistant-styled welcome/template — NOT added to messages list."""
        self._append(text, "asst")

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def clear(self):
        self._messages.clear()
        self._txt.clear()

    def set_locked(self, locked: bool):
        """Lock input entirely (not connected). Different from set_generating."""
        self._locked = locked
        if locked:
            self._entry.setEnabled(False)
            self._entry.setPlaceholderText("Connect to DHIS2 first to get started…")
            self._send_btn.setEnabled(False)
            self._send_btn.setText("Send ↵")
        else:
            self._entry.setEnabled(True)
            self._entry.setPlaceholderText("Enter your request or question…")
            self._send_btn.setEnabled(True)
            self._send_btn.setText("Send ↵")

    def set_generating(self, flag: bool):
        self._generating = flag
        enabled = not flag
        self._entry.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._send_btn.setText("…" if flag else "Send ↵")

    def set_hint(self, text: str):
        self._hint_lbl.setText(text)

    # ── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Header bar ──────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(34)
        hdr.setStyleSheet(
            "QFrame { background: #f0f4f8; border: none; border-radius: 0px; }"
        )
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(12, 0, 8, 0)
        hdr_layout.setSpacing(6)

        title_lbl = QLabel("💬 Chat")
        title_lbl.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #1e2d3d; background: transparent;"
        )

        self._hint_lbl = QLabel("Describe your report → click Generate")
        self._hint_lbl.setStyleSheet(
            "font-size: 10px; color: #8aa3b8; background: transparent;"
        )
        self._hint_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedSize(46, 22)
        clear_btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 10px; color: #6b8299;"
            "  background: transparent;"
            "  border: 1px solid #c8d8e8;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover { background: #e8f0f8; }"
        )
        clear_btn.clicked.connect(self._on_xoa_click)

        hdr_layout.addWidget(title_lbl)
        hdr_layout.addWidget(self._hint_lbl)
        hdr_layout.addWidget(clear_btn)

        root_layout.addWidget(hdr)

        # ── Chat display ─────────────────────────────────────────────────────
        self._txt = QTextEdit()
        self._txt.setReadOnly(True)
        self._txt.setStyleSheet(
            "QTextEdit {"
            "  background: #f8fbff;"
            "  border: none;"
            "  font-family: 'Segoe UI', sans-serif;"
            "  font-size: 11px;"
            "  padding: 6px 10px;"
            "}"
            "QScrollBar:vertical {"
            "  width: 10px; background: #f0f4f8;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: #c8d8e8; border-radius: 4px; min-height: 20px;"
            "}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }"
        )
        self._txt.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root_layout.addWidget(self._txt, stretch=1)

        # ── Input bar ────────────────────────────────────────────────────────
        inp = QFrame()
        inp.setFixedHeight(42)
        inp.setStyleSheet(
            "QFrame { background: #f0f4f8; border: none; }"
        )
        inp_layout = QHBoxLayout(inp)
        inp_layout.setContentsMargins(10, 6, 10, 6)
        inp_layout.setSpacing(6)

        self._entry = QLineEdit()
        self._entry.setPlaceholderText("Enter your request or question…")
        self._entry.setFixedHeight(30)
        self._entry.setStyleSheet(
            "QLineEdit {"
            "  font-size: 12px;"
            "  border: 1px solid #c8d8e8;"
            "  border-radius: 4px;"
            "  padding: 0 8px;"
            "  background: white;"
            "}"
            "QLineEdit:focus { border-color: #1a6fa8; }"
            "QLineEdit:disabled { background: #eef2f6; color: #aab8c4; }"
        )
        self._entry.returnPressed.connect(self._on_send)

        self._send_btn = QPushButton("Send ↵")
        self._send_btn.setFixedSize(78, 30)
        self._send_btn.setStyleSheet(
            "QPushButton {"
            f"  background: {DHIS2_BLUE};"
            "  color: white;"
            "  font-size: 12px;"
            "  border: none;"
            "  border-radius: 4px;"
            "}"
            "QPushButton:hover { background: #155a8a; }"
            "QPushButton:disabled { background: #8ab8d8; color: #d0e8f4; }"
        )
        self._send_btn.clicked.connect(self._on_send)

        inp_layout.addWidget(self._entry)
        inp_layout.addWidget(self._send_btn)

        root_layout.addWidget(inp)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _on_xoa_click(self):
        if self._clear_cb:
            self._clear_cb()  # delegate entirely to app_window._on_clear
        else:
            self.clear()

    def _on_send(self):
        text = self._entry.text().strip()
        if not text or self._generating or self._locked:
            return
        self._entry.clear()
        self.add_user_message(text)
        if self._send_cb:
            self._send_cb(text)

    def _append(self, text: str, kind: str):
        cursor = self._txt.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._txt.setTextCursor(cursor)

        if kind == "note":
            self._txt.insertHtml(
                "<div style='"
                "  text-align: center;"
                "  color: #8aa3b8;"
                "  font-size: 9px;"
                "  font-style: italic;"
                "  margin: 4px 0;"
                f"'>&#8212; {self._escape(text)} &#8212;</div>"
            )
        elif kind == "user":
            self._txt.insertHtml(
                "<div style='margin: 6px 0 2px 0;'>"
                f"<span style='color: {DHIS2_BLUE}; font-weight: bold; font-size: 10px;'>You:&nbsp;&nbsp;</span>"
                f"<span style='color: #1e2d3d; font-size: 11px;'>{self._escape(text)}</span>"
                "</div>"
            )
        else:  # asst
            self._txt.insertHtml(
                "<div style='margin: 6px 0 2px 0;'>"
                "<span style='color: #374151; font-weight: bold; font-size: 10px;'>Claude:&nbsp;&nbsp;</span>"
                f"<span style='color: #374151; font-size: 11px;'>{self._escape(text)}</span>"
                "</div>"
            )

        # Auto-scroll to bottom
        scrollbar = self._txt.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @staticmethod
    def _escape(text: str) -> str:
        """Minimal HTML escaping for safe insertHtml use."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "<br>")
        )
