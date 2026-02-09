"""页面基类 - 由 LayoutTokens 控制间距/字号"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from app.ui.layout_profile import LayoutTokens


class PageBase(QWidget):
    """页面统一基类：大标题 + TODO 占位。支持 set_tokens 注入布局 token。"""

    def __init__(self, title: str):
        super().__init__()
        self._tokens: LayoutTokens | None = None
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)

        todo_label = QLabel("TODO")
        todo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        todo_label.setObjectName("accent")
        todo_label.setStyleSheet("font-size: 14px;")
        layout.addWidget(todo_label)

        layout.addStretch()

    def set_tokens(self, tokens: LayoutTokens) -> None:
        """注入布局 profile tokens，子类可覆盖以应用 pad_page/gap 等。"""
        self._tokens = tokens
        layout = self.layout()
        if layout and tokens:
            layout.setSpacing(tokens.gap)
            layout.setContentsMargins(
                tokens.pad_page, tokens.pad_page,
                tokens.pad_page, tokens.pad_page,
            )
