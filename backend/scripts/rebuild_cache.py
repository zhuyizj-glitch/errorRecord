#!/usr/bin/env python3
"""
从 IMA 重建本地缓存。

本地缓存只是**可丢弃的物化视图**，IMA 才是错题的记录来源（见 discuss.md 8.36）。
缓存丢了、坏了，或者你怀疑它和云端不一致时，用这个脚本以 IMA 为准重新拉一遍。

它与定时同步的区别：定时同步是保守的，不会用旧快照覆盖本地更新的记录；
重建则跳过冲突保护，因为此时本地的版本号已经不可信。

用法（容器内）：

    docker compose exec backend python scripts/rebuild_cache.py --dry-run   # 预览
    docker compose exec backend python scripts/rebuild_cache.py             # 重建
    docker compose exec backend python scripts/rebuild_cache.py --prune     # 顺带清理本地独有项

注意：容器不会自动带上新脚本（Dockerfile 在构建时 COPY 源码，compose 不挂载
backend 目录），改动过脚本后需要先 `docker compose up -d --build backend`。

⚠️ IMA 没有删除接口，重建不会动云端任何内容，只写本地。
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings  # noqa: E402
from app.db import database  # noqa: E402
from app.services.storage_manager import get_storage_manager  # noqa: E402


def load_allowed_scopes() -> set[tuple[str, str]]:
    """当前数据库里存在的 (account_id, child_id) 组合。"""
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute("SELECT account_id, id, name FROM children").fetchall()
    print(f"      数据库中共 {len(rows)} 个孩子")
    for row in rows:
        print(f"        - {row['name']} ({row['account_id'][:14]}… / {row['id'][:14]}…)")
    return {(row["account_id"], row["id"]) for row in rows}


async def main() -> int:
    parser = argparse.ArgumentParser(description="从 IMA 重建本地缓存")
    parser.add_argument("--dry-run", action="store_true", help="只统计不写入，用来预览")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="一并删除只在本地、IMA 里没有的错题文件（默认只报告）",
    )
    parser.add_argument(
        "--skip-unchanged",
        action="store_true",
        help="跳过云端未变更的笔记（快很多，但假定本地文件没被绕过系统改过）",
    )
    args = parser.parse_args()

    print("=" * 68)
    print("从 IMA 重建本地缓存")
    if args.dry_run:
        print("【预演模式 — 不会写入任何文件】")
    print("=" * 68)

    if not settings.ima_enabled:
        print("\n❌ IMA 未启用（IMA_ENABLED=false），本地文件就是记录来源，无需重建")
        return 1
    if not settings.ima_knowledge_base_id:
        print("\n❌ 未配置 IMA_KNOWLEDGE_BASE_ID")
        return 1

    print(f"\n[1/3] 读取账号与孩子")
    scopes = load_allowed_scopes()
    if not scopes:
        print(
            "\n⚠️  数据库里还没有孩子。IMA 中的错题会因为「归属未知」被全部跳过，"
            "\n    请先在网页上创建孩子再重建。"
        )
        return 1

    print(f"\n[2/3] 从 IMA 拉取{'（预演）' if args.dry_run else ''}…")
    storage = get_storage_manager()
    if not storage.ima_mode:
        print("\n❌ 当前存储不是 IMA 主模式，无法重建")
        return 1

    stats = await storage.sync_to_obsidian(
        scopes,
        force=True,
        prune=args.prune,
        dry_run=args.dry_run,
        skip_unchanged=args.skip_unchanged,
    )

    print(f"\n[3/3] 结果")
    print(f"      新建      {stats.get('created', 0)}")
    print(f"      覆盖      {stats.get('forced', 0)}")
    print(f"      未变更    {stats.get('unchanged', 0)}（跳过读取）")
    print(f"      预筛跳过  {stats.get('preskipped', 0)}")
    print(f"      跳过      {stats.get('skipped', 0)}（非错题笔记）")
    print(f"      错误      {stats.get('errors', 0)}")
    print(f"      本地独有  {stats.get('local_only', 0)}")
    if args.prune:
        print(f"      已清理    {stats.get('pruned', 0)}")

    local_only_ids = stats.get("local_only_ids") or []
    if local_only_ids:
        print(
            "\n⚠️  以下错题只在本地、IMA 里没有。IMA 既然是记录来源，"
            "\n    这说明某次写入没落到云端，建议先看一眼再决定是否清理："
        )
        for question_id in local_only_ids[:20]:
            print(f"      - {question_id}")
        if len(local_only_ids) > 20:
            print(f"      …另有 {len(local_only_ids) - 20} 条")
        if not args.prune:
            print("\n    （确认无误后可加 --prune 清理，或直接忽略）")

    print("\n" + "=" * 68)
    if args.dry_run:
        print("预演结束，未写入任何文件。去掉 --dry-run 实际执行。")
    else:
        print("重建完成。IMA 侧未做任何改动。")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(130)
