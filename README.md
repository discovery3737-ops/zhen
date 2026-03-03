# IntelligentCrawler2.0

爬虫运行中心 + noVNC 授权闭环（M0/M1 联调基线）。

## 项目结构

```
IntelligentCrawler2.0/
├── backend/          # FastAPI 后端
│   ├── app/
│   ├── scripts/
│   ├── reports/
│   └── requirements.txt
├── frontend/         # React + Vite 前端
├── browser/          # noVNC + Chromium Docker 镜像
├── verify/           # 验收脚本
└── docker-compose.yml
```

## 快速启动

### 方式一：本地启动（无 Docker）

**PowerShell：**

```powershell
# 1. 后端
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_runs.py
.\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000

# 2. 前端（新终端）
cd frontend
npm install
npm run dev
```

**若 PowerShell 禁止运行脚本**（activate 或 npm 报错），可任选其一：

- 临时放行：`Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process`，再执行上述命令
- 不激活 venv，直接指定可执行文件：
  ```powershell
  cd backend
  .\venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
  ```
- 前端用：`npm.cmd run dev`

**CMD：**

```cmd
cd backend
venv\Scripts\activate.bat
pip install -r requirements.txt
python scripts/seed_runs.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

新开 CMD 启动前端：`cd frontend` → `npm install` → `npm run dev`。

---

### 方式二：Docker Compose

```powershell
cd IntelligentCrawler2.0
docker compose up -d
```

- 会启动：browser(6080/9222)、postgres(5432)、api(8000)
- 前端仍需本地启动：`cd frontend; npm.cmd run dev`

只启动部分服务示例：

```powershell
docker compose up -d postgres api    # 仅数据库 + API
docker compose up -d browser         # 仅 noVNC 浏览器
```

---

### 可选：示例数据与报表

```powershell
cd backend
.\venv\Scripts\python.exe scripts/seed_runs.py
.\venv\Scripts\python.exe scripts/create_sample_report.py 2025-02-28
```

- `seed_runs.py`：建表并插入示例 run 记录
- `create_sample_report.py`：生成 `reports/daily/daily_report_YYYY-MM-DD.xlsx`，供下载接口测试

## 验收步骤

### M0 联调基线

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
Invoke-RestMethod -Uri "http://localhost:8000/runs?page=1&page_size=20"
Invoke-WebRequest -Uri "http://localhost:8000/reports/daily/download?dt=2025-02-28" -OutFile "daily_report.xlsx" -UseBasicParsing
```

### M1 noVNC 授权闭环

```powershell
$base = "http://localhost:8000"
Invoke-RestMethod "$base/auth/session/start" -Method Post
Invoke-RestMethod "$base/auth/credential/status"
```

## API 文档

- M0：`/health`、`/runs`、`/runs/{run_id}`、`/reports/daily/download`
- M1：`/auth/session/start`、`/auth/session/finish`、`/auth/credential/status`

详见 `docs/API_M1_AUTH.md`。
