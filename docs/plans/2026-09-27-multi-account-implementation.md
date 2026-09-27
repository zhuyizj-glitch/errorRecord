# Multi-Account Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 增加一次性邀请码注册、管理员后台、账号级孩子课程管理，以及贯穿 IMA/Obsidian 的数据隔离和历史数据迁移。

**Architecture:** 当前 Docker 部署使用持久化 SQLite 保存账号、会话、邀请码、孩子和课程；FastAPI 依赖从 HttpOnly Cookie 解析当前账号。错题仍双写 IMA 与 Obsidian，但全部接口、元数据和文件路径增加账号与孩子 ID 范围。若选择 EdgeOne Makers 部署，实施前先把 SQLite 替换为外部关系数据库、图片替换为对象存储，并移除对本地 vault 与常驻进程的依赖。

**Tech Stack:** FastAPI、Pydantic、Python sqlite3/hashlib/secrets、React、TypeScript、Zustand、Docker、IMA OpenAPI、Obsidian Markdown。

---

### Task 1: 固化当前基线并建立数据库层

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models/auth.py`
- Create: `backend/tests/test_db.py`
- Modify: `backend/app/core/config.py`

**Steps:**
1. 先提交当前已验证但尚未入库的复习与图片修复，确保多账号改造有清晰基线。
2. 写失败测试：临时 SQLite 初始化后应创建五张表，重复初始化不报错。
3. 使用 `sqlite3` 实现连接、事务、schema 初始化和 `config/app.db` 路径。
4. 为外键、唯一用户名、唯一孩子课程和邀请码状态添加约束及索引。
5. 在容器中运行数据库测试，确认通过后提交。

### Task 2: 密码、邀请码和会话服务

**Files:**
- Create: `backend/app/services/auth_service.py`
- Create: `backend/tests/test_auth_service.py`

**Steps:**
1. 写失败测试覆盖 scrypt 密码验证、错误密码、一次性邀请码、过期/作废邀请码、会话过期和撤销。
2. 用 `secrets` 生成邀请码、临时密码和会话令牌；数据库只保存 SHA-256 令牌哈希。
3. 用 `hashlib.scrypt` 和每个密码独立随机盐实现密码存储。
4. 注册消费邀请码使用 `BEGIN IMMEDIATE` 事务，防止同一码并发注册。
5. 运行测试并提交。

### Task 3: 认证 API 与统一权限依赖

**Files:**
- Create: `backend/app/api/deps/auth.py`
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/tests/test_auth_api.py`
- Modify: `backend/main.py`

**Steps:**
1. 写失败接口测试：初始化状态、首次管理员、重复初始化、登录、登出、当前账号、邀请码注册和强制改密。
2. 实现 `get_current_account` 与 `require_admin` 依赖。
3. 登录设置 HttpOnly/SameSite Cookie；退出和改密撤销会话。
4. 对登录失败实施小范围内存限流，响应不暴露用户名是否存在。
5. 运行认证测试并提交。

### Task 4: 管理员邀请码和密码重置 API

**Files:**
- Create: `backend/app/api/routes/admin.py`
- Create: `backend/tests/test_admin_api.py`
- Modify: `backend/main.py`

**Steps:**
1. 写失败测试：普通用户返回 403；管理员可生成、列出和作废邀请码。
2. 写失败测试：重置密码后全部旧会话失效，新临时密码可登录且 `must_change_password=true`。
3. 实现管理员账号摘要列表，不返回密码哈希、盐或会话令牌。
4. 实现一次性显示邀请码和临时密码。
5. 运行测试并提交。

### Task 5: 动态孩子和课程 API

**Files:**
- Replace: `backend/app/api/routes/children.py`
- Create: `backend/tests/test_children_api.py`
- Modify: `backend/app/models/question.py`

**Steps:**
1. 写失败测试：每个账号只列出自己的孩子；同名孩子可跨账号和账号内存在。
2. 写失败测试：课程只能来自九门白名单，取消课程只禁用记录，不删除目录。
3. 实现新增孩子、改名、修改 emoji 和启用课程接口。
4. 返回不可变 `child_id`，逐步替换 `daughter/son` 键。
5. 运行测试并提交。

### Task 6: Obsidian 文件与图片账号隔离

**Files:**
- Modify: `backend/app/services/file_ops.py`
- Modify: `backend/app/services/file_storage.py`
- Modify: `backend/app/services/storage_backend.py`
- Modify: `backend/app/api/routes/questions.py`
- Modify: `backend/app/api/routes/upload.py`
- Modify: `backend/app/api/routes/tasks.py`
- Extend: `backend/tests/test_question_flow.py`

