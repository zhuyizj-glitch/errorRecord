"""真题库接口（v2.0 · 三形态 + 时代/主题轴）"""

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
    ZhentiImportRequest, ZhentiPatchRequest, ZhentiPracticeRequest,
    ZhentiSaveRequest, ZhentiToMistakeRequest,
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
    with auth.db.connect() as connection:
        child_ids = [r["id"] for r in connection.execute(
            "SELECT id FROM children WHERE account_id = ?", (account_id,))]
    questions: list[dict] = []
    for child_id in child_ids:
        questions.extend(file_ops.list_questions(account_id, child_id))
    return questions


def _load_zhenti(account_id: str, zhenti_id: str, subject: Optional[str]) -> dict:
    path = zhenti_ops.find_zhenti_file(account_id, zhenti_id, subject)
    if not path:
        raise HTTPException(status_code=404, detail="真题不存在")
    return zhenti_ops.read_zhenti(str(path))


async def _run_exam_analysis(task_id: str, image_paths: list[Path], vocab: list[str], subject: str):
    async with _analysis_lock:
        try:
            await task_manager.update_status(task_id, TaskStatus.PROCESSING)
            result = await llm.analyze_exam_images(image_paths, vocab, subject)
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
    """创建真题分析任务（每页一个，分学科提示词，后台串行）"""
    _require_subject(req.subject)
    account_dir = (TEMP_DIR / account.id).resolve()
    valid_ids, valid_paths = [], []
    for img in req.image_ids:
        path = Path(img.get("path", "")).resolve()
        if path.parent == account_dir and path.is_file():
            valid_ids.append(img)
            valid_paths.append(path)
    if not valid_paths:
        raise HTTPException(status_code=400, detail="没有找到有效的图片文件")

    vocab = zhenti_match.knowledge_vocab(
        _account_questions(auth, account.id), zhenti_ops.list_zhenti(account.id))
    task = task_manager.create_task(
        account.id, "", req.subject, valid_ids,
        kind="zhenti", meta={"year": req.year.strip(), "source": req.source.strip()})
    background_tasks.add_task(_run_exam_analysis, task.id, valid_paths, vocab, req.subject)
    return {"task_id": task.id, "status": task.status.value, "created_at": task.created_at}


@router.get("/zhenti/tasks")
async def list_zhenti_tasks(account: Account = Depends(get_active_account)):
    tasks = [t for t in task_manager.list_tasks(account.id) if t.get("kind") == "zhenti"]
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/zhenti/questions")
async def save_zhenti_questions(
    req: ZhentiSaveRequest, account: Account = Depends(get_active_account),
):
    """批量保存人工确认后的真题（三形态）"""
    _require_subject(req.subject)
    saved_ids = []
    for item in req.questions:
        zhenti_id = uuid.uuid4().hex[:8]
        data = item.model_dump()
        fm = zhenti_ops.new_frontmatter(
            zhenti_id, account.id, req.subject, req.year.strip(), req.source.strip(), data)
        zhenti_ops.save_zhenti(zhenti_id, account.id, req.subject, fm, zhenti_ops.build_body(data))
        saved_ids.append(zhenti_id)
    return {"success": True, "saved": len(saved_ids), "ids": saved_ids}


