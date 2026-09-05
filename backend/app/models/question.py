"""错题数据模型"""

from pydantic import BaseModel
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


class AnalyzeResult(BaseModel):
    """AI 分析返回结果"""
    source_type: str
    question_text: str
    has_diagram: bool = False
    diagram_description: Optional[str] = None
    student_answer: StudentAnswer
    correct_answer: str
    solution_steps: str
    error_analysis: Optional[ErrorAnalysis] = None
    metadata: QuestionMetadata
    confidence: str = "medium"


class QuestionCreate(BaseModel):
    """创建错题的请求"""
    child: str
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
    image_ids: list[str] = []  # 上传阶段返回的临时图片 ID


class RedoRequest(BaseModel):
    """重做请求"""
    result: str  # "correct" | "wrong"
    note: Optional[str] = None
