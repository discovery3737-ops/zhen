"""小屏友好：左列 label 固定宽，右列控件填充。支持 set_tokens。"""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from app.ui.layout_profile import LayoutTokens


# 默认左侧标签宽度（WVGA 下可略小，由 tokens.pad_card*15 估算）
def _default_label_width(tokens: "LayoutTokens | None") -> int:
    return (tokens.pad_card * 15) if tokens else 120


class TwoColumnFormRow(QFrame):
    """单行表单：左侧 label 固定宽度，右侧由调用方传入的控件填充；最小高度 btn_h。"""

    def __init__(
        self,
        label: str,
        widget: QWidget,
        label_width: int | None = None,
        parent: QWidget | None = None,
        *,
        tokens: "LayoutTokens | None" = None,
    ):
        super().__init__(parent)
        self.setObjectName("twoColumnFormRow")
        self._tokens = tokens
        h = tokens.btn_h if tokens else 44
        self.setMinimumHeight(h)
        w = label_width if label_width is not None else _default_label_width(tokens)

        layout = QHBoxLayout(self)
        v = tokens.gap // 2 if tokens else 4
        layout.setContentsMargins(0, v, 0, v)
        layout.setSpacing(tokens.gap if tokens else 12)

        lbl = QLabel(label)
        lbl.setObjectName("twoColumnFormLabel")
        lbl.setMinimumWidth(w)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl)

        if not widget.objectName():
            widget.setObjectName("twoColumnFormWidget")
        layout.addWidget(widget, 1)

    def set_tokens(self, tokens: "LayoutTokens") -> None:
        self._tokens = tokens
        self.setMinimumHeight(tokens.btn_h)
        layout = self.layout()
        if layout:
            v = tokens.gap // 2
            layout.setContentsMargins(0, v, 0, v)
            layout.setSpacing(tokens.gap)
        lbl = self.findChild(QLabel)
        if lbl and tokens:
            lbl.setMinimumWidth(_default_label_width(tokens))
