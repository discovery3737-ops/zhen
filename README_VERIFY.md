# 验收脚本模板（按 Prompt 分段自测）

本目录提供 9 个 Prompt 的自测模板，每个 Prompt 独立执行：
- `verify/promptXX/verify.sh`：curl + MinIO（mc）检查 + 调用 SQL 校验
- `verify/promptXX/verify.sql`：数据库校验（表/列/行数/视图存在性）

## 依赖
- bash、curl
- jq（可选，建议安装）
- docker compose（建议）
- MinIO Client `mc`（可选，用于检查对象存储）
- Postgres 客户端：推荐使用 `docker compose exec postgres psql ...`（脚本默认如此）

## 使用方法
1) 把本目录拷贝到你的仓库根目录（与 `docker-compose.yml` 同级）
2) 启动服务（示例）：
   ```bash
   docker compose up -d
   ```
3) 设置环境变量（可选）：
   ```bash
   export API_BASE=http://localhost:8000
   export DT=2026-03-01
   export MINIO_ENDPOINT=http://localhost:9000
   export MINIO_BUCKET=uc-artifacts
   export MINIO_AK=minio
   export MINIO_SK=minio123456
   ```
4) 执行对应 Prompt 的脚本：
   ```bash
   bash verify/prompt01/verify.sh
   ```

## 注意
- Prompt02（noVNC）包含人工步骤：你需要先在前端授权中心完成登录，再运行 verify.sh 去检查 credential 状态。
- MinIO 检查如果未安装 `mc` 会自动跳过并提示。
