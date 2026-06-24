import tempfile, os, webbrowser

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QApplication, QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette


class ReportView(QFrame):
    """
    Shows the generated HTML source and provides:
      - Preview in Browser
      - Verify DEs (cross-check analytics call IDs against metadata)
      - Deploy to DHIS2  (wired in by AppWindow via set_deploy_callback)
      - Copy HTML
    Report name is entered here — required before deploy.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "ReportView { background: white; border: 1px solid #d0dde8; border-radius: 8px; }"
        )

        self._html: str | None = None
        self._deploy_cb = None
        self._verify_cb = None
        self._edit_cb = None

        self._build()

    # ─── Public API ──────────────────────────────────────────────────────────

    def set_deploy_callback(self, cb):
        self._deploy_cb = cb

    def set_verify_callback(self, cb):
        self._verify_cb = cb

    def set_edit_callback(self, cb):
        self._edit_cb = cb
        if cb:
            self._edit_btn.setVisible(True)
        else:
            self._edit_btn.setVisible(False)

    def get_report_name(self) -> str:
        return self._name_entry.text().strip()

    def focus_report_name(self):
        self._name_entry.setFocus()

    def show(self, html: str):
        self._html = html
        self._code_box.setPlainText(html)

        self._empty_lbl.setVisible(False)
        self._code_box.setVisible(True)
        self._preview_btn.setVisible(True)
        self._copy_btn.setVisible(True)
        self._deploy_bar.setVisible(True)
        # Edit button visibility is controlled by set_edit_callback; only show
        # it here if a callback was already registered.
        if self._edit_cb:
            self._edit_btn.setVisible(True)

    def clear(self):
        self._html = None
        self._code_box.setPlainText("")
        self._code_box.setVisible(False)
        self._preview_btn.setVisible(False)
        self._copy_btn.setVisible(False)
        self._edit_btn.setVisible(False)
        self._deploy_bar.setVisible(False)
        self._empty_lbl.setVisible(True)

    def get_html(self) -> str | None:
        return self._html

    # ─── Layout ──────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Row 0: action toolbar ─────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setFixedHeight(44)
        toolbar.setStyleSheet("background: #f0f4f8; border: none;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 0, 8, 0)
        toolbar_layout.setSpacing(8)

        title_lbl = QLabel("Generated HTML Report")
        title_lbl.setStyleSheet(
            "color: #1e2d3d; font-size: 12px; font-weight: bold; background: transparent;"
        )
        toolbar_layout.addWidget(title_lbl)
        toolbar_layout.addStretch(1)

        self._preview_btn = QPushButton("Preview in Browser")
        self._preview_btn.setFixedHeight(28)
        self._preview_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; border: 1px solid #1a6fa8;"
            "  color: #1a6fa8; border-radius: 4px; padding: 0 10px; font-size: 11px;"
            "}"
            "QPushButton:hover { background: #e8f0f8; }"
        )
        self._preview_btn.clicked.connect(self._on_preview)
        toolbar_layout.addWidget(self._preview_btn)

        self._copy_btn = QPushButton("Copy HTML")
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; border: 1px solid #8aa3b8;"
            "  color: #4a6278; border-radius: 4px; padding: 0 10px; font-size: 11px;"
            "}"
            "QPushButton:hover { background: #e8f0f8; }"
        )
        self._copy_btn.clicked.connect(self._on_copy)
        toolbar_layout.addWidget(self._copy_btn)

        self._edit_btn = QPushButton("✏ Edit Dashboard")
        self._edit_btn.setFixedHeight(28)
        self._edit_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; border: 1px solid #f39c12;"
            "  color: #f39c12; border-radius: 4px; padding: 0 10px; font-size: 11px;"
            "}"
            "QPushButton:hover { background: #fff8e8; }"
        )
        self._edit_btn.clicked.connect(self._on_edit)
        toolbar_layout.addWidget(self._edit_btn)

        # Hide until HTML is ready / callback registered
        self._preview_btn.setVisible(False)
        self._copy_btn.setVisible(False)
        self._edit_btn.setVisible(False)

        root.addWidget(toolbar)

        # ── Row 1: deploy bar ─────────────────────────────────────────────────
        deploy_bar = QFrame()
        deploy_bar.setFixedHeight(40)
        deploy_bar.setStyleSheet("background: #e8f4ec; border: none;")
        deploy_layout = QHBoxLayout(deploy_bar)
        deploy_layout.setContentsMargins(14, 0, 14, 0)
        deploy_layout.setSpacing(8)

        name_lbl = QLabel("Report name:")
        name_lbl.setStyleSheet(
            "color: #2d6a3f; font-size: 11px; background: transparent;"
        )
        deploy_layout.addWidget(name_lbl)

        self._name_entry = QLineEdit()
        self._name_entry.setPlaceholderText("Enter report name… (required to deploy)")
        self._name_entry.setFixedHeight(28)
        self._name_entry.setStyleSheet(
            "QLineEdit { font-size: 11px; border: 1px solid #b0ccb8;"
            "  border-radius: 4px; padding: 0 6px; background: white; }"
        )
        deploy_layout.addWidget(self._name_entry, 1)

        self._verify_btn = QPushButton("\U0001f50d Verify DEs")
        self._verify_btn.setFixedHeight(28)
        self._verify_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; border: 1px solid #2d8a5f;"
            "  color: #2d6a3f; border-radius: 4px; padding: 0 10px; font-size: 11px;"
            "}"
            "QPushButton:hover { background: #d4edda; }"
        )
        self._verify_btn.clicked.connect(self._on_verify)
        deploy_layout.addWidget(self._verify_btn)

        self._deploy_btn = QPushButton("Deploy to DHIS2 ▲")
        self._deploy_btn.setFixedHeight(28)
        self._deploy_btn.setStyleSheet(
            "QPushButton {"
            "  background: #27ae60; color: white; border: none;"
            "  border-radius: 4px; padding: 0 14px; font-size: 11px; font-weight: bold;"
            "}"
            "QPushButton:hover { background: #1e8449; }"
        )
        self._deploy_btn.clicked.connect(self._on_deploy)
        deploy_layout.addWidget(self._deploy_btn)

        # Hide deploy bar until HTML is ready
        deploy_bar.setVisible(False)
        self._deploy_bar = deploy_bar

        root.addWidget(deploy_bar)

        # ── Row 2: HTML source text box ───────────────────────────────────────
        self._code_box = QTextEdit()
        self._code_box.setReadOnly(True)
        self._code_box.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        code_font = QFont("Consolas", 11)
        code_font.setStyleHint(QFont.StyleHint.Monospace)
        self._code_box.setFont(code_font)
        self._code_box.setStyleSheet(
            "QTextEdit {"
            "  background: #1e1e2e; color: #cdd6f4;"
            "  border: none; border-radius: 0;"
            "}"
        )
        self._code_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._code_box.setVisible(False)
        root.addWidget(self._code_box, 1)

        # ── Empty state label ─────────────────────────────────────────────────
        self._empty_lbl = QLabel(
            "The HTML report will appear here after Generate.\n"
            "You can then Preview and Deploy to DHIS2."
        )
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            "color: #b0c0d0; font-size: 12px; background: transparent;"
        )
        self._empty_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._empty_lbl, 1)

    # ─── Actions ─────────────────────────────────────────────────────────────

    def _on_preview(self):
        if not self._html:
            return
        try:
            from llm.html_utils import fix_cdn_links
            html = fix_cdn_links(self._html)
        except ImportError:
            html = self._html
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".html", mode="w", encoding="utf-8"
        )
        tmp.write(html)
        tmp.close()
        webbrowser.open(f"file:///{tmp.name.replace(os.sep, '/')}")

    def _on_copy(self):
        if not self._html:
            return
        QApplication.clipboard().setText(self._html)
        self._copy_btn.setText("Copied ✓")
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("Copy HTML"))

    def _on_edit(self):
        if self._edit_cb:
            self._edit_cb()

    def _on_verify(self):
        if self._verify_cb and self._html:
            self._verify_cb(self._html)

    def _on_deploy(self):
        if self._deploy_cb:
            self._deploy_cb()
