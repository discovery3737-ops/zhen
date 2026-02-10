\# zhen



Python + PyQt6 UI + Modbus(可选) + 视频(可选) 项目。



\## Quick Start (Windows)

```powershell

cd C:\\path\\to\\zhen

python -m venv .venv

.\\.venv\\Scripts\\activate

pip install -U pip

pip install -r requirements.txt

python -m app.main


Quick Start (Raspberry Pi OS)
cd /path/to/zhen
python3 -m venv venv
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python3 -m app.main


## 真实硬件启用 Modbus

默认 `config.yaml` 不存在或 `modbus.use_mock: true` 时使用模拟数据，无需串口。真实树莓派 RS485/Modbus 部署需：

1. 安装依赖：`pip install pymodbus[serial]`
2. 复制 `config.yaml.example` 为 `config.yaml`，并修改：
   - `modbus.use_mock: false`
   - `modbus.port: /dev/ttyUSB0`（或实际串口设备，如 `/dev/ttyAMA0`、`/dev/ttyS0`）
3. 确保用户有串口访问权限，例如：`sudo usermod -aG dialout $USER`


## 树莓派视频嵌入推荐：使用 X11 会话

RTSP 视频在 Qt 窗口内嵌显示依赖 GStreamer 的 overlay（如 ximagesink/waylandsink）。在 **Raspberry Pi OS** 上推荐使用 **X11** 会话以获得稳定内嵌，避免弹窗或黑屏。

- **若当前为 Wayland**：部分环境下 overlay 可能不可用，应用会自动降级为占位画面并提示“建议切换到 X11”。可在系统设置中将会话改为 X11，或使用 startx / 选择“X11 session”登录。
- **若为 X11**：一般无需改配置；若遇问题可在 `config.yaml` 中设置 `video.sink: ximagesink` 或 `ximagesink`/`glimagesink` 尝试。
- **仅需占位、不播放**：可设置 `video.force_no_embed: true`，界面将只显示提示文案不尝试嵌入。

## 启用硬件亮度控制（树莓派 7 寸 DSI）

设置页「显示与语言」中的「屏幕亮度」滑条可调节 Raspberry Pi 官方 7 寸 DSI 背光（`/sys/class/backlight/rpi_backlight`）。为避免以 root 运行整个应用，亮度写入通过 **sudo 调用小脚本** 完成。

1. **创建亮度脚本** `/usr/local/bin/rpi_set_backlight`（可执行）：
   ```bash
   #!/bin/sh
   echo "$1" > /sys/class/backlight/rpi_backlight/brightness
   ```
2. **放行无密码执行**：新建 `/etc/sudoers.d/rv-hmi-backlight`，内容（将 `pi` 改为实际运行 HMI 的用户名）：
   ```
   pi ALL=(ALL) NOPASSWD: /usr/local/bin/rpi_set_backlight
   ```
   然后执行 `sudo chmod 440 /etc/sudoers.d/rv-hmi-backlight`。
3. 在 `config.yaml` 中可设置 `display.brightness_percent: 60`（0~100）；应用启动约 1 秒后会应用该亮度，设置页中调节会即时生效并写回配置。

**为何不用 root 跑整个应用**：仅让一个小脚本通过 sudo 写 sysfs，应用主体以普通用户运行，可降低权限、减少攻击面；若以 root 运行整个 GUI，一旦被利用则拥有完整系统权限。


