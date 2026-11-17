"""真题数据模型（v2.0）

真题库是账号级资源：不绑定孩子，账号下所有孩子共用；
薄弱点聚合与练习记录按孩子区分。
"""

from pydantic import BaseModel, Field
from typing import Optional


class ZhentiQuestionAnalysis(BaseModel):
    """AI 从真题卷拆出的单道题（无学生作答，与错题分析区分）"""

    number: Optional[str] = None
    question_text: str = ""
    has_diagram: bool = False
    diagram_description: Optional[str] = None
    correct_answer: str = ""
    solution_steps: Optional[str] = None
    topic: Optional[str] = None
    knowledge_points: list[str] = []
    difficulty: str = "中等"
    confidence: str = "medium"


class ZhentiAnalyzeResult(BaseModel):
    """真题分析结果：一张图（一页）可能含多道题"""

    subject: Optional[str] = None
    questions: list[ZhentiQuestionAnalysis] = []


class ZhentiImportRequest(BaseModel):
    """创建真题分析任务"""

    subject: str
    year: str = Field(min_length=1, max_length=20)
    source: str = Field(min_length=1, max_length=120)
    image_ids: list[dict]


class ZhentiSaveItem(BaseModel):
    """批量入库的单道真题（人工预览确认后的内容）"""

    number: Optional[str] = None
    question_text: str = Field(min_length=1)
    has_diagram: bool = False
    diagram_description: Optional[str] = None
    correct_answer: str = ""
    solution_steps: Optional[str] = None
    topic: Optional[str] = None
    knowledge_points: list[str] = []
    difficulty: str = "中等"


class ZhentiSaveRequest(BaseModel):
    subject: str
    year: str = Field(min_length=1, max_length=20)
    source: str = Field(min_length=1, max_length=120)
    questions: list[ZhentiSaveItem] = Field(min_length=1)


class ZhentiPatchRequest(BaseModel):
    """修正题库条目（真题可编辑，与错题的不可变约定不同）"""

    question_text: Optional[str] = None
    correct_answer: Optional[str] = None
    solution_steps: Optional[str] = None
    topic: Optional[str] = None
    knowledge_points: Optional[list[str]] = None
    difficulty: Optional[str] = None
    year: Optional[str] = None
    source: Optional[str] = None
    number: Optional[str] = None


class ZhentiPracticeRequest(BaseModel):
    child_id: str
    result: str  # "correct" | "wrong"
    note: Optional[str] = None


class ZhentiToMistakeRequest(BaseModel):
    """把做错的真题转为指定孩子的错题"""

    child_id: str
    subject: Optional[str] = None  # 缺省用真题自身学科
    error_type: Optional[str] = None
    parent_note: Optional[str] = None
