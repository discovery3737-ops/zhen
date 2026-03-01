# Modbus 规格

## modbus_spec.json

由 `RV_HMI_Modbus_Register_Map_v1.xlsx` 解析得到，结构为：

```json
{
  "slave_id": {
    "coils": [],
    "discrete_inputs": [],
    "holding_regs": [],
    "input_regs": []
  }
}
```

每条点位包含：`fc`, `type`, `addr0`, `name`, `rw`, `dtype`, `scale`, `unit`, `poll`, `desc`, `notes`。

### 如何生成

1. 安装依赖：`pip install openpyxl`
2. 将 `RV_HMI_Modbus_Register_Map_v1.xlsx` 放在项目根目录或 `tools/` 下，或通过参数指定路径
3. 在项目根目录执行：

   ```bash
   python tools/gen_modbus_spec.py
   # 或指定 xlsx 路径：
   python tools/gen_modbus_spec.py "C:\path\to\RV_HMI_Modbus_Register_Map_v1.xlsx"
   ```

生成文件会写入 `app/spec/modbus_spec.json`。若仓库未提交该文件，按上述步骤即可重新生成。
