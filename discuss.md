# 错题集项目 - 设计讨论记录

> 开始日期：2026-08-30
> 最后更新：2026-11-17

---

## 目录

1. [项目背景与需求概述](#1-项目背景与需求概述)
2. [技术决策与部署架构](#2-技术决策与部署架构)
3. [数据模型设计](#3-数据模型设计)
4. [核心功能流程](#4-核心功能流程)
5. [借鉴分析：智学精灵项目](#5-借鉴分析智学精灵项目)
6. [错题收集与解析完整流程及异常处理](#6-错题收集与解析完整流程及异常处理)
7. [技术实现与部署方案](#7-技术实现与部署方案)
8. [项目初始化与当前进展](#8-项目初始化与当前进展)
   - 8.1 已完成事项
   - 8.2 Bug 修复记录
   - 8.3 端口配置变更记录
   - 8.4 UI 优化
   - 8.5 新增功能：家长备注
   - 8.6 产品介绍页面
   - 8.7 LLM 配置
   - 8.8 完整链路验证
   - 8.9 错题详情页
   - 8.10 复习重做流程
   - 8.11 当前运行状态
   - 8.12 PWA 支持
   - 8.13 统计仪表盘
   - 8.14 图片压缩优化
   - 8.15 异步任务队列
   - 8.16 数学公式渲染优化
   - 8.17 任务列表与错题列表增强
   - 8.18 待做事项
   - 8.19 Git 版本控制
   - 8.20 掌握度评估算法重构
   - 8.21 部署方案建议
   - 8.22 版本固化与备份
   - 8.23 IMA 知识库集成
   - 8.24 IMA 集成的落地修复与优化
   - 8.25 分页机制与元数据格式重构
   - 8.26 复习提交与上传图片保存回归验证
   - 8.27 多账号、邀请码注册与账号级数据隔离设计
   - 8.28 EdgeOne Makers 部署适配评估
   - 8.29 多账号功能实施记录
   - 8.30 全量测试与文档回填
   - 8.31 IMA 主存储的可行性核查与数据安全修复
   - 8.32 OneDrive 作为云存储后端的可行性评估
   - 8.33 追加事件模型设计（待实测确认）
   - 8.34 图片改为「分析后丢弃」
   - 8.35 错题文件名改为「人名·学科·日期-id」
   - 8.36 本地定位：IMA 为唯一记录来源 + 可丢弃缓存
   - 8.37 append_doc 实测结果
   - 8.38 追加事件模型落地
   - 8.39 缓存重建入口
   - 8.40 批量读取优化：跳过未变更的笔记
   - 8.41 使用手册与一处文档纠错
   - 8.42 面向数学的 LaTeX 版改造
   - 8.43 实测：DeepSeek flash 输出 LaTeX 验证

---

> **说明**：第 3 节已于 2026-09-27 按实际实现重写。文档其余部分（尤其是第 4 节流程与第 7 节 API 表）
> 仍保留设计初期的描述，其中部分细节已被 8.20 及之后的改造取代，阅读时请以 8.x 节的后续记录为准。

---

## 1. 项目背景与需求概述

为两个孩子分别创建各自学科的错题集：
- **女儿（daughter）**：语文、数学、英语、历史、地理、政治（6 门）
- **儿子（son）**：语文、数学、英语（3 门）

### 需求概述

- 考虑到课程特点：有文字、手写图片、各类小学/初中/高中的数学图形、以及政治历史地理等学科可能会遇到的各类非 OCR 类的图片题
- 上传各科题目时，给出正确答案，并分析错误答案的错误点
- 分门别类管理，以便后续随时调用错题给孩子练习
- 支持切换孩子账号（无密码，简单切换）

---

## 2. 技术决策与部署架构

### 平台选择：Web 应用 + Obsidian 归档

**理由：**
- 上传题目最方便的方式是手机拍照（手写试卷、图形题），Web 应用手机直接打开就能上传
- 两个孩子切换账号在 Web 上也很自然
- 后续调用错题练习时，平板/电脑/手机都能访问
- Obsidian 天然优势：Markdown 文件、双向链接 + 标签、Dataview 插件灵活查询、Spaced Repetition 插件复习、本地存储数据完全在自己手里

### 部署架构

- **前端**：宿主机上（不进容器），React + TypeScript + Vite
- **后端**：Docker 容器中，Python FastAPI
- **数据存储**：Obsidian Vault 目录 + markdown 文件（无需额外数据库）
- **AI 接口**：可配置的多模态 LLM（OpenAI 兼容 API），用户通过设置页面配置端点、Key、模型

### 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    宿主机 (macOS)                        │
│                                                         │
│  ┌──────────────────┐    HTTP     ┌──────────────────┐ │
│  │   Frontend       │◄──────────►│  Backend (Docker)│ │
│  │   (React/Vite)   │  :3001     │  (FastAPI)       │ │
│  │   localhost:5173 │            │  localhost:8000  │ │
│  └──────────────────┘            └────────┬─────────┘ │
│                                            │            │
│                                            │ volume mount│
│                                            ▼            │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Obsidian Vault                                   │  │
│  │  /Users/zhuyi/.../OneDrive-.../错题集/            │  │
│  │  ├── daughter/                                    │  │
│  │  │   ├── 语文/  数学/  英语/                      │  │
│  │  │   └── 历史/  地理/  政治/                      │  │
│  │  └── son/                                         │  │
│  │      └── 语文/  数学/  英语/                      │  │
│  └──────────────────────────────────────────────────┘  │
│                          ▲                              │
│                          │ OneDrive 自动同步             │
└─────────────────────────────────────────────────────────┘
```

### 局域网手机访问

前端和后端都监听 `0.0.0.0`，手机通过宿主机局域网 IP 访问：

```bash
# 前端（Vite）启动时绑定到局域网
npm run dev -- --host 0.0.0.0

# 后端 Docker 端口映射已经对外，天然支持
docker compose up
```

手机访问：`http://192.168.1.100:5173`（IP 替换为实际局域网 IP）

---

## 3. 数据模型设计

> **本节已于 2026-09-27 按实际实现重写。**
> 早期版本描述的扣减制掌握度算法、`similar_error_count` 系列字段、错误类型 → 建议映射表，均已被后续改造取代或从未落地。
> 历史决策见 8.20（算法重构）与 8.27 / 8.29（账号化改造），本节只描述代码当前的真实行为。

### 3.1 存储分层

| 数据 | 存放位置 | 说明 |
|---|---|---|
| 账号、会话、邀请码、孩子、课程 | `config/app.db`（SQLite） | 容器内路径 `/app/config/app.db`，不进 vault |
| 错题正文 | `${VAULT_PATH}/accounts/{account_id}/{child_id}/{subject}/*.md` | Obsidian 直接可读，Dataview 可查询 |
| 错题图片 | `${VAULT_PATH}/_assets/accounts/{account_id}/{child_id}/{subject}/{question_id}/` | 与 Markdown 分离存放 |
| 上传临时图片 | 容器内 `/tmp/mistakes_uploads/{account_id}/` | 保存错题或删除任务后清理 |
| LLM 配置 | `config/settings.json` | 全局共享，仅管理员可读写 |

### 3.2 目录结构

```
${VAULT_PATH}/
├── _assets/
│   └── accounts/
│       └── {account_id}/
│           └── {child_id}/
│               └── {subject}/
│                   └── {question_id}/
│                       └── {上传时的原始文件名}
└── accounts/
    └── {account_id}/
        └── {child_id}/
            └── {subject}/
                └── {error_date}-{question_id}.md
```

Markdown 文件位于 vault 下的第 4 层目录，因此正文引用图片时使用**四层上溯**的相对路径：

```markdown
![原题](../../../../_assets/accounts/{account_id}/{child_id}/{subject}/{question_id}/{filename})
```

之所以用相对路径而不是绝对路径：错题移动到其他孩子或学科时（`PATCH /api/questions/{id}`），目录层数不变，只需改写路径中间的两段标识即可，图片会随目录一起 `shutil.move` 过去。

### 3.3 错题 frontmatter（实际字段）

```yaml
---
id: 9d0519e0
account_id: acc_c9348c5b101a442f869f9acdae5b2939
child_id: child_6d706c123cc44e9f8358c99d5a1f4205
child_name: 大女儿
subject: 数学
topic: 一元二次方程
error_type: 计算错误
source_type: 手写题
difficulty: 中等
error_date: 2026-09-20
created_at: 2026-09-27
redo_count: 5
correct_count: 4
wrong_count: 1
consecutive_correct: 1
mastery_score: 56
mastery_level: medium
mastery_status: reviewing
repeat_streak: 0
max_repeat_streak: 0
repeat_pattern: false
next_review_date: 2026-09-28
review_interval_days: 1
total_reviews: 5
error_suggestion: null
knowledge_points:
  - 因式分解
  - 一元二次方程
tags:
  - 错题
  - 数学/代数
---
```

注意两个**首次重做后才会出现**的字段：`redo_history`（数组）和 `last_redo_at`。新建错题时不会写入这两个键，`redo` 接口用 `get(..., []) or []` 兼容缺失。

### 3.4 字段说明

| 字段 | 含义 | 更新方式 |
|---|---|---|
| `account_id` / `child_id` / `child_name` | 归属账号与孩子 | 保存时由服务端从会话和数据库填入，**不信任前端提交的账号标识** |
| `error_date` | 错误发生日期（考试/作业当天） | 录入时填写；同时决定 Markdown 文件名前缀 |
| `created_at` | 录入系统的日期 | 保存时写入 |
| `redo_count` | 累计重做次数 | 每次重做 +1 |
| `correct_count` | 重做做对次数 | 做对 +1 |
| `wrong_count` | 重做做错次数 | 做错 +1 |
| `consecutive_correct` | 当前连续做对次数 | 做对 +1；**做错归零** |
| `redo_history` | 每次重做的日期、结果、备注 | 每次重做追加一条 |
| `last_redo_at` | 最近一次重做日期 | 每次重做覆盖 |
| `mastery_score` | 掌握度分数 0–100 | 每次重做重新计算；新建时为 0 |
| `mastery_level` | 掌握等级 | 由 `mastery_score` 与 `consecutive_correct` 共同决定 |
| `mastery_status` | 掌握状态 | 由 `redo_count` 与 `mastery_level` 共同决定 |
| `next_review_date` | 下次复习日期 | 每次重做后按间隔规则计算；新建时为当天（立即可复习） |
| `review_interval_days` | 当前复习间隔天数 | 随重做结果动态调整；新建时为 1 |
| `total_reviews` | 总复习次数 | 每次重做 +1（与 `redo_count` 同步增长，保留作为独立计数字段） |
| `error_suggestion` | 针对该题的学习建议 | 由 AI 分析结果填入，非规则映射 |
| `knowledge_points` / `tags` | 知识点与标签 | 保存时写入，供统计与筛选使用 |

### 3.5 掌握度评分算法

> 2026-09-06 由扣减制改为综合方案，理由见 8.20。

```
基础分   = (correct_count / (correct_count + wrong_count)) × 60
连续奖励 = min(consecutive_correct, 5) × 8
mastery_score = min(100, int(基础分 + 连续奖励))

重做次数为 0 时，mastery_score = 0
```

设计意图：基础分只奖励「做对的**比例**」，避免靠刷次数刷分；连续奖励给正反馈，但封顶 5 次（最多 40 分），防止无限累积。

实测对照（已回归验证，与 8.20 的表格一致）：

| 场景 | correct | wrong | consecutive | 基础分 | 连续奖励 | 总分 | 等级 |
|---|---|---|---|---|---|---|---|
| 做错 1 次 | 0 | 1 | 0 | 0 | 0 | 0 | low |
| 做对 1 次 | 1 | 0 | 1 | 60 | 8 | 68 | medium |
| 连续做对 3 次 | 3 | 0 | 3 | 60 | 24 | 84 | high ✓ |
| 做错后归零 | 3 | 1 | 0 | 45 | 0 | 45 | low |
| 再做对 1 次 | 4 | 1 | 1 | 48 | 8 | 56 | medium |

### 3.6 等级与状态映射

```
mastery_level：
  mastery_score ≥ 80 且 consecutive_correct ≥ 3  →  high（已掌握）
  mastery_score ≥ 50                             →  medium（待加强）
  其余                                            →  low（薄弱）

mastery_status：
  redo_count = 0        →  new（刚录入，还没重做过）
  mastery_level = high  →  mastered
  其余                   →  reviewing
```

关键点：`high` 需要**同时**满足分数和连续做对次数，所以"做过很多次但中途错过"的题不会因为平均分高就被判定为已掌握。

新建错题的初始值：`mastery_score = 0`、`mastery_level = low`、`mastery_status = new`、`next_review_date = 当天`。

### 3.7 间隔复习规则

| 重做后的 mastery_level | 做对 | 做错 |
|---|---|---|
| low（薄弱） | 固定 1 天 | 固定 1 天 |
| medium（待加强） | `int(current_interval × 1.5)` | 重置为 1 天 |
| high（已掌握） | `current_interval × 2` | 重置为 3 天 |

`next_review_date = 今天 + 新的间隔天数`。注意间隔计算用的是**本次重做之后的**等级，而不是重做之前的。

复习计划接口（`GET /api/review/plan`）返回 `next_review_date ≤ 今天` 的错题，按 `mastery_score` **升序**排列，即最薄弱的排在最前面。

### 3.8 重复犯错检测：字段已预留，但尚未接线

`analyzer.detect_repeat_streak()` 已实现（同一组 error_date 按升序排列，相邻间隔 ≤ 7 天则 streak +1，`max_repeat_streak ≥ 2` 判定为重复犯错模式），规则本身与早期设计一致。

**但当前没有任何代码路径调用它。** `repeat_streak` / `max_repeat_streak` / `repeat_pattern` 三个字段只在新建错题时写入 `0 / 0 / false`，重做流程不更新它们。

由此产生的实际影响：

- 统计接口 `GET /api/stats/subject/{subject}` 返回的 `repeat_error_count` 恒为 0；
- 详情页已实现「⚠️ 重复犯错模式（连续 N 次）」的展示，但该分支永远不会触发。

要接通需要在保存错题和提交重做时，按知识点跨题目重算 streak 并回写同组错题，属于待实现功能（详见 8.30）。

### 3.9 已废弃或从未落地的设计

| 项 | 状态 |
|---|---|
| 满分 100 扣减制算法（错误次数 ×8 等） | 已被 3.5 的综合方案取代 |
| `similar_error_count`、`similar_error_redo_fail` | **从未实现**，字段不存在于任何写入路径 |
| 错误类型 → 建议映射表（概念不清→费曼学习法等） | **从未实现**。`error_suggestion` 由 AI 在分析时自由生成，没有本地规则表 |
| 按 `error_type` 统计同类型错题数的自动累计 | 未实现；统计接口只在读取时按当前题目现算分布 |

---

## 4. 核心功能流程

### 流程 4.1：上传错题（核心流程）

```
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌───────────┐
│  选择    │    │  上传    │    │  AI 分析   │    │  确认保存 │
│  孩子+   │───►│  题目    │───►│  (LLM)    │───►│  写入     │
│  学科    │    │  图片    │    │           │    │  Obsidian │
└─────────┘    └──────────┘    └───────────┘    └───────────┘
```

**详细步骤：**

1. **选择孩子和学科** — 页面顶部有切换栏，选好当前是哪个孩子、哪门课
2. **上传图片** — 支持多张（手机拍照 / 相册选择 / 直接拖拽文件）
3. **AI 分析** — 后端调用配置的多模态 LLM，返回：
   - 识别出的题目内容（文字）
   - 题目类型判断（手写题 / 印刷题 / 图形题 / 纯文字题）
   - 正确答案及解题过程
   - 如果孩子上传了自己的答案图片，同时识别并分析错误
4. **预览确认** — 前端展示 AI 的分析结果，**用户可以修改**（AI 不一定全对）
   - 可以编辑题目文字、正确答案、错误分析
   - 可以调整 error_type、topic、difficulty 等分类
   - 可以补充 `error_date`（错误发生日期）
5. **保存** — 写入 Obsidian vault 对应目录的 markdown 文件 + 图片存入 `_assets/`

**关键交互细节：**
- 如果一次上传多张图片（比如一道大题有 3 页），AI 需要合并分析为一道题
- 支持"只上传题目"（不上传孩子的答案）→ 系统只记录题目和正确答案，error_type 留空待后续补充
- 保存时可以手动加 tag

---

### 流程 4.2：复习重做

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  筛选    │    │  展示    │    │  孩子    │    │  记录    │
│  错题    │───►│  题目    │───►│  作答    │───►│  结果    │
│  列表    │    │  (隐藏   │    │          │    │  更新    │
│          │    │   答案)  │    │          │    │  状态    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

**详细步骤：**

1. **筛选** — 按条件筛选错题：
   - 按 `error_type`（只看计算失误的）
   - 按 `mastery_status`（只看还没掌握的）
   - 按 `topic` / `knowledge_points`（只练某个章节）
   - 按时间范围（最近一周的错题）
2. **展示题目** — 默认隐藏答案，只显示原题
3. **孩子作答** — 两种模式：
   - **纸质模式**：把题目打印/抄出来做，做完后回来对答案
   - **屏幕模式**：直接在网页上作答（适合选择题/填空题）
4. **对答案 + 记录** — 展示正确答案和错误分析，标记本次重做结果：
   - ✅ 做对了 → `redo_count +1`，追加 `redo_history` 为 `correct`
   - ❌ 又错了 → `redo_count +1`，追加 `redo_history` 为 `wrong`，可填原因
5. **自动更新** — 根据重做结果更新 `mastery_status`，更新相关题目的 `similar_error_count` 等统计字段

---

### 流程 4.3：设置页面（LLM 配置）

```
┌──────────────────────────────────────────┐
│  AI 模型设置                              │
│                                          │
│  API 地址:  [https://api.openai.com/v1 ] │
│  API Key:   [sk-•••••••••••••  👁]      │
│  模型名称:  [gpt-4o              ]       │
│                                          │
│  [测试连接]  ← 发一条简单测试验证可用      │
│                                          │
│  系统提示词（可选）:                       │
│  ┌──────────────────────────────────┐    │
│  │ 你是一位经验丰富的教师...         │    │
│  └──────────────────────────────────┘    │
│                                          │
│              [保存设置]                   │
└──────────────────────────────────────────┘
```

**说明：**
- 使用 **OpenAI 兼容 API 格式**（`/v1/chat/completions`），这样 OpenAI、Claude（通过代理）、国产模型、本地 Ollama 都能用
- 设置持久化在容器内的配置文件里（不写入 Obsidian vault）
- "测试连接" 发一张简单的数学题图片，验证 AI 能正常返回分析结果
- 系统提示词可自定义，用于调优 AI 分析风格

---

### 流程 4.4：账号切换

```
顶部导航栏：

[👧 女儿 ▼]  [ 数学 ▼]  [⚙️ 设置]
[👦 儿子 ▼]
```

- 无密码，点击头像/名字直接切换
- 切换后，学科列表、错题列表全部跟着变
- 学科列表根据孩子自动变化（女儿 6 门 / 儿子 3 门）

---

### 流程 4.5：AI 出题（后续扩展）

这个流程现在不做，但数据结构已为它预留了基础：

```
用户请求 → "帮我给女儿出 5 道数学题，重点练因式分解"
                    ↓
系统查询 vault → 找到相关错题 + 错误模式
                    ↓
AI 根据错因模式 → 生成针对性练习题
                    ↓
输出新题（可选写入 vault 作为新练习题）
```

---

## 5. 借鉴分析：智学精灵项目

> 来源：`~/Downloads/学习/借鉴.md`（Electron + 原生前端项目）

### 5.1 高价值借鉴（建议纳入初版）

#### ⭐⭐⭐ 掌握度评分算法（替代简单的 new/reviewing/mastered）

满分 100 扣减制：

| 扣分项 | 公式 | 上限 |
|---|---|---|
| 错误次数 | 次数 × 8 | 扣 40 |
| 低难度还错（难度 ≤ 2） | 次数 × 5 | 扣 15 |
| 多种错误类型 | (类型数 - 1) × 5 | 扣 15 |
| 近期犯错时间衰减 | max(0, 10 - 距今天数 × 1.5) | 扣 10 |

等级划分：

| 分数区间 | 等级 | 含义 |
|---|---|---|
| ≥ 70 | high | 已掌握 |
| 40 - 69 | medium | 待加强 |
| < 40 | low | 薄弱 |

**对我们的价值：** 把 `mastery_status` 升级为 **数值分数 + 等级**，AI 出题时能更精准地挑薄弱题。

#### ⭐⭐⭐ 重复犯错检测（Streak 机制）

```
同一知识点，相邻两次犯错间隔 ≤ 7 天 → streak + 1
maxStreak ≥ 2 → 标记为"重复犯错模式"
maxStreak ≥ 4 → 严重度 high
```

**对我们的价值：** 识别"反复犯同类错误"的模式，帮 AI 出题时精准打击顽固错误。

#### ⭐⭐⭐ 学习优先级排序

| 条件 | 优先级 |
|---|---|
| 薄弱 + 3天内出错 | 🔴 最高优先 (highest) |
| 薄弱 | 🟡 高优先 (high) |
| 待加强 + 3次以上且7天内出错 | 🟡 高优先 |
| 待加强 | 🔵 中优先 (medium) |

**对我们的价值：** 直接服务于"AI 出题"功能，智能推荐最需要练的题。

### 5.2 中价值借鉴（可选纳入）

#### ⭐⭐ 间隔复习计划

| 掌握等级 | 复习频率 | 开始时间 |
|---|---|---|
| 薄弱 | 每天 | 立即 |
| 待加强 | 每周 3 次 | 立即 |
| 已掌握 | 每月 1 次 | 14 天后（防遗忘） |

**对我们的价值：** 集成到复习流程里，自动安排下次复习日期。

#### ⭐⭐ 错误类型 → 针对性建议映射

| 错误类型 | 建议 |
|---|---|
| 概念不清 | 回顾课本定义和定理，用费曼学习法讲出来 |
| 计算错误 | 每步写清楚，做完立刻代入检验 |
| 审题错误 | 圈出关键词，用自己的话复述再下笔 |
| 知识遗忘 | 建知识卡片，间隔重复法复习 |
| 方法错误 | 总结题型套路，做题前先想考什么 |
| 粗心大意 | 设立检查清单，考试留 5 分钟专门检查 |

**对我们的价值：** AI 分析错题时，根据 `error_type` 自动附上针对性建议。

#### ⭐⭐ 本地规则 AI 引擎（降级策略）

```
LLM API 调用失败 → 自动降级到本地规则引擎
```

**对我们的价值：** 网络不稳定或 API 额度用完时，系统不至于完全瘫痪。

### 5.3 低优先级（后续扩展）

#### ⭐ 可视化模块（ECharts / D3）

- 科目分布饼图、错误趋势折线图、薄弱知识点 TOP10 条形图
- 思维导图：科目 → 知识点 → 错误类型，节点颜色 = 掌握度

#### ⭐ 批量导入（CSV / JSON）

- 已有现成错题数据时一次性导入

---

## 6. 错题收集与解析完整流程及异常处理

### 阶段 6.1：前置条件检查

```
用户点击"上传错题"
       │
       ▼
┌─────────────────┐
│ 1. 是否已选择孩子？ │
│ 2. 是否已选择学科？ │
│ 3. LLM 是否已配置？ │
└─────────────────┘
       │
  ┌────┴────┐
  │ 任一不满足 │──► 引导到对应设置页面
  └─────────┘
       │ 全部满足
       ▼
   进入上传界面
```

**异常处理：**
- LLM 未配置 → 弹出提示"请先在设置页面配置 AI 模型"，附跳转链接
- 未选择孩子/学科 → 上传按钮置灰，顶部导航栏闪烁提示

---

### 阶段 6.2：图片上传

```
用户操作：拍照 / 选相册 / 拖拽文件
              │
              ▼
       ┌─────────────┐
       │ 前端校验      │
       │ - 文件格式    │
       │ - 文件大小    │
       │ - 图片数量    │
       └─────────────┘
              │
         ┌────┴────┐
         │ 校验失败？ │──► Toast 提示具体原因，拒绝上传
         └─────────┘
              │ 通过
              ▼
       显示图片预览缩略图
       用户可删除/重排/补充
              │
              ▼
       点击"开始分析"
```

**校验规则与异常处理：**

| 校验项 | 规则 | 异常提示 |
|---|---|---|
| 文件格式 | 仅 jpg / jpeg / png / heic / heif / webp，且文件头嗅探通过 | "{文件名} 格式不受支持，请上传 jpg / png / heic / webp 图片" |
| 文件大小 | 单张 ≤ 20MB | "{文件名} 超过 20MB，请压缩后重试" |
| 图片数量 | 单次 ≤ 10 张 | "一次最多上传 10 张图片" |
| 分辨率 | 最短边 ≥ 200px | "{文件名} 分辨率偏低（WxH），可能影响识别效果"（警告，不阻止） |

**用户操作：**
- 预览阶段可以长按拖动调整顺序（多页题需要正确顺序）
- 可以点击 × 删除不需要的图片
- 可以追加更多图片

---

### 阶段 6.3：AI 分析

```
前端发送请求到后端
       │
       ▼
┌──────────────────────┐
│ 后端处理流程           │
│                      │
│ 1. 图片预处理         │
│    - 压缩到合理尺寸    │
│    - 按顺序编号        │
│                      │
│ 2. 构建 Prompt        │
│    - 系统提示词        │
│    - 用户配置          │
│    - 图片数据          │
│                      │
│ 3. 调用 LLM API       │
│    - 设置超时 (60s)    │
│    - 错误重试 (2次)    │
│                      │
│ 4. 解析返回结果        │
│    - 校验 JSON 格式    │
│    - 提取各字段        │
└──────────────────────┘
```

**Prompt 设计要求 LLM 返回结构化 JSON：**

```json
{
  "source_type": "手写题",
  "question_text": "已知方程 x² - 5x + 6 = 0，求 x 的值。",
  "has_diagram": false,
  "diagram_description": null,
  "student_answer": {
    "detected": true,
    "text": "x = 2 或 x = -3",
    "confidence": "high"
  },
  "correct_answer": "x = 2 或 x = 3",
  "solution_steps": "使用因式分解：(x-2)(x-3)=0...",
  "error_analysis": {
    "error_point": "第二个根计算错误，写成了 -3 而不是 3",
    "error_type": "概念理解错误",
    "root_cause": "因式分解时常数项因数组合的正负号判断失误",
    "suggestion": "多练习因式分解中常数项与一次项系数的符号关系"
  },
  "metadata": {
    "topic": "一元二次方程",
    "knowledge_points": ["求根公式", "因式分解"],
    "difficulty": "中等"
  }
}
```

**异常处理（重点）：**

| 异常情况 | 处理策略 |
|---|---|
| **图片模糊/无法识别** | LLM 返回 `confidence: low` 或明确说无法识别 → 前端提示"图片可能太模糊，AI 无法准确识别，请手动补充题目内容"，进入**半自动模式** |
| **图片包含多道题** | LLM 检测到多道题 → 前端展示识别结果，让用户选择"拆分为多道错题"或"合并为一道" |
| **LLM API 超时** | 重试 2 次（间隔 3s / 8s）→ 仍失败则提示"AI 分析超时，请检查网络或稍后重试"，图片保留不丢失 |
| **LLM API 返回错误** | 401 → "API Key 无效，请检查设置" / 429 → "API 调用频率超限，请稍后重试" / 500 → "AI 服务异常，请稍后重试" |
| **LLM 返回格式异常** | JSON 解析失败 → 重试一次（提示 LLM 重新输出 JSON）→ 仍失败则降级到**手动录入模式** |
| **AI 分析结果明显错误** | 用户确认阶段发现 → 直接手动修改，系统不阻止 |
| **没有检测到孩子答案** | 正常情况（只拍了题目没拍答案）→ `student_answer.detected: false`，error_analysis 留空，标记为"待补充错因" |
| **图片含数学图形/公式** | LLM 识别图形并用文字描述 → 在 markdown 中保留图片 + 文字描述双份，方便复习时参考 |

---

### 阶段 6.4：结果预览与确认（人机协作）

```
AI 返回结果
       │
       ▼
┌──────────────────────────────────────┐
│         预览页面布局                   │
│                                      │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ 原始图片  │  │ AI 分析结果       │  │
│  │ (可点击   │  │                  │  │
│  │  放大)    │  │ 题目：[可编辑]    │  │
│  │          │  │ 答案：[可编辑]    │  │
│  │          │  │ 分析：[可编辑]    │  │
│  │          │  │                  │  │
│  │          │  │ 分类：           │  │
│  │          │  │  错误类型 [下拉]  │  │
│  │          │  │  知识点   [下拉]  │  │
│  │          │  │  难度     [星级]  │  │
│  │          │  │  错误日期 [日期]  │  │
│  └──────────┘  └──────────────────┘  │
│                                      │
│  置信度指示器：🟢高 / 🟡中 / 🔴低     │
│                                      │
│         [保存]  [重新分析]  [手动录入] │
└──────────────────────────────────────┘
```

**关键交互：**

- **置信度指示器**：AI 对识别结果的自信程度，低置信度时醒目提示用户仔细检查
- **可编辑**：所有 AI 生成的内容都可以手动修改
- **重新分析**：对当前结果不满意，可以换一种方式描述需求让 AI 重新分析
- **手动录入**：完全跳过 AI，自己填写所有内容
- **图片与原结果对照**：左边原图右边结果，方便逐字核对

**异常处理：**

| 场景 | 处理 |
|---|---|
| 用户修改了 AI 的题目识别文字 | 保存时以用户修改后的版本为准，原图仍然保留 |
| 用户点了"手动录入" | 切换到空白表单，所有字段手动填写，图片仍然关联 |
| 用户长时间未操作（>10 分钟） | 草稿自动保存到 localStorage，下次进来提示"有未完成的录入" |
| 用户关闭页面/刷新 | 同上，草稿不丢失 |

---

### 阶段 6.5：保存写入

```
用户点击"保存"
       │
       ▼
┌─────────────────────────────┐
│ 后端执行保存流程              │
│                             │
│ 1. 生成唯一 ID              │
│ 2. 保存图片到 _assets/      │
│ 3. 生成 markdown 文件内容    │
│ 4. 写入对应学科目录          │
│ 5. 更新相关题目的统计字段     │
│    (similar_error_count等)  │
│ 6. 返回保存结果             │
└─────────────────────────────┘
       │
  ┌────┴────┐
  │ 保存成功？│
  └─────────┘
    │      │
   是      否
    │      │
    ▼      ▼
  前端   提示错误
  跳转   保留草稿
  到列
  表页
```

**异常处理：**

| 异常 | 处理 |
|---|---|
| 图片写入失败（磁盘满/权限问题） | 提示"保存失败：磁盘空间不足或权限错误"，草稿保留不丢失 |
| Markdown 写入失败 | 同上，图片可能已保存但 md 没写入 → 提示"部分保存失败"，列出哪些成功了哪些没有 |
| 文件名冲突（极小概率 ID 重复） | 自动追加后缀重试 |
| 相关题目统计字段更新失败 | 非致命错误，不影响主流程，后台记录日志，下次有机会时补偿更新 |

---

### 阶段 6.6：保存后的自动处理

```
保存成功
    │
    ├──► 更新 Obsidian vault 文件（OneDrive 自动同步）
    │
    ├──► 更新 frontmatter 中的统计字段
    │    - 同 knowledge_points 的其他题目的 similar_error_count
    │    - 同 error_type 的其他题目的相关计数
    │
    ├──► 更新该孩子的 mastery_score（如果纳入了掌握度评分算法）
    │
    └──► 前端 Toast 提示"保存成功"，跳转到错题列表
```

---

### 全局异常处理策略总结

| 层级 | 策略 |
|---|---|
| **前端** | 草稿自动保存、表单状态恢复、离线检测（断网时提示但允许继续编辑） |
| **后端 ↔ LLM** | 超时重试（2 次）、降级到手动模式、结构化错误码 |
| **后端 → 文件系统** | 事务性写入（先写临时文件再 rename）、失败回滚、磁盘空间预检 |
| **数据一致性** | 图片已保存但 md 写入失败 → 标记为"待修复"，下次进入时提示修复 |

**核心原则：AI 做初稿，人做最终确认；任何环节失败都不丢数据。**

---

## 待确认

- [x] 掌握度评分算法纳入初版（已更新 frontmatter v2）
- [x] 重复犯错检测纳入初版（已新增字段）
- [x] 间隔复习计划纳入初版（已新增字段）
- [x] 错误类型建议映射纳入初版（已新增字段）
- [x] 技术实现与部署方案（已完成，见第 7 节）

---

## 7. 技术实现与部署方案

### 7.1 项目结构

```
mistakes/                              # 项目根目录（当前目录）
├── backend/                           # 后端（进 Docker）
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                        # FastAPI 入口
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── children.py        # 孩子、学科相关
│   │   │   │   ├── questions.py       # 错题 CRUD
│   │   │   │   ├── upload.py          # 图片上传 + AI 分析
│   │   │   │   ├── review.py          # 复习重做
│   │   │   │   └── settings.py        # LLM 设置
│   │   │   └── deps.py                # 依赖注入
│   │   ├── services/
│   │   │   ├── llm.py                 # LLM API 调用（OpenAI 兼容）
│   │   │   ├── analyzer.py            # 掌握度评分、重复犯错检测
│   │   │   ├── file_ops.py            # Markdown + 图片文件读写
│   │   │   └── review_scheduler.py    # 间隔复习计划计算
│   │   ├── core/
│   │   │   ├── config.py              # 应用配置
│   │   │   └── prompts.py             # AI 分析 Prompt 模板
│   │   └── models/
│   │       ├── question.py            # 错题数据模型
│   │       └── settings.py            # 设置数据模型
│   └── tests/
│
├── frontend/                          # 前端（宿主机运行）
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── UploadPage.tsx         # 上传错题
│   │   │   ├── ListPage.tsx           # 错题列表
│   │   │   ├── ReviewPage.tsx         # 复习重做
│   │   │   ├── SettingsPage.tsx       # LLM 设置
│   │   │   └── DashboardPage.tsx      # 总览（二期）
│   │   ├── components/
│   │   │   ├── ImageUploader.tsx      # 图片上传组件
│   │   │   ├── AnalysisPreview.tsx    # AI 分析结果预览
│   │   │   ├── QuestionEditor.tsx     # 错题编辑器
│   │   │   ├── ChildSwitcher.tsx      # 孩子切换
│   │   │   └── SubjectSelector.tsx    # 学科选择
│   │   ├── api/
│   │   │   └── client.ts             # API 请求封装
│   │   ├── store/
│   │   │   └── useStore.ts           # 全局状态（Zustand）
│   │   └── types/
│   │       └── index.ts              # TypeScript 类型定义
│   └── tsconfig.json
│
├── config/                            # 持久化配置（Docker volume 挂载）
│   └── settings.json                  # LLM 设置（不进 vault）
│
├── docker-compose.yml
├── .env                               # 环境变量（端口等）
└── discuss.md                         # 设计讨论文档
```

---

### 7.2 后端 API 设计

| 模块 | 方法 | 路径 | 说明 |
|---|---|---|---|
| **孩子** | GET | `/api/children` | 获取孩子列表 + 各自学科 |
| **上传** | POST | `/api/upload/images` | 上传图片（multipart），返回临时 image_ids |
| **分析** | POST | `/api/analyze` | 发送 image_ids → AI 分析 → 返回结构化结果 |
| **分析（重试）** | POST | `/api/analyze/retry` | 对上一次分析结果不满意，重新分析 |
| **保存** | POST | `/api/questions` | 保存错题为 markdown + 图片归档 |
| **列表** | GET | `/api/questions` | 按 child / subject / error_type / mastery_level 等筛选 |
| **详情** | GET | `/api/questions/{id}` | 获取单条错题详情 |
| **更新** | PUT | `/api/questions/{id}` | 编辑错题 |
| **删除** | DELETE | `/api/questions/{id}` | 删除错题（同时删除图片和 md 文件） |
| **重做** | POST | `/api/questions/{id}/redo` | 提交重做结果 → 更新 mastery_score、review 计划等 |
| **复习计划** | GET | `/api/review/plan` | 获取今日待复习的错题列表 |
| **设置** | GET | `/api/settings` | 获取 LLM 配置 |
| **设置** | PUT | `/api/settings` | 保存 LLM 配置 |
| **设置** | POST | `/api/settings/test` | 测试 LLM 连接 |
| **统计** | GET | `/api/stats/overview` | 总览统计（错题数、掌握度分布等） |
| **统计** | GET | `/api/stats/subject/{subject}` | 某学科详细统计 |

---

### 7.3 Docker 配置

**docker-compose.yml：**

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: mistakes-backend
    ports:
      - "8000:8000"
    volumes:
      # Obsidian vault（写入错题文件）
      - /Users/zhuyi/Library/CloudStorage/OneDrive-共享的库-oneDrive/错题集:/vault
      # 持久化配置（LLM 设置等）
      - ./config:/app/config
    environment:
      - VAULT_PATH=/vault
      - CONFIG_PATH=/app/config
      - CORS_ORIGINS=http://localhost:5173,http://192.168.1.100:5173
    restart: unless-stopped
```

**Dockerfile：**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/config

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**requirements.txt：**

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
python-multipart==0.0.*
httpx==0.28.*          # 异步 HTTP 客户端（调用 LLM API）
pydantic==2.*
pyyaml==6.*            # 解析/生成 markdown frontmatter
Pillow==11.*           # 图片预处理
python-dotenv==1.*
```

---

### 7.4 前端关键配置

**vite.config.ts（关键部分）：**

```typescript
export default defineConfig({
  server: {
    host: '0.0.0.0',       // 局域网可访问
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // 代理到 Docker 后端
        changeOrigin: true,
      },
    },
  },
})
```

**环境变量（.env）：**

```bash
BACKEND_PORT=8000
FRONTEND_PORT=5173
```

---

### 7.5 启动与部署流程

```bash
# 1. 初始化 Obsidian vault 目录结构
mkdir -p ~/Library/CloudStorage/OneDrive-共享的库-oneDrive/错题集/{daughter/{语文,数学,英语,历史,地理,政治},son/{语文,数学,英语},_assets/{daughter,son}}

# 2. 启动后端（Docker）
cd /path/to/mistakes
docker compose up -d --build

# 3. 启动前端（宿主机）
cd frontend
npm install
npm run dev -- --host 0.0.0.0

# 4. 访问
# 电脑：http://localhost:5173
# 手机：http://<宿主机局域网IP>:5173
```

---

### 7.6 数据流总览

```
手机/电脑浏览器
       │
       │ HTTP :5173
       ▼
┌─────────────┐     proxy /api      ┌──────────────────┐
│   Frontend  │ ──────────────────► │  Backend (Docker) │
│   React+Vite│                     │  FastAPI :8000    │
│  (宿主机)    │ ◄────────────────── │                  │
└─────────────┘     JSON response   │  ┌────────────┐  │
                                    │  │ LLM Service │  │
                                    │  │ (httpx)     │  │
                                    │  └─────┬──────┘  │
                                    │  ┌─────▼──────┐  │
                                    │  │ File Ops    │  │
                                    │  │ (写md+图片) │  │
                                    │  └─────┬──────┘  │
                                    └────────│─────────┘
                                             │ volume mount
                                             ▼
                                    ┌────────────────┐
                                    │  Obsidian Vault │
                                    │  /vault/...     │
                                    └────────┬───────┘
                                             │ OneDrive
                                             ▼
                                    ┌────────────────┐
                                    │   Obsidian App  │
                                    │   (宿主机)      │
                                    └────────────────┘
```

---

### 7.7 开发顺序建议

| 阶段 | 内容 | 预计工作量 |
|---|---|---|
| **P0** | 后端骨架 + 文件读写 + LLM 调用 + 保存错题 | 核心链路 |
| **P1** | 前端上传页面 + 预览确认 + 保存 | 能跑通完整流程 |
| **P2** | 错题列表 + 筛选 + 详情查看 | 基本管理功能 |
| **P3** | 复习重做流程 + mastery_score/review 自动更新 | 复习闭环 |
| **P4** | 设置页面 + 测试连接 | 可配置性 |
| **P5** | 统计分析 + 可视化（二期） | 锦上添花 |

---

## 待确认

- [x] 掌握度评分算法纳入初版（已更新 frontmatter v2）
- [x] 重复犯错检测纳入初版（已新增字段）
- [x] 间隔复习计划纳入初版（已新增字段）
- [x] 错误类型建议映射纳入初版（已新增字段）
- [x] 技术实现与部署方案（已完成，见第 7 节）

---

## 8. 项目初始化与当前进展

> 日期：2026-08-31

### 8.1 已完成事项

| 项目 | 状态 | 说明 |
|---|---|---|
| 项目骨架搭建 | ✅ | backend/ + frontend/ + config/ 目录结构 |
| Docker 后端 | ✅ | FastAPI 运行在 `:8001`（因 `:8000` 被其他容器占用） |
| React 前端 | ✅ | Vite 运行在 `:5173`，局域网 `192.168.88.168:5173` |
| Obsidian vault | ✅ | 路径：`/Users/zhuyi/Library/CloudStorage/OneDrive-共享的库-oneDrive/错题集/` |
| API 验证 | ✅ | `/api/health`、`/api/children`、`/api/questions`、`/api/settings` 均正常 |
| 前端页面渲染 | ✅ | 孩子切换、学科选择、各页面路由正常 |
| Bug 修复 | ✅ | 修复 zustand selector 使用不当导致的无限渲染循环 |

### 8.2 Bug 修复记录

| 问题 | 原因 | 修复方式 |
|---|---|---|
| 前端页面空白无反应 | `useStore()` 没有用 selector，导致每次状态变更都返回新对象，触发无限渲染循环 | 所有组件改为 `useStore(s => s.xxx)` selector 模式 |
| `SubjectSelector` 无限循环 | `subjects` 数组每次渲染都是新引用，导致 `useEffect` 反复触发 | 用 `useMemo` 缓存 subjects，`useEffect` 只依赖 `currentChild` |
| 后端启动失败（CORS 配置） | `CORS_ORIGINS` 环境变量是逗号分隔字符串，但 Settings 期望 `list[str]` | `cors_origins` 改为 `str` 类型，添加 `cors_origin_list` 属性解析 |
| 后端端口冲突 | `:8000` 被 `dev-api` 容器占用 | 改用 `:8001` |

### 8.3 端口配置变更记录

| 原设计 | 实际 | 原因 |
|---|---|---|
| 后端 `:8000` | 后端 `:8001` | `:8000` 被 `dev-api` 容器占用 |
| docker-compose `version: '3.8'` | 已移除 | Docker Compose 新版不再需要 version 字段 |

### 8.4 UI 优化（已完成）

**全局样式体系：**
- 新增 `index.css`，定义 CSS 变量（颜色、圆角、阴影）
- 统一卡片设计：白色背景 + 轻阴影 + 细边框
- 响应式布局，手机/平板/电脑自适应
- 渐变 logo + 粘性导航栏

**各页面改进：**

| 页面 | 改进内容 |
|---|---|
| 上传页 | 拖拽高亮反馈、分析结果分区块展示、置信度颜色标签、成功/错误提示样式 |
| 列表页 | 掌握度徽章（红/黄/绿）、筛选下拉、空状态提示、删除按钮 |
| 复习页 | 空状态庆祝动画、待复习卡片带"开始重做"按钮 |
| 设置页 | 表单卡片化、测试连接反馈、保存成功提示 |
| 导航栏 | 当前页面高亮、渐变色 logo、分隔线 |

### 8.5 新增功能：家长备注

> 日期：2026-08-31

**需求：** 上传错题时，家长可以输入自己的观察和建议（选填）。

**实现：**

| 层 | 改动 |
|---|---|
| 前端 | 上传页新增 `<textarea>` 输入框，绑定 `parentNote` state，保存时传递给 API |
| 后端模型 | `QuestionCreate` 新增 `parent_note: Optional[str]` 字段 |
| Markdown 输出 | 保存时如果有备注，在文件末尾添加 `## 家长备注` 章节 |

**生成的 Markdown 示例：**

```markdown
## 原题
...

## 正确答案
...

## 错误分析
...

## 家长备注

这道题是期中考试错的，孩子对分数加减法一直不太熟练，需要多练习通分。
```

### 8.6 产品介绍页面

> 日期：2026-08-31

生成了 `intro.html` 产品介绍页面，用于向他人展示软件功能。

**页面特性：**
- 暗色调现代设计风格
- 滚动触发的淡入动画（Intersection Observer）
- 背景渐变旋转 + 鼠标跟随光晕效果
- 卡片悬停浮起 + 边框高亮
- 响应式布局

**页面结构：**

| 区域 | 内容 |
|---|---|
| Hero | 大标题 + 标语 + 模拟界面截图（脉冲动画） |
| 核心功能 | 9 张功能卡片（拍照即录、AI 分析、掌握度评估、重复犯错检测、间隔复习、Obsidian 归档、多孩子管理、家长备注、多端访问） |
| 工作流程 | 4 步时间线（拍照 → AI 分析 → 确认保存 → 智能复习） |
| 系统架构 | 可视化架构图 + 数据指标（100% 本地存储 / 9 学科 / ∞ 可扩展） |
| 技术栈 | React / FastAPI / Obsidian / LLM 四大技术介绍 |

**文件路径：** `mistakes/intro.html`

### 8.7 LLM 配置

> 日期：2026-08-31

**配置的 AI 服务：**

| 配置项 | 值 |
|---|---|
| 服务商 | 火山引擎方舟（Volces Ark） |
| API 地址 | `https://ark.cn-beijing.volces.com/api/coding/v3` |
| 模型 | `ark-code-latest` |
| 状态 | ✅ 已验证可用 |

**踩坑记录：**

| 问题 | 原因 | 解决 |
|---|---|---|
| 404 Not Found | base URL 不正确（`/api/coding` 或 `/api/v3`） | 正确 URL 为 `/api/coding/v3` |
| ASCII 编码错误 | 前端发回脱敏 API Key（含 `•` 字符），HTTP header 无法编码 | 后端检测脱敏 key，自动从配置文件读取真实 key |
| JSON 解析失败 | AI 返回 LaTeX 公式（`\frac`, `\pm`, `\sqrt`），JSON 中为非法转义 | 后端添加 regex 修复，将非法转义双写反斜杠 |

### 8.8 完整链路验证

> 日期：2026-08-31

使用程序生成的测试图片（一元二次方程题目）验证完整链路：

**测试结果：**

| 步骤 | 状态 | 说明 |
|---|---|---|
| 1. 上传图片 | ✅ | 保存为临时文件，返回 image_id |
| 2. AI 分析 | ✅ | 正确识别题目、学生答案、错误原因（含 LaTeX 公式） |
| 3. 保存错题 | ✅ | Markdown 文件生成在 Obsidian vault，frontmatter 完整 |
| 4. 重做更新 | ✅ | `redo_count +1`，`mastery_score` 重算，`next_review_date` 更新 |

**生成的测试文件：** `/Users/zhuyi/.../错题集/daughter/数学/2026-08-31-cb34fe9b.md`

### 8.9 错题详情页

> 日期：2026-08-31

**新增功能：**

| 项 | 说明 |
|---|---|
| 前端页面 | `DetailPage.tsx` — 展示题目图片、完整 markdown 内容、知识点标签、重做记录 |
| 后端接口 | `GET /api/questions/{id}` — 返回完整 frontmatter + body |
| 图片服务 | `GET /api/questions/{id}/images` — 列出图片；`GET /api/questions/{id}/images/{filename}` — 提供图片文件 |
| 列表跳转 | 列表页卡片可点击，跳转到详情页（`/question/:id?child=...&subject=...`） |

**详情页布局：**
1. 头部：题目名 + 孩子/学科 + 掌握度分数大数字
2. 统计：重做次数、下次复习日期、重复犯错警告
3. 题目图片（可点击放大）
4. Markdown 渲染的正文（原题、答案、分析、家长备注）
5. 知识点标签
6. 重做历史记录

### 8.10 复习重做流程

> 日期：2026-08-31

**后端接口：** `POST /api/questions/{id}/redo?child=...&subject=...`

请求体：`{"result": "correct" | "wrong", "note": "..."}`

**自动更新逻辑：**

| 字段 | 更新规则 |
|---|---|
| `redo_count` | +1 |
| `redo_history` | 追加本次记录（日期、结果、备注） |
| `mastery_score` | 根据算法重新计算（错误次数、难度、时间衰减） |
| `mastery_level` | 由 mastery_score 映射 |
| `mastery_status` | 由 mastery_level 和 redo_count 决定 |
| `next_review_date` | 根据 mastery_level 和本次结果计算间隔 |
| `review_interval_days` | 做对 → 间隔增长；做错 → 间隔重置 |

**前端复习页面功能：**
- 显示今日待复习题目列表
- 进度条显示复习进度
- 点击"查看答案"后展示答案区域
- "做对了" / "又错了" 两个按钮
- 自动推进到下一题
- 全部完成后刷新列表

### 8.11 当前运行状态

```bash
# 后端（Docker）
docker ps  # mistakes-backend on :8001

# 前端（宿主机）
cd frontend && npm run dev -- --host 0.0.0.0
# → Local: http://localhost:5173
# → Tailscale: http://100.123.137.127:5173

# PWA 生产构建
cd frontend && npm run build
# → dist/ 目录，可部署到任何静态服务器
```

### 8.12 PWA 支持

> 日期：2026-09-01

**实现内容：**

| 项 | 说明 |
|---|---|
| `vite-plugin-pwa` | 自动生成 manifest 和 service worker |
| App 图标 | 192x192 和 512x512 PNG（紫色渐变背景 + 笔记本图案） |
| iOS 兼容 | `apple-touch-icon`、`apple-mobile-web-app-*` meta 标签 |
| 离线缓存 | Workbox 配置：HTML/JS/CSS 预缓存，字体缓存 1 年，API 网络优先 |
| 安全区域 | iPhone 刘海/底部安全区 padding |
| 全屏模式 | `display: standalone`，添加到桌面后无浏览器地址栏 |

**注意：** PWA 功能在**生产构建**下完全可用。开发模式下 service worker 不生效。

### 8.13 统计仪表盘

> 日期：2026-09-01

**后端 API：**

| 端点 | 说明 |
|---|---|
| `GET /api/stats/overview?child=...` | 总览统计：总数、学科分布、掌握度分布、错误类型、7 天趋势 |
| `GET /api/stats/subject/{subject}?child=...` | 学科详细统计：知识点掌握度、错误类型、重复犯错数 |
| `GET /api/stats/weak-points?child=...` | 薄弱知识点 TOP N |

**前端页面：** 使用 `recharts` 库实现可视化

| 图表 | 类型 | 数据 |
|---|---|---|
| 概览卡片 | 4 个 StatCard | 错题总数、平均掌握度、待复习数、已掌握率 |
| 学科分布 | 环形饼图 | 各科错题数量 |
| 掌握度分布 | 饼图 | 薄弱/待加强/已掌握数量 |
| 错误类型分布 | 水平条形图 | 各错误类型数量 |
| 最近 7 天趋势 | 折线图 | 每日新增错题数 |

### 8.14 图片压缩优化

> 日期：2026-09-05

**问题：** iPhone 拍摄的照片（如 12.9MB PNG）直接发送导致 API 返回 400 Bad Request。

**解决方案：** 在 `backend/app/services/llm.py` 中添加 `_preprocess_image()` 函数：

```python
def _preprocess_image(image_path: Path) -> tuple[str, str]:
    img = Image.open(image_path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # 缩放到最长边 1024px
    w, h = img.size
    if max(w, h) > 1024:
        scale = 1024 / max(w, h)
        img = img.resize((int(w*scale), int(h*scale)), Image.Resampling.LANCZOS)

    # 压缩为 JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)
    jpeg_bytes = buffer.getvalue()

    # 如果仍超过 4MB，进一步压缩
    if len(jpeg_bytes) > 4 * 1024 * 1024:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=60, optimize=True)
        jpeg_bytes = buffer.getvalue()

    return base64.b64encode(jpeg_bytes).decode("utf-8"), "image/jpeg"
```

**效果：** 12.9MB PNG → 191KB JPEG（压缩 66 倍）

### 8.15 异步任务队列

> 日期：2026-09-05

**需求：** 上传图片后，"开始分析"按钮立即可用，分析在后台异步执行，页面下方显示任务列表。

**后端实现：**

新增 `backend/app/services/task_manager.py`：
- `TaskManager` 单例，内存管理任务
- 任务状态：`pending` → `processing` → `completed` / `failed`
- 自动清理 24 小时前的旧任务

新增 `backend/app/api/routes/tasks.py`：

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/tasks` | POST | 创建任务（立即返回 task_id，后台执行分析） |
| `/api/tasks` | GET | 列出所有任务（按创建时间倒序） |
| `/api/tasks/{id}` | GET | 查询任务状态和结果 |
| `/api/tasks/{id}` | DELETE | 删除任务 |

**前端实现：**

`UploadPage.tsx` 重构为异步任务列表模式：
- 上传图片后立即清空上传区，"开始分析"按钮立即可用
- 任务列表按时间倒序显示
- 每 2 秒轮询任务状态
- 完成的任务可展开查看 AI 结果
- 提供"保存"和"忽略"操作
- 失败的任务提供"重试"操作

**用户体验：**
```
┌─────────────────────────────────────────┐
│  📷 上传区域                             │
│  [🔍 开始分析] ← 点完立即恢复可用        │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  📋 分析任务 (2)                        │
│  🔄 女儿·数学   分析中  11:35 · 1张图    │
│  ✅ 女儿·语文   [💾保存] [忽略]          │
│     └─ 展开查看 AI 分析结果             │
└─────────────────────────────────────────┘
```

### 8.16 数学公式渲染优化

> 日期：2026-09-05

**问题：** AI 返回的数学公式使用 LaTeX（如 `$15\frac{3}{4}=15×\frac{4}{3}=20$`），前端显示为乱码。

**解决方案（方案 C：Prompt + KaTeX 组合）：**

**1. AI Prompt 优化**（`backend/app/core/prompts.py`）：

新增格式要求，让 AI 优先输出纯文本/Unicode：
```
- 分数：用 "3/4" 而不是 "\\frac{3}{4}"
- 乘法：用 "×" 而不是 "\\times"
- 平方：用 "x²" 而不是 "x^2"
- 根号：用 "√4" 而不是 "\\sqrt{4}"
- 只有复杂公式（矩阵、积分等）才使用 LaTeX
```

**2. 前端 KaTeX 渲染**（兜底处理残留 LaTeX）：

安装 `katex` 库，创建 `frontend/src/utils/mathRenderer.ts`：
- `renderLatex()` - 渲染单个 LaTeX 公式
- `renderMathInText()` - 处理文本中的 `$...$` 和 `$$...$$`
- `renderMarkdownWithMath()` - 带数学公式的 Markdown 渲染

应用到 `AnalysisPreview.tsx` 和 `DetailPage.tsx`。

**效果：**
- 大部分公式以纯文本显示，简洁易读
- 残留 LaTeX 自动渲染为漂亮数学公式
- 复杂公式也能正确显示

### 8.17 任务列表与错题列表增强

> 日期：2026-09-05

#### 任务列表增强（保存前）

**1. 直接编辑 AI 分析结果**

`AnalysisPreview.tsx` 新增 `editable` 和 `onChange` props：
- 点击"编辑"按钮进入编辑模式
- 所有字段（题目、答案、分析、知识点、难度）可直接修改
- 修改实时更新到任务状态

**2. 重新生成**

后端新增 `POST /api/tasks/{id}/regenerate`：
- 重新上传图片并调用 AI 分析
- 任务状态重置为 processing
- 完成后替换原有分析结果

**3. 反馈优化**

后端新增 `POST /api/tasks/{id}/refine`：
- 用户输入反馈意见
- 后端 `llm.refine_analysis()` 根据反馈重新优化
- Prompt 包含当前分析结果 + 用户反馈
- AI 返回改进后的分析结果

```python
async def refine_analysis(image_paths, feedback, current_result):
    prompt = f"""你之前的分析：{current_result}
    
    用户反馈：{feedback}
    
    请根据反馈重新生成完整分析..."""
    return await llm_call(prompt)
```

**4. 保存前切换孩子/学科**

任务卡片展开后顶部显示下拉框：
- 可选择归属孩子（女儿/儿子）
- 可选择学科（根据孩子的学科列表动态变化）
- 切换后立即生效，保存时使用新选择

#### 错题列表增强（保存后）

**移动错题到其他孩子/学科**

后端新增 `PATCH /api/questions/{id}`：
- 参数：`new_child`, `new_subject`
- 自动移动图片文件到新的 `_assets` 目录
- 删除旧 markdown 文件，创建新的
- 更新 frontmatter 中的 child 和 subject 字段

```python
@router.patch("/questions/{question_id}")
async def update_question(question_id, new_child, new_subject):
    # 移动图片
    shutil.move(old_assets, new_assets)
    # 重建 markdown 文件
    file_ops.save_question(question_id, new_child, new_subject, data, body)
```

前端 `ListPage.tsx`：
- 每个错题卡片新增"↗️ 移动"按钮
- 点击后展开移动 UI（选择新孩子/学科）
- 确认后调用 PATCH API

**用户体验：**
```
┌─────────────────────────────────────────┐
│  ✅ 一元二次方程  [ mastered · 92分 ]    │
│     🏷 计算错误  🔄 重做 1 次            │
│                              [↗️] [×]   │
│  ┌───────────────────────────────────┐  │
│  │ 移动到：[ 👧 女儿 ▼] [ 数学 ▼]    │  │
│  │          [确认移动] [取消]         │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 8.18 待做事项

| 优先级 | 事项 | 状态 |
|---|---|---|
| P0 | 配置 LLM API → 测试图片上传 → AI 分析完整流程 | ✅ 已完成 |
| P1 | 前端 UI 优化 | ✅ 已完成 |
| P1.5 | 家长备注功能 | ✅ 已完成 |
| P2 | 错题列表筛选 + 详情查看 | ✅ 已完成 |
| P3 | 复习重做流程 | ✅ 已完成 |
| P4 | 错题编辑功能（修改已有错题） | ⚠️ **未完成**（见 8.41） |
| P5 | PWA 支持 | ✅ 已完成 |
| P6 | 统计仪表盘 | ✅ 已完成 |
| P7 | 图片压缩优化 | ✅ 已完成 |
| P8 | 异步任务队列 | ✅ 已完成 |
| P9 | 数学公式渲染优化 | ✅ 已完成 |
| P10 | 任务列表增强（编辑/重新生成/反馈优化/切换归属） | ✅ 已完成 |
| P11 | 错题列表增强（移动到其他孩子/学科） | ✅ 已完成 |
| - | 产品介绍页面 | ✅ 已完成 |
| - | Tailscale 手机访问 | ✅ 已完成 |
| - | Git 版本控制 | ✅ 已完成 |

### 8.19 Git 版本控制

> 日期：2026-09-05

**初始化配置：**

```bash
# 初始化仓库
git init

# 配置用户
git config user.email "user@example.com"
git config user.name "User"

# 添加远程仓库
git remote add origin https://github.com/zhuyizj-glitch/errorRecord.git

# 配置 credential helper（macOS Keychain）
git config --global credential.helper osxkeychain
```

**.gitignore 配置：**

排除敏感文件：
- `config/settings.json` - 包含 API key
- `.claude/settings.local.json` - 包含命令历史中的 API key
- `.env` - 环境配置
- `node_modules/` - 依赖包

**仓库信息：**

| 项目 | 值 |
|---|---|
| 远程地址 | https://github.com/zhuyizj-glitch/errorRecord |
| 分支 | main |
| 初始提交 | v0.1.0 (b05057b) |
| 文件数 | 58 个文件，13,914 行代码 |

**日常使用：**

```bash
git add .
git commit -m "提交说明"
git push
```

**安全注意：**
- ✅ API key 等敏感信息已排除
- ✅ 凭证已保存到 macOS Keychain
- ✅ 可直接 `git push` 无需每次输入密码

### 8.20 掌握度评估算法重构

> 日期：2026-09-06

**问题：** 原算法（扣减制）不符合实际学习规律：
- 新错题初始 100 分，直接"已掌握"
- 做错 1-2 次就 84-92 分，太容易掌握
- 缺少"连续做对"的奖励机制
- 时间衰减逻辑反向

**新算法（综合方案）：**

```
基础分 = (做对次数 / 总重做次数) × 60
连续奖励 = min(连续做对次数, 5) × 8
mastery_score = 基础分 + 连续奖励
```

**掌握标准：**
- `mastery_score >= 80` 且 `consecutive_correct >= 3` → **high（已掌握）**
- `mastery_score >= 50` → **medium（待加强）**
- `mastery_score < 50` → **low（薄弱）**

**新增字段：**
- `correct_count` - 重做做对次数
- `wrong_count` - 重做做错次数
- `consecutive_correct` - 当前连续做对次数（做错归零）

**示例验证：**
| 场景 | correct | wrong | consecutive | 基础分 | 连续奖励 | 总分 | 等级 |
|---|---|---|---|---|---|---|---|
| 做错 1 次 | 0 | 1 | 0 | 0 | 0 | 0 | low |
| 做对 1 次 | 1 | 0 | 1 | 60 | 8 | 68 | medium |
| 连续 3 次 | 3 | 0 | 3 | 60 | 24 | 84 | high ✓ |
| 做错后归零 | 3 | 1 | 0 | 45 | 0 | 45 | low |
| 再做对 1 次 | 4 | 1 | 1 | 48 | 8 | 56 | medium |

**实际测试：**
- 第 1 次做对 → 68 分 (medium)
- 第 2 次做对 → 76 分 (medium)
- 第 3 次做对 → 84 分 (high) ✓ 达到掌握标准
- 第 4 次做错 → 45 分 (low) ✓ 连续计数归零
- 第 5 次做对 → 56 分 (medium)

**代码位置：**
- `backend/app/services/analyzer.py` - 算法实现
- `backend/app/api/routes/questions.py` - 重做逻辑

### 8.21 部署方案建议

> 日期：2026-09-06

#### Cloud Studio 可行性分析

**结论：❌ 不适合**

Cloud Studio 是**云端开发环境（IDE）**，不是应用托管平台。

**核心限制：**

| 限制项 | 说明 |
|---|---|
| **临时预览** | 生成的访问链接有有效期，不是永久地址 |
| **闲置回收** | 免费工作空间闲置 30 天后自动删除，数据不可恢复 |
| **私有访问** | 默认仅创建者可访问，不适合多人使用 |
| **定位不符** | 设计用于开发调试，非生产环境托管 |

**需求对比：**

| 需求 | Cloud Studio |
|---|---|
| 长期稳定运行的后端服务 | ❌ 会超时关闭 |
| 持久化数据存储 | ❌ 30天不用就删除 |
| 手机随时访问 | ❌ 临时链接会失效 |
| 多人（孩子）使用 | ❌ 默认私有 |

#### 替代方案对比

| 方案 | 价格 | 优点 | 缺点 |
|---|---|---|---|
| **腾讯轻量服务器** | ~50元/月 | 完整控制、稳定、可公网访问 | 需要运维 |
| **阿里云函数计算** | 按调用计费 | 免运维、自动扩缩 | 冷启动延迟 |
| **Vercel + Supabase** | 免费额度 | 部署简单、全球CDN | 需改造架构 |
| **保持现状** | 免费 | 稳定、数据本地、隐私好 | 依赖本机开机 |

#### 当前方案优势

现有方案（本地 Docker + Tailscale）已经很优秀：
- ✅ 零成本
- ✅ 数据完全本地，隐私安全
- ✅ 手机可通过 Tailscale 访问
- ✅ 无需额外运维

**建议：** 除非有明确的公网访问、多人协作或 24/7 不间断服务需求，否则无需迁移。

### 8.22 版本固化与备份

> 日期：2026-09-06

在进行大调整前，已创建双重备份机制：

**1. 版本标签 `v0.1.0`**
- 不可变的版本标记，指向 commit `b194572`
- 随时可回到这个精确的 commit
- 命令：`git show v0.1.0`

**2. 备份分支 `backup/v0.1.0-stable`**
- 完整的分支备份
- 可切换到这个分支继续开发或对比
- 命令：`git checkout backup/v0.1.0-stable`

**当前 Git 状态：**
```
main                    ← 当前开发分支
v0.1.0                  ← 稳定版本标签
backup/v0.1.0-stable    ← 备份分支
```

**恢复方法：**
```bash
# 方法1：查看标签内容
git show v0.1.0

# 方法2：切换到备份分支
git checkout backup/v0.1.0-stable

# 方法3：从备份创建新分支
git checkout -b new-feature backup/v0.1.0-stable

# 方法4：回到标签（detached HEAD）
git checkout v0.1.0
```

**备份内容：**
- ✅ 完整功能实现（上传/分析/保存/复习）
- ✅ 掌握度评估算法（综合方案）
- ✅ 任务列表增强功能
- ✅ PWA 支持
- ✅ 统计仪表盘
- ✅ 所有 Bug 修复
- ✅ 完整设计文档（discuss.md）

### 8.23 IMA 知识库集成

> 日期：2026-09-07

将腾讯 IMA 作为主数据库，Obsidian 作为下游本地副本（Phase 2 架构）。

#### 架构设计

```
┌──────────────┐
│   Frontend   │
└──────┬───────┘
       │ HTTP API（接口不变）
       ▼
┌──────────────────┐
│ Storage Manager  │  主备策略
└──┬────────────┬──┘
   │ 主          │ 降级
   ▼            ▼
┌─────────┐  ┌──────────┐
│ IMA     │  │ File     │
│ 知识库   │  │ Obsidian │
└────┬────┘  └──────────┘
     │ 定时同步（12h）+ 手动触发
     └──────────────►
```

#### 新增文件

| 文件 | 职责 |
|---|---|
| `services/ima_client.py` | IMA OpenAPI 客户端，通过 ima-skills 的 `ima_api.cjs` 调用 |
| `services/ima_storage.py` | IMA 存储后端，实现 StorageBackend 协议 |
| `services/file_storage.py` | 本地文件存储后端（降级方案） |
| `services/storage_backend.py` | 存储接口协议定义 |
| `services/storage_manager.py` | 主备存储管理器，自动故障转移 |
| `services/sync_service.py` | IMA → Obsidian 单向同步 |
| `services/scheduler.py` | APScheduler 定时任务（每 12 小时） |
| `api/routes/sync.py` | 同步 API（手动触发 + 状态查询） |

#### IMA API 接入方式

**关键：不直接调 REST API，而是通过官方 skill 的 Node 脚本调用。**

```python
# 通过 subprocess 调用 ima_api.cjs
proc = await asyncio.create_subprocess_exec(
    "node", "~/.claude/skills/@tencent-adm/ima-skills/ima_api.cjs",
    endpoint,                              # 如 openapi/note/v1/import_doc
    json.dumps(payload),
    json.dumps({"clientId": ..., "apiKey": ...}),
)
```

**凭证位置：** `~/.config/ima/client_id` 和 `~/.config/ima/api_key`

#### 核心 API 端点

| 操作 | 端点 | 关键参数 |
|---|---|---|
| 创建笔记 | `openapi/note/v1/import_doc` | `content_format=1`（必须，Markdown） |
| 列出笔记 | `openapi/note/v1/list_note_by_folder_id` | `limit ≤ 20` |
| 读取笔记 | `openapi/note/v1/get_doc_content` | `target_content_format` |
| 搜索笔记 | `openapi/note/v1/search_note` | `search_type=0` + `query_info.title` |
| 列出知识库 | `openapi/wiki/v1/search_knowledge_base` | `query=""` 列出全部，`limit ≤ 20` |
| 浏览知识库 | `openapi/wiki/v1/get_knowledge_list` | 可传 `folder_id` 进子文件夹 |
| 添加到知识库 | `openapi/wiki/v1/add_knowledge` | `media_type=11` + `title`（必填）+ `note_info.content_id` |

#### 踩坑记录

| 问题 | 现象 | 根因 | 修复 |
|---|---|---|---|
| API 全部 404 | 所有端点返回 404 | 端点路径猜错（试过 `/api/v1/notes` 等 5 种） | 正确路径是 `openapi/note/v1/*` |
| 认证失败 | `clientID or apiKey is empty` | 直接用 httpx 调 REST API，header 格式不对 | 改用 skill 的 `ima_api.cjs` 脚本 |
| 凭证不匹配 | `skill auth failed` | `~/.config/ima/` 里存的是旧 key | 更新为当前有效凭证 |
| 创建笔记失败 | `ImportDoc just support markdown` | 缺少 `content_format` | 加上 `content_format: 1` |
| limit 超限 | `value must be inside range (0, 20]` | 传了 `limit=100` / `limit=50` | 统一 `min(limit, 20)` |
| frontmatter 解析失败 | 读回来的字段全是 None | IMA 把 `---` 转成了 `***` + `-----`，并转义了 `_` → `\_` | `_parse_note_content()` 支持 3 种格式，还原转义字符 |
| **笔记没进知识库** | 保存成功但知识库为空 | **`docker-compose.yml` 的 `environment` 段没传 IMA 变量**，容器内 `IMA_ENABLED=False`、知识库 ID 为空 | 补齐 5 个环境变量 |
| add_knowledge 失败 | 静默失败 | 缺少必填的 `title` | 补上 `title` 参数 |

#### 自动归类实现

新增 `find_folder_by_path()`，按「孩子/学科」路径逐层查找文件夹（`media_type=99`）：

```python
folder_id = await client.find_folder_by_path(kb_id, ["女儿", "数学"])
await client.add_note_to_knowledge_base(
    note_id=note_id, knowledge_base_id=kb_id,
    title=title, folder_id=folder_id,
)
```

#### Docker 配置变更

```yaml
volumes:
  - ~/.config/ima:/root/.config/ima:ro                    # IMA 凭证
  - ~/.claude/skills/@tencent-adm/ima-skills:/root/.claude/skills/@tencent-adm/ima-skills:ro
environment:
  - IMA_ENABLED=${IMA_ENABLED:-false}
  - IMA_API_KEY=${IMA_API_KEY:-}
  - IMA_CLIENT_ID=${IMA_CLIENT_ID:-}
  - IMA_KNOWLEDGE_BASE_ID=${IMA_KNOWLEDGE_BASE_ID:-}
  - IMA_SYNC_INTERVAL_HOURS=${IMA_SYNC_INTERVAL_HOURS:-12}
```

Dockerfile 新增 Node.js 20（运行 `ima_api.cjs`）。

#### 验证结果

```
✅ 保存到「女儿/数学」→ [daughter][数学] 因式分解 - e2e-001
✅ 保存到「儿子/语文」→ [son][语文] 成语运用 - e2e-002
✅ 自动查找文件夹并归类
✅ 主备切换（IMA 不可用时降级到本地文件）
```

#### 已知限制

- IMA API **不支持创建知识库和文件夹**，需在客户端手动创建
- IMA API **不支持删除笔记**，测试笔记需手动清理
- IMA API **不支持图片上传**（`upload_image` 返回 None），图片仍存本地
- 分页只取第一页（20 条），大量数据需要完善 cursor 分页

### 8.24 IMA 集成的落地修复与优化

> 日期：2026-09-07 ~ 09-08

8.23 节建好了存储抽象层，但实际测试暴露出三个问题，本节记录修复过程。

#### 问题 1：API 路由没接存储管理器

**现象：** 前端保存成功（HTTP 200），但 IMA 知识库里什么都没有。

**根因：** 存储抽象层（`StorageManager`）建好了，但 `api/routes/questions.py` 里的所有操作仍在直接调 `file_ops.*`，`StorageManager` 完全没被使用。

```python
# 修复前
file_path = file_ops.save_question(question_id, q.child, q.subject, frontmatter, body)

# 修复后
storage = get_storage_manager()
storage_id = await storage.save_question(
    question_id=question_id, child=q.child, subject=q.subject,
    frontmatter=frontmatter, body=body,
)
```

**教训：** 建了抽象层要记得把调用方切过去，否则等于没建。

#### 问题 2：主备策略应该是双写，不是降级

**原设计：** 主存储失败才降级到备用（try-except-fallback）。

**问题：** IMA 成功时本地不写，但读取链路（`list_questions` 等）还在读本地文件 → 保存成功但列表看不到。

**改为双写：**

```python
async def save_question(self, *args, **kwargs) -> str:
    primary_id, fallback_id, primary_err = None, None, None

    try:
        primary_id = await self.primary.save_question(*args, **kwargs)
    except Exception as e:
        primary_err = e

    if self.fallback:
        try:
            fallback_id = await self.fallback.save_question(*args, **kwargs)
        except Exception as e:
            logger.error(f"备用存储写入失败: {e}")

    if primary_id is None and fallback_id is None:
        raise primary_err or Exception("所有存储后端写入失败")

    # 返回本地路径供现有读取链路使用
    return fallback_id or primary_id
```

**好处：**
- IMA 挂了不丢数据（本地兜住）
- 读取链路不用改（本地始终有文件）
- Obsidian 里立即可见，不用等定时同步

#### 问题 3：只读挂载导致 IMA 写入失败

**现象：**
```
EROFS: read-only file system, open '/root/.config/ima/last_update_check'
```

**根因：** 凭证目录挂成 `:ro`（出于安全考虑），但 `ima_api.cjs` 每天首次调用要写 `last_update_check` 时间戳做版本检查，写不进去就直接报错退出。

**修复：** 用 `lastCheckFile` 选项把时间戳重定向到容器可写目录，凭证目录保持只读。

```python
opts = json.dumps({
    "clientId": client_id,
    "apiKey": api_key,
    "lastCheckFile": "/tmp/ima_last_update_check",  # 重定向
})
```

同时在 `docker-compose.yml` 加了环境变量 `IMA_LAST_CHECK_FILE=/tmp/ima_last_update_check` 作为双保险。

**这个 bug 是双写策略救回来的** — IMA 写失败，本地写成功，数据没丢，只是没进云端。

#### 优化 1：日志输出

之前 `logger.info/error` 全部不输出（没配 handler），排查全靠猜。加上：

```python
# main.py
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

现在保存时能看到完整链路：
```
IMA 笔记创建成功: 7502879434766300
笔记已添加到知识库, media_id=note_8d8b...
错题已保存到 IMA 知识库 [儿子/数学]
错题已保存到文件: /vault/son/数学/2026-09-08-404b4e7f.md
双写成功: IMA=7502879434766300, File=/vault/...
```

#### 优化 2：笔记标题可读性

**问题：** IMA 里笔记标题显示为 `id: 9f4e249e`，完全看不出是什么题。

**根因：** IMA **忽略 API 传的 `title` 参数**，自己从 Markdown 内容里提取标题 — 而内容开头是 frontmatter，第一行就是 `id: xxx`。

**修复：** 把标题作为 H1 放在内容最前面：

```python
def _build_note_content(self, frontmatter, body, title=None):
    """
    结构：
        # 【女儿·英语】现在完成时（概念不清） 2026-09-08   ← IMA 从这里提取
        ---
        frontmatter (YAML)
        ---
        正文
    """
    fm_yaml = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    parts = []
    if title:
        parts.append(f"# {title}\n")
    parts.append(f"---\n{fm_yaml}---\n")
    parts.append(body)
    return "\n".join(parts)
```

解析时把 H1 剥掉，避免污染 body：

```python
content = re.sub(r"^#\s+.+?\n+", "", content, count=1)
```

**标题格式：** `【女儿·英语】现在完成时（概念不清） 2026-09-08`

抽成 `_build_title()` 方法，创建和更新共用。用中文名 + 全角括号在 IMA 列表里更易读，日期放最后便于排序。

**效果对比：**

| 修复前 | 修复后 |
|---|---|
| `id: 9f4e249e` | `【儿子·数学】分数除法（概念不清） 2026-09-05` |
| `id: 8c7fc31d` | `【女儿·英语】现在完成时（概念不清） 2026-09-08` |

#### 新增：反向同步脚本

**用途：** 补齐 IMA 中缺失的错题（如 IMA 写入失败时只存了本地的那些）。

**文件：** `backend/scripts/sync_local_to_ima.py`

```bash
# 预演（推荐先跑）
docker exec mistakes-backend python3 scripts/sync_local_to_ima.py --dry-run

# 实际执行
docker exec mistakes-backend python3 scripts/sync_local_to_ima.py
```

**设计要点：**

| 特性 | 实现 |
|---|---|
| 幂等 | 对比 frontmatter 里的业务 `id`，已存在则跳过 |
| 预演模式 | `--dry-run` 只列出会同步什么，不实际写入 |
| 多格式兼容 | 支持 3 种历史标题格式的 ID 提取（`id: xxx`、`... - xxx`、新格式读 frontmatter） |
| 逐条容错 | 单条失败不中断，最后汇总成功/失败数 |

**首次运行结果：** 检测到 5 条缺失（都在儿子/数学），全部同步成功。再次运行显示「无需同步」，幂等性验证通过。

#### 验证结果

```
✅ 双写成功（IMA + 本地）
✅ 自动归类到 知识库 > 孩子 > 学科
✅ 标题可读（【女儿·英语】现在完成时（概念不清） 2026-09-08）
✅ frontmatter 解析完整（H1 被正确剥离）
✅ 反向同步幂等
✅ IMA 失败时本地兜底
```

#### 补充的已知限制

- **分页只取第一页**（20 条）：`list_notes` 和同步逻辑都没实现 cursor 分页，错题超过 20 条后同步会漏。需要完善。
- IMA API 不支持删除笔记，测试笔记需在客户端手动清理

### 8.25 分页机制与元数据格式重构

> 日期：2026-09-08

8.24 节留了个已知限制 —— 分页只取第一页（20 条）。本节彻底解决，过程中还发现了更严重的元数据格式问题。

#### 问题 1：分页缺失

**影响：** IMA 里错题超过 20 条后，列表和同步都会漏掉后面的。

**探测过程：** IMA 文档没写分页机制，写脚本实测三种可能：

| 方式 | 结果 |
|---|---|
| 响应的 `next_cursor` 字段 | ❌ API 不返回这个字段 |
| 用最后一条的 `docid` 作 cursor | ❌ 立即返回 `is_end=True` |
| **数字偏移量字符串**（`"20"`、`"40"`） | ✅ **可用，无重复** |

响应只有 `is_end` 布尔标记，需要自己累加偏移。

**实现：** 加通用分页方法 `_paginate()`：

```python
PAGE_SIZE = 20      # IMA 单页上限
MAX_PAGES = 100     # 安全上限，防 API 异常导致无限循环

async def _paginate(self, endpoint, base_payload, list_field, max_items=None):
    all_items = []
    offset = 0
    for page in range(self.MAX_PAGES):
        payload = {**base_payload, "cursor": "" if offset == 0 else str(offset),
                   "limit": self.PAGE_SIZE}
        data = await self._call_api(endpoint, payload)
        items = data.get(list_field, []) or []
        all_items.extend(items)

        if data.get("is_end") or not items:
            break
        if max_items and len(all_items) >= max_items:
            return all_items[:max_items]
        offset += len(items)
    else:
        logger.warning(f"{endpoint} 达到安全上限，可能未取完")
    return all_items
```

**应用到三处：**
- `list_notes()` — 默认取全部，`limit ≤ 20` 时走单页快路径省一次请求
- `find_folder_by_path()` — 原来硬编码 `limit: 50`（超 API 上限），改分页
- 新增 `list_knowledge_items()` — 知识库内容列表

**验证：** IMA 里有 22 条笔记（> 20 单页上限），`list_notes()` 返回 22 条且无重复。

#### 问题 2：ima_storage 里的假分页

原代码有个更隐蔽的 bug：

```python
for page in range(max_pages):
    notes_page = await self.client.list_notes(limit=20, offset=0, folder_id=None)
    #                                                   ^^^^^^^^ 每次都请求第一页
    all_notes.extend(notes_page)
    if len(notes_page) < 20:
        break
    break  # ← 无条件 break，循环体只执行一次
```

写了个看起来像分页的循环，但 `offset` 从不递增，最后还无条件 `break`。改为直接调 `list_notes()`（内部已自动分页）。

#### 问题 3：sync_to_obsidian 传空 child

```python
ima_questions = await self.list_questions("", None)  # child=""
```

而 `list_questions` 的过滤逻辑是 `if frontmatter.get("child") != child: continue` —— 传空字符串会过滤掉所有笔记，导致同步结果永远是全 0。

这解释了 8.23 节定时同步日志里的 `{created: 0, updated: 0}` —— 不是"本地已同步"，是根本没同步。

**重写 `sync_to_obsidian`：** 直接遍历笔记，不复用带过滤的 `list_questions`。同时加了本地查询缓存（`{(child, subject): {id: path}}`），避免每条错题都扫一遍目录。

#### 问题 4（意外发现）：YAML 元数据被 IMA 破坏

修好分页后同步跑起来了，但出现 6 个错误：

```
同步笔记 7502880760147615 失败: while scanning a quoted scalar
同步笔记 7502880751779764 失败: while parsing a block mapping
```

**根因：** IMA 会重写 Markdown 内容，对 YAML frontmatter 是致命的：

| IMA 的改写 | 后果 |
|---|---|
| `_` → `\_` | 字段名变成 `error\_type` |
| 列表 `- item` → `* item` | YAML 数组语法失效 |
| 字段间插入空行 | 结构变松散 |
| **多行字符串被拆成多个段落** | 引号内字符串断裂 → 解析必然失败 |

前两个能用字符串替换还原，但多行字符串（比如 `error_suggestion` 里的多行学习建议）被拆断后无法可靠恢复。

**方案对比：**

| 方案 | 评估 |
|---|---|
| 继续修 YAML 解析 | ❌ 多行字符串信息已丢失，修不回来 |
| 元数据放笔记标题 | ❌ 长度受限，字段多了放不下 |
| **JSON 代码块** | ✅ 代码块内容 IMA 不会改写 |

**改为 JSON 代码块：**

```python
def _build_note_content(self, frontmatter, body, title=None):
    """
    结构：
        # 【女儿·数学】一元二次方程（计算错误） 2026-09-08
        ```json
        {"id": "...", "child": "...", "knowledge_points": [...]}
        ```
        正文
    """
    meta_json = json.dumps(frontmatter, ensure_ascii=False, indent=2, default=str)
    parts = []
    if title:
        parts.append(f"# {title}\n")
    parts.append(f"```json\n{meta_json}\n```\n")
    parts.append(body)
    return "\n".join(parts)
```

**解析器改为三级兼容：**

1. ```json 代码块（当前格式）
2. 标准 YAML frontmatter（本地文件格式）
3. IMA 改写后的 YAML（历史数据）

第三级用了个更健壮的行级解析器 `_parse_ima_mangled_yaml()` —— 逐行提取 `key: value`，单个字段坏了不影响其他字段，比整体 `yaml.safe_load` 容错性强得多。同时做类型推断（`"0"` → `0`、`"false"` → `False`）。

**两边格式各自最优：**

| 存储 | 格式 | 原因 |
|---|---|---|
| IMA | JSON 代码块 | 抗 IMA 改写 |
| 本地 Obsidian | YAML frontmatter | Obsidian/Dataview 原生支持 |

#### 验证结果

**解析器单元测试（三种格式）：**
```
[JSON 格式] id=abc123, points=['因式分解', '配方法']  ✅
[IMA YAML]  redo_count=0 (int), repeat_pattern=False (bool), points=[...]  ✅
[标准 YAML] id=xyz789, subject=英语  ✅
```

**分页：** 22 条笔记（> 20 上限）全部取到，无重复

**同步：** `errors: 6 → 0`

```
修复前: {created: 8, updated: 3, skipped: 5, errors: 6}
修复后: {created: 0, updated: 18, skipped: 5, errors: 0}
```

`skipped: 5` 是 IMA 里的非错题笔记（4 条测试笔记 + 1 条使用指南），无元数据，跳过是正确行为。

**端到端：** 保存含数组字段（`knowledge_points`、`tags`）的错题，回读后元数据完整无损。

#### 已解决的限制

~~分页只取第一页（20 条）~~ → 已实现完整分页

#### 仍存在的限制

- IMA API 不支持创建知识库/文件夹（需客户端手动建）
- IMA API 不支持删除笔记（测试笔记需手动清理）
- IMA API 不支持图片上传（图片仍存本地）
- `list_questions` 需逐条读笔记才能过滤，请求数与笔记总数成正比，笔记多时慢

### 8.26 复习提交与上传图片保存回归验证（2026-09-16）

复习页面此前只把 `result` 放在 URL 查询参数中，后端的 `RedoRequest` 从 JSON body 读取，因此会返回 422。现改为发送 `{ "result": "correct" }` 或 `{ "result": "wrong" }` JSON body。

上传完成后，任务现在保留上传接口返回的图片 ID、临时路径及文件名；保存错题时将其传回后端。后端从上传临时目录读取图片并传给存储层，Obsidian 图片链接使用从孩子/学科笔记目录到 vault `_assets` 的相对路径 `../../_assets/...`，保存成功后清理临时图片。非法或失效的图片路径返回 400，避免静默保存没有图片的错题，也避免读取上传目录以外的文件。

验证：前端 `npm run build` 通过；Python 编译检查通过；容器内接口回归测试覆盖上传、无效路径拒绝、笔记与图片保存、临时图片清理，以及“做对/又错”两次复习提交，均通过。测试使用临时 vault 与本地存储替身，未向 IMA 写入测试题。当前容器已启动，`/api/health` 返回 `ok`。IMA 端不支持图片上传，图片仍存本地 vault。

### 8.27 多账号、邀请码注册与账号级数据隔离设计（2026-09-27）

本期确定增加管理员和普通账号。系统首次启动时创建唯一的初始管理员；普通用户使用管理员在网页后台生成的一次性邀请码，以用户名、显示名称和密码注册。管理员可以查看邀请码状态、作废未使用邀请码，并为用户重置密码。重置后旧会话失效，用户必须先修改临时密码。

账号系统采用 SQLite 与服务端 Cookie 会话。数据库持久化在 `config/app.db`；密码使用 scrypt 加盐哈希，邀请码和会话令牌只保存哈希。LLM 配置全局共享，仅管理员可查看和修改，普通账号只能调用分析功能。

每个账号可以创建多个孩子，并从语文、数学、英语、物理、化学、生物、政治、历史、地理九门课程中选择。孩子和课程第一期只支持新增、改名和调整，不提供删除或归档。错题不删除，根据掌握程度逐步延长复习间隔。

数据采用逻辑隔离：IMA 继续共用一个知识库，但所有错题写入并强制过滤 `account_id`、`child_id`、`child_name`；Obsidian 使用 `accounts/{account_id}/{child_id}/{subject}` 目录，图片使用 `_assets/accounts/...`。后端从登录会话取得账号，不信任前端提交的账号标识，跨账号资源统一返回 404。

现有女儿和儿子及其 Markdown、图片、IMA 元数据全部迁入首次创建的管理员账号。迁移前完整备份，迁移脚本支持 dry-run、异常清单和幂等重跑。完整设计见 `docs/plans/2026-09-27-multi-account-design.md`，实施步骤见 `docs/plans/2026-09-27-multi-account-implementation.md`。

### 8.28 EdgeOne Makers 部署适配评估（2026-09-27）

当前项目不能原样部署到 EdgeOne Makers，但可以经过架构适配后部署。React/Vite 静态前端可以直接部署；EdgeOne Cloud Functions 官方支持 Python 3.10、ASGI 和 FastAPI，因此 API 路由与主要业务逻辑可以迁移。HttpOnly Cookie、账号鉴权和管理员权限模型也符合平台能力。

不兼容项包括：Docker Compose 常驻容器、持久化 SQLite 文件、本地 Obsidian vault、上传图片临时文件、进程内异步任务列表，以及依赖容器内 Node 和全局 `ima-skills` 的 IMA 调用。Cloud Functions 单次请求体上限 6 MB，默认最长 30 秒、可配置到 120 秒，也会限制当前多图上传和长时间 LLM 分析。

如果选择全量 EdgeOne 部署，建议改为：Pages 承载前端；Python Cloud Functions 承载 FastAPI；Neon/PostgreSQL 或腾讯云数据库承载账号和业务元数据；COS 或 EdgeOne Blob 承载图片；任务状态放数据库并使用可恢复的异步执行方式；IMA 改为直接 HTTP OpenAPI 调用。Obsidian 回流改为宿主机定时拉取，而不是云函数直接写本地 vault。

如果保留现有 Docker 后端，EdgeOne 只部署静态前端并反向访问宿主机 API，则改动较小，但宿主机仍需持续在线，且必须处理 HTTPS、跨域和公网入口。综合稳定性与改造成本，近期继续 Docker/Tailscale 最稳；决定正式公网化后，再按全量 EdgeOne 方案改造持久层。

### 8.29 多账号功能实施记录（2026-09-27）

本次已按 8.27 的设计完成多账号主体改造：

- 增加 SQLite 账号、会话、邀请码、孩子和课程数据表，数据库固定持久化在 `config/app.db`。
- 增加首次管理员初始化、登录、退出、一次性邀请注册、修改密码、管理员重置密码和会话撤销。密码使用 scrypt 加盐哈希，会话使用 HttpOnly Cookie。
- 增加管理员网页，可生成/查看/作废邀请码、查看账号、为账号重置临时密码。邀请码和临时密码只在生成时显示明文。
- 孩子改为账号内动态创建，每个孩子可选语、数、英、物、化、生、政、史、地。孩子支持改名、更换 emoji 和调整课程，本期不删除孩子。
- 错题、图片、上传临时文件、分析任务、复习和统计均由服务端按当前账号强制校验；跨账号请求返回 404。Obsidian 目录改为 `accounts/{account_id}/{child_id}/{subject}`。
- IMA 笔记补充 `account_id`/`child_id`/`child_name`，列表、读取和同步强制按账号范围处理；手动同步仅管理员可执行。
- 全局 LLM 配置仅管理员可读取、修改和测试，普通账号直接请求返回 403。
- 错题不再提供删除入口，保留历史记录，由掌握度和重做结果调整复习频率。

历史数据迁移脚本为 `backend/scripts/migrate_to_accounts.py`。它默认 dry-run，正式执行前备份 SQLite、旧 `daughter/son` 目录和图片，然后迁移 Markdown 并补写 IMA 元数据，支持幂等重跑。真实数据要在新版首次管理员初始化后，先核对 dry-run 计数再正式执行。

验证结果：后端 25 项测试全部通过，包括账号隔离、邀请码、密码重置、图片访问、复习提交、IMA 范围和历史迁移；前端 TypeScript 与 Vite/PWA 生产构建通过。

### 8.30 全量测试与文档回填（2026-09-27）

对 8.29 交付的多账号版本做了一次全量验证，并修复验证中发现的问题。

#### 测试结果

| 测试 | 结果 |
|---|---|
| 后端 pytest | 25 项全通过（与 8.29 声称一致）；本轮新增上传校验 11 项，现共 36 项 |
| 接口冒烟（真实 HTTP） | 82 项全通过：初始化、邀请码、权限边界、保存、复习、统计、跨账号隔离 |
| 前端构建 | TypeScript + Vite + PWA 产物齐全 |
| 浏览器 UI 实测 | Playwright + headless Chrome，16 项全通过 |

掌握度算法逐格复核 8.20 的对照表（68 → 76 → 84 → 45 → 56，做错后连续计数归零）完全吻合。跨账号隔离在所有入口都返回 404，路径穿越文件名、未关联学科、非本账号图片均被拒绝。

#### 本轮修复

**1. Git 凭证外泄**

`.git/config` 的 remote URL 内嵌了 GitHub Personal Access Token 明文，且项目目录处于 OneDrive 同步范围内。已改为标准 URL，认证交回 macOS Keychain：

```bash
git remote set-url origin https://github.com/zhuyizj-glitch/errorRecord.git
```

**Token 本身必须在 GitHub 上重新生成**——本地清理不能撤销已经发生的暴露。

**2. 密码长度规则不一致**

前端初始化、邀请码注册、修改密码三处都是 `minLength={8}` 且提示「至少 8 位」，后端 `auth_service._validate_password` 却要求 10 位。用户按页面提示填写 8 位密码会被后端拒绝。三处已统一为 10 位。

**3. 上传校验缺失**

第 6.2 节规定的校验规则此前**任何一层都没有实现**：后端直接落盘，前端只有一行提示文字，`accept="image/*"` 也不是白名单。现已落地：

| 校验项 | 规则 | 行为 |
|---|---|---|
| 文件数量 | 单次 ≤ 10 张 | 拒绝 |
| 文件格式 | 扩展名白名单 jpg / jpeg / png / heic / heif / webp **且**文件头嗅探通过 | 拒绝 |
| 文件大小 | 单张 ≤ 20MB | 拒绝 |
| 分辨率 | 最短边 < 200px | 提示但不拦截 |
| 空文件 | — | 拒绝 |

格式校验同时做扩展名与文件头嗅探，避免改名后的任意文件绕过。HEIC 通过 ISO-BMFF 的 `ftyp` brand 识别；分辨率检测对 Pillow 无法解码的 HEIC 静默跳过，不做误判。

上传响应新增 `warnings` 字段，前端以黄色提示条展示（区别于红色错误条）。同时修复了上传接口的错误处理——此前前端不做 `response.ok` 判断，后端返回的 400 具体原因会被吞掉，只显示笼统的「上传失败」。

图片列表的扩展名白名单改为复用上传模块的常量，避免两处不同步（此前 `.heif` 能上传却不出现在图片列表里）。

**4. 配置示例补齐**

`.env.example` 补上 `BACKEND_PORT` / `FRONTEND_PORT` / `COOKIE_SECURE`。`docker-compose.yml` 的端口映射改为 `${BACKEND_PORT:-8001}`，让 `.env` 里的端口配置真正生效（此前硬编码 8001）。

#### 发现但本轮未处理

**重复犯错检测从未接线**（详见 3.8）。`analyzer.detect_repeat_streak()` 已实现但没有任何调用方；`repeat_streak` / `max_repeat_streak` / `repeat_pattern` 只在新建时写入 0 / 0 / false。后果是统计接口的 `repeat_error_count` 恒为 0，详情页「⚠️ 重复犯错模式」的展示分支永远不会触发。接通需要按知识点跨题目重算并回写同组错题，属于待实现功能。

**主 JS bundle 偏大**：`index-*.js` 约 1.03MB（gzip 309KB），Vite 已警告超过 500KB。主要是 recharts 与 katex，建议做动态导入拆分以改善手机首屏。

**`.claude/settings.local.json` 含 LLM API Key 明文**：该文件已在 `.gitignore` 中不会被提交，但仍随 OneDrive 同步。建议轮换密钥，并把密钥类文件移出同步目录。

#### 文档回填

第 3 节已按实际实现重写（存储分层、目录结构、frontmatter 字段、掌握度算法、等级状态映射、间隔复习规则、重复犯错现状、已废弃设计）。目录补上 8.23–8.30。

第 4 节流程与第 7 节 API 表仍保留设计初期的描述，尚未逐条回填；已知过时项包括：7.2 的 API 表缺少 auth / admin / children / tasks 等接口、`DELETE /api/questions/{id}` 实际返回 405、4.4 的「无密码切换孩子」已被账号体系取代。

#### 涉及文件

```
backend/app/api/routes/upload.py          上传校验规则与文件头嗅探
backend/app/api/routes/questions.py       图片白名单复用上传模块常量
backend/tests/test_upload_validation.py   新增，11 项校验测试
backend/tests/test_question_flow.py       改用真实 PNG 字节
backend/tests/test_question_account_isolation.py  同上
frontend/src/components/ImageUploader.tsx         前端校验与提示
frontend/src/pages/UploadPage.tsx                 错误处理与告警提示条
frontend/src/pages/InitializePage.tsx             密码长度
frontend/src/pages/RegisterPage.tsx               密码长度
frontend/src/pages/ChangePasswordPage.tsx         密码长度
.env.example / docker-compose.yml                 配置项补齐
discuss.md                                        第 3 节重写、目录与本节
```

### 8.31 IMA 主存储的可行性核查与数据安全修复（2026-09-27）

起因是复核 IMA 在系统中的实际地位，发现设计意图（错题优先写入 IMA）与实现存在多处偏差，其中一处会导致数据丢失。

#### 发现 1：定时同步会用旧快照覆盖本地（已修复）

**问题**：重做只更新本地 markdown，IMA 笔记保持创建时的内容。而每 12 小时的定时同步方向是 IMA → 本地，`sync_to_obsidian` 拿到 IMA 的旧 frontmatter 后直接整体覆写本地文件——没有合并，也没有版本比较。孩子复习三次把掌握度做到 84 分，下一次同步就会回退到 0 分，`redo_history`、`consecutive_correct` 一并丢失。

**潜伏期**：该问题此前不会触发，因为 `children` 表为空导致 `allowed_scopes` 为空集，所有笔记都被判为「归属未知」而跳过。一旦迁移完孩子数据即会生效。

**修复**：
1. frontmatter 引入 `updated_at`（UTC ISO8601），保存/重做/移动都会刷新
2. `sync_to_obsidian` 覆写前比对版本，只有 IMA 不旧于本地时才写；否则跳过并计入 `conflicts`
3. IMA 侧没有版本标记时不覆盖本地（保守策略，避免用无版本信息的数据冲掉有版本的记录）

#### 发现 2：`IMAClient` 从来没有 `update_note` 方法

`IMAStorageBackend.update_question` 调用 `self.client.update_note(...)`，但该方法**在 `IMAClient` 中从未实现过**——从 v0.2.0 写下那天起就是坏的。异常被 `except` 捕获后仅记录日志并返回 `False`，所以没有任何测试能发现，因为测试替身自己实现了 `update_note`，比真客户端更"能干"。

同时 `migrate_to_accounts.py --migrate-ima` 依赖同一条路径，每处理一条笔记就抛 `RuntimeError("IMA 更新失败")`。

#### 发现 3（根本原因）：IMA OpenAPI 不支持修改笔记

核对官方接口表后确认，IMA OpenAPI 只有六个接口：

| 接口 | 用途 |
|---|---|
| `import_doc` | 新建笔记（Markdown） |
| `get_doc_content` | 读取笔记内容 |
| `append_doc` | **追加**内容到笔记末尾 |
| `list_note_by_folder_id` | 按笔记本列笔记 |
| `search_note_book` | 搜索笔记 |
| `list_note_folder_by_cursor` | 列出笔记本 |

**没有修改接口，也没有删除接口。** `append_doc` 只能追加、不能替换，用它"更新"会在笔记里留下第二份元数据块，反而破坏解析。

这解释了三件事：为什么 `update_note` 从未实现、为什么 `DOCS/IMA_MIGRATION_STATUS.md` 的测试清单里「更新错题 → IMA 中更新」和「删除错题」两项从未打勾、为什么 `test_ima_api.py` 里写着「IMA API 可能没有删除笔记的端点」。

**结论：IMA 笔记是「一次写入、只读、可追加」的。** 题目本身（原题、正确答案、解题过程、错因分析）是不可变信息，写入后可靠；掌握度、重做记录这类可变状态**无法回写到已有的 IMA 笔记**。

因此「IMA 真·主库」在当前 API 能力下无法完整实现。当前实际架构是：

```
不可变题目信息：IMA（权威）+ 本地副本
可变学习状态：  本地（权威，随重做更新）
同步方向：      IMA → 本地，且受版本保护，不会回退本地
```

#### 本轮代码改动

| 文件 | 改动 |
|---|---|
| `app/services/storage_manager.py` | 新增 `utc_now_iso()`；`update_question` 改为双写（IMA + 本地）；保存时把 IMA 笔记 ID 注入本地副本 |
| `app/services/ima_storage.py` | 新增 `_ima_is_newer()` 版本比较；同步加冲突保护并回写 `ima_note_id`；`update_question`/`delete_question` 显式识别「客户端无此能力」并给出可操作的日志 |
| `app/api/routes/questions.py` | 重做与移动改走 `StorageManager.update_question`，并透传正文避免两端各自回读 |
| `app/services/file_ops.py` | 新增 `find_question_file()`，按 question_id 定位本地文件 |
| `scripts/migrate_to_accounts.py` | `migrate_ima_notes` 改为 `audit_ima_notes`：只统计受影响的旧笔记、不写入，并说明无法补齐的原因 |

`ima_note_id` 记录在**本地副本**中（IMA 笔记自身不需要这个字段），由保存流程和同步流程共同写入，供后续更新定位云端笔记。历史错题缺少该字段时，重做会记录警告并跳过云端更新，本地照常——这是有意的优雅降级。

#### 验证

```
后端 pytest: 49 项全部通过（原 36 + 新增 IMA 双写与冲突保护 13 项）
接口冒烟:    82 项全部通过
```

新增测试覆盖：保存注入版本标记与笔记 ID、重做双写、缺少 `ima_note_id` 降级、内部字段不写入存储、IMA 更新时覆盖本地、**本地更新时拒绝被覆盖**、IMA 无版本时不覆盖本地、本地丢失时从 IMA 恢复、真客户端无 `update_note` 时本地仍正常更新、迁移脚本只审计不写入。

#### 待办：如何让 IMA 里面也能看到复习历史

由于 IMA 笔记不可修改，若希望家长在 IMA 客户端里也能看到复习进展，唯一可行路径是**追加式记录**：每次重做向同一篇笔记 `append_doc` 追加一条复习记录（如 `## 复习记录 / 2026-09-27 做对 / 掌握度 68`），解析时把初始元数据块与追加记录合并。

需要注意两个约束：追加不可撤销；单篇笔记有大小上限（错误码 `100009` 单篇笔记超过最大限制），长期追加终会触顶。因此这一方案适合「记录复习轨迹」，不适合把完整状态机搬到 IMA。

#### 另有两处待你核实的疑点

1. `ima_client.get_note()` 传的是 `note_id`，而官方文档的参数名是 `doc_id`（有资料说明两者是别名，未实测）
2. 同一处传的 `target_content_format: 1`，官方表格标注 `1`=Markdown **「不支持」**，推荐 `0`=纯文本、`2`=JSON。但 8.25 记录过 IMA 会重写 Markdown（`_` → `\_`、`-` → `*`），说明实际返回过 Markdown 内容。这两点需要在有凭证的环境实测确认。

### 8.32 OneDrive 作为云存储后端的可行性评估（2026-09-27）

8.31 确认 IMA 不能修改笔记，无法承担可变数据的主库角色。因此评估另一条路径：**用 Microsoft Graph API 直连 OneDrive 云存储**（不是本地 OneDrive 同步目录），把 OneDrive 当作后端的数据源。

#### 结论

技术上可行。Graph API 解决了 IMA 的全部三个致命问题，但引入了新的约束，其中**认证方式完全取决于账号类型**。

#### Graph API 解决了 IMA 的问题

| IMA 的限制 | Graph API |
|---|---|
| 无修改接口，笔记创建即冻结 | ✅ 完整 CRUD：读/写/改/删/列目录/搜索 |
| `upload_image` 未实现，笔记无图 | ✅ 支持二进制上传下载 |
| 读取要走 list + 逐条 get | ⚠️ 同类问题仍在（见下） |
| 无删除 | ✅ 支持 |
| 无版本历史 | ✅ 有 `/versions` 端点 |

#### 约束一：认证方式由账号类型决定（最关键）

**个人账号**（`@outlook.com` / `@hotmail.com`）：**不支持 app-only（client credentials）**。微软在 Q&A 中明确回复，个人账号必须使用委托权限与授权码流程，因为要认证的是账号本身而不是应用。

服务端因此只能保存 **refresh token** 续期，而它有两个脆弱点：
- **90 天不使用即失效**（个人账号不支持配置令牌生存期策略）
- 用户改密码或触发安全事件会使其失效

一旦失效，**应用会完全失去对所有数据的访问**，恢复必须重新走一次浏览器交互授权。对一个"寒暑假可能连续数月不使用"的家庭应用来说，这是真实存在的运维风险，不是理论问题。

**工作/学校账号**（M365）：可以使用 app-only，服务端无需交互登录，也没有令牌过期问题。但有资料报告通过 Graph 以 app-only 访问 OneDrive for Business 会返回 404，需要在真实账号上实测确认。

**世纪互联运营的国内版 M365**：Graph 端点是另一个域名，功能与限制均有差异，需要单独确认。

**确认方法**：用该账号登录 Microsoft Graph Explorer，调用 `GET /me/drive`，看返回的 `driveType` 字段——`personal` 为个人账号，`business` 为工作/学校账号。

#### 约束二：N+1 请求（与 IMA 共有的结构性问题）

当前 `list_questions` 的实现是「扫描目录 + 逐个读取文件解析 frontmatter」。这套逻辑放到 Graph API 上就是 **N+1 次 HTTPS 往返**：200 道错题意味着 200 次请求，列表页需要数秒，并且会撞上节流限制。

这不是 IMA 或 OneDrive 特有的问题，而是「用文件当数据库」的固有限制——按学科、掌握度、错误类型筛选时，现在也是全量读文件后在内存里过滤。

**本方案选择**：全部内容仍以文件形式存储，通过缓存层缓解（本地磁盘保存工作副本，读取走本地，写入双写，按需或定时从云端重建）。

**未采纳的备选**：把可查询的元数据（学科、掌握度、重做记录、知识点、时间）放入已有的 `config/app.db`，OneDrive 只存正文与图片。列表与筛选变成一次 SQL 查询，正文按需拉取。这个方案能根治 N+1，代价是元数据与正文分离，需要处理两者的一致性。留待后续需要时再评估。

#### 约束三：上传分块与节流

- **上传大小**：直接 PUT 上限 **4MB**，超过必须使用 upload session 分块。除最后一块外，块大小须为 **320KiB 的倍数**。会话 URL 在最后一次成功分块后约 15 分钟内有效。
- 错题图片压缩后通常约 200KB，走简单上传即可；但原始图片上限为 20MB（见 6.2），这部分必须分块。
- **节流**：超限返回 **HTTP 429**，须按 `Retry-After` 退避。2026 年 3 月 1 日起，限制改为**按租户累计计算**，此前通过多个应用注册规避的做法不再有效。
- 文件名含中文需正确 URL 编码。

#### 与对象存储的对比

若目标只是「服务端能直接读写云存储、不依赖本地文件夹」，对象存储是更契合的工具：

| 维度 | OneDrive + Graph | 对象存储（R2 / COS） |
|---|---|---|
| 认证 | 个人账号需 refresh token，有失效风险 | 固定密钥，无过期问题 |
| 列表性能 | 目录列举，需 N+1 读取内容 | 列表轻量，可按前缀过滤 |
| 成本 | 随 M365 套餐，通常已有 | R2 免费 10GB 且出口不收费 |
| Obsidian 直读 | ✅ 同步客户端直接读 | ❌ 需 rclone 或定时同步 |
| 版本历史 | ✅ | 部分支持 |

**取舍点**：核心诉求若是「摆脱本地文件夹」，对象存储更合适；核心诉求若是「Obsidian 里能翻 + 云端留一份」，OneDrive 更合适。

#### 与现有代码的关系

本轮的改动正好为这个方案铺好了路，可以直接复用：

| 已有能力 | 在 OneDrive 方案中的角色 |
|---|---|
| `StorageBackend` 协议 | 新增 `OneDriveStorageBackend` 实现该协议即可接入 |
| `StorageManager` 双写 | 写本地 + 写 OneDrive，策略不变 |
| `updated_at` 版本标记 | 冲突判定的依据，同样适用 |
| `sync_to_obsidian` 的冲突保护 | 改造成「从 OneDrive 拉取」，比较逻辑不变 |
| `ima_note_id` 字段 | 换成 `onedrive_item_id`，作用完全相同 |

**关键差异**：Graph API 能修改文件，所以这次的**双写会真正生效**——而 IMA 那次是空转（`update_question` 因无接口而始终返回 False）。

#### 后续实施需要注意的两点

**令牌保活**：目前 `scheduler` 只在 `IMA_ENABLED=true` 时启动（见 `main.py`）。若改用 OneDrive 并关闭 IMA，需要一个独立的心跳任务定期刷新令牌，否则 90 天不活动会导致令牌失效。这一点必须在实现时一并处理。

**缓存一致性**：本地工作副本与云端可能不一致。可复用 8.31 引入的 `updated_at` 比较逻辑来决定覆盖方向。

#### 未决问题

1. OneDrive 账号类型（个人 / 工作学校 / 世纪互联版）——决定认证方案，是能否做干净的前提
2. 缓存重建策略：启动时全量拉取，还是按需拉取 + 增量同步
3. 是否需要把元数据迁入 SQLite（当前选择是暂不迁，用缓存缓解）

### 8.33 追加事件模型设计（待实测确认，2026-09-27）

8.31 确认 IMA 无修改与删除接口，8.32 评估了 OneDrive 方案。综合考虑后决定**继续使用 IMA**，改用追加式写入绕开接口限制——对一个不可变的 API，追加是唯一正确的写入方式。

#### 设计

**状态变化**（重做、掌握度、下次复习日期）用 `append_doc` 追加事件到同一篇笔记：

```
# 【女儿·数学】一元二次方程（计算错误） 2026-09-20
```json
{v1 元数据}          ← 创建时写入，之后不动
```
（原题、正确答案、解题过程、错误分析）

```json
{"type":"redo","rev":2,"at":"...","result":"correct","mastery_score":68}
```
```

读取时把基础块与所有追加事件折叠成当前状态。

**内容修正**（AI 识别错误、答案写错、归属搞错）才新建修订版笔记，并给旧笔记追加墓碑。因为这类改动是"原始内容本身错了"，追加小增量救不回来。

**删除**用墓碑事件：

```json
{"type":"delete","at":"...","reason":"重复录入"}
```

读取时过滤带墓碑的 id。与追加事件共用同一机制，概念统一。

#### 为什么不用「新建」通吃所有更新

一道题重做 10 次就会产生 10 篇笔记。500 道题 × 平均 5 个版本 = 2500 篇，而 `list_questions` 需要逐条读笔记才能拿到元数据，列表页将变成 2500 次 API 调用。同时 IMA 客户端会被重复笔记刷屏，人工浏览失效。

追加方案下**一道题始终一篇笔记**，列表成本不随复习次数增长。

#### 收益

1. **IMA 成为真正的权威存储**——这正是最初的设计意图，8.31 之前它只是装饰
2. **免费版本历史**：整个学习轨迹都留在笔记里，能看出这道题是怎么被攻克的
3. **追加天然并发安全**：两台设备同时写不会互相覆盖，按时间戳排序即可，比"最后写入者获胜"安全
4. **每次只传增量**，不必重传整篇

#### 已知约束

1. **图片进不了 IMA**：官方六个接口中没有图片上传，`upload_image()` 也一直返回 `None`。所以 IMA 能当文字与状态的权威库，**图片只能在本地**——本地 vault 必须保留
2. **单篇笔记有大小上限**（错误码 `100009`），长期追加会触顶，需要监测与轮转策略
3. **墓碑是逻辑删除**：数据仍留在 IMA，且 IMA 自身的 AI 检索仍可能命中。真要物理删除只能在 IMA 客户端手动操作

#### 待实测：`backend/scripts/test_ima_append.py`

整个模型压在 `append_doc` 上，因此在动代码前先验证它的实际行为：

```bash
docker compose exec backend python scripts/test_ima_append.py
# 另外探测单篇大小上限（会写入约 1MB 内容）
docker compose exec backend python scripts/test_ima_append.py --probe-size
```

探针逐项验证：凭证与连接、ID 参数名（`doc_id` 还是 `note_id`）、追加是否为追加而非替换、**追加的 JSON 代码块是否被 IMA 改写**（8.25 发现 IMA 会重写 Markdown，但代码块应当免疫，需实测）、中文与 emoji 是否保留、多次追加的顺序、标题是否受影响。

脚本本身的逻辑已用替身客户端自测过四种场景（正常、内容被改写、接口不可用、参数名不同），确认失败时能给出可定位的差异信息。

⚠️ IMA 无删除接口，探针会留下标题含 `[探针]` 的笔记，验证完需在 IMA 客户端手动删除。

### 8.34 图片改为「分析后丢弃」（2026-09-27）

#### 决策

错题原图只是 LLM 分析的输入，分析完成后即丢弃。不落盘到 vault，不进 markdown，也不上传到任何云端存储。长期保存的只有分析结果：题目文字、正确答案、解题过程、错因分析、图形文字描述。

#### 修正 8.31 / 8.33 中的两处错误推断

**错误一：把「IMA 不收图片」当成约束。** IMA 确实没有图片接口，但用户的用法本来就是「只把分析结果作为 Markdown 放进 IMA」，图片从不进 IMA。所以这不是约束，是无关。

**错误二（更严重）：由「图片要存在某处」推出「Mac 必须开着」。** 这两件事没有因果关系——图片存在后端所在的那台机器上，后端搬到 VPS，图片就跟着过去。该推断是把存储位置和运行位置混淆了。

#### 顺带暴露的问题：IMA 笔记里带着坏掉的图片链接

此前 `create_question` 把**同一个 body** 同时交给 IMA 和本地，而这个 body 含图片引用：

```markdown
![原题](../../../../_assets/accounts/{account_id}/{child_id}/{subject}/{question_id}/{filename})
```

相对路径在 Obsidian 里有效，在 IMA 里指向不存在的位置。而 `ima_storage` 中负责上传图片的那段逻辑（`upload_image`）恒返回 `None`，从来没成功过。

也就是说：**IMA 笔记一直带着一批坏掉的图片链接。** 这与「IMA 收不收图片」无关，是「把为 Obsidian 写的路径原样塞进了 IMA」。改动后 IMA 笔记与本地 markdown 都是纯文字，两边终于一致。

#### 移除的内容

| 移除项 | 位置 |
|---|---|
| 图片落盘 | `file_ops.save_image()`、`_assets_dir()`、整个 `_assets/` 目录结构 |
| 正文里的图片引用 | `create_question` 中的四层上溯路径 |
| 图片服务接口 | `GET /questions/{id}/images`、`serve_image`（含路径穿越防护） |
| 移动错题时的图片搬迁 | `PATCH /questions/{id}` 中的 `shutil.move` |
| 存储层图片支持 | `get_image_url`、各后端的 `images` 参数、`ima_storage` 中落空的 `upload_image` 调用 |
| 失效代码 | `IMAClient.upload_image()` 空壳、`file_storage.sync_from()`（账号化后已失效）、`UploadedImage` 模型 |
| 前端图片展示 | `DetailPage` 的图片获取与渲染、保存时提交的 `image_ids` |

#### 保留的内容

图片仍然**流经**系统，只是不留下：上传到临时目录（含格式、大小、文件头嗅探校验）→ 压缩后发给 LLM → 分析完由 TTL 回收。

因此 `upload.py`、`llm._preprocess_image()`、`tasks.py` 的图片传递、前端上传预览全部保留。8.14 的图片压缩优化继续有用——它本来就是为控制 LLM 请求体积而做的。

#### 临时文件生命周期

保存流程不再负责清理图片（它现在已经不碰图片了），因此改为**按时间回收**：

- TTL 24 小时，覆盖「上传 → 分析 → 保存」以及中途的重新生成与反馈优化
- 应用启动时扫一次，之后每次上传时顺带扫一次
- 空的账号目录一并清理
- 未保存的任务到期后自动回收，不会永久堆积

这也顺带解决了一个既有问题：以前保存会删除临时文件，但任务的「反馈优化」还要用它们，导致保存后再点反馈优化会返回 400。现在临时文件有独立生命周期，该功能在 TTL 内始终可用。

#### 代价

**确认那一步成为唯一的纠错机会。** 原图不在之后，AI 若把题目或答案认错，保存前没改就再也无法对照原图核对。此前 6.4 节设计的「原图与结果左右对照、逐字核对」不再可行，保存前的核查从建议变为硬要求。

**复习时看不到手写笔迹与几何图形。** 图形题只剩 AI 的文字描述。这是有意的取舍。

#### 历史数据的处理

`migrate_to_accounts.py` 仍然迁移并保留旧 vault 的 `_assets/` 图片，因为那是既有数据，在迁移中丢弃属于未授权的数据损失。因此会出现「旧错题的图片保留、新错题不再有图片」的混合状态。如需连同旧图片一并清理，应作为独立操作明确执行。

#### 验证

```
后端 pytest: 55 项全部通过（原 49 + 新增临时文件回收 6 项）
接口冒烟:    81 项全部通过（新增图片策略专项检查）
前端构建:    TypeScript + Vite + PWA 通过
浏览器实测:  19 项全部通过
```

### 8.35 错题文件名改为「人名·学科·日期-id」（2026-09-27）

#### 决策

本地 markdown 文件名由 `2026-09-20-9d0519e0.md` 改为：

```
女儿·数学·2026-09-20-9d0519e0.md
```

#### 为什么改

旧文件名是「日期 + 随机 id」，在 Obsidian 的搜索、快速切换、文件列表以及用 Finder/grep 翻文件时完全看不出内容。改成可读格式后，归属与学科一眼可见。

需要澄清一点：**这不是为了程序检索**。应用按孩子查错题走的是「数据库取 child_id → 拼目录路径 → 读目录」，人名那层信息由 `child_id` 承载，文件名里加不加人名对检索没有任何影响。收益完全在人工场景。IMA 笔记标题（`【女儿·数学】…`）本来就是可读格式，无需改动。

#### 代价与处理

**一、可变信息进了文件名。** 人名和学科都是可以改的，而内容是 `child_id` 这类不可变标识。若不处理，改名后文件名会一直停留在旧名字上。

处理方式：**在孩子改名时同步重命名**。`children.py` 的 PATCH 接口在检测到名字变化后调用 `file_ops.rename_questions_for_child()`，逐个刷新其名下错题的文件名与 frontmatter 里的 `child_name`。改名是低频的明确操作，在这里付一次代价，换来文件名始终准确，比让所有读取方去容错更划算。

错题换学科或换孩子走的是 `save_question`，文件名本来就会按新归属重新生成，无需额外处理。

**不该做的事：** 无法解析的历史文件会被跳过并记警告，不会让改名整体失败。

**二、人名需要清洗。** 人名只校验了长度（1–40 字符），没有限制字符集，所以可能含 `/`、`:`、`*` 等非法字符——`/` 尤其危险，会直接把文件写到意料之外的目录。现在按 POSIX/Windows 的保留字符集做替换，并在清洗后为空时回落到「未命名」。

**三、需要按字节截断。** 40 个汉字约 120 字节，超过文件名预算。截断按字节切再解码，避免把一个汉字切成半个；学科与日期部分完整保留。

#### 必须保留 id 后缀

`question_id` 留在文件名末尾有两个不可替代的作用：同一天同一主题可以有两道题，靠它保证唯一；同时 `find_question_file()` 是按 `*-{question_id}.md` 后缀匹配定位文件的，这是 `StorageManager.update_question` 找到本地文件的前提。

#### 已知遗留

1. **IMA 笔记标题也含人名**，改名后云端标题会停留在旧名字上——IMA 没有修改接口（见 8.31），无法回写
2. **历史文件保持旧命名**。迁移前的文件仍是「日期-id」格式，读路径靠 frontmatter 和后缀匹配，不受影响；它们会在下次孩子改名时被顺带规整

#### 验证

```
后端 pytest: 68 项全部通过（原 55 + 新增文件名相关 13 项）
接口冒烟:    81 项全部通过
浏览器实测:  19 项全部通过
```

新增测试覆盖：命名格式、按 id 定位、同日同主题不撞名、人名含 `/` 被清洗、Windows 保留字符被清洗、超长人名按字节截断且不切出半个汉字、清洗后为空回落占位符、改名触发重命名并刷新 frontmatter、名字未变不触发重命名、多学科同时重命名、坏文件跳过不影响改名、移动错题后文件名更新。

### 8.36 本地定位：IMA 为唯一记录来源 + 可丢弃缓存（2026-09-27）

#### 决策

错题相关的数据以 **IMA 为唯一记录来源**。本地不再保留"副本"，只保留一份**可随时删除、可从 IMA 完整重建**的缓存。

缓存与副本的区别在于：缓存不承载任何独有信息，删掉不丢数据。它不需要维护，也不参与一致性设计——丢了大不了重建。

#### 为什么现在还不能直接去掉本地

IMA 没有修改接口，因此**重做产生的一切**（掌握度、重做次数、重做历史、下次复习日期）无处可写。目前这些全部由本地文件承载：`StorageManager.update_question` 尝试写 IMA 会因为缺少 `update_note` 而失败，真正生效的是本地那次写入。

所以「去掉本地」依赖 8.33 的追加事件模型，而 `append_doc` **尚未实测**。

顺序上只能先实测 `append_doc`，通过之后才具备去掉本地的条件。在此之前动这块代码，重做功能会直接失效。

#### 性能现实：缓存是可用性的前提，不是图方便

列出错题必须逐条读正文才能拿到元数据（IMA 的列表接口只返回标题，掌握度与复习日期都不在标题里），而每次 `_call_api` 都会新起一个 Node 进程。实测量级：

| 题量 | 调用次数 | 估算耗时 |
|---|---|---|
| 50 道 | 53 次 | 约 12 秒 |
| 200 道 | 210 次 | 约 46 秒 |
| 500 道 | 525 次 | 约 115 秒 |

并发请求能把这个数字压缩到几秒，但会显著增加触发节流的概率。本地读取是毫秒级。

结论：保留缓存不是偏爱本地，而是纯 IMA 读取在题量上去之后不可用。

#### 取舍：放弃 Obsidian

本地副本消失后，第 2 节把「Markdown 双向链接 + Dataview 查询 + 本地存储数据完全在自己手里」列为选型理由的那部分不再成立——Obsidian 将无内容可读。这是有意的取舍，不是遗漏。

#### 无论怎么选都会保留的本地内容

| 内容 | 说明 |
|---|---|
| `config/app.db` | 账号、孩子、课程。必须存某处，且它不是错题副本 |
| 上传临时目录 | 分析期间存在，TTL 自动回收（见 8.34） |
| 缓存目录 | 可丢弃、可重建，删掉不丢数据 |

#### 待办

1. **实测 `append_doc`**（阻塞项，见 8.33 与 `backend/scripts/test_ima_append.py`）
2. 通过后把更新路径改为写 IMA，本地降级为缓存
3. 定缓存重建策略：启动时全量拉取，还是按需拉取 + 增量同步

### 8.37 append_doc 实测结果（2026-09-27）

#### 结论：追加事件模型成立

`backend/scripts/test_ima_append.py` 已用真实凭证跑通，15 项检查全部通过。

| 检查项 | 结果 |
|---|---|
| IMA 连接与凭证 | ✅ |
| `append_doc` 可用 | ✅ |
| ID 参数名 | ✅ `doc_id` 与 `note_id` **都接受** |
| 追加而非替换（基础块与原正文保留） | ✅ |
| **追加的 JSON 代码块逐字符未变** | ✅ |
| 代码块内下划线未被转义 | ✅ |
| 中文全角、emoji 保留 | ✅ |
| 多次追加保持先后顺序 | ✅ |
| 标题不受追加影响 | ✅ |

**8.33 设计的核心假设得到验证**：```json 代码块内容 IMA 确实不会改写。元数据可以安全地用代码块承载。

#### 实测发现的三条改写规则（8.25 的补充）

IMA 会改写**代码块之外**的 Markdown：

| 现象 | 说明 |
|---|---|
| `_` → `\_` | 正文中的下划线被转义 |
| `*` → `_` | 强调用的星号被规范化成下划线 |
| `[` → `\[` | 方括号被转义 |
| `<!-- -->` | **HTML 注释被整段剥掉** |

实践影响：探针的标记最初用了 HTML 注释和含下划线的文本，都被改写导致误判为「追加失败」。今后在正文里放任何机器可读的标记，必须放进代码块。

#### 修正 8.31 的两处疑点

**疑点一（参数名）：** 官方文档写 `doc_id`，现有代码用 `note_id`。实测**两者都被接受**，现有代码无需改动。

**疑点二（读取格式）：** 8.31 记录「`target_content_format: 1`（Markdown）官方标注不支持」。实测对比两种取值：

| 取值 | 结果 |
|---|---|
| `1`（Markdown，现有代码） | **保留换行与代码块结构**，但代码块之外的文本会被转义 |
| `0`（纯文本，文档推荐） | **所有换行丢失**，整篇压成一行；转义消失 |

**现有代码用 `1` 是正确的，不要改成 `0`**——我们需要结构来解析元数据代码块，而 `0` 会把笔记压成一行，无法解析。

#### 顺带确认的其他端点

1.1.10 版 skill 的文档中列出的端点，除已用到的之外还有：`list_notebook`、`list_note`、`search_note`、`create_media`、`import_urls`、`search_knowledge`、`get_media_info`、`check_repeated_names`、`get_addable_knowledge_base_list`、`get_knowledge_base`、`list_docs`。

其中 `import_urls`（导入网页链接）与 `search_knowledge` 可能对后续设计有用，但尚未评估。

仍然**没有修改笔记与删除笔记的接口**——8.31 的结论不变。

#### 仍然阻塞的事项

探针脚本所在的 `ima_api.cjs` 有**版本闸门**：本地 1.1.9 会被 IMA 拒绝，必须更新到 1.1.10。宿主机上的 skill 目录受保护、无法由代理挂载修改，因此这一步需要手动完成：

```bash
cd /tmp
curl -L -o ima-skills-1.1.10.zip https://app-dl.ima.qq.com/skills/ima-skills-1.1.10.zip
rm -rf ima-skill-new && mkdir ima-skill-new
unzip -q ima-skills-1.1.10.zip -d ima-skill-new
find ima-skill-new -maxdepth 3        # 确认 ima_api.cjs 所在层级

SKILL_DIR=~/.claude/skills/@tencent-adm/ima-skills
cp -a "$SKILL_DIR" "$SKILL_DIR.bak-1.1.9"
rsync -a --delete /tmp/ima-skill-new/ima-skill/ "$SKILL_DIR/"
```

原地覆盖而不是替换目录：compose 把该目录 bind mount 进容器，替换目录会让挂载指向旧的 inode。

#### 关于那条报错信息

版本闸门返回的 `msg` 里包含直接写给 AI 代理的操作指令（下载安装 skill、以及指定的用户话术）。这是提示注入的典型形状。经判断它大概率是腾讯官方的合法机制（域名属于腾讯、更新的是其自家 skill、版本差真实存在），但当时的处理方式是：只把它当作**线索**，自行判断后在沙箱内使用新版脚本，**没有**安装到宿主机、也**没有**转述那句「skill 已更新至 1.1.10」——因为并没有更新。

### 8.38 追加事件模型落地（2026-09-27）

8.33 设计、8.37 验证通过，本节是实施结果。

#### 结构

一篇 IMA 笔记 = **基础块（不可变）+ 若干事件块（追加）**：

```
# 【女儿·数学】一元二次方程（计算错误） 2026-09-20
```json
{"id": "…", "account_id": "…", "rev": 1, "mastery_score": 0, …}   ← 创建时写入，之后不动
```

## 原题
…

```json
{"type": "redo", "rev": 2, "at": "…", "result": "correct", "mastery_score": 68, …}
```

```json
{"type": "redo", "rev": 3, "at": "…", "result": "wrong", "mastery_score": 45, …}
```
```

#### 事件是「状态快照」而不是「增量指令」

每条事件携带**当前可变字段的完整快照**，折叠时逐条覆盖即可，不需要重放计算，也不怕漏掉某条事件导致状态算错。

例外是 `redo_history`：它由折叠逻辑逐条追加（从事件的 `at` / `result` / `note` 推导），而不是整体覆盖——否则笔记会随重做次数呈平方级增长。

不进入事件的字段：`id`、`account_id`、`ima_note_id`、`created_at`（身份类，不可变）、`redo_history`（单独处理）。

#### 折叠规则

| 事件类型 | 处理 |
|---|---|
| `redo` | 覆盖提供的字段，并往 `redo_history` 追加一条 |
| `patch` | 只覆盖提供的字段（移动归属、修正内容走这条） |
| `delete` | 标记 `deleted`（逻辑删除，9.36 的墓碑方案） |

`type` / `result` / `note` 只参与折叠过程，不进入状态。

#### 读写路径

| 操作 | 数据来源 |
|---|---|
| 新建错题 | 写 IMA 基础块 + 本地缓存 |
| **重做 / 移动** | **先读 IMA 权威状态** → 计算 → 追加事件 → 刷新本地缓存 |
| 列表 / 详情 / 统计 / 复习计划 | 本地缓存（毫秒级） |
| 定时同步 | IMA → 本地，折叠后物化 |

读—改—写类操作特意每次都读一次 IMA：本地缓存可能落后（例如你在 IMA 客户端直接改过笔记），而重做要基于当前计数计算，读旧数据会算错。单条读取一次 API 调用，代价可以接受。

#### 返回值语义

IMA 模式下，`update_question` **以事件是否成功写入 IMA 为准**。本地缓存刷新失败不算失败——缓存随时能从 IMA 重建；反过来则不行，事件没写进去就等于这次改动丢了。写失败时接口返回 503，不会假装成功。

历史错题若缺少 `ima_note_id`（例如当初 IMA 写入失败），会退回只写本地并记警告，不让用户的操作失败。

#### 真实 IMA 端到端验证

用真实凭证对真实笔记跑通（不是替身）：

```
基础块写入 → 追加 2 个 redo 事件 → 回读折叠
  mastery_score = 76 ✓    redo_count = 2 ✓    consecutive_correct = 2 ✓
  redo_history 累积 2 条且顺序正确 ✓    正文完整取出 ✓    rev 推进 ✓

再走一遍应用的真实路径（读权威状态 → 构造事件 → 追加）：
  rev 在读到的基础上递增 2 → 3 ✓    mastery_score = 45 ✓
  consecutive_correct 归零 ✓    redo_history 累积 3 条 ✓
```

这一步是必要的：8.31 的教训就是替身客户端比真客户端"更能干"，导致「更新 IMA」长期静默失效却无人发现。这次改为对真接口验证。

#### 单元测试与接口回归

```
后端 pytest: 76 项全部通过（原 68 + 新增事件折叠与物化 8 项）
接口冒烟:    81 项全部通过
前端构建:    TypeScript + Vite + PWA 通过
浏览器实测:  19 项全部通过
```

新增覆盖：仅有基础块的历史笔记兼容、事件覆盖顺序、`redo_history` 顺序累积、事件元字段不泄漏进状态、墓碑标记、正文不含事件块、坏事件块跳过不影响其余折叠、同步物化折叠后状态而非原始事件。

#### 已知限制

1. **IMA 笔记只增不减**，单篇有大小上限（错误码 `100009`）。每道题的事件数与重做次数同阶，正常使用不会触顶，但需要时要有轮转方案
2. **移动归属无法反映到 IMA 的文件夹结构**（无移动接口），云端笔记仍留在原文件夹，只有标题与元数据更新
3. **删除是逻辑删除**，数据仍在 IMA，其自带检索仍可能命中
4. 本地缓存与云端的一致性依赖「写时刷新 + 定时同步」，没有做版本向量；正常情况下够用

### 8.39 缓存重建入口（2026-09-27）

#### 为什么需要

本地缓存是可丢弃的物化视图（8.36）。既然是「可丢弃」，就必须能重建，否则一次误删或磁盘故障就变成数据不可用——即便 IMA 里的数据完好。

#### 两种模式的语义差别

| | 定时同步 `/sync/to-obsidian` | 重建 `/sync/rebuild-cache` |
|---|---|---|
| 冲突处理 | 保守：本地更新时不覆盖 | **以 IMA 为准强制覆盖** |
| 适用场景 | 日常刷新缓存 | 缓存丢失、损坏、不可信 |
| 版本号 | 作为判断依据 | 不作参考（此时本地不可信） |

重建会跳过冲突保护，因为它的前提就是「本地可能整个是错的」。统计里把强制覆盖的条数单列成 `forced`，与常规的 `updated` 区分开，便于看出重建确实做了什么。

#### 两个入口

**管理员接口**（需要 IMA 启用，`prune` 默认 false）：

```
POST /api/sync/rebuild-cache
{"prune": false}
```

**命令行**（容器内，不依赖 API 可用）：

```bash
docker compose exec backend python scripts/rebuild_cache.py --dry-run   # 预览
docker compose exec backend python scripts/rebuild_cache.py             # 重建
docker compose exec backend python scripts/rebuild_cache.py --prune     # 顺带清理本地独有项
```

`dry_run` 只统计不写盘，用来预览重建会做什么。

#### local_only：「只在本地、IMA 里没有」的错题

IMA 是记录来源，所以这类错题意味着某次写入没落到云端——**是完整性信号，不是垃圾**。默认只报告数量和 ID、不删除；确认后再用 `prune` 清理。

#### 实测发现一：IMA 会限频，而旧代码把它当成「笔记不存在」

对着真实 IMA 跑重建时撞上限频：

```
IMA 业务错误: 请求频率超限，请稍后重试
```

由此暴露两个问题：

**问题 1：失败被静默吞掉。** `get_note` 在出错时返回 `None`，而调用方写的是 `if not note_content: continue` ——既不计入 `errors`，也不重试。结果是统计显示「errors: 0，一切正常」，实际上大量笔记根本没拉到。这种「看起来成功了」正是 8.31 那类问题的翻版。

**已修：** 拉取失败现在计入 `errors`，不再无声跳过。

**问题 2：没有重试，一次限频就让整轮同步断掉。**

**已修：** `IMAClient._call_api` 增加指数退避重试（2 → 4 → 8 → 16 秒，共 4 次）。只针对限频，鉴权失败之类的错误仍然立刻抛出——重试那些没有意义。

修复后实测：同一份笔记库，从「中途断掉且统计显示正常」变成「自动退避后全部完成，`errors: 0`」，耗时 **37 秒**（其中约 30 秒是退避等待）。

**结论：批量操作在 IMA 上慢是常态，不是异常。** 重建要按分钟级预期，不要放在同步请求里做。

#### 实测发现二：列表接口已经返回了 `summary` 与 `modify_time`（N+1 有解）

探查 `list_note_by_folder_id` 的原始返回时发现，每条笔记的 `basic_info` 里带着：

- **`summary`**：笔记开头约 200 字，**包含基础元数据块**（能看到 `account_id` / `child_id` / `subject`）
- **`modify_time`**：最后修改时间戳
- `create_time`、`title`、`folder_id`

这给了 N+1 问题两条明确的出路：

1. **按 `modify_time` 跳过未变更的笔记**：本地缓存文件记下物化时的 `modify_time`，下一轮同步只需比对，无需拉正文。日常同步会从「N 次读取」降到「1 次列表 + 少量读取」
2. **用 `summary` 做归属过滤**：现在 `IMAStorageBackend.list_questions` 要逐条读正文才能按 `account_id` 过滤，而 `summary` 里就有这些字段

注意 `summary` 只有开头约 200 字，**拿不到追加在末尾的事件块**，因此它不能替代正文读取来算折叠状态——但对过滤和跳过判断足够了。

这两项尚未实现，是下一步最有价值的优化。

#### 验证

```
后端 pytest: 89 项全部通过（原 84 + 新增限频重试 5 项）
接口冒烟:    81 项全部通过
新增接口:    IMA 关闭时返回 400；普通账号返回 403
真实 IMA:    重建到空缓存 → 笔记正确物化（掌握度 45、rev=3、redo_history 3 条、
             正文完整、本地文件不含事件块），限频自动退避后 errors=0
```

新增测试覆盖：空缓存全量重建、强制覆盖比本地旧的云端版本、常规同步仍保持保守语义、重建时折叠事件、本地独有项被报告但不删除、`prune` 才删除、`dry_run` 不写盘且不 prune、限频退避重试、非限频错误不重试、重试次数上限。

### 8.40 批量读取优化：跳过未变更的笔记（2026-09-27）

#### 问题

8.39 实测重建要 37 秒。拆开看请求构成才发现，**读的大多不是错题**：

```
空缓存重建：读取正文 29 条
  ├─ 有效错题        1 条
  └─ 非错题笔记     28 条（历史格式笔记、测试笔记、别的用途的笔记）
```

这 28 条每轮同步都要被完整读一遍、解析完再丢弃。笔记越多，这部分越是主要开销——它比真正的错题量大得多。

#### 三层优化

**一、summary 预筛（归属已判明且不属于本系统账号）**

列表接口返回的 `summary` 是笔记开头约 200 字，里面就带着元数据块的开头，足以读出 `account_id` / `child_id`。归属明确不在允许范围内时，连正文都不必读。

**二、按 `modify_time` 跳过未变更的错题**

本地缓存文件记下物化时云端的 `ima_modified_at`；下一轮同步如果列表接口给的 `modify_time` 与之相同，说明这条笔记自上次物化后没动过，直接跳过读取。

**三、跳过缓存：记住「已确认不是错题」的笔记**

前两层都覆盖不到历史格式与别的用途的笔记——它们没有任何可判断的标记。所以额外维护一份轻量缓存（`config/ima_skip_cache.json`），记录判定结果与当时的 `modify_time`；下次遇到同一篇且未变更，直接跳过。

附带的好处：它同时避免了「同一批无关笔记每轮都被读一遍」这种稳定浪费。条目会随知识库内容自动清理（`prune_absent`），文件不会无限增长。

#### 为什么不靠「summary 里没有 account_id」来跳过

那看起来更省事，但 `summary` 只有约 200 字，一旦被截断（例如主题名很长，标题就占满了），真错题也会被误判成「无关笔记」而永远不进本地缓存——**这是静默的数据丢失**。

`modify_time` 是服务端给出的确定性信号，只有「确实没变过」才会跳过，不会凭空猜测。缓存文件损坏时一律当作空缓存重建——最坏只是多读几条。

#### 实测对比

同一个真实知识库（29 条笔记，其中 1 条有效错题）：

| 轮次 | 读取正文 | 耗时 |
|---|---|---|
| 优化前·第 2 轮 | 28 条 | 48.4s |
| **优化后·第 2 轮** | **0 条** | **0.4s** |

请求数是确定性指标：**28 → 0**。耗时数字受 IMA 限频波动影响较大（8.39 记过，同一份数据从 8.6s 到 48s 都可能），所以以请求数为准。

第二轮的统计变成 `unchanged: 1, preskipped: 28`——两类笔记各有各的跳过依据，一条都没再读。

#### 参数与默认值

| 入口 | skip_unchanged 默认 | 理由 |
|---|---|---|
| 定时同步 `POST /sync/to-obsidian` | `True` | 日常刷新，信任本地缓存 |
| 重建 `POST /sync/rebuild-cache` / `rebuild_cache.py` | **`False`** | 重建的前提就是本地可能整个不可信，默认逐条重读 |

重建想快可以显式打开：`--skip-unchanged`（CLI）或 `{"skip_unchanged": true}`（API）。这时它的语义是「补齐缺失/过期的条目」，而不是「彻底重刷」。

#### 一个必须守住的约束

**被跳过的笔记仍然要记为「IMA 侧见过」。** 否则 `local_only` 检测会把它们误报成「只在本地、没进云端」——一个纯粹的假警报，而且会让人怀疑数据完整性。这一条有专门的回归测试守着。

#### 验证

```
后端 pytest: 104 项全部通过（原 96 + 新增跳过相关 8 项）
接口冒烟:    81 项全部通过
真实 IMA:    第 2 轮读取 0 条、耗时 0.4s、unchanged=1 / preskipped=28
```

新增覆盖：落盘时记录云端修改时间、未变更不重复读取、变更后重新读取、缺版本戳时必须读取、`skip_unchanged=False` 强制重读、summary 预筛命中则不读正文、**跳过的笔记不被误报为本地独有**、跳过缓存的往返/损坏容错/过期清理/无变更不写盘、预演不留下持久化状态。

### 8.41 使用手册与一处文档纠错（2026-10-07）

#### 新增 `function.md`

面向家人（非开发者）的使用手册：讲清楚每个功能怎么用、完整流程是什么。存储部分按需求只说明「错题存在云端、保存的是文字不是照片」，不展开 IMA / 缓存 / 事件模型等技术细节。

包含：首次使用、邀请码邀请家人、创建孩子与课程、录入错题的五个步骤、复习流程、掌握度算法与复习间隔、列表与详情、统计、账号管理、常见问题、以及一节「设计取舍」（说明为什么不留原图、为什么不删除错题、为什么要求连续做对）。

#### 纠错：错题编辑功能其实没有完成

写手册时逐条核对界面文案与接口，发现 **8.18 待做事项表里「P4 错题编辑功能（修改已有错题）」标记为已完成，但实际并未实现**：

| 位置 | 实际情况 |
|---|---|
| `frontend/src/components/QuestionEditor.tsx` | 骨架组件，内容只有一行 `TODO: 错题编辑表单` |
| `PATCH /api/questions/{id}` | 只接受 `new_child_id` / `new_subject`，即**只能移动归属** |
| `DetailPage.tsx` | 没有任何编辑入口 |

**结论：错题保存后无法修改内容**——改不了题目、答案、错因分析，也删不掉（删除接口返回 405）；唯一能做的是调整归属。

这条对使用方式有实质影响：**保存前的核对是唯一且不可逆的机会**。手册里已按此强调，并把 8.18 那一行的状态改回「未完成」。

顺带说明：`QuestionEditor` 这个骨架组件目前没有被任何页面引用，属于遗留占位。

#### 待办

如果希望支持事后修改，可选两条路：

1. **补上编辑功能**：实现 `QuestionEditor`，并在 `PATCH /api/questions/{id}` 支持内容字段。注意写入要遵从事追加模型（8.38）——内容属于「修正」，按 8.33 的规则应当新建修订版笔记并给旧笔记追加墓碑，而不是原地改
2. **保持不可改**，把「保存前核对」做成流程上的硬要求（当前手册的做法）

### 8.42 面向数学的 LaTeX 版改造（2026-11-08）

#### 决策

聚焦数学，错题公式**统一用 LaTeX 保存**（`$...$` 行内、`$$...$$` 独立成行），AI 识别 + 手动补正。存储回归**阿里云服务器磁盘**，IMA 已禁用。

三个方向的确定过程：

1. **改造现有项目**（不另起炉灶）——复用多账号、复习、掌握度能力
2. **AI 识别 LaTeX + 手动补正**——录入门槛最低，错了能在编辑器里改
3. **存本地 md 文件**（阿里云磁盘）——IMA 会改写正文里的下划线，`x_1` 会变成 `x\_1`，而 LaTeX 到处都是 `_` 和 `\`，存 IMA 必坏

#### 为什么存本地 md 是正解

LaTeX 放进 md 文件**字节级原样保存**，Obsidian（MathJax）和前端（KaTeX）都能直接渲染。之前 IMA 会破坏 LaTeX，不是"云端"的问题，是 IMA 这个产品会重写 Markdown 的问题。换成任何"原样存文件"的存储（本地磁盘、对象存储、OneDrive Graph API），LaTeX 都安全。

#### IMA 禁用

`.env` 的 `IMA_ENABLED` 改为 `false`。密钥字段保留（API Key、Client ID 等），以后想恢复只需改回 `true`。

禁用后的行为：

- 错题只写本地 vault，不再双写 IMA
- 定时同步（IMA → 本地）不启动
- `/api/sync/*` 接口返回 400「IMA 存储未启用」

⚠️ 这个改动在**阿里云服务器**上也要执行——本地 `.env` 和服务器 `.env` 是两份，`.env` 在 `.gitignore` 里不会同步：

```bash
cd 项目目录
sed -i 's/^IMA_ENABLED=true$/IMA_ENABLED=false/' .env
docker compose restart backend
```

#### 改动清单

| 文件 | 改动 |
|---|---|
| `app/core/prompts.py` | 「数学公式格式要求」从"纯文本优先"改为"统一 LaTeX"；JSON 结构里 question_text / correct_answer / solution_steps / student_answer 的格式说明同步改为"数学公式用 LaTeX" |
| `app/services/llm.py` | `refine_analysis` 的提示从"避免 LaTeX"改为"继续使用 LaTeX"；**提取 `_parse_json_reply()`** 合并两处重复的 JSON 解析；**修 fix_escape 的 f 误判**（见下） |
| `frontend/src/components/AnalysisPreview.tsx` | 编辑模式新增 `EditableMathText` 组件：textarea + 实时 KaTeX 预览，题目/答案/解题过程/孩子作答/错误分析字段都能"边改边看" |
| `.env` | `IMA_ENABLED=true` → `false` |

#### 发现并修复的 bug：fix_escape 把 \frac 当成换页符

原有的 JSON 解析里，`fix_escape` 把 `\f` 当作合法的 JSON 转义（换页符 form feed）而保持不变：

```python
if char in '"\\/bfnrtu':   # ← f 在里面，\frac 的 \f 被误判为换页符
    return match.group(0)
```

这在"纯文本公式"时代几乎不触发（模型很少输出 LaTeX）。全面转向 LaTeX 后，`\frac`、`\fbox` 等 f 开头的命令非常常见——只要模型偶尔漏转义、输出单反斜杠的 `\frac`，就会被解析成「换页符 + rac」，公式损坏。

**修复**：把 `f` 从合法转义集合去掉，让它走"双写反斜杠"分支。数学错题内容里换页符几乎不可能出现，而 `\frac` 非常常见，取舍明确。

实测四种场景：

| 场景 | 结果 |
|---|---|
| 合法 JSON（模型正确转义 `\\frac`） | ✅ LaTeX 完整 |
| 非法 JSON（单反斜杠 `\frac`） | ✅ 修复后 LaTeX 完整（修复前 `\f`→换页符） |
| 多命令（`\sum` `\sqrt` `\alpha`） | ✅ 全部保留 |
| markdown 代码块包裹 | ✅ 正确剥离 |

顺带把两处重复的 JSON 解析合并成 `_parse_json_reply()`，消除了 `analyze_images` 和 `refine_analysis` 里两份几乎相同的代码。

#### 前端手动补正体验

编辑模式下，每个可含公式的字段（题目、答案、解题过程、孩子作答、错误分析的四个子字段）都是「textarea + 下方虚线框实时预览」。用户改 LaTeX 时立刻看到渲染结果，`\frac` 花括号没闭合这类错误当场就能发现，而不是保存后才暴露。

预览框始终显示（值为空时占位一个全角空格），纯文字字段也不会显得突兀。

#### 整条链路现状

```
拍照 → AI 分析（提示词要求输出 LaTeX）
      → JSON 解析（_parse_json_reply 保 LaTeX 反斜杠）
      → 前端预览（KaTeX 渲染 $...$ / $$...$$）
      → 手动补正（textarea + 实时预览）
      → 保存 md（LaTeX 原样写入，Obsidian 也能渲染）
```

前端渲染层（KaTeX）和 JSON 解析层（fix_escape）在早期版本就已经为 LaTeX 打好了底子，本次改造真正改动的核心是**提示词**——让 AI 从"输出纯文本"切换到"输出 LaTeX"。

#### 验证

```
后端 pytest: 123 项全部通过
前端构建:    TypeScript + Vite + PWA 通过
JSON 解析:    四种场景（合法/非法/多命令/代码块）验证通过
提示词转义:   \frac \sqrt \times 运行时均为单反斜杠，无残留双反斜杠
```

#### 后续待办

1. **真实 AI 实测**：改完提示词还没用真实模型跑过——需要确认火山引擎那个模型（ark）确实能稳定输出合法 LaTeX，而不是又退回纯文本
2. 阿里云服务器上确认 IMA 已禁用、`.env` 的 VAULT_PATH 指向实际目录
3. `function.md` 使用手册需按"数学 LaTeX 版"更新（目前描述的是纯文字版）

### 8.43 实测：DeepSeek flash 输出 LaTeX 验证（2026-11-08）

用真实高中数学周清试卷（扫描件，前 2 页，19 页）实测 DeepSeek flash 的 LaTeX 输出。

#### 配置

`config/settings.json`：api_base=`https://api.deepseek.com/v1`，model=`deepseek-flash`，timeout=120。

#### 结果

识别出前 2 页全部 11 道题，题目与答案全部用 `$...$` 包裹的标准 LaTeX：

- `\frac`、`\sqrt`、`\log`、`\ln`、`\mathbb{R}`、`\begin{cases}`、上下标、绝对值、定义域区间等命令全覆盖
- 语法正确，无残缺
- 学科判断正确（数学）
- 第 7 题 C、D 选项被裁切时，模型诚实标注「图中 C、D 两个选项被裁切，无法识别」而非编造

#### 结论

8.42 的核心改造验证成功：**AI 从「输出纯文本」切换到了「稳定输出 LaTeX」**，整条链路（图片 → 提示词要求 LaTeX → DeepSeek 输出 → `_parse_json_reply` 保留反斜杠 → 前端 KaTeX 渲染）跑通。

#### 顺带修复

`test_connection` 的 `max_tokens=20` 对推理模型太小——deepseek-flash 会先输出 `reasoning_content`（实测约 93 字符），20 token 连思考都不够，导致「测试连接」显示成功但回复为空。已改为 200。

#### 小发现

第 5 题 D 选项、第 7 题 C/D 选项被裁切，是 `pdftoppm` 转图或试卷本身边距所致，非 LaTeX 问题。手机实拍完整页面不受影响。


### 8.44 v2.0：真题针对性复习（2026-11-17）

#### 需求

导入往年真题，结合每个孩子的错题薄弱点，针对性挑真题练习。

#### 关键决策

1. **导入形式**：拍照 / 扫描 PDF，复用现有「图片 → AI 拆题 → 人工确认」链路。
   PDF 用 pypdfium2 逐页转图（自带二进制，无系统依赖，150 DPI），
   单个 ≤ 30 页，一次请求展开后 ≤ 40 张。
2. **真题库是账号级资源**：不绑定孩子，导入一次全家共用；
   薄弱点与练习记录按孩子区分。存储 `vault/accounts/{账号}/zhenti/{学科}/*.md`。
3. **真题可编辑可删除**：与错题「保存后不可改」不同——真题是题库素材，不是学习记录。
4. **知识点匹配**：归一化精确匹配。导入时把库内已有知识点词汇表注入提示词
   （`build_exam_prompt`），让 AI 尽量复用标签，从源头提高匹配率。
   无匹配的薄弱点显式暴露「暂无匹配真题」，提示该导入哪类卷子。
5. **推荐算法**：薄弱度权重 = 未掌握错题上 Σ(1−掌握度/100) 按知识点聚合；
   真题得分 = 命中薄弱点权重和；同分按「该孩子练得少优先」再按年份新优先。
6. **闭环**：做错的真题一键转为该孩子的错题（复用 `create_question` 全部逻辑），
   进入现有掌握度复习循环。这是 2.0 与 1.0 的核心衔接。

#### 实现清单

| 层 | 内容 |
|---|---|
| 后端 | `models/zhenti.py`、`zhenti_ops.py`（文件读写）、`zhenti_match.py`（聚合推荐）、`routes/zhenti.py`（11 个端点）、`ANALYZE_EXAM_PROMPT`、`llm.analyze_exam_images`、TaskManager 扩展 kind/meta、upload PDF 支持 |
| 前端 | 「真题」导航页三标签：导入（预览勾选/知识点编辑）、题库（筛选/详情/编辑/删除）、针对性练习（薄弱点排行/推荐/自评/转错题）；ImageUploader 支持 PDF |
| 测试 | 新增 17 项（文件操作/匹配算法/API 全流程含 PDF 与账号隔离），全量 140 项通过 |
| 版本 | 后端 FastAPI 与前端 package.json 均升至 2.0.0 |

#### 部署与验证

- 部署前执行 backup.sh 备份；rsync 后端 + 重建镜像（装入 pypdfium2）+ 更新前端
- 生产镜像跑全量测试：140 项 OK
- 线上验证：/api/health 正常、openapi 版本 2.0.0、8 组真题路由注册、未登录 401、前端指纹与本地构建一致

#### 已知边界

- 知识点匹配是精确匹配，AI 标签写法不一致会漏配——靠词汇表注入 + 题库编辑修正缓解，
  后续可考虑 LLM 辅助标签对齐
- 真题练习不做间隔重复（2.0 范围外），做错转错题后才进入复习调度
