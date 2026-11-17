# 部署到阿里云

把本地代码与配置更新到阿里云服务器。核心思路：

- **代码**走 git（本地 push → 服务器 pull）
- **配置**（含密钥）在 `.gitignore` 里，不走 git，需单独同步
- 本地改完 → 服务器拉取 → 重建后端 → 重新构建前端

---

## 部署前检查（本地）

```bash
cd 项目目录
# 后端测试应全绿
cd backend && python3 -m pytest tests/ -q && cd ..
# 前端构建应通过
cd frontend && npm run build && cd ..
```

---

## 第一段：Mac 上提交代码

```bash
cd 项目目录
git add -A
git commit -m "feat: 数学 LaTeX 版 + DeepSeek flash + 禁用 IMA"
git push origin main
```

> 敏感文件（`.env`、`config/settings.json`、`config/app.db`）已被 `.gitignore`
> 排除，`git add -A` 不会提交它们。

---

## 第二段：阿里云上更新

### 1. 拉取代码

```bash
cd 项目目录
git pull origin main
```

### 2. 同步配置文件（关键，两步）

**（a）禁用 IMA** —— 只改 `.env` 里这一行，其余（VAULT_PATH 等）保持服务器原值：

```bash
sed -i 's/^IMA_ENABLED=true$/IMA_ENABLED=false/' .env
grep '^IMA_ENABLED' .env    # 应输出 IMA_ENABLED=false
```

**（b）配置 DeepSeek** —— 把本地 `config/settings.json` 的内容复制过去。
最简单的方式是直接在服务器上编辑 `config/settings.json`，改成：

```json
{
  "llm": {
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "sk-你的key",
    "model": "deepseek-flash",
    "timeout": 120
  }
}
```

> 或者从 Mac 传过去：
> `scp config/settings.json 用户@服务器:项目目录/config/settings.json`

### 3. 重启后端

```bash
docker compose up -d --build backend
docker compose logs -f backend    # 看启动日志，确认无报错后 Ctrl+C 退出
```

### 4. 重新构建前端

```bash
cd frontend
npm install
npm run build
# 然后按你现有的前端部署方式重新部署（nginx / 静态托管 / dev server）
```

> 前端部署方式与之前一致，只需重新 build。如果前端是 nginx 托管，
> 把 `dist/` 内容放到对应目录即可。

### 5. 验证

```bash
# 后端健康检查
curl -s http://localhost:8001/api/health
# 应返回 {"status":"ok",...}

# 浏览器打开前端，登录 → 上传一道数学题 → 看 AI 是否输出 LaTeX 公式
```

---

## 部署内容清单（本次相对上次的变更）

| 类别 | 内容 |
|---|---|
| 数学 LaTeX 版 | AI 提示词输出 LaTeX、前端编辑实时预览、JSON 解析修复 `\frac` |
| LLM 切换 | 火山引擎 → DeepSeek flash |
| 存储 | 禁用 IMA，错题只存本地 vault |
| 其他 | 上传校验、文件名「人名·学科·日期-id」、缓存重建、批量读取优化、时区适配等 |

详细记录见 `discuss.md` 8.30 之后各节。

---

## 回滚

如果部署后有问题，代码回滚：

```bash
cd 项目目录
git checkout <上一个正常 commit>
docker compose up -d --build backend
```

配置回滚：`config/settings.json` 改回旧的 LLM 配置，`.env` 的 `IMA_ENABLED` 改回 `true`。
