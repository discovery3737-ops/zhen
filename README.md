# IntelligentCrawler2.0 - M0 联调基线

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
cd IntelligentCrawler2.0
docker compose up -d
```

等待 postgres 就绪后，API 在 `http://localhost:8000`。

前端需单独启动：

```bash
cd frontend
pnpm install   # 或 npm install
pnpm dev       # 或 npm run dev
```

### 方式二：本地启动（无 Docker）

```bash
# 1. 后端
cd backend
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python scripts/seed_runs.py              # 初始化表并插入示例 runs
python scripts/create_sample_report.py 2025-02-28  # 创建示例报表
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2. 前端（新终端）
cd frontend
pnpm install   # 或 npm install
pnpm dev       # 或 npm run dev
```

说明：未设置 `DATABASE_URL` 时，默认使用 SQLite `./crawler.db`；Docker 部署时使用 PostgreSQL。`seed_runs.py` 会自动建表并插入示例 runs；`create_sample_report.py` 会生成示例报表供下载测试。

---

## 验收步骤

### curl 验收

```bash
# 1. GET /health
curl -s http://localhost:8000/health

# 2. GET /runs
curl -s "http://localhost:8000/runs?page=1&page_size=20"

# 3. 下载报表（-O 保存到文件，-J 使用 Content-Disposition 文件名）
curl -OJ "http://localhost:8000/reports/daily/download?dt=2025-02-28"
# 文件会下载为 daily_report_2025-02-28.xlsx

# 4. 404 测试（文件不存在）
curl -s "http://localhost:8000/reports/daily/download?dt=2099-01-01"
# 应返回 {"ok":false,"message":"Report not found"}
```

### 前端验收

1. 打开 `http://localhost:5173`
2. Runs 页面应显示 run 列表（若已执行 seed_runs.py）
3. 点击「下载报表」按钮应触发浏览器下载 xlsx
4. 若后端未启动，应显示 fallback mock 数据提示

---

## 目录结构

```
IntelligentCrawler2.0/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py        # app_job_run
│   │   ├── schemas.py
│   │   ├── services.py
│   │   └── routers/
│   │       ├── health.py    # GET /health
│   │       ├── runs.py      # GET /runs, GET /runs/{run_id}
│   │       └── reports.py   # GET /reports/daily/download
│   ├── scripts/
│   │   ├── seed_runs.py
│   │   └── create_sample_report.py
│   ├── reports/daily/       # 报表存储
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api.js
│   │   ├── pages/RunsPage.jsx
│   │   └── ...
│   ├── package.json
│   └── vite.config.js      # /api 代理到 8000
├── docker-compose.yml
└── README.md
```

---

## API 说明

| 接口 | 说明 |
|------|------|
| `GET /health` | 返回 `{ok:true, data:{service, version, time}}` |
| `GET /runs?page=1&page_size=20` | 分页列表 |
| `GET /runs/{run_id}` | 单条详情 |
| `GET /reports/daily/download?dt=YYYY-MM-DD` | 文件流下载 xlsx，不存在 404 |

统一成功：`{ok:true, data:{...}}`  
统一错误：`{ok:false, message, detail?}`
