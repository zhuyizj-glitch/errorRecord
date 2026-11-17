"""错题 CRUD 接口"""

import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import timeutil
from app.models.question import QuestionCreate, RedoRequest
from app.services import file_ops, analyzer, llm
from app.services.review_scheduler import calculate_next_review
from app.api.routes.upload import TEMP_DIR
from app.api.deps import get_active_account, get_auth_service
from app.models.auth import Account
from app.services.auth_service import AuthService

router = APIRouter()


def _get_child(auth: AuthService, account_id: str, child_id: str, subject: str | None = None):
    with auth.db.connect() as connection:
        child = connection.execute(
            "SELECT id, name FROM children WHERE id = ? AND account_id = ?",
            (child_id, account_id),
        ).fetchone()
        if child and subject:
            enabled = connection.execute(
                "SELECT 1 FROM child_subjects WHERE child_id = ? AND subject = ? AND enabled = 1",
                (child_id, subject),
            ).fetchone()
            if not enabled:
                child = None
    if not child:
        raise HTTPException(status_code=404, detail="孩子或课程不存在")
    return child


def _find_local_question(
    account_id: str, child_id: str, subject: str, question_id: str
) -> dict:
    """在本地缓存里按 id 找错题，找不到抛 404。"""
    for q in file_ops.list_questions(account_id, child_id, subject):
        if q.get("id") == question_id:
            return q
    raise HTTPException(status_code=404, detail="错题不存在")


async def _load_for_update(
    storage, account_id: str, child_id: str, subject: str, question_id: str
) -> tuple[dict, str]:
    """
    读取待修改的错题，返回 (元数据, 正文)。

    可变状态以 IMA 为准：本地是缓存，可能落后（例如你在 IMA 客户端直接改过笔记）。
    读不到云端时退回本地缓存，保证断网也能操作。
    """
    target = _find_local_question(account_id, child_id, subject, question_id)
    data = await storage.read_authoritative(target.get("ima_note_id"))
    if data is None:
        data = file_ops.read_question(target["_file"])
    data.pop("_file", None)
    data.pop("_storage_id", None)
    body = data.pop("_body", "")
    return data, body


@router.post("/analyze")
async def analyze_images(
    image_ids: list[dict],
    account: Account = Depends(get_active_account),
):
    """调用 LLM 分析题目图片"""
    account_dir = (TEMP_DIR / account.id).resolve()
    paths = [
        path for img in image_ids
        if (path := Path(img.get("path", "")).resolve()).parent == account_dir and path.is_file()
    ]
    if not paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")
    try:
        result = await llm.analyze_images(paths)
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM API 调用失败: {e}")


