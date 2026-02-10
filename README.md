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



