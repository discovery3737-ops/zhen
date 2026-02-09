"""小屏友好：左列 label 固定宽（如 120px），右列控件填充。依赖 QSS，不写死颜色。"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt


# 默认左侧标签宽度，可由 QSS 或调用方覆盖
DEFAULT_LABEL_WIDTH = 120


class TwoColumnFormRow(QFrame):
    """单行表单：左侧 label 固定宽度，右侧由调用方传入的控件填充。"""

    def __init__(
        self,
        label: str,
        widget: QWidget,
        label_width: int = DEFAULT_LABEL_WIDTH,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("twoColumnFormRow")
        self.setMinimumHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        lbl = QLabel(label)
        lbl.setObjectName("twoColumnFormLabel")
        lbl.setMinimumWidth(label_width)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(lbl)

        widget.setObjectName("twoColumnFormWidget")
        layout.addWidget(widget, 1)

    @staticmethod
    def label_width() -> int:
        return DEFAULT_LABEL_WIDTH
