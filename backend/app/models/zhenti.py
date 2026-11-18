"""真题数据模型（v2.0 · 三形态模型，2026-11-17 经六科原卷校验定稿）

真题库是账号级资源：不绑定孩子，账号下所有孩子共用；
薄弱点聚合与练习记录按孩子区分。

三种题目形态（question_form）：
- independent     独立小题：一题一考点（数学全部、语文默写/语用、历史政治单题）
- material_group  材料组题：共享材料/图，子题考点独立（地理选择组、历史政治材料题）
- passage         语篇整题：语篇与子题不可拆分，整篇练 + 难度评级（语文英语阅读/完形等）

组织轴：
- 历史 era（朝代/时期）+ 事件知识点
- 政治 module（主题）+ 知识点
- 英语语篇子题可双层打标（语法/词汇），供薄弱点精确匹配
"""

from pydantic import BaseModel, Field
from typing import Optional


QUESTION_FORMS = ("independent", "material_group", "passage")
RATINGS = ("简单", "中等", "较难")


class ZhentiSubQuestion(BaseModel):
    """材料组题 / 语篇整题的子题（各自独立打标，可单独调用）"""

    number: Optional[str] = None
    question_text: str = ""
    correct_answer: str = ""
    solution_steps: Optional[str] = None
    knowledge_points: list[str] = []
    era: Optional[str] = None      # 历史子题时代
    module: Optional[str] = None   # 政治子题主题


class ZhentiQuestionAnalysis(BaseModel):
    """AI 从真题卷拆出的题目单元"""

    number: Optional[str] = None
    question_form: str = "independent"
    question_type: Optional[str] = None
    rating: Optional[str] = None          # 语篇整题难度评级
    passage: Optional[str] = None         # 语篇/共享材料原文
    # independent 形态的顶层内容
    question_text: str = ""
    has_diagram: bool = False
    diagram_description: Optional[str] = None
    correct_answer: str = ""
    solution_steps: Optional[str] = None
    topic: Optional[str] = None
    knowledge_points: list[str] = []
    era: Optional[str] = None
    module: Optional[str] = None
    difficulty: str = "中等"
    confidence: str = "medium"
    sub_questions: list[ZhentiSubQuestion] = []


class ZhentiAnalyzeResult(BaseModel):
    subject: Optional[str] = None
    questions: list[ZhentiQuestionAnalysis] = []


class ZhentiImportRequest(BaseModel):
    subject: str
    year: str = Field(min_length=1, max_length=20)
    source: str = Field(min_length=1, max_length=120)
    stage: str = ""
    image_ids: list[dict]


class ZhentiSaveItem(BaseModel):
    """批量入库的题目单元（人工预览确认后）"""

    number: Optional[str] = None
    question_form: str = "independent"
    question_type: Optional[str] = None
    rating: Optional[str] = None
    passage: Optional[str] = None
    question_text: str = ""
    has_diagram: bool = False
    diagram_description: Optional[str] = None
    correct_answer: str = ""
    solution_steps: Optional[str] = None
    topic: Optional[str] = None
    knowledge_points: list[str] = []
    era: Optional[str] = None
    module: Optional[str] = None
    difficulty: str = "中等"
    sub_questions: list[ZhentiSubQuestion] = []


class ZhentiSaveRequest(BaseModel):
    subject: str
    year: str = Field(min_length=1, max_length=20)
    source: str = Field(min_length=1, max_length=120)
    stage: str = ""
    questions: list[ZhentiSaveItem] = Field(min_length=1)


class ZhentiPatchRequest(BaseModel):
    """修正题库条目（真题可编辑）"""

    question_text: Optional[str] = None
    correct_answer: Optional[str] = None
    solution_steps: Optional[str] = None
    topic: Optional[str] = None
    knowledge_points: Optional[list[str]] = None
    difficulty: Optional[str] = None
    year: Optional[str] = None
    source: Optional[str] = None
    number: Optional[str] = None
    question_type: Optional[str] = None
    rating: Optional[str] = None
    era: Optional[str] = None
    module: Optional[str] = None
    stage: Optional[str] = None
    passage: Optional[str] = None
    sub_questions: Optional[list[ZhentiSubQuestion]] = None


class ZhentiPracticeRequest(BaseModel):
    child_id: str
    result: str  # "correct" | "wrong"
    note: Optional[str] = None
    sub_number: Optional[str] = None  # 材料组题/语篇可记录到具体子题


class ZhentiToMistakeRequest(BaseModel):
    child_id: str
    subject: Optional[str] = None
    error_type: Optional[str] = None
    parent_note: Optional[str] = None
    sub_number: Optional[str] = None  # 指定子题转错题（缺省整题/顶层）
