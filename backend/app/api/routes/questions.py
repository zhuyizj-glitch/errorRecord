"""错题 CRUD 接口"""

import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.question import QuestionCreate, RedoRequest
from app.services import file_ops, analyzer, llm
from app.services.review_scheduler import calculate_next_review
from app.core.config import settings

router = APIRouter()


@router.post("/analyze")
async def analyze_images(image_ids: list[dict]):
    """调用 LLM 分析题目图片"""
    paths = [Path(img["path"]) for img in image_ids if Path(img["path"]).exists()]
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
async def create_question(q: QuestionCreate):
    """保存新错题"""
    question_id = uuid.uuid4().hex[:8]

    # 保存图片到 vault
    image_paths = []
    for img_id_info in q.image_ids:
        # img_id_info 可以是 image_id 字符串或 dict
        if isinstance(img_id_info, dict):
            src = Path(img_id_info.get("path", ""))
            orig_name = img_id_info.get("filename", "image.jpg")
        else:
            src = Path(f"/tmp/mistakes_uploads/{img_id_info}.*")
            orig_name = "image.jpg"

        if src.exists():
            dest = file_ops.save_image(
                src.read_bytes(), q.child, q.subject, question_id, orig_name
            )
            image_paths.append(dest)

    # 构建 frontmatter（新错题初始掌握度为 0）
    mastery_score = 0  # 新错题还没重做过，初始为 0
    mastery_level = "low"
    mastery_status = "new"

    frontmatter = {
        "id": question_id,
        "child": q.child,
        "subject": q.subject,
        "topic": q.topic,
        "error_type": q.error_type,
        "source_type": q.source_type,
        "difficulty": q.difficulty,
        "error_date": q.error_date.isoformat(),
        "created_at": date.today().isoformat(),
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
        "next_review_date": date.today().isoformat(),
        "review_interval_days": 1,
        "total_reviews": 0,
        "error_suggestion": q.error_suggestion,
        "knowledge_points": q.knowledge_points,
        "tags": q.tags,
    }

    # 构建 body
    body_parts = ["## 原题\n"]
    for p in image_paths:
        rel = p.relative_to(settings.vault / "_assets")
        body_parts.append(f"![原题](_assets/{rel})\n")
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

    # 通过存储管理器保存（IMA 主存储 + 本地文件降级）
    from app.services.storage_manager import get_storage_manager
    storage = get_storage_manager()
    storage_id = await storage.save_question(
        question_id=question_id,
        child=q.child,
        subject=q.subject,
        frontmatter=frontmatter,
        body=body,
    )

    return {"success": True, "id": question_id, "file": str(storage_id)}


@router.get("/questions")
async def list_questions(
    child: str = Query(...),
    subject: Optional[str] = Query(None),
    error_type: Optional[str] = Query(None),
    mastery_level: Optional[str] = Query(None),
):
    """列出错题"""
    questions = file_ops.list_questions(child, subject)

    # 筛选
    if error_type:
        questions = [q for q in questions if q.get("error_type") == error_type]
    if mastery_level:
        questions = [q for q in questions if q.get("mastery_level") == mastery_level]

    return {"questions": questions, "total": len(questions)}


@router.get("/questions/{question_id}")
async def get_question(question_id: str, child: str = Query(...), subject: str = Query(...)):
    """获取单个错题详情"""
    # 通过 file_ops 查找文件
    questions = file_ops.list_questions(child, subject)
    for q in questions:
        if q.get("id") == question_id:
            return file_ops.read_question(q["_file"])
    raise HTTPException(status_code=404, detail="错题不存在")


@router.get("/questions/{question_id}/images")
async def get_question_images(
    question_id: str, child: str = Query(...), subject: str = Query(...)
):
    """获取错题关联的图片列表"""
    from app.core.config import settings as app_settings
    assets_dir = app_settings.vault / "_assets" / child / subject / question_id
    if not assets_dir.exists():
        return {"images": []}
    images = []
    for f in sorted(assets_dir.iterdir()):
        if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.heic'):
            images.append({
                "filename": f.name,
                "url": f"/api/questions/{question_id}/images/{f.name}?child={child}&subject={subject}",
            })
    return {"images": images}


