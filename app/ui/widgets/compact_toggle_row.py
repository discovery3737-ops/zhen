"""小屏友好：左侧 label（可带副标题），右侧 Switch/Checkbox，整体高度 >= btn_h。支持 set_tokens。"""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox, QWidget
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from app.ui.layout_profile import LayoutTokens


class CompactToggleRow(QFrame):
    """单行：左侧主标题（可选副标题），右侧开关/复选框；最小高度 btn_h。"""

    def __init__(
        self,
        label: str,
        subtitle: str = "",
        tokens: "LayoutTokens | None" = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("compactToggleRow")
        self._tokens = tokens
        h = tokens.btn_h if tokens else 44
        self.setMinimumHeight(h)

        layout = QHBoxLayout(self)
        v = tokens.gap // 2 if tokens else 4
        layout.setContentsMargins(0, v, 0, v)
        layout.setSpacing(tokens.gap if tokens else 12)

        # 左侧：主标题 + 可选副标题
        label_w = QWidget()
        label_ly = QVBoxLayout(label_w)
        label_ly.setContentsMargins(0, 0, 0, 0)
        label_ly.setSpacing(0)
        self._title_label = QLabel(label)
        self._title_label.setObjectName("compactToggleTitle")
        label_ly.addWidget(self._title_label)
        self._subtitle_label: QLabel | None = None
        if subtitle:
            self._subtitle_label = QLabel(subtitle)
            self._subtitle_label.setObjectName("compactToggleSubtitle")
            label_ly.addWidget(self._subtitle_label)
        layout.addWidget(label_w, 1)

        # 右侧：开关（QCheckBox，由 QSS 可做成 Switch 样式）
        self._check = QCheckBox()
        self._check.setObjectName("compactToggleSwitch")
        layout.addWidget(self._check, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def set_title(self, text: str) -> None:
        self._title_label.setText(text)

    def set_subtitle(self, text: str) -> None:
        if self._subtitle_label is not None:
            self._subtitle_label.setText(text)
            self._subtitle_label.setVisible(bool(text))

    def set_checked(self, checked: bool) -> None:
        self._check.setChecked(checked)

    def is_checked(self) -> bool:
        return self._check.isChecked()

    def checkbox(self) -> QCheckBox:
        """暴露右侧 QCheckBox，便于连接 toggled/clicked 与 setChecked。"""
        return self._check

    def set_tokens(self, tokens: "LayoutTokens") -> None:
        self._tokens = tokens
        self.setMinimumHeight(tokens.btn_h)
        layout = self.layout()
        if layout:
            v = tokens.gap // 2
            layout.setContentsMargins(0, v, 0, v)
            layout.setSpacing(tokens.gap)
