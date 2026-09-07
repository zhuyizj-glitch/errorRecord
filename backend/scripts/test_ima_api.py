#!/usr/bin/env python3
"""测试 IMA API 连接"""

import asyncio
import sys
from pathlib import Path

# 添加 backend 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ima_client import IMAClient


async def test_ima_api():
    """测试 IMA API"""
    print("=" * 60)
    print("测试 IMA API 连接")
    print("=" * 60)

    client = IMAClient()

    # 打印配置信息
    print(f"\n配置信息:")
    print(f"  Skill 目录: {client.skill_dir}")
    print(f"  API 脚本: {client.ima_api_script}")

    # 1. 测试连接
    print("\n1. 测试连接...")
    connected = await client.test_connection()
    if connected:
        print("✅ 连接成功")
    else:
        print("❌ 连接失败")
        return False

    # 2. 测试创建笔记
    print("\n2. 测试创建笔记...")
    note_id = await client.create_note(
        title="测试笔记 - IMA API 连接测试",
        content="""# 测试笔记

这是一个测试笔记，用于验证 IMA API 连接。

## 测试项目
- ✅ 创建笔记
- ✅ Markdown 格式
- ✅ 中文支持
- ✅ API 端点正确

## 时间
测试时间：2026-09-07
""",
    )

    if note_id:
        print(f"✅ 笔记创建成功: {note_id}")
    else:
        print("❌ 笔记创建失败")

    # 3. 测试列出笔记
    print("\n3. 测试列出笔记...")
    notes = await client.list_notes(limit=5)
    if notes is not None:
        print(f"✅ 列出笔记成功: {len(notes)} 条")
        for note in notes[:3]:
            print(f"   - {note.get('title', '无标题')} (ID: {note.get('id', 'N/A')})")
    else:
        print("❌ 列出笔记失败")

    # 4. 测试搜索笔记
    print("\n4. 测试搜索笔记...")
    results = await client.search_notes("测试", limit=5)
    if results is not None:
        print(f"✅ 搜索笔记成功: {len(results)} 条结果")
    else:
        print("❌ 搜索笔记失败")

    # 5. 清理：删除测试笔记
    if note_id:
        print(f"\n5. 清理测试笔记...")
        # 注意：IMA API 可能没有删除笔记的端点
        # 如果有，可以取消下面的注释
        print("   跳过删除（API 可能不支持）")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_ima_api())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