@router.get("/zhenti/questions")
async def list_zhenti_questions(
    subject: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    knowledge_point: Optional[str] = Query(None),
    era: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    question_form: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """题库列表（学科/年份/知识点/时代/主题/形态/题型筛选）"""
    items = zhenti_ops.list_zhenti(account.id, subject)
    if year:
        items = [i for i in items if str(i.get("year")) == year]
    if era:
        items = [i for i in items if i.get("era") == era or any(
            s.get("era") == era for s in i.get("sub_questions") or [])]
    if module:
        items = [i for i in items if i.get("module") == module or any(
            s.get("module") == module for s in i.get("sub_questions") or [])]
    if question_form:
        items = [i for i in items if i.get("question_form", "independent") == question_form]
    if question_type:
        items = [i for i in items if i.get("question_type") == question_type]
    if knowledge_point:
        query = zhenti_match.normalize_kp(knowledge_point)
        def hit(i):
            kps = list(i.get("knowledge_points") or [])
            for s in i.get("sub_questions") or []:
                kps += s.get("knowledge_points") or []
            return any(query in zhenti_match.normalize_kp(k) for k in kps)
        items = [i for i in items if hit(i)]
    items.sort(key=lambda i: (str(i.get("year") or ""), i.get("created_at") or ""), reverse=True)
    return {"questions": items, "total": len(items)}


@router.get("/zhenti/dimensions")
async def get_dimensions(
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """题库可用筛选维度：历史时代轴 / 政治主题轴 / 语篇题型与评级"""
    items = zhenti_ops.list_zhenti(account.id, subject)
    eras, modules, types, ratings = set(), set(), set(), set()
    for i in items:
        if i.get("era"):
            eras.add(i["era"])
        if i.get("module"):
            modules.add(i["module"])
        if i.get("question_type"):
            types.add(i["question_type"])
        if i.get("rating"):
            ratings.add(i["rating"])
        for s in i.get("sub_questions") or []:
            if s.get("era"):
                eras.add(s["era"])
            if s.get("module"):
                modules.add(s["module"])
    return {"eras": sorted(eras), "modules": sorted(modules),
            "question_types": sorted(types), "ratings": sorted(ratings)}


@router.get("/zhenti/questions/{zhenti_id}")
async def get_zhenti_question(
    zhenti_id: str, subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    data = _load_zhenti(account.id, zhenti_id, subject)
    return decorate_with_sections(data)


@router.patch("/zhenti/questions/{zhenti_id}")
async def patch_zhenti_question(
    zhenti_id: str, req: ZhentiPatchRequest,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    """修正真题内容/标签/形态字段"""
    data = _load_zhenti(account.id, zhenti_id, subject)
    body = data.pop("_body", "")
    old_file = data.pop("_file")
    form = data.get("question_form", "independent")

    # 顶层内容字段（independent）
    parsed = parse_question_body(body)
    content_changed = any(getattr(req, f) is not None for f in
                          ("question_text", "correct_answer", "solution_steps"))
    if form == "independent" and content_changed:
        content = {
            "question_text": req.question_text if req.question_text is not None else parsed["question"],
            "correct_answer": req.correct_answer if req.correct_answer is not None else parsed["answer"],
            "solution_steps": req.solution_steps if req.solution_steps is not None else parsed["solution"],
            "has_diagram": data.get("has_diagram"),
            "diagram_description": data.get("diagram_description"),
        }
        body = zhenti_ops.build_body(content)

    for field in ("topic", "knowledge_points", "difficulty", "year", "source", "number",
                  "question_type", "rating", "era", "module"):
        value = getattr(req, field)
        if value is not None:
            data[field] = value

    # 语篇/材料组：passage 与 sub_questions 可整体更新
    group_changed = False
    if req.passage is not None:
        data["passage"] = req.passage
        group_changed = True
    if req.sub_questions is not None:
        data["sub_questions"] = [s.model_dump() for s in req.sub_questions]
        group_changed = True
    if form in ("material_group", "passage") and group_changed:
        body = zhenti_ops.build_body(data)

    zhenti_ops.update_zhenti(old_file, data, body)
    if req.year is not None or req.source is not None:
        new_path = Path(old_file).parent / zhenti_ops._generate_filename(
            zhenti_id, data, data.get("subject", ""))
        if new_path != Path(old_file):
            Path(old_file).rename(new_path)
            old_file = str(new_path)
    return {"success": True, "file": old_file}


@router.delete("/zhenti/questions/{zhenti_id}")
async def delete_zhenti_question(
    zhenti_id: str, subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
):
    data = _load_zhenti(account.id, zhenti_id, subject)
    zhenti_ops.delete_zhenti(data["_file"])
    return {"success": True}


@router.post("/zhenti/questions/{zhenti_id}/practice")
async def practice_zhenti(
    zhenti_id: str, req: ZhentiPracticeRequest,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    if req.result not in ("correct", "wrong"):
        raise HTTPException(status_code=400, detail="result 必须是 correct 或 wrong")
    _require_child(auth, account.id, req.child_id)
    data = _load_zhenti(account.id, zhenti_id, subject)
    body = data.pop("_body", "")
    file_path = data.pop("_file")
    history = data.get("practice_history") or []
    history.append({
        "date": timeutil.today().isoformat(), "child_id": req.child_id,
        "result": req.result, "note": req.note, "sub_number": req.sub_number,
    })
    data["practice_history"] = history
    data["practice_count"] = int(data.get("practice_count", 0)) + 1
    if req.result == "correct":
        data["correct_count"] = int(data.get("correct_count", 0)) + 1
    else:
        data["wrong_count"] = int(data.get("wrong_count", 0)) + 1
    data["last_practice_at"] = timeutil.today().isoformat()
    zhenti_ops.update_zhenti(file_path, data, body)
    return {"success": True, "practice_count": data["practice_count"],
            "child_practice_count": zhenti_match.child_practice_count(data, req.child_id)}


@router.post("/zhenti/questions/{zhenti_id}/to-mistake")
async def zhenti_to_mistake(
    zhenti_id: str, req: ZhentiToMistakeRequest,
    subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """把真题（或指定子题）转为指定孩子的错题"""
    data = _load_zhenti(account.id, zhenti_id, subject)
    final_subject = req.subject or data.get("subject", "")
    child = _get_child(auth, account.id, req.child_id, final_subject)

    number = data.get("number") or ""
    kps = data.get("knowledge_points") or []
    if req.sub_number:
        sub = next((s for s in data.get("sub_questions") or []
                    if str(s.get("number")) == str(req.sub_number)), None)
        if not sub:
            raise HTTPException(status_code=404, detail="子题不存在")
        q_text = sub.get("question_text", "")
        answer = sub.get("correct_answer", "")
        solution = sub.get("solution_steps")
        kps = sub.get("knowledge_points") or kps
        number = sub.get("number") or number
    else:
        parsed = parse_question_body(data.get("_body", ""))
        q_text = parsed["question"] or parsed["raw"]
        answer = parsed["answer"]
        solution = parsed["solution"] or None

    default_note = f"来自真题：{data.get('source', '')}（{data.get('year', '')}）"
    if number:
        default_note += f" 第{number}题"
    question = QuestionCreate(
        child_id=req.child_id, subject=final_subject,
        topic=data.get("topic") or "真题练习", error_type=req.error_type,
        source_type="印刷题", difficulty=data.get("difficulty") or "中等",
        error_date=timeutil.today(), question_text=q_text, correct_answer=answer,
        solution_steps=solution, parent_note=req.parent_note or default_note,
        knowledge_points=kps, tags=["真题转化"])
    created = await create_question(question, account, auth)

    converted = data.get("converted_to") or []
    converted.append({"child_id": req.child_id, "child_name": child["name"],
                      "question_id": created["id"], "sub_number": req.sub_number,
                      "date": timeutil.today().isoformat()})
    data["converted_to"] = converted
    body = data.pop("_body", "")
    file_path = data.pop("_file")
    zhenti_ops.update_zhenti(file_path, data, body)
    return {"success": True, "question_id": created["id"], "child_name": child["name"]}


@router.get("/zhenti/weak-points")
async def get_weak_points(
    child_id: str = Query(...), subject: Optional[str] = Query(None),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id, subject)
    weak = zhenti_match.collect_weak_points(questions)
    return {"weak_points": weak, "total": len(weak)}


@router.get("/zhenti/recommend")
async def recommend_zhenti(
    child_id: str = Query(...),
    subject: Optional[str] = Query(None),
    era: Optional[str] = Query(None),
    module: Optional[str] = Query(None),
    question_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    """薄弱点推荐（子题级匹配）+ 时代/主题专项切片 + 语篇整题梯度列表"""
    _require_child(auth, account.id, child_id)
    questions = file_ops.list_questions(account.id, child_id, subject)
    weak = zhenti_match.collect_weak_points(questions)
    bank = zhenti_ops.list_zhenti(account.id, subject)
    recommendations = zhenti_match.recommend(
        weak, bank, child_id, subject=subject, era=era, module=module, limit=limit)

    bank_kps = set()
    for item in bank:
        for unit in zhenti_match.matchable_units(item):
            for raw in unit["kp"]:
                bank_kps.add(zhenti_match.normalize_kp(raw))
    unmatched = [w["knowledge_point"] for w in weak if w["knowledge_point"] not in bank_kps]

    passages = zhenti_match.list_passages(bank, subject=subject, question_type=question_type)
    return {"weak_points": weak, "unmatched_points": unmatched,
            "recommendations": recommendations, "passages": passages,
            "total": len(recommendations)}
