# 错题集项目 - 设计讨论记录

> 开始日期：2026-08-30
> 最后更新：2026-08-31

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

### 目录结构

```
错题集/
├── _assets/                    # 图片统一存放
│   ├── daughter/
│   │   ├── 数学/
│   │   │   └── abc12345/      # 按题目 ID 分子目录
│   │   │       ├── question.png
│   │   │       └── answer.png
│   │   └── ...
│   └── son/
│       └── ...
├── daughter/
│   ├── 语文/
│   │   └── 2026-08-30-题目ID.md
│   ├── 数学/
│   ├── 英语/
│   ├── 历史/
│   ├── 地理/
│   └── 政治/
└── son/
    ├── 语文/
    ├── 数学/
    └── 英语/
```

### 错题 Frontmatter 字段（v2 - 纳入掌握度评分 + 间隔复习 + 重复犯错检测）

```yaml
---
id: abc12345
child: daughter
subject: 数学
topic: 一元二次方程
error_type: 概念理解错误
source_type: 手写题
difficulty: 中等

# ── 时间线 ──
error_date: 2026-08-28              # 错误发生日期（比如考试/作业那天）
created_at: 2026-08-30              # 录入系统的日期

# ── 重做追踪 ──
redo_count: 2                       # 重做次数
last_redo_at: 2026-09-05            # 最近一次重做日期
redo_history:                       # 每次重做的记录
  - date: 2026-09-01
    result: wrong                   # 又做错了
    note: 还是符号判断出错
  - date: 2026-09-05
    result: correct                 # 这次做对了
    note: 因式分解步骤正确

# ── 同类型错误统计（AI 自动累计）──
similar_error_count: 5              # 同一 error_type + 相近 knowledge_points 的错题总数
similar_error_redo_fail: 2          # 同类题重做仍然出错的次数

# ── 掌握度评分（借鉴自智学精灵）──
mastery_score: 45                   # 0-100，扣减制计算（详见评分算法）
mastery_level: medium               # low(<40) / medium(40-69) / high(≥70)
mastery_status: reviewing           # new / reviewing / mastered（由 mastery_level 驱动）

# ── 重复犯错检测 ──
repeat_streak: 2                    # 当前连续重复犯错次数（相邻犯错间隔 ≤ 7 天）
max_repeat_streak: 3                # 历史最高连续重复次数
repeat_pattern: true                # 是否处于重复犯错模式（max_repeat_streak ≥ 2）

# ── 间隔复习计划（借鉴自智学精灵）──
next_review_date: 2026-09-07        # 下次复习日期
review_interval_days: 3             # 当前复习间隔天数
total_reviews: 5                    # 总复习次数

# ── 错误类型建议（AI 分析时自动匹配）──
error_suggestion: "回顾课本定义和定理，用费曼学习法讲出来"

# ── 知识点与标签 ──
knowledge_points:
  - 一元二次方程的求根公式
  - 判别式的应用
tags:
  - 错题
  - 数学/代数
---
```

### 字段说明

| 字段 | 含义 | 更新方式 |
|---|---|---|
| `error_date` | 错误发生的日期（考试/作业当天） | 录入时填写，可手动调整 |
| `redo_count` | 累计重做次数 | 每次重做自动 +1 |
| `redo_history` | 每次重做的日期、结果、备注 | 每次重做时追加记录 |
| `similar_error_count` | 同类型错题的数量 | 新错题录入时，系统自动更新相关题目的该字段 |
| `similar_error_redo_fail` | 同类题重做仍出错的次数 | 重做时系统自动更新 |
| `mastery_score` | 掌握度分数 0-100 | 每次重做后重新计算 |
| `mastery_level` | 掌握等级 | 由 mastery_score 映射：low(<40) / medium(40-69) / high(≥70) |
| `mastery_status` | 掌握状态 | new(未重做) / reviewing(未掌握) / mastered(已掌握) |
| `repeat_streak` | 当前连续重复犯错次数 | 重做后根据间隔自动更新 |
| `max_repeat_streak` | 历史最高连续重复次数 | 取历史最大值 |
| `repeat_pattern` | 是否处于重复犯错模式 | max_repeat_streak ≥ 2 时为 true |
| `next_review_date` | 下次复习日期 | 重做后根据间隔规则自动计算 |
| `review_interval_days` | 当前复习间隔天数 | 根据 mastery_level 和重做结果动态调整 |
| `total_reviews` | 总复习次数 | 每次重做自动 +1 |
| `error_suggestion` | 针对错误类型的学习建议 | AI 分析时根据 error_type 自动匹配 |

