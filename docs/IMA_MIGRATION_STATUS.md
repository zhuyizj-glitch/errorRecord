# IMA 迁移实施状态报告

## 📋 实施进度概览

### ✅ 已完成（架构和框架）

1. **IMA 客户端基础框架** (`backend/app/services/ima_client.py`)
   - API 客户端类，支持笔记 CRUD 操作
   - 图片上传功能
   - 连接测试方法
   - ⚠️ **待完善**: API 端点需要根据官方文档调整

2. **配置管理** 
   - `backend/app/core/config.py`: 添加 IMA 配置项
   - `.env`: 添加 IMA API 凭证
   - 支持功能开关 (`IMA_ENABLED`)

3. **存储层抽象** (`backend/app/services/storage_backend.py`)
   - 定义统一的存储接口协议
   - 支持不同存储后端的无缝切换

4. **文件存储后端** (`backend/app/services/file_storage.py`)
   - 实现基于本地文件的存储
   - 作为降级方案使用
   - 完全兼容现有功能

5. **IMA 存储后端** (`backend/app/services/ima_storage.py`)
   - 实现基于 IMA 的云存储
   - 支持 Markdown + frontmatter 格式
   - 图片上传到 IMA
   - ⚠️ **待完善**: API 端点需要根据官方文档调整

6. **存储管理器** (`backend/app/services/storage_manager.py`)
   - 主备存储策略
   - 自动故障转移
   - 根据配置选择存储后端

7. **同步服务** (`backend/app/services/sync_service.py`)
   - IMA → Obsidian 单向同步
   - 同步状态跟踪
   - 同步统计信息

8. **定时调度器** (`backend/app/services/scheduler.py`)
   - 基于 APScheduler
   - 支持配置同步间隔（默认 12 小时）
   - 应用生命周期集成

9. **同步 API** (`backend/app/api/routes/sync.py`)
   - `POST /api/sync/to-obsidian`: 手动触发同步
   - `GET /api/sync/status`: 获取同步状态
   - `GET /api/sync/config`: 获取同步配置

10. **依赖更新** (`backend/requirements.txt`)
    - 添加 `apscheduler>=3.10.0,<4.0`

---

## ⚠️ 待完成（需要官方文档）

### IMA API 端点确认

**问题**: 所有测试的 API 端点都返回 404

**已测试的端点模式**:
```
❌ https://ima.qq.com/api/v1/notes
❌ https://ima.qq.com/openapi/notes/v1/list
❌ https://ima.qq.com/notes/list
❌ https://ima.qq.com/api/notes/list
❌ https://ima.qq.com/v1/notes/list
```

**需要确认**:
1. IMA API 的基础 URL
2. 笔记操作的具体端点路径
3. 请求/响应格式
4. 图片上传的接口规范
5. 认证方式（API Key + Client ID 的使用方式）

**获取官方文档的途径**:
- 访问 https://ima.qq.com/agent-interface 查看开发者文档
- 联系腾讯 IMA 技术支持
- 查看 IMA SDK 源码（如果有开源）

---

## 🏗️ 架构设计

### 当前架构

```
┌─────────────────────────────────────────┐
│         API Routes (questions.py)       │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│      Storage Manager (主备策略)          │
│  - 主存储: IMA (如果启用)                │
│  - 备用存储: File (本地文件)             │
└────────┬───────────────────┬────────────┘
         │                   │
         ▼                   ▼
┌─────────────────┐  ┌─────────────────┐
│ IMA Storage     │  │ File Storage    │
│ Backend         │  │ Backend         │
│                 │  │                 │
│ - 云存储        │  │ - 本地文件      │
│ - Markdown      │  │ - Markdown      │
│ - 图片上传      │  │ - 图片本地存储  │
└────────┬────────┘  └─────────────────┘
         │
         │ 定时同步 (每 12 小时)
         │ + 手动触发
         ▼
┌─────────────────┐
│ Obsidian Vault  │
│ (本地副本)      │
└─────────────────┘
```

### 数据流

1. **写入流程**:
   ```
   前端 → API → Storage Manager → IMA (主)
                                ↓ (失败时)
                              File (备)
   ```

