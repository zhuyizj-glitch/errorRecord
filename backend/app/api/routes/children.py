"""账号级孩子和课程配置接口。"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from app.api.deps import get_active_account, get_auth_service
from app.models.auth import Account
from app.services.auth_service import AuthService
from app.services import file_ops


router = APIRouter()
SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"]


class ChildRequest(BaseModel):
    name: str
    emoji: str = "🧒"
    subjects: list[str]

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 40:
            raise ValueError("孩子名称长度须为 1-40 个字符")
        return value

    @field_validator("subjects")
    @classmethod
    def valid_subjects(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("至少选择一门课程")
        if len(value) != len(set(value)) or any(subject not in SUBJECTS for subject in value):
            raise ValueError("课程必须来自九门课程列表且不能重复")
        return [subject for subject in SUBJECTS if subject in value]


def _read_child(connection, child_id: str, account_id: str) -> dict | None:
    child = connection.execute(
        "SELECT id, name, emoji FROM children WHERE id = ? AND account_id = ?",
        (child_id, account_id),
    ).fetchone()
    if not child:
        return None
    enabled = connection.execute(
        "SELECT subject FROM child_subjects WHERE child_id = ? AND enabled = 1",
        (child_id,),
    ).fetchall()
    selected = {row["subject"] for row in enabled}
    return {**dict(child), "subjects": [subject for subject in SUBJECTS if subject in selected]}


@router.get("/children")
def list_children(
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    with auth.db.connect() as connection:
        ids = connection.execute(
            "SELECT id FROM children WHERE account_id = ? ORDER BY created_at, id",
            (account.id,),
        ).fetchall()
        children = [_read_child(connection, row["id"], account.id) for row in ids]
    return {"children": children, "available_subjects": SUBJECTS}


@router.post("/children", status_code=status.HTTP_201_CREATED)
def create_child(
    req: ChildRequest,
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    child_id = f"child_{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc).isoformat()
    with auth.db.transaction() as connection:
        connection.execute(
            "INSERT INTO children (id, account_id, name, emoji, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (child_id, account.id, req.name, req.emoji, now, now),
        )
        connection.executemany(
            "INSERT INTO child_subjects (child_id, subject, enabled) VALUES (?, ?, 1)",
            [(child_id, subject) for subject in req.subjects],
        )
        result = _read_child(connection, child_id, account.id)
    for subject in req.subjects:
        file_ops.ensure_subject_dir(account.id, child_id, subject)
    return result


@router.patch("/children/{child_id}")
def update_child(
    child_id: str,
    req: ChildRequest,
    account: Account = Depends(get_active_account),
    auth: AuthService = Depends(get_auth_service),
):
    now = datetime.now(timezone.utc).isoformat()
    with auth.db.transaction() as connection:
        updated = connection.execute(
            "UPDATE children SET name = ?, emoji = ?, updated_at = ? "
            "WHERE id = ? AND account_id = ?",
            (req.name, req.emoji, now, child_id, account.id),
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=404, detail="孩子不存在")
        connection.execute("UPDATE child_subjects SET enabled = 0 WHERE child_id = ?", (child_id,))
        for subject in req.subjects:
            connection.execute(
                "INSERT INTO child_subjects (child_id, subject, enabled) VALUES (?, ?, 1) "
                "ON CONFLICT(child_id, subject) DO UPDATE SET enabled = 1",
                (child_id, subject),
            )
        result = _read_child(connection, child_id, account.id)
    for subject in req.subjects:
        file_ops.ensure_subject_dir(account.id, child_id, subject)
    return result
