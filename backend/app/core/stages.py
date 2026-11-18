"""学习阶段词汇表与排序（v2.0）

阶段以考卷为准：导入时指定整卷阶段，所有题目继承。
阶段有自然先后顺序，推荐时只推「阶段 ≤ 孩子当前阶段」的题，避免超纲。

每学期内约定顺序：月考1 < 月考2 < 期中 < 月考3 < 月考4 < 期末。
（月考与期中的相对位置按常见教学安排约定；如学校实际不同，可调整本表顺序。）
"""

_GRADES = ["高一", "高二", "高三"]
_SEMESTERS = ["上", "下"]
_EXAMS = ["月考1", "月考2", "期中", "月考3", "月考4", "期末"]

# 完整阶段序列（索引即进度 rank）
STAGES: list[str] = [
    f"{g}{s}{e}" for g in _GRADES for s in _SEMESTERS for e in _EXAMS
] + ["高考模拟"]

_RANK = {stage: i for i, stage in enumerate(STAGES)}


def stage_rank(stage) -> int:
    """阶段的进度序号；未知/空阶段返回 -1（视为最早，永远可推荐）。"""
    if not stage:
        return -1
    return _RANK.get(str(stage).strip(), -1)


def is_valid_stage(stage) -> bool:
    return bool(stage) and str(stage).strip() in _RANK