@router.post("/questions")
async def create_question(
    q: QuestionCreate,
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """保存新错题"""
    question_id = uuid.uuid4().hex[:8]
    child = _get_child(auth, account.id, q.child_id, q.subject)

    # 注意：原始图片不落盘、不进 markdown。
    # 图片只是 LLM 分析的输入，分析结果（题目、答案、解题过程、错因、
    # 图形文字描述）才是要长期保存的内容。临时文件由 upload 模块按 TTL 回收。

    # 构建 frontmatter（新错题初始掌握度为 0）
    mastery_score = 0  # 新错题还没重做过，初始为 0
    mastery_level = "low"
    mastery_status = "new"

    frontmatter = {
        "id": question_id,
        "account_id": account.id,
        "child_id": q.child_id,
        "child_name": child["name"],
        "subject": q.subject,
        "topic": q.topic,
        "error_type": q.error_type,
        "source_type": q.source_type,
        "difficulty": q.difficulty,
        "error_date": q.error_date.isoformat(),
        "created_at": timeutil.today().isoformat(),
        "redo_count": 0,
        "correct_count": 0,      # 重做做对次数
        "wrong_count": 0,        # 重做做错次数
        "consecutive_correct": 0, # 当前连续做对次数
        "mastery_score": mastery_score,
        "mastery_level": mastery_level,
        "mastery_status": mastery_status,
        "repeat_streak": 0,
        "max_repeat_streak": 0,
        "repeat_pattern": False,
        "next_review_date": timeutil.today().isoformat(),
        "review_interval_days": 1,
        "total_reviews": 0,
        "error_suggestion": q.error_suggestion,
        "knowledge_points": q.knowledge_points,
        "tags": q.tags,
    }

    # 构建 body（纯文字：题目、答案、解题过程、错因分析、家长备注）
    body_parts = ["## 原题\n"]
    if q.question_text:
        body_parts.append(f"\n> **题目内容**：{q.question_text}\n")
    body_parts.append(f"\n## 正确答案\n\n{q.correct_answer}\n")
    if q.solution_steps:
        body_parts.append(f"\n## 解题过程\n\n{q.solution_steps}\n")
    if q.error_analysis:
        body_parts.append(f"\n## 错误分析\n")
        if q.error_analysis.error_point:
            body_parts.append(f"**错误点：** {q.error_analysis.error_point}\n")
        if q.error_analysis.root_cause:
            body_parts.append(f"**错因诊断：** {q.error_analysis.root_cause}\n")
        if q.error_analysis.suggestion:
            body_parts.append(f"**建议：** {q.error_analysis.suggestion}\n")

    if q.parent_note:
        body_parts.append(f"\n## 家长备注\n\n{q.parent_note}\n")

    body = "\n".join(body_parts)

    # 通过存储管理器保存（IMA + 本地双写）
    from app.services.storage_manager import get_storage_manager
    storage = get_storage_manager()
    storage_id = await storage.save_question(
        question_id=question_id,
        account_id=account.id,
        child_id=q.child_id,
        subject=q.subject,
        frontmatter=frontmatter,
        body=body,
    )

    return {
        "success": True,
        "id": question_id,
        "file": str(storage_id),
    }


@router.get("/questions")
async def list_questions(
    child_id: str = Query(...),
    subject: Optional[str] = Query(None),
    error_type: Optional[str] = Query(None),
    mastery_level: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """列出错题"""
    _get_child(auth, account.id, child_id, subject)
    questions = file_ops.list_questions(account.id, child_id, subject)

    # 筛选
    if error_type:
        questions = [q for q in questions if q.get("error_type") == error_type]
    if mastery_level:
        questions = [q for q in questions if q.get("mastery_level") == mastery_level]

    return {"questions": questions, "total": len(questions)}


@router.get("/questions/{question_id}")
async def get_question(
    question_id: str,
    child_id: str = Query(...),
    subject: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """获取单个错题详情"""
    # 通过 file_ops 查找文件
    _get_child(auth, account.id, child_id, subject)
    questions = file_ops.list_questions(account.id, child_id, subject)
    for q in questions:
        if q.get("id") == question_id:
            return file_ops.read_question(q["_file"])
    raise HTTPException(status_code=404, detail="错题不存在")


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: str,
    account: Account = Depends(get_active_account),
):
    """错题永久保留，通过掌握度控制复习频次。"""
    raise HTTPException(status_code=405, detail="错题不支持删除")


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: str,
    new_child_id: Optional[str] = Query(None),
    new_subject: Optional[str] = Query(None),
    child_id: str = Query(...),
    subject: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """修改错题的孩子/学科归属（移动文件）"""
    if not new_child_id and not new_subject:
        raise HTTPException(status_code=400, detail="至少需要指定 new_child_id 或 new_subject")

    # 校验归属与课程，再读当前状态（IMA 为准，本地缓存兜底）
    _get_child(auth, account.id, child_id, subject)
    from app.services.storage_manager import get_storage_manager
    storage = get_storage_manager()
    target = _find_local_question(account.id, child_id, subject, question_id)
    old_file = target["_file"]
    full_data, body = await _load_for_update(
        storage, account.id, child_id, subject, question_id
    )

    # 更新字段
    final_child_id = new_child_id or child_id
    final_subject = new_subject or subject
    final_child = _get_child(auth, account.id, final_child_id, final_subject)
    if new_child_id:
        full_data["child_id"] = new_child_id
        full_data["child_name"] = final_child["name"]
    if new_subject:
        full_data["subject"] = new_subject

    # 移动错题：变更孩子/学科时，本地缓存文件也要挪到新目录
    if final_child_id != child_id or final_subject != subject:
        from pathlib import Path as PathLib
        PathLib(old_file).unlink()
        new_file = file_ops.save_question(
            question_id, account.id, final_child_id, final_subject, full_data, body
        )
        # IMA 没有移动笔记的接口，云端笔记仍留在原文件夹，只有标题与元数据会更新
        ok = await storage.update_question(full_data, body, event={"type": "patch"})
        if not ok:
            raise HTTPException(status_code=503, detail="同步移动结果失败，请稍后重试")
        return {"success": True, "file": str(new_file)}

    ok = await storage.update_question(full_data, body, event={"type": "patch"})
    if not ok:
        raise HTTPException(status_code=503, detail="保存修改失败，请稍后重试")
    return {"success": True, "file": old_file}


@router.post("/questions/{question_id}/redo")
async def redo_question(
    question_id: str,
    req: RedoRequest,
    child_id: str = Query(...),
    subject: str = Query(...),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """提交重做结果，更新掌握度、间隔复习等"""
    from datetime import date
    from app.services.analyzer import calculate_mastery_score, mastery_level_from_score, mastery_status_from
    from app.services.review_scheduler import calculate_next_review

    # 校验归属与课程，再读当前状态（IMA 为准，本地缓存兜底）
    _get_child(auth, account.id, child_id, subject)
    from app.services.storage_manager import get_storage_manager
    storage = get_storage_manager()
    full_data, body = await _load_for_update(
        storage, account.id, child_id, subject, question_id
    )

    # 更新重做记录
    redo_count = full_data.get("redo_count", 0) + 1
    redo_history = full_data.get("redo_history", []) or []
    redo_history.append({
        "date": timeutil.today().isoformat(),
        "result": req.result,
        "note": req.note,
    })

    # 更新做对/做错计数
    correct_count = full_data.get("correct_count", 0)
    wrong_count = full_data.get("wrong_count", 0)
    consecutive_correct = full_data.get("consecutive_correct", 0)

    if req.result == "correct":
        correct_count += 1
        consecutive_correct += 1
    else:
        wrong_count += 1
        consecutive_correct = 0  # 做错则连续计数归零

    # 重新计算掌握度（新算法）
    mastery_score = calculate_mastery_score(
        correct_count=correct_count,
        wrong_count=wrong_count,
        consecutive_correct=consecutive_correct,
    )
    mastery_level = mastery_level_from_score(mastery_score, consecutive_correct)
    mastery_status = mastery_status_from(redo_count, mastery_level)

    # 计算下次复习日期
    current_interval = full_data.get("review_interval_days", 1)
    next_review, new_interval = calculate_next_review(mastery_level, req.result, current_interval)

    # 更新字段
    full_data["redo_count"] = redo_count
    full_data["correct_count"] = correct_count
    full_data["wrong_count"] = wrong_count
    full_data["consecutive_correct"] = consecutive_correct
    full_data["redo_history"] = redo_history
    full_data["last_redo_at"] = timeutil.today().isoformat()
    full_data["mastery_score"] = mastery_score
    full_data["mastery_level"] = mastery_level
    full_data["mastery_status"] = mastery_status
    full_data["next_review_date"] = next_review.isoformat()
    full_data["review_interval_days"] = new_interval
    full_data["total_reviews"] = full_data.get("total_reviews", 0) + 1

    # 以事件形式追加到 IMA（权威来源），本地缓存同步刷新
    ok = await storage.update_question(
        full_data,
        body,
        event={"type": "redo", "result": req.result, "note": req.note},
    )
    if not ok:
        raise HTTPException(status_code=503, detail="保存重做结果失败，请稍后重试")

    return {
        "success": True,
        "mastery_score": mastery_score,
        "mastery_level": mastery_level,
        "next_review_date": next_review.isoformat(),
    }
