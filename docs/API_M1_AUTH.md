# M1 noVNC 授权闭环 API 文档

## 概述

授权中心提供 noVNC 远程浏览器，用户完成登录（账号密码→拼图→短信验证码）后，点击「完成授权」即可导出 storageState 并加密入库，供 daily job 自动采集使用。

## 接口

### POST /auth/session/start

创建授权会话，返回 noVNC 地址。

**响应** `200 OK`:
```json
{
  "ok": true,
  "data": {
    "session_id": "sess_xxx",
    "token": "xxx",
    "novnc_url": "http://localhost:6080/vnc.html?autoconnect=1&token=xxx&session=sess_xxx",
    "expires_at": "2025-03-01T10:30:00+00:00"
  }
}
```

- `novnc_url`: 放入 iframe 供用户完成登录
- `expires_at`: 15 分钟内有效，超时自动回收

---

### POST /auth/session/finish

完成授权。前端传入 `session_id` 和 `token`。

**请求体**:
```json
{
  "session_id": "sess_xxx",
  "token": "xxx"
}
```

**成功** `200 OK`:
```json
{
  "ok": true,
  "data": {
    "message": "Credential saved",
    "status": "ACTIVE"
  }
}
```

**失败**（未完成短信验证或登录校验失败）:
```json
{
  "ok": false,
  "message": "Login not completed",
  "detail": "..."
}
```

**流程**:
1. 校验 session_id 与 token
2. 通过 CDP 连接共享浏览器，导出 storageState
3. 使用 storageState 请求 AUTH_CHECK_URL，若返回 200 则登录有效
4. 校验通过：加密 storageState 入库 app_credential(status=ACTIVE)，并 stop_session
5. 校验失败：不保存，返回 `{ok:false, message:'Login not completed'}`

---

### GET /auth/credential/status

获取当前凭证状态。

**响应** `200 OK`:
```json
{
  "ok": true,
  "data": {
    "status": "ACTIVE",
    "last_check": "2025-03-01T10:00:00+00:00",
    "message": "Saved from noVNC session"
  }
}
```

无有效凭证时 `status` 为 `EXPIRED`，`last_check` 为 `null`。

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| BROWSER_NOVNC_URL | http://localhost:6080 | noVNC 服务地址（前端可访问） |
| BROWSER_CDP_URL | http://localhost:9222 | CDP 地址（API 连接浏览器） |
| AUTH_CHECK_URL | https://httpbin.org/cookies | 登录校验接口（必须登录才 200） |
| CREDENTIAL_ENCRYPT_KEY | dev-key-32-bytes-base64encoded! | storageState 加密密钥（生产需更换） |
| SESSION_EXPIRE_MINUTES | 15 | 会话过期时间（分钟） |

---

## 安全约束

- novnc_url 携带一次性 token，finish 必须校验 token 与 session_id
- 不记录用户输入，不做验证码识别，不存短信验证码
- storageState 必须加密后入库，禁止明文
