"""More 菜单：车机底部弹出的 bottom-sheet（全屏半透明遮罩 + 底部 QFrame#bottomSheet），2 列网格 + 关闭按钮，Esc 关闭，样式由 theme.qss 统一。"""

import logging

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QWidget,
    QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut

from app.ui.layout_profile import LayoutTokens, get_tokens

logger = logging.getLogger(__name__)

MORE_ITEMS = [
    ("灯光", 4),
    ("环境", 5),
    ("摄像头", 6),
    ("诊断", 7),
    ("设置", 8),
]


class _Overlay(QWidget):
    """半透明遮罩，点击关闭"""

    def __init__(self, dialog: QDialog, parent=None):
        super().__init__(parent)
        self._dialog = dialog

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dialog.reject()
        super().mousePressEvent(event)


class MoreMenuDialog(QDialog):
    """More 底部弹层：全屏遮罩 + 底部 sheet，2 列网格 5 入口，关闭按钮，Esc 关闭，emit page_selected(int) 后关闭。"""

    page_selected = pyqtSignal(int)

    def __init__(self, tokens: LayoutTokens | None = None, parent=None):
        super().__init__(parent)
        self._tokens = tokens or get_tokens()
        self.setWindowTitle("更多")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        if parent and parent.isVisible():
            self.setGeometry(parent.geometry())
        self._setup_ui()
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.reject)

    def _setup_ui(self):
        t = self._tokens
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        overlay = _Overlay(self, self)
        overlay.setObjectName("bottomSheetOverlay")
        root.addWidget(overlay, 1)

        sheet = QFrame(objectName="bottomSheet")
        sheet_ly = QVBoxLayout(sheet)
        sheet_ly.setSpacing(t.gap)
        sheet_ly.setContentsMargins(t.pad_page, t.pad_page, t.pad_page, t.pad_page)

        header = QHBoxLayout()
        title = QLabel("更多")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("shortcutBtn")
        close_btn.setMinimumHeight(t.btn_h_key)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        sheet_ly.addLayout(header)

        grid = QGridLayout()
        for i, (label, idx) in enumerate(MORE_ITEMS):
            btn = QPushButton(label, objectName="moreMenuItem")
            btn.setMinimumHeight(t.btn_h_key)
            btn.setProperty("stack_index", idx)
            btn.clicked.connect(lambda checked, index=idx: self._on_item_clicked(index))
            row, col = i // 2, i % 2
            grid.addWidget(btn, row, col)
        sheet_ly.addLayout(grid)

        root.addWidget(sheet, 0)

    def _on_item_clicked(self, stack_index: int):
        self.page_selected.emit(stack_index)
        self.accept()
