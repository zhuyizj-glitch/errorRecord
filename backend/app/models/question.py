"""错题数据模型"""

from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional
from enum import Enum


class Difficulty(str, Enum):
    EASY = "简单"
    MEDIUM = "中等"
    HARD = "较难"


class MasteryLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MasteryStatus(str, Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    MASTERED = "mastered"


class RedoRecord(BaseModel):
    date: date
    result: str  # "correct" | "wrong"
    note: Optional[str] = None


class StudentAnswer(BaseModel):
    detected: bool
    text: Optional[str] = None
    confidence: Optional[str] = None


class ErrorAnalysis(BaseModel):
    error_point: Optional[str] = None
    error_type: Optional[str] = None
    root_cause: Optional[str] = None
    suggestion: Optional[str] = None


class QuestionMetadata(BaseModel):
    topic: Optional[str] = None
    knowledge_points: list[str] = []
    difficulty: Optional[str] = None


class QuestionAnalysis(BaseModel):
    """图片中的单道题

    一张照片通常含多道题，AI 会把它们逐题拆开，每题对应一个本对象。
    """
    number: Optional[str] = None
    """题号，如 "10"。图中没标号则为 None。"""

    looks_correct: bool = False
    """AI 初判「看起来做对了没有」。**仅供家长参考**，不用于自动筛选 ——
    订正过的题看着对了，未必真的掌握。"""

    has_correction: bool = False
    """这道题有没有订正痕迹（划掉重写、红笔修改等）。
    有订正痕迹时 looks_correct 按订正前的作答判断。"""

    source_type: str = "印刷题"
    question_text: str = ""
    has_diagram: bool = False
    diagram_description: Optional[str] = None
    student_answer: StudentAnswer = Field(default_factory=lambda: StudentAnswer(detected=False))
    correct_answer: str = ""
    solution_steps: Optional[str] = None
    error_analysis: Optional[ErrorAnalysis] = None
    metadata: QuestionMetadata = Field(default_factory=QuestionMetadata)
    confidence: str = "medium"


class AnalyzeResult(BaseModel):
    """AI 分析返回结果

    一张图可能含多道题，所以题目是列表 —— 前端会列出每道题让用户逐题勾选入库。
    """
    subject: Optional[str] = None
    """AI 判断的学科（九门课之一）。上传时用户选的学科是凭印象挑的，
    看过题目内容之后 AI 判断更准，前端会据此自动更正任务的学科。"""

    questions: list[QuestionAnalysis] = []
    """图中拆出来的所有题目。只有一道题时列表长度为 1。"""


class QuestionCreate(BaseModel):
    """创建错题的请求

    注意：不包含图片字段。原图只是 LLM 分析的输入，分析完成后丢弃，
    保存的只有分析结果（题目、答案、解题过程、错因分析）。
    """
    child_id: str
    subject: str
    topic: str
    error_type: Optional[str] = None
    source_type: str
    difficulty: str
    error_date: date
    question_text: str
    correct_answer: str
    solution_steps: Optional[str] = None
    error_analysis: Optional[ErrorAnalysis] = None
    error_suggestion: Optional[str] = None
    parent_note: Optional[str] = None
    knowledge_points: list[str] = []
    tags: list[str] = []


class RedoRequest(BaseModel):
    """重做请求"""
    result: str  # "correct" | "wrong"
    note: Optional[str] = None