**Steps:**
1. 写两个账号同名孩子的接口测试，确认互相读取错题、详情和图片均返回 404。
2. 将所有路径改为 `accounts/{account_id}/{child_id}/{subject}` 和 `_assets/accounts/...`。
3. 创建错题时从会话注入 `account_id`，从数据库解析 `child_name`，不接受客户端账号或路径。
4. 上传临时文件关联当前账号，任务读取和保存时验证归属。
5. 更新移动学科、复习、统计和图片接口的归属检查。
6. 运行完整后端测试并提交。

### Task 7: IMA 元数据隔离与同步

**Files:**
- Modify: `backend/app/services/ima_storage.py`
- Modify: `backend/app/services/storage_manager.py`
- Modify: `backend/app/services/sync_service.py`
- Modify: `backend/app/api/routes/sync.py`
- Create: `backend/tests/test_ima_account_scope.py`

**Steps:**
1. 使用假的 IMA client 写失败测试，混合两个账号笔记时只返回当前账号数据。
2. IMA 标题使用孩子显示名；JSON 元数据写入 `account_id`、`child_id`、`child_name`。
3. 所有列表、读取、更新和同步按账号过滤，未知归属进入错误统计。
4. 手动同步只允许管理员执行；定时同步按全部已知账号逐一处理。
5. 运行 IMA 单元测试和现有同步回归测试后提交。

### Task 8: 历史数据备份与幂等迁移

**Files:**
- Create: `backend/scripts/migrate_to_accounts.py`
- Create: `backend/tests/test_account_migration.py`
- Modify: `docs/IMA_MIGRATION_STATUS.md`

**Steps:**
1. 写临时 vault 测试：`daughter`、`son`、图片和链接迁入管理员账号的新目录。
2. 脚本启动时备份 SQLite 与旧目录，写迁移清单和每题状态。
3. 补写 Markdown 和 IMA 元数据；使用题目 ID 保证重跑不重复。
4. 增加 `--dry-run` 与明确的异常报告；无管理员时拒绝执行。
5. 在真实数据上先运行 dry-run，人工核对计数后再执行正式迁移并保存日志。
6. 验证题目数、图片数和 IMA 记录数一致后提交。

### Task 9: 前端认证与首次初始化流程

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/RegisterPage.tsx`
- Create: `frontend/src/pages/InitializePage.tsx`
- Create: `frontend/src/pages/ChangePasswordPage.tsx`
- Create: `frontend/src/store/useAuthStore.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`

**Steps:**
1. 为 API 客户端启用 Cookie，并统一处理 401。
2. 实现初始化、登录、邀请码注册和强制改密页面。
3. 增加受保护路由；重新登录后返回原地址。
4. 确认普通账号无法渲染管理员入口和 LLM 设置。
5. 运行 TypeScript 构建和浏览器流程测试后提交。

### Task 10: 前端孩子课程与管理员页面

**Files:**
- Create: `frontend/src/pages/ChildrenPage.tsx`
- Create: `frontend/src/pages/AdminPage.tsx`
- Create: `frontend/src/components/AccountMenu.tsx`
- Modify: `frontend/src/store/useStore.ts`
- Modify: `frontend/src/components/ChildSwitcher.tsx`
- Modify: `frontend/src/components/SubjectSelector.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`
- Modify: `frontend/src/types/index.ts`

**Steps:**
1. 将全局状态从固定 `daughter/son` 改为 `child_id`。
2. 实现首次创建孩子引导、孩子改名和九门课程多选。
3. 实现账号菜单、邀请码管理、账号摘要与密码重置界面。
4. 管理员设置页保留 LLM 配置；普通用户只显示个人设置。
5. 在桌面与手机宽度验证导航和表单，运行前端构建后提交。

### Task 11: 端到端隔离、部署和文档

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `discuss.md`

**Steps:**
1. 重建容器并确认 SQLite 位于持久化 `config` 卷。
2. 创建管理员和两个普通测试账号，分别创建同名孩子及不同课程。
3. 对每个账号完成上传、分析、保存、列表、详情、复习、统计和图片访问。
4. 用跨账号 ID 直接请求全部资源接口，确认返回 404。
5. 测试邀请码消费、作废、密码重置、旧会话撤销和强制改密。
6. 验证 IMA 共享知识库中的元数据正确，Obsidian 目录完全分离。
7. 更新部署、备份、恢复和管理员操作文档，运行所有测试及构建后提交。
