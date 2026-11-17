"""把旧版 daughter/son vault 迁移到账号级目录。默认仅预览。"""

import argparse
import asyncio
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.db import Database
from app.services.ima_storage import IMAStorageBackend


LEGACY_CHILDREN = {
    "daughter": ("女儿", "👧", ["语文", "数学", "英语", "历史", "地理", "政治"]),
    "son": ("儿子", "👦", ["语文", "数学", "英语"]),
}


def _read_note(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.+?)\n---\n\n?(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"无 frontmatter: {path}")
    return yaml.safe_load(match.group(1)) or {}, match.group(2)


def _write_note(path: Path, frontmatter: dict, body: str) -> None:
    encoded = yaml.safe_dump(
        frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False
    )
    path.write_text(f"---\n{encoded}---\n\n{body}", encoding="utf-8")


def _existing_or_create_child(
    database: Database, account_id: str, name: str, emoji: str, subjects: list[str]
) -> str:
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT id FROM children WHERE account_id = ? AND name = ? ORDER BY created_at LIMIT 1",
            (account_id, name),
        ).fetchone()
        if row:
            child_id = row["id"]
        else:
            child_id = f"child_{uuid.uuid4().hex}"
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "INSERT INTO children (id, account_id, name, emoji, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (child_id, account_id, name, emoji, now, now),
            )
        for subject in subjects:
            connection.execute(
                "INSERT INTO child_subjects (child_id, subject, enabled) VALUES (?, ?, 1) "
                "ON CONFLICT(child_id, subject) DO UPDATE SET enabled = 1",
                (child_id, subject),
            )
    return child_id


def _backup(database: Database, vault: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = vault / "_migration_backups" / stamp
    backup.mkdir(parents=True)
    if database.path.exists():
        shutil.copy2(database.path, backup / "app.db")
    for legacy in LEGACY_CHILDREN:
        source = vault / legacy
        if source.exists():
            shutil.copytree(source, backup / legacy)
        assets = vault / "_assets" / legacy
        if assets.exists():
            shutil.copytree(assets, backup / "_assets" / legacy)
    return backup


def migrate_local_vault(
    database: Database, vault: Path, admin_id: str, dry_run: bool = True
) -> dict:
    vault = Path(vault)
    legacy_notes = [
        note
        for legacy in LEGACY_CHILDREN
        for note in (vault / legacy).glob("*/*.md")
    ]
    image_count = sum(
        1
        for legacy in LEGACY_CHILDREN
        for path in (vault / "_assets" / legacy).glob("**/*")
        if path.is_file()
    )
    result = {
        "dry_run": dry_run,
        "questions": len(legacy_notes),
        "images": image_count,
        "children": len(LEGACY_CHILDREN),
        "errors": [],
    }
    if dry_run:
        return result

    with database.connect() as connection:
        admin = connection.execute(
            "SELECT role FROM accounts WHERE id = ?", (admin_id,)
        ).fetchone()
    if not admin or admin["role"] != "admin":
        raise ValueError("必须指定已经存在的管理员账号")

    if legacy_notes or image_count:
        result["backup"] = str(_backup(database, vault))

    child_ids = {}
    for legacy, (name, emoji, subjects) in LEGACY_CHILDREN.items():
        child_id = _existing_or_create_child(database, admin_id, name, emoji, subjects)
        child_ids[legacy] = child_id
        for subject in subjects:
            (vault / "accounts" / admin_id / child_id / subject).mkdir(parents=True, exist_ok=True)

    migrated = 0
    for source in legacy_notes:
        legacy = source.parent.parent.name
        subject = source.parent.name
        child_id = child_ids[legacy]
        try:
            frontmatter, body = _read_note(source)
            frontmatter.pop("child", None)
            frontmatter["account_id"] = admin_id
            frontmatter["child_id"] = child_id
            frontmatter["child_name"] = LEGACY_CHILDREN[legacy][0]
            body = body.replace(
                f"_assets/{legacy}/",
                f"_assets/accounts/{admin_id}/{child_id}/",
            )
            target = vault / "accounts" / admin_id / child_id / subject / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_note(target, frontmatter, body)
            source.unlink()
            migrated += 1
        except Exception as exc:
            result["errors"].append({"file": str(source), "error": str(exc)})

    for legacy, child_id in child_ids.items():
        source_assets = vault / "_assets" / legacy
        if source_assets.exists():
            target_assets = vault / "_assets" / "accounts" / admin_id / child_id
            shutil.copytree(source_assets, target_assets, dirs_exist_ok=True)
            shutil.rmtree(source_assets)
        source_dir = vault / legacy
        if source_dir.exists() and not any(source_dir.rglob("*.md")):
            shutil.rmtree(source_dir)

    result["questions"] = migrated
    return result


async def audit_ima_notes(
    storage: IMAStorageBackend,
    admin_id: str,
    child_ids: dict[str, str],
) -> dict:
    """
    审计 IMA 中需要补账号元数据的旧笔记。

    ⚠️ 本函数**只统计，不写入**。原因：IMA OpenAPI 没有修改笔记的接口，
    可用能力只有 import_doc（新建）、append_doc（追加）、get_doc_content
    （读取）、list_note_by_folder_id（列表）、search_note_book（搜索）、
    list_note_folder_by_cursor（列笔记本）。append_doc 只能往末尾追加，
    用它补字段会在笔记里留下第二份元数据块，破坏解析。

    影响：这些旧笔记在同步时会被判为「归属未知」而跳过
    （见 IMAStorageBackend.sync_to_obsidian 的 allowed_scopes 检查）。
    题目内容本身仍完整保存在 IMA 里，需要时可在 IMA 客户端手动整理。
    """
    result = {
        "matched": 0,
        "updated": 0,
        "unsupported_reason": "IMA OpenAPI 不支持修改笔记，无法补齐账号元数据",
        "affected_notes": [],
    }
    for note in await storage.client.list_notes():
        note_id = note.get("id")
        if not note_id:
            continue
        try:
            note_data = await storage.client.get_note(note_id)
            frontmatter, _ = storage._parse_note_content(note_data.get("content", ""))
            legacy = frontmatter.get("child")
            if frontmatter.get("account_id") or legacy not in child_ids:
                continue
            result["matched"] += 1
            result["affected_notes"].append({
                "note_id": note_id,
                "question_id": frontmatter.get("id"),
                "legacy_child": legacy,
            })
        except Exception as exc:
            result.setdefault("errors", []).append({"note_id": note_id, "error": str(exc)})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--admin-id", required=True)
    parser.add_argument("--apply", action="store_true", help="实际执行；不传时仅 dry-run")
    parser.add_argument("--migrate-ima", action="store_true")
    args = parser.parse_args()
    database = Database(args.database_url)
    database.initialize()
    result = migrate_local_vault(database, args.vault, args.admin_id, dry_run=not args.apply)
    if args.migrate_ima:
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT id, name FROM children WHERE account_id = ?", (args.admin_id,)
            ).fetchall()
        by_name = {row["name"]: row["id"] for row in rows}
        child_ids = {
            legacy: by_name[name]
            for legacy, (name, _, _) in LEGACY_CHILDREN.items()
            if name in by_name
        }
        result["ima"] = asyncio.run(
            audit_ima_notes(IMAStorageBackend(), args.admin_id, child_ids)
        )
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))


if __name__ == "__main__":
    main()
