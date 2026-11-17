"""真题库接口（v2.0）

真题库是账号级资源：导入一次，账号下所有孩子共用。
薄弱点聚合与练习记录按孩子区分；做错的真题可转为该孩子的错题，
进入现有掌握度复习循环。
"""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app.api.deps import get_active_account, get_auth_service
from app.api.routes.children import SUBJECTS
from app.api.routes.questions import _get_child, create_question
from app.api.routes.tasks import _analysis_lock
from app.api.routes.upload import TEMP_DIR
from app.core import timeutil
from app.models.auth import Account
from app.models.question import QuestionCreate
from app.models.zhenti import (
    ZhentiImportRequest,
    ZhentiPatchRequest,
    ZhentiPracticeRequest,
    ZhentiSaveRequest,
    ZhentiToMistakeRequest,
)
from app.services import file_ops, llm, zhenti_match, zhenti_ops
from app.services.auth_service import AuthService
from app.services.body_parser import decorate_with_sections, parse_question_body
from app.services.task_manager import TaskStatus, task_manager

router = APIRouter()


def _require_subject(subject: str) -> None:
    if subject not in SUBJECTS:
        raise HTTPException(status_code=400, detail="学科不在可选范围内")


def _require_child(auth: AuthService, account_id: str, child_id: str) -> None:
    with auth.db.connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM children WHERE id = ? AND account_id = ?",
            (child_id, account_id),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="孩子不存在")


def _account_questions(auth: AuthService, account_id: str) -> list[dict]:
    """账号下所有孩子的错题（知识点词汇表用，不带正文）"""
    with auth.db.connect() as connection:
        child_ids = [
            row["id"] for row in connection.execute(
                "SELECT id FROM children WHERE account_id = ?", (account_id,)
            )
        ]
    questions: list[dict] = []
    for child_id in child_ids:
        questions.extend(file_ops.list_questions(account_id, child_id))
    return questions


def _load_zhenti(account_id: str, zhenti_id: str, subject: Optional[str]) -> dict:
    path = zhenti_ops.find_zhenti_file(account_id, zhenti_id, subject)
    if not path:
        raise HTTPException(status_code=404, detail="真题不存在")
    return zhenti_ops.read_zhenti(str(path))


async def _run_exam_analysis(task_id: str, image_paths: list[Path], vocab: list[str]):
    """后台执行真题分析（与错题分析共用串行锁，避免并发打 AI 服务）"""
    async with _analysis_lock:
        try:
            await task_manager.update_status(task_id, TaskStatus.PROCESSING)
            result = await llm.analyze_exam_images(image_paths, vocab)
            await task_manager.update_status(task_id, TaskStatus.COMPLETED, result=result)
        except Exception as e:
            await task_manager.update_status(task_id, TaskStatus.FAILED, error=str(e))


