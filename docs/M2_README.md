# M2 配置入库与 Web 配置化

## 迁移与初始化

```powershell
cd backend
.\venv\Scripts\python.exe -m pip install alembic
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe scripts/seed_config.py
```

或依赖 `create_all` 自动建表后，直接运行 `seed_config.py`。

## API 示例

```powershell
$base = "http://localhost:8000"

# GET/PUT 全局配置
Invoke-RestMethod "$base/config/global"
Invoke-RestMethod "$base/config/global" -Method Put -Body '{"daily_start_time":"00:15"}' -ContentType "application/json"

# GET/PUT 数据源配置
Invoke-RestMethod "$base/datasets/config"

# GET/PUT 调度配置
Invoke-RestMethod "$base/schedule/daily"
Invoke-RestMethod "$base/schedule/daily" -Method Put -Body '{"time":"00:10"}' -ContentType "application/json"

# GET/PUT 发送配置
Invoke-RestMethod "$base/delivery"

# 触发 daily job
Invoke-RestMethod "$base/jobs/daily/run?dt=2025-03-02" -Method Post
```

## 验收

1. 配置保存后 DB 可查：`SELECT * FROM dataset_config;`
2. 关闭某数据源 enabled=false 后，`/jobs/daily/run` 的 `enabled_datasets` 不再包含该数据源
3. 调度默认显示 00:10，可修改保存
