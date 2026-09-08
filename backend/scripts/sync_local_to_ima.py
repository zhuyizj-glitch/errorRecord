#!/usr/bin/env python3
"""
反向同步：本地 Obsidian → IMA 知识库

用途：补齐 IMA 中缺失的错题（如 IMA 写入失败时降级到本地的那些）。

用法：
    python3 scripts/sync_local_to_ima.py --dry-run   # 预演，只看会同步什么
    python3 scripts/sync_local_to_ima.py             # 实际执行
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services import file_ops
from app.services.ima_client import get_ima_client
from app.services.ima_storage import IMAStorageBackend

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 孩子标识 → IMA 文件夹名
CHILD_FOLDER_NAME = {"daughter": "女儿", "son": "儿子"}


def collect_local_questions() -> list[dict]:
    """扫描本地 vault，收集所有错题"""
    questions = []
    for child in CHILD_FOLDER_NAME:
        child_dir = settings.vault / child
        if not child_dir.exists():
            continue
        for subject_dir in child_dir.iterdir():
            if not subject_dir.is_dir():
                continue
            for md_file in sorted(subject_dir.glob("*.md")):
                try:
                    data = file_ops.read_question(str(md_file))
                except Exception as e:
                    logger.warning(f"跳过无法解析的文件 {md_file.name}: {e}")
                    continue

                qid = data.get("id")
                if not qid:
                    logger.warning(f"跳过缺少 id 的文件: {md_file.name}")
                    continue

                questions.append({
                    "id": qid,
                    "child": data.get("child", child),
                    "subject": data.get("subject", subject_dir.name),
                    "topic": data.get("topic", "未命名"),
                    "file": str(md_file),
                    "frontmatter": {k: v for k, v in data.items() if not k.startswith("_")},
                    "body": data.get("_body", ""),
                })
    return questions


async def collect_ima_question_ids(client) -> set[str]:
    """
    收集 IMA 中已有的错题 id（frontmatter 里的业务 id）

    新标题格式不含业务 ID（如「【儿子·数学】分数除法（概念不清） 2026-09-05」），
    所以需要读取笔记内容解析 frontmatter。历史格式仍从标题提取。
    """
    from app.services.ima_storage import IMAStorageBackend

    existing = set()
    notes = await client.list_notes()  # 取全部（自动分页）
    if not notes:
        return existing

    storage = IMAStorageBackend()

    for note in notes:
        title = (note.get("title") or "").strip()
        note_id = note.get("id")

        # 历史格式 1: "[daughter][数学] 路由集成测试 - 8ee3ce5a"
        if " - " in title:
            existing.add(title.rsplit(" - ", 1)[-1].strip())
            continue

        # 历史格式 2: "id: 259b0a9c"
        if title.startswith("id:"):
            existing.add(title[3:].strip())
            continue

        # 新格式：读内容解析 frontmatter 里的 id
        if note_id:
            try:
                full = await client.get_note(note_id)
                if full:
                    fm, _ = storage._parse_note_content(full.get("content", ""))
                    qid = fm.get("id")
                    if qid:
                        existing.add(str(qid))
            except Exception as e:
                logger.warning(f"解析笔记 {note_id} 失败: {e}")

    return existing


async def main():
    parser = argparse.ArgumentParser(description="反向同步：本地 → IMA")
    parser.add_argument("--dry-run", action="store_true", help="只预演，不实际写入")
    args = parser.parse_args()

    if not settings.ima_enabled:
        print("❌ IMA 未启用（IMA_ENABLED=false），无需同步")
        return 1

    if not settings.ima_knowledge_base_id:
        print("❌ 未配置 IMA_KNOWLEDGE_BASE_ID")
        return 1

    print("=" * 60)
    print("反向同步：本地 Obsidian → IMA 知识库")
    if args.dry_run:
        print("【预演模式 — 不会实际写入】")
    print("=" * 60)

    # 1. 扫描本地
    print("\n[1/3] 扫描本地 vault...")
    local = collect_local_questions()
    print(f"      本地共 {len(local)} 条错题")

    # 2. 查询 IMA 已有
    print("\n[2/3] 查询 IMA 已有错题...")
    client = get_ima_client()
    try:
        existing_ids = await collect_ima_question_ids(client)
        print(f"      IMA 中已有 {len(existing_ids)} 条（含测试笔记）")

        # 3. 找出缺失的
        missing = [q for q in local if q["id"] not in existing_ids]

        if not missing:
            print("\n✅ IMA 已包含所有本地错题，无需同步")
            return 0

        print(f"\n[3/3] 需要同步 {len(missing)} 条：")
        for q in missing:
            folder = f"{CHILD_FOLDER_NAME.get(q['child'], q['child'])}/{q['subject']}"
            print(f"      - {q['id']} | {folder} | {q['topic']}")

        if args.dry_run:
            print("\n【预演结束】加 --dry-run 之外的参数实际执行")
            return 0

        # 实际同步
        print("\n开始同步...")
        storage = IMAStorageBackend()
        ok, failed = 0, 0

        for q in missing:
            try:
                note_id = await storage.save_question(
                    question_id=q["id"],
                    child=q["child"],
                    subject=q["subject"],
                    frontmatter=q["frontmatter"],
                    body=q["body"],
                )
                folder = f"{CHILD_FOLDER_NAME.get(q['child'], q['child'])}/{q['subject']}"
                print(f"  ✅ {q['id']} → {folder} (笔记 ID: {note_id})")
                ok += 1
            except Exception as e:
                print(f"  ❌ {q['id']} 失败: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"同步完成：成功 {ok} 条，失败 {failed} 条")
        print("=" * 60)
        return 0 if failed == 0 else 1

    finally:
        await client.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(1)