@router.post("/zhenti/import")
async def import_zhenti(
    req: ZhentiImportRequest,
    background_tasks: BackgroundTasks,
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """创建真题分析任务（每页一个任务，立即返回，后台串行分析）"""
    _require_subject(req.subject)

    account_dir = (TEMP_DIR / account.id).resolve()
    valid_ids = []
    valid_paths = []
    for img in req.image_ids:
        path = Path(img.get("path", "")).resolve()
        if path.parent == account_dir and path.is_file():
            valid_ids.append(img)
            valid_paths.append(path)
    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")

    # 注入已有知识点词汇表，让 AI 尽量复用标签，提高薄弱点匹配率
    vocab = zhenti_match.knowledge_vocab(
        _account_questions(auth, account.id),
        zhenti_ops.list_zhenti(account.id),
    )

    task = task_manager.create_task(
        account.id, "", req.subject, valid_ids,
        kind="zhenti", meta={"year": req.year.strip(), "source": req.source.strip()},
    )
    background_tasks.add_task(_run_exam_analysis, task.id, valid_paths, vocab)
    return {"task_id": task.id, "status": task.status.value, "created_at": task.created_at}


@router.get("/zhenti/tasks")
async def list_zhenti_tasks(account: Account = Depends(get_active_account)):
    """本账号的真题分析任务（按创建时间倒序）"""
    tasks = [t for t in task_manager.list_tasks(account.id) if t.get("kind") == "zhenti"]
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/zhenti/questions")
async def save_zhenti_questions(
    req: ZhentiSaveRequest,
    account: Account = Depends(get_active_account),
):
    """批量保存人工确认后的真题"""
    _require_subject(req.subject)
    saved_ids = []
    for item in req.questions:
        zhenti_id = uuid.uuid4().hex[:8]
        data = item.model_dump()
        frontmatter = zhenti_ops.new_frontmatter(
            zhenti_id, account.id, req.subject, req.year.strip(), req.source.strip(), data
        )
        zhenti_ops.save_zhenti(
            zhenti_id, account.id, req.subject, frontmatter, zhenti_ops.build_body(data)
        )
        saved_ids.append(zhenti_id)
    return {"success": True, "saved": len(saved_ids), "ids": saved_ids}


@router.get("/zhenti/questions")
async def list_zhenti_questions(
    subject: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    knowledge_point: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """题库列表（支持学科/年份/知识点筛选）"""
    items = zhenti_ops.list_zhenti(account.id, subject)
    if year:
        items = [i for i in items if str(i.get("year")) == year]
    if knowledge_point:
        query = zhenti_match.normalize_kp(knowledge_point)
        items = [
            i for i in items
            if any(query in zhenti_match.normalize_kp(kp) for kp in i.get("knowledge_points") or [])
        ]
    items.sort(key=lambda i: (str(i.get("year") or ""), i.get("created_at") or ""), reverse=True)
    return {"questions": items, "total": len(items)}


@router.get("/zhenti/questions/{zhenti_id}")
async def get_zhenti_question(
    zhenti_id: str,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """真题详情（含结构化段落，供前端渲染）"""
    data = _load_zhenti(account.id, zhenti_id, subject)
    return decorate_with_sections(data)


@router.patch("/zhenti/questions/{zhenti_id}")
async def patch_zhenti_question(
    zhenti_id: str,
    req: ZhentiPatchRequest,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """修正真题内容或标签（真题是题库素材，允许编辑）"""
    data = _load_zhenti(account.id, zhenti_id, subject)
    body = data.pop("_body", "")
    old_file = data.pop("_file")
    parsed = parse_question_body(body)

    # 内容字段：以现有正文为底，覆盖请求里提供的部分，再重建正文
    content = {
        "question_text": req.question_text if req.question_text is not None else parsed["question"],
        "correct_answer": req.correct_answer if req.correct_answer is not None else parsed["answer"],
        "solution_steps": req.solution_steps if req.solution_steps is not None else parsed["solution"],
        "has_diagram": data.get("has_diagram"),
        "diagram_description": data.get("diagram_description"),
    }
    content_changed = any(
        getattr(req, field) is not None
        for field in ("question_text", "correct_answer", "solution_steps")
    )

    for field in ("topic", "knowledge_points", "difficulty", "year", "source", "number"):
        value = getattr(req, field)
        if value is not None:
            data[field] = value

    if content_changed:
        body = zhenti_ops.build_body(content)
    zhenti_ops.update_zhenti(old_file, data, body)

    # 年份/来源变了，文件名也要跟着变（文件名含这两段）
    if req.year is not None or req.source is not None:
        new_path = Path(old_file).parent / zhenti_ops._generate_filename(
            zhenti_id, data, data.get("subject", "")
        )
        if new_path != Path(old_file):
            Path(old_file).rename(new_path)
            old_file = str(new_path)
    return {"success": True, "file": old_file}


@router.delete("/zhenti/questions/{zhenti_id}")
async def delete_zhenti_question(
    zhenti_id: str,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """删除题库条目（真题可删，与错题的永久保留约定不同）"""
    data = _load_zhenti(account.id, zhenti_id, subject)
    zhenti_ops.delete_zhenti(data["_file"])
    return {"success": True}


@router.post("/zhenti/questions/{zhenti_id}/practice")
async def practice_zhenti(
    zhenti_id: str,
    req: ZhentiPracticeRequest,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """提交练习结果（按孩子记录，同一道题不同孩子各自计数）"""
    if req.result not in ("correct", "wrong"):
        raise HTTPException(status_code=400, detail="result 必须是 correct 或 wrong")
    _require_child(auth, account.id, req.child_id)

    data = _load_zhenti(account.id, zhenti_id, subject)
    body = data.pop("_body", "")
    file_path = data.pop("_file")

    history = data.get("practice_history") or []
    history.append({
        "date": timeutil.today().isoformat(),
        "child_id": req.child_id,
        "result": req.result,
        "note": req.note,
    })
    data["practice_history"] = history
    data["practice_count"] = int(data.get("practice_count", 0)) + 1
    if req.result == "correct":
        data["correct_count"] = int(data.get("correct_count", 0)) + 1
    else:
        data["wrong_count"] = int(data.get("wrong_count", 0)) + 1
    data["last_practice_at"] = timeutil.today().isoformat()

    zhenti_ops.update_zhenti(file_path, data, body)
    return {
        "success": True,
        "practice_count": data["practice_count"],
        "child_practice_count": zhenti_match.child_practice_count(data, req.child_id),
    }


@router.post("/zhenti/questions/{zhenti_id}/to-mistake")
async def zhenti_to_mistake(
    zhenti_id: str,
    req: ZhentiToMistakeRequest,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """把真题转为指定孩子的错题，进入掌握度复习循环"""
    data = _load_zhenti(account.id, zhenti_id, subject)
    final_subject = req.subject or data.get("subject", "")
    child = _get_child(auth, account.id, req.child_id, final_subject)
    parsed = parse_question_body(data.get("_body", ""))

    number = data.get("number") or ""
    default_note = f"来自真题：{data.get('source', '')}（{data.get('year', '')}）"
    if number:
        default_note += f" 第{number}题"

    question = QuestionCreate(
        child_id=req.child_id,
        subject=final_subject,
        topic=data.get("topic") or "真题练习",
        error_type=req.error_type,
        source_type="印刷题",
        difficulty=data.get("difficulty") or "中等",
        error_date=timeutil.today(),
        question_text=parsed["question"] or parsed["raw"],
        correct_answer=parsed["answer"],
        solution_steps=parsed["solution"] or None,
        parent_note=req.parent_note or default_note,
        knowledge_points=data.get("knowledge_points") or [],
        tags=["真题转化"],
    )
    # 复用错题创建的全部逻辑（初始掌握度、复习计划、存储写入）
    created = await create_question(question, account, auth)

    converted = data.get("converted_to") or []
    converted.append({
        "child_id": req.child_id,
        "child_name": child["name"],
        "question_id": created["id"],
        "date": timeutil.today().isoformat(),
    })
    data["converted_to"] = converted
    body = data.pop("_body", "")
    file_path = data.pop("_file")
    zhenti_ops.update_zhenti(file_path, data, body)

    return {"success": True, "question_id": created["id"], "child_name": child["name"]}


@router.get("/zhenti/weak-points")
async def get_weak_points(
    child_id: str = Query(...),
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """孩子的薄弱知识点排行（未掌握错题按知识点聚合）"""
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id, subject)
    weak = zhenti_match.collect_weak_points(questions)
    return {"weak_points": weak, "total": len(weak)}


@router.get("/zhenti/recommend")
async def recommend_zhenti(
    child_id: str = Query(...),
    subject: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """按薄弱点推荐真题；无匹配的薄弱点显式返回，暴露题库缺口"""
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id, subject)
    weak = zhenti_match.collect_weak_points(questions)
    bank = zhenti_ops.list_zhenti(account.id, subject)
    recommendations = zhenti_match.recommend(weak, bank, child_id, subject=subject, limit=limit)

    bank_kps = {
        zhenti_match.normalize_kp(kp)
        for item in bank for kp in item.get("knowledge_points") or []
    }
    unmatched = [w["knowledge_point"] for w in weak if w["knowledge_point"] not in bank_kps]
    return {
        "weak_points": weak,
        "unmatched_points": unmatched,
        "recommendations": recommendations,
        "total": len(recommendations),
    }