@router.get("/questions/{question_id}/images/{filename}")
async def serve_image(
    question_id: str, filename: str, child: str = Query(...), subject: str = Query(...)
):
    """提供图片文件"""
    from app.core.config import settings as app_settings
    file_path = app_settings.vault / "_assets" / child / subject / question_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(file_path)


@router.delete("/questions/{question_id}")
async def delete_question(
    question_id: str, child: str = Query(...), subject: str = Query(...)
):
    """删除错题"""
    questions = file_ops.list_questions(child, subject)
    for q in questions:
        if q.get("id") == question_id:
            file_ops.delete_question(q["_file"], child, subject, question_id)
            return {"success": True}
    raise HTTPException(status_code=404, detail="错题不存在")


@router.patch("/questions/{question_id}")
async def update_question(
    question_id: str,
    new_child: Optional[str] = Query(None),
    new_subject: Optional[str] = Query(None),
    child: str = Query(...),
    subject: str = Query(...),
):
    """修改错题的孩子/学科归属（移动文件）"""
    if not new_child and not new_subject:
        raise HTTPException(status_code=400, detail="至少需要指定 new_child 或 new_subject")

    # 查找文件
    questions = file_ops.list_questions(child, subject)
    target = None
    for q in questions:
        if q.get("id") == question_id:
            target = q
            break

    if not target:
        raise HTTPException(status_code=404, detail="错题不存在")

    # 读取完整数据
    full_data = file_ops.read_question(target["_file"])
    old_file = full_data.pop("_file")
    body = full_data.pop("_body", "")

    # 更新字段
    if new_child:
        full_data["child"] = new_child
    if new_subject:
        full_data["subject"] = new_subject

    final_child = full_data["child"]
    final_subject = full_data["subject"]

    # 移动文件（如果目标位置不同）
    if final_child != child or final_subject != subject:
        # 移动图片
        old_assets = settings.vault / "_assets" / child / subject / question_id
        new_assets = settings.vault / "_assets" / final_child / final_subject / question_id
        if old_assets.exists():
            import shutil
            new_assets.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_assets), str(new_assets))

        # 删除旧 markdown 文件
        from pathlib import Path as PathLib
        PathLib(old_file).unlink()

        # 创建新的 markdown 文件
        new_file = file_ops.save_question(question_id, final_child, final_subject, full_data, body)
        return {"success": True, "file": str(new_file)}
    else:
        # 只更新内容（不移动文件）
        file_ops.update_question(old_file, full_data, body)
        return {"success": True, "file": old_file}


@router.post("/questions/{question_id}/redo")
async def redo_question(
    question_id: str,
    req: RedoRequest,
    child: str = Query(...),
    subject: str = Query(...),
):
    """提交重做结果，更新掌握度、间隔复习等"""
    from datetime import date
    from app.services.analyzer import calculate_mastery_score, mastery_level_from_score, mastery_status_from
    from app.services.review_scheduler import calculate_next_review

    # 查找文件
    questions = file_ops.list_questions(child, subject)
    target = None
    for q in questions:
        if q.get("id") == question_id:
            target = q
            break
    if not target:
        raise HTTPException(status_code=404, detail="错题不存在")

    # 读取当前数据
    full_data = file_ops.read_question(target["_file"])
    file_path = full_data.pop("_file")
    full_data.pop("_body", None)

    # 更新重做记录
    redo_count = full_data.get("redo_count", 0) + 1
    redo_history = full_data.get("redo_history", []) or []
    redo_history.append({
        "date": date.today().isoformat(),
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
    full_data["last_redo_at"] = date.today().isoformat()
    full_data["mastery_score"] = mastery_score
    full_data["mastery_level"] = mastery_level
    full_data["mastery_status"] = mastery_status
    full_data["next_review_date"] = next_review.isoformat()
    full_data["review_interval_days"] = new_interval
    full_data["total_reviews"] = full_data.get("total_reviews", 0) + 1

    # 保存
    file_ops.update_question(file_path, full_data)

    return {
        "success": True,
        "mastery_score": mastery_score,
        "mastery_level": mastery_level,
        "next_review_date": next_review.isoformat(),
    }
