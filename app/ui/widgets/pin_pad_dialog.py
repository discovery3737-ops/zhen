"""维护 PIN 输入对话框：数字键盘，触控友好，4~8 位数字。"""

from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QWidget,
    QSizePolicy,
)
from PyQt6.QtCore import Qt

if TYPE_CHECKING:
    from app.ui.layout_profile import LayoutTokens


PIN_MIN_LEN = 4
PIN_MAX_LEN = 8


class PinPadDialog(QDialog):
    """数字键盘 PIN 输入：4~8 位，确认返回输入的 PIN 字符串，取消/错误返回 None。"""

    def __init__(
        self,
        title: str = "输入维护 PIN",
        tokens: "LayoutTokens | None" = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._tokens = tokens
        self._pin: list[str] = []
        self.setWindowTitle(title)
        self.setModal(True)
        bh = tokens.btn_h_key if tokens else 52
        pad = tokens.pad_card if tokens else 12
        self._setup_ui(bh, pad)

    def _setup_ui(self, btn_height: int, pad: int) -> None:
        ly = QVBoxLayout(self)
        ly.setSpacing(pad)
        ly.setContentsMargins(pad, pad, pad, pad)

        self._display = QLabel("••••")
        self._display.setObjectName("bigNumber")
        self._display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._display.setMinimumHeight(btn_height)
        self._display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        ly.addWidget(self._display)

        # 3x4 数字 + 底部操作
        grid = QGridLayout()
        # 1 2 3
        # 4 5 6
        # 7 8 9
        # 空 0 退格
        for row, digits in enumerate([("1", "2", "3"), ("4", "5", "6"), ("7", "8", "9"), ("", "0", "⌫")]):
            for col, d in enumerate(digits):
                if d == "⌫":
                    btn = QPushButton("退格")
                    btn.setMinimumHeight(btn_height)
                    btn.clicked.connect(self._on_backspace)
                elif d:
                    btn = QPushButton(d)
                    btn.setMinimumHeight(btn_height)
                    btn.clicked.connect(lambda checked=False, x=d: self._on_digit(x))
                else:
                    btn = QWidget()
                    btn.setFixedHeight(btn_height)
                    btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                grid.addWidget(btn, row, col)

        ly.addLayout(grid)

        # 清除 / 确定 / 取消
        row_ly = QHBoxLayout()
        clear_btn = QPushButton("清除")
        clear_btn.setMinimumHeight(btn_height)
        clear_btn.clicked.connect(self._on_clear)
        ok_btn = QPushButton("确定")
        ok_btn.setMinimumHeight(btn_height)
        ok_btn.setProperty("primary", True)
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(btn_height)
        cancel_btn.clicked.connect(self.reject)
        row_ly.addWidget(clear_btn)
        row_ly.addWidget(ok_btn)
        row_ly.addWidget(cancel_btn)
        ly.addLayout(row_ly)

        self._update_display()

    def _update_display(self) -> None:
        if not self._pin:
            self._display.setText("••••")
        else:
            self._display.setText("•" * len(self._pin))

    def _on_digit(self, d: str) -> None:
        if len(self._pin) < PIN_MAX_LEN:
            self._pin.append(d)
            self._update_display()

    def _on_backspace(self) -> None:
        if self._pin:
            self._pin.pop()
            self._update_display()

    def _on_clear(self) -> None:
        self._pin.clear()
        self._update_display()

    def _on_ok(self) -> None:
        if len(self._pin) < PIN_MIN_LEN or len(self._pin) > PIN_MAX_LEN:
            QMessageBox.warning(
                self,
                "输入错误",
                "请输入 4~8 位数字。",
                QMessageBox.StandardButton.Ok,
            )
            return
        self.accept()

    def get_pin(self) -> str | None:
        """若用户点击确定且长度合法，返回 PIN 字符串；否则返回 None。"""
        if self.result() == QDialog.DialogCode.Accepted and PIN_MIN_LEN <= len(self._pin) <= PIN_MAX_LEN:
            return "".join(self._pin)
        return None


def ask_maintenance_pin(
    expected_pin: str,
    tokens: "LayoutTokens | None" = None,
    parent: QWidget | None = None,
) -> bool:
    """
    弹出 PIN 对话框，用户输入与 expected_pin 一致则返回 True，取消或错误返回 False。
    错误时弹中文提示，不抛异常。
    """
    try:
        dlg = PinPadDialog(title="输入维护 PIN", tokens=tokens, parent=parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False
        pin = dlg.get_pin()
        if pin is None:
            return False
        if pin != expected_pin:
            QMessageBox.warning(
                parent or dlg,
                "PIN 错误",
                "维护 PIN 不正确，请重试。",
                QMessageBox.StandardButton.Ok,
            )
            return False
        return True
    except Exception:
        if parent:
            QMessageBox.warning(parent, "错误", "验证失败，请重试。", QMessageBox.StandardButton.Ok)
        return False
