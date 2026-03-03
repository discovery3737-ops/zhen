# M1 noVNC 授权闭环 - 运行说明

## 启动

### Docker Compose（推荐）

```bash
cd IntelligentCrawler2.0
docker compose up -d
```

- **browser**: noVNC 6080, CDP 9222
- **api**: 8000
- **postgres**: 5432

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 → 点击「授权中心」

---

## 验收步骤

### 1. curl 验收 start

```powershell
# PowerShell
Invoke-RestMethod -Uri "http://localhost:8000/auth/session/start" -Method Post
```

应返回 `ok: true`, `data.novnc_url` 含 token。

### 2. 手动操作

1. 前端打开「授权中心」
2. 点击「创建授权会话」
3. 在 iframe 中的 noVNC 里完成登录（账号密码→拼图→短信验证码）
4. 点击「完成授权」

### 3. curl 验收 finish / status

```powershell
# 完成授权后
Invoke-RestMethod -Uri "http://localhost:8000/auth/credential/status"
```

应返回 `status: ACTIVE`。

### 4. 若未完成短信验证

finish 应返回 `{ok: false, message: "Login not completed"}`，且不保存 credential。

---

## 最小验收脚本

```bash
# Linux/Git Bash
bash verify/prompt02/verify.sh
```

---

## 配置

| 环境变量 | 默认 | 说明 |
|----------|------|------|
| BROWSER_NOVNC_URL | http://localhost:6080 | noVNC 地址（前端可访问） |
| BROWSER_CDP_URL | http://localhost:9222 | CDP 地址（API 连接） |
| AUTH_CHECK_URL | https://httpbin.org/cookies | 登录校验接口（必须登录才 200） |
| CREDENTIAL_ENCRYPT_KEY | dev-key-32-bytes... | 加密密钥（生产需更换） |

AUTH_CHECK_URL 需改为实际业务“必须登录才 200”的接口（如 `/admin/dict/type/process_mode`）。
