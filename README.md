# 错题集

一个支持多账号、动态孩子课程、图片错题分析、复习计划、IMA 主存储和 Obsidian 备份的家庭错题管理系统。

## 部署结构

- 前端：宿主机运行 React/Vite，默认端口 `5173`
- 后端：Docker 中运行 FastAPI，宿主机端口 `8001`
- 账号数据库：`config/app.db`，由 Docker 持久化挂载
- Obsidian：`${VAULT_PATH}/accounts/{account_id}/{child_id}/{subject}`
- IMA：共享一个知识库，以 `account_id` 和 `child_id` 做服务端强制隔离

## 首次启动

1. 复制 `.env.example` 为 `.env`，填写 `VAULT_PATH`。如需手机通过 Tailscale 访问，把 Mac 的 Tailscale 地址加入 `CORS_ORIGINS`。
2. 启动后端：

   ```bash
   docker compose up -d --build backend
   ```

3. 启动前端：

   ```bash
   cd frontend
   npm install
   npm run dev -- --host 0.0.0.0
   ```

4. 浏览器打开 `http://localhost:5173`。首次访问会要求创建管理员账号。
5. 在“孩子”页面创建孩子并选择课程。可选课程为语文、数学、英语、物理、化学、生物、政治、历史、地理。

管理员可访问“设置”和“管理”：全局 LLM 配置仅管理员可修改；普通账号通过一次性邀请码注册。管理员重置密码后，目标账号的旧会话会失效，用户首次登录必须修改临时密码。

## 手机访问

Mac 和 iPhone 均登录 Tailscale 后，在手机浏览器打开：

```text
http://<Mac 的 Tailscale IP>:5173
```

前端必须使用 `--host 0.0.0.0` 启动，并把该来源加入 `.env` 的 `CORS_ORIGINS`。当前为 HTTP 时保持 `COOKIE_SECURE=false`；以后启用 HTTPS 时改为 `true`。

## 历史数据迁移

先创建管理员，再进行预演：

```bash
docker compose exec backend python scripts/migrate_to_accounts.py \
  --database-url sqlite:////app/config/app.db \
  --vault /vault \
  --admin-id <管理员账号ID> \
  --migrate-ima
```

核对错题、图片和 IMA 匹配数量后，原命令增加 `--apply` 执行正式迁移。脚本会先备份数据库、旧 `daughter/son` 目录和旧图片；重复执行不会重复创建孩子或错题。

## 验证

```bash
docker run --rm -v "$PWD/backend:/app" -w /app mistakes-backend \
  python -m unittest discover -s tests -v
cd frontend && npm run build
```

目前错题不提供删除功能。复习中持续做对会提高掌握度并逐步延长复习间隔；再次做错会降低掌握度并缩短间隔。
