# v2.0 设计：真题针对性复习

> 日期：2026-11-17
> 状态：已确认，实施中

## 目标

导入往年真题，结合每个孩子的错题薄弱点，针对性地挑真题练习。
做错的真题可一键转为错题，进入现有掌握度复习循环。

## 关键决策

1. **导入形式**：拍照 / 扫描 PDF。复用现有「图片 → AI 拆题 → 人工确认」链路，
   新增 PDF 逐页转图（pypdfium2，无系统依赖）。
2. **真题库是账号级资源**：不绑定孩子，家长导入一次，账号下所有孩子共用；
   薄弱点与练习记录按孩子区分。
3. **存储**：`vault/accounts/{账号}/zhenti/{学科}/*.md`，LaTeX 原样保存。
   IMA 已弃用，真题只走文件存储，不进 IMA 事件模型。
4. **真题可编辑、可删除**：与错题「保存后不可改」不同——真题是题库素材，
   不是学习记录，导错了要能修正。
5. **知识点匹配**：归一化后精确匹配。导入时把库内已有知识点词汇表注入提示词，
   让 AI 尽量复用标签，提高匹配率。无匹配的薄弱点显式暴露「暂无匹配真题」。

## 数据模型

真题 frontmatter：id / account_id / subject / year / source / number / topic /
knowledge_points / difficulty / has_diagram / diagram_description / created_at /
practice_count / correct_count / wrong_count / last_practice_at /
practice_history（每条含 child_id）/ converted_to（转错题记录）。

文件名：`来源·学科·年份-id.md`（沿用全角间隔号约定，id 结尾供后缀定位）。

正文模板：`## 原题` / `## 参考答案` / `## 解题分析`，
与 body_parser 的段落别名兼容，decorate_with_sections 直接复用。

## 薄弱点与推荐算法

- 薄弱度权重：孩子未掌握（mastery_status != mastered）错题上
  按知识点聚合 Σ(1 − mastery_score/100)，附题目数与平均掌握度。
- 真题得分：命中薄弱点的权重和；同分按「该孩子练得少的优先」，再按年份新优先。
- 推荐结果附带 matched_points，前端展示「针对薄弱点：XXX」。

## 接口（/api/zhenti/*）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /import | 创建真题分析任务（每图一个，kind=zhenti，串行锁共用） |
| GET | /tasks | 本账号真题任务列表 |
| POST | /questions | 批量保存勾选的真题 |
| GET | /questions | 题库列表（subject/year/knowledge_point 筛选） |
| GET | /questions/{id} | 详情（含结构化段落） |
| PATCH | /questions/{id} | 修正内容或标签 |
| DELETE | /questions/{id} | 删除题库条目 |
| POST | /questions/{id}/practice | 提交练习结果（按孩子记录） |
| POST | /questions/{id}/to-mistake | 转为指定孩子的错题 |
| GET | /weak-points | 孩子薄弱知识点排行 |
| GET | /recommend | 针对性真题推荐 |

任务复用 TaskManager（新增 kind/meta 字段，向后兼容）与 /api/tasks/{id} 查询/删除。

## 前端

新增「真题」导航页，三个标签页：
- **导入**：上传（支持 PDF）+ 年份/来源/学科 → 任务进度 → 预览勾选（可改知识点）→ 批量入库
- **题库**：筛选浏览、详情（KaTeX 渲染）、编辑、删除
- **针对性练习**：薄弱点排行 → 推荐真题 → 出题/显示答案/自评 → 做错可转错题

## 测试

zhenti_ops 文件读写与隔离、匹配算法、API 全流程（mock LLM）。
部署前在服务器 Docker 环境跑全量套件。

## 版本

后端 FastAPI version 与前端 package.json 升至 2.0.0。