### 掌握度评分算法（借鉴自智学精灵，满分 100 扣减制）

```
扣分项                          公式                        上限
────────────────────────────────────────────────────────────────
错误次数                        redo_count × 8              扣 40
低难度还错（difficulty ≤ 2）    low_diff_errors × 5         扣 15
多种错误类型（同一知识点）       (error_type_count - 1) × 5  扣 15
近期犯错时间衰减                max(0, 10 - 距今天数 × 1.5)  扣 10

mastery_score = 100 - 各项扣分之和
```

### 掌握状态与等级映射

```
mastery_score  ≥ 70  →  mastery_level = high    →  mastery_status = mastered
mastery_score  40-69 →  mastery_level = medium  →  mastery_status = reviewing
mastery_score  < 40  →  mastery_level = low     →  mastery_status = reviewing
redo_count = 0        →  mastery_status = new（刚录入，还没重做过）
```

### 间隔复习规则（借鉴自智学精灵）

| mastery_level | 复习频率 | 间隔天数递增规则 |
|---|---|---|
| low（薄弱） | 每天 | 保持 1 天 |
| medium（待加强） | 每 3 天 | 重做对 → 间隔 ×1.5；重做错 → 间隔重置为 1 |
| high（已掌握） | 每 14 天 | 重做对 → 间隔 ×2；重做错 → 间隔重置为 3 |

### 重复犯错检测规则

```
1. 同一知识点，按 error_date 升序排列
2. 遍历相邻两条：间隔 ≤ 7 天 → repeat_streak + 1；否则重置为 1
3. 记录 max_repeat_streak = max(所有 streak 值)
4. max_repeat_streak ≥ 2 → repeat_pattern = true（标记为重复犯错模式）
5. 严重度：max_repeat_streak ≥ 4 = high，≥ 3 = medium，其余 = low
```

### 错误类型 → 建议映射表

| error_type | 自动建议 |
|---|---|
| 概念不清 | 回顾课本定义和定理，用费曼学习法讲出来 |
| 计算错误 | 每步写清楚，做完立刻代入检验 |
| 审题错误 | 圈出关键词，用自己的话复述再下笔 |
| 知识遗忘 | 建知识卡片，间隔重复法复习 |
| 方法错误 | 总结题型套路，做题前先想考什么 |
| 粗心大意 | 设立检查清单，考试留 5 分钟专门检查 |

### 设计理由

1. **Frontmatter 元数据** → Obsidian 的 Dataview 插件可以直接查询，比如"找出 daughter 所有 `error_type: 计算失误` 的数学题"
2. **图片用相对路径** → 跟着 OneDrive 一起同步，不依赖服务器
3. **AI 识别结果单独引用** → 原题图片保留原始信息，AI 识别的文字是辅助参考，可以人工修正
4. **错误类型标准化** → 方便按错因分类复习，这是错题集最有价值的维度
5. **掌握度量化** → 从简单的三级状态升级为 0-100 分数，AI 出题时能更精准地挑薄弱题
6. **间隔复习** → 根据掌握程度自动安排复习节奏，避免过度复习已掌握的内容，也避免遗忘薄弱知识点
7. **重复犯错检测** → 识别顽固错误模式，帮 AI 出题时精准打击

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
| 文件格式 | 仅 jpg / png / heic / webp | "不支持的文件格式，请上传图片" |
| 文件大小 | 单张 ≤ 20MB | "图片过大（超过 20MB），请压缩后重试" |
| 图片数量 | 单次 ≤ 10 张 | "一次最多上传 10 张图片" |
| 分辨率 | 最短边 ≥ 200px | "图片分辨率过低，可能影响识别效果"（警告，不阻止） |

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
| P4 | 错题编辑功能（修改已有错题） | ✅ 已完成 |
| P5 | PWA 支持 | ✅ 已完成 |
| P6 | 统计仪表盘 | ✅ 已完成 |
| P7 | 图片压缩优化 | ✅ 已完成 |
| P8 | 异步任务队列 | ✅ 已完成 |
| P9 | 数学公式渲染优化 | ✅ 已完成 |
| P10 | 任务列表增强（编辑/重新生成/反馈优化/切换归属） | ✅ 已完成 |
| P11 | 错题列表增强（移动到其他孩子/学科） | ✅ 已完成 |
| - | 产品介绍页面 | ✅ 已完成 |
| - | Tailscale 手机访问 | ✅ 已完成 |