2. **同步流程**:
   ```
   定时任务/手动触发 → Sync Service → IMA 读取
                                      ↓
                                    Obsidian 写入
   ```

3. **读取流程**:
   ```
   前端 → API → Storage Manager → IMA (主)
                                ↓ (失败时)
                              File (备)
   ```

---

## 🔧 使用方式

### 1. 启用 IMA 存储

编辑 `.env` 文件:
```bash
IMA_ENABLED=true
IMA_API_KEY=your_api_key
IMA_CLIENT_ID=your_client_id
IMA_SYNC_INTERVAL_HOURS=12
```

### 2. 手动同步

```bash
curl -X POST http://localhost:8001/api/sync/to-obsidian
```

### 3. 查看同步状态

```bash
curl http://localhost:8001/api/sync/status
```

### 4. 降级模式

如果 IMA 不可用，系统会自动切换到本地文件存储：
```bash
# 查看当前存储模式
curl http://localhost:8001/api/sync/config
```

---

## 📝 下一步行动

### 优先级 1: 获取 IMA API 文档

1. 访问 https://ima.qq.com/agent-interface
2. 查找开发者文档或 API 参考
3. 确认正确的 API 端点和认证方式
4. 更新 `ima_client.py` 中的端点配置

### 优先级 2: 测试和调试

1. 使用正确的 API 端点测试连接
2. 测试笔记 CRUD 操作
3. 测试图片上传
4. 验证数据格式兼容性

### 优先级 3: 数据迁移

1. 创建迁移脚本 (`backend/scripts/migrate_to_ima.py`)
2. 执行数据迁移（先 dry-run）
3. 验证迁移结果
4. 切换到 IMA 主存储

### 优先级 4: 前端集成

1. 在设置页面显示 IMA 连接状态
2. 添加手动同步按钮
3. 显示同步状态和历史

---

## 🎯 关键文件清单

### 新增文件

```
backend/app/services/
├── ima_client.py          # IMA API 客户端
├── ima_storage.py         # IMA 存储后端
├── file_storage.py        # 文件存储后端
├── storage_backend.py     # 存储接口定义
├── storage_manager.py     # 存储管理器
├── sync_service.py        # 同步服务
└── scheduler.py           # 定时调度器

backend/app/api/routes/
└── sync.py                # 同步 API 路由
```

### 修改文件

```
backend/
├── main.py                # 注册路由和生命周期
├── requirements.txt       # 添加 APScheduler
└── app/core/config.py     # 添加 IMA 配置

.env                       # 添加 IMA 凭证
```

---

## 📊 测试清单

### 功能测试

- [ ] IMA 连接测试
- [ ] 创建错题 → IMA 中有记录
- [ ] 读取错题 ← 从 IMA 获取
- [ ] 更新错题 → IMA 中更新
- [ ] 删除错题 → IMA 中删除
- [ ] 手动同步 → Obsidian 中出现文件
- [ ] 定时同步 → 12 小时后自动执行

### 降级测试

- [ ] IMA 不可用 → 自动切换到文件存储
- [ ] IMA 恢复 → 自动切回 IMA
- [ ] 同步失败 → 不影响主流程

### 性能测试

- [ ] API 响应时间 < 1s
- [ ] 同步耗时 < 5min (1000 条数据)
- [ ] 并发写入无冲突

---

## 📚 参考资料

- **实施计划**: `/Users/zhuyi/.claude/plans/eager-zooming-beacon.md`
- **设计文档**: `discuss.md` (第 8.21 节)
- **IMA 官网**: https://ima.qq.com/
- **IMA 开发者入口**: https://ima.qq.com/agent-interface

---

## 💡 注意事项

1. **API 端点未确认**: 当前 IMA 客户端中的端点是推测的，需要根据官方文档调整
2. **数据格式**: 假设 IMA 支持 Markdown + frontmatter，需要验证
3. **图片存储**: 选择方案 A（全部上传到 IMA），需要验证图片大小限制
4. **同步冲突**: 采用单向同步（IMA → Obsidian），避免冲突
5. **性能考虑**: 大量数据同步时需要考虑分页和批处理

---

**报告生成时间**: 2026-09-06
**实施状态**: 架构完成，等待 API 文档
