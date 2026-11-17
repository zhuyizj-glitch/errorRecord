#!/usr/bin/env python3
"""
实测 IMA append_doc 的行为边界。

背景：IMA OpenAPI 没有修改笔记的接口，因此「追加事件」是唯一可行的写入方式
（见 discuss.md 8.32 / 8.33）。整个追加事件模型压在 append_doc 上，本脚本
逐一验证它的前提，避免又出现 8.31 那种「方法从未实现却没人发现」的情况。

运行（在容器内）：

    docker compose exec backend python scripts/test_ima_append.py

    # 另外探测单篇笔记的大小上限（会写入较大内容）：
    docker compose exec backend python scripts/test_ima_append.py --probe-size

⚠️ IMA 没有删除接口，本脚本会留下标题以 [探针] 开头的测试笔记。
   跑完后请到 IMA 客户端手动删除。

安全说明：脚本只创建和追加自己的探针笔记，不会读取或修改任何真实错题。
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ima_client import IMAClient  # noqa: E402

APPEND_ENDPOINT = "openapi/note/v1/append_doc"

BASE_JSON = (
    '{"probe": "base", "mastery_score": 0, "next_review_date": "2026-09-27", '
    '"knowledge_points": ["因式分解"], "note": "含_下划线"}'
)
BASE_CONTENT = f"""# [探针] IMA append_doc 行为实测

这是 discuss.md 8.33 的实测探针，验证完请在 IMA 客户端手动删除。

## 基础块

```json
{BASE_JSON}
```

## 原题

解方程 x² - 5x + 6 = 0
"""

# 追加的 JSON 事件：字段名带下划线，验证 IMA 是否改写代码块内容
EVENT_JSON = (
    '{"type": "redo", "rev": 2, "at": "2026-09-27T10:00:00+00:00", '
    '"result": "correct", "mastery_score": 68, "consecutive_correct": 1}'
)
EVENT_CONTENT = f"""
```json
{EVENT_JSON}
```
"""

# 追加的 markdown 特殊字符：验证代码块之外的内容会被怎样改写
SPECIAL_CONTENT = """
## 特殊字符检查

下划线 _a_b_ 星号 *c* 减号 - 连字符 -- 井号 # 方括号 [d] 竖线 |e| 反引号 `f`
中文全角：（括号）【方括号】、顿号、·间隔号
emoji：👧🧒
"""

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"\n        {detail}" if detail else ""))
    return ok


def first_difference(expected: str, actual: str) -> str:
    """定位首个差异，便于判断 IMA 到底改了什么。"""
    for index, (left, right) in enumerate(zip(expected, actual)):
        if left != right:
            start = max(0, index - 30)
            return (
                f"第 {index} 字符处\n"
                f"        期望: ...{expected[start:index + 30]!r}\n"
                f"        实际: ...{actual[start:index + 30]!r}"
            )
    if len(expected) != len(actual):
        return f"长度不同：期望 {len(expected)}，实际 {len(actual)}\n        尾部差异: {actual[len(expected):][:80]!r}"
    return ""


async def read_content(client: IMAClient, doc_id: str) -> str:
    note = await client.get_note(doc_id)
    return (note or {}).get("content", "")


async def do_append(client: IMAClient, doc_id: str, content: str, id_key: str) -> dict:
    return await client._call_api(
        APPEND_ENDPOINT,
        {id_key: doc_id, "content": content, "content_format": 1},
    )


async def run(probe_size: bool) -> int:
    print("=" * 72)
    print("IMA append_doc 行为实测")
    print("=" * 72)

    client = IMAClient()

    # ── 1. 凭证与连接 ──
    print("\n[1/7] 检查凭证与连接")
    try:
        client._get_credentials()
    except Exception as exc:
        record(
            "读取 IMA 凭证",
            False,
            f"读不到 ~/.config/ima 下的凭证：{exc}\n"
            "        容器需要挂载 ~/.config/ima（见 docker-compose.yml）",
        )
        return 1
    record("读取 IMA 凭证", True, "")

    try:
        connected = await client.test_connection()
    except Exception as exc:
        record("IMA 连接", False, f"异常: {exc}")
        return 1
    if not record("IMA 连接", bool(connected), "" if connected else "连接失败，后续检查无法进行"):
        return 1

    # ── 2. 创建探针笔记 ──
    print("\n[2/7] 创建探针笔记")
    doc_id = await client.create_note(title="[探针] IMA append_doc 行为实测", content=BASE_CONTENT)
    if not record("创建探针笔记", bool(doc_id), f"doc_id={doc_id}"):
        return 1

    before = await read_content(client, doc_id)
    record("回读基础内容", BASE_JSON in before, f"长度 {len(before)} 字符")

    # ── 3. 参数名：doc_id 还是 note_id ──
    print("\n[3/7] 探测 append_doc 的 ID 参数名")
    # 标记刻意不含下划线：IMA 会把代码块之外的 `_` 转义成 `\_`，
    # 也不能用 HTML 注释（会被整段剥掉），两者都会造成「追加失败」的误判。
    id_key = None
    accepted_keys = []
    for candidate in ("doc_id", "note_id"):
        marker = f"@@marker-{candidate.replace('_', '')}@@"
        try:
            await do_append(client, doc_id, f"\n\n{marker}\n", candidate)
            accepted_keys.append(candidate)
            if id_key is None:
                id_key = candidate
        except Exception as exc:
            print(f"        {candidate} 不可用: {exc}")
    if not record("确定 ID 参数名", bool(id_key), f"可用参数名: {accepted_keys or '无'}"):
        return 1

    after_key_probe = await read_content(client, doc_id)
    expected_marker = f"@@marker-{id_key.replace('_', '')}@@"
    record(
        f"追加成功写入内容（{id_key}）",
        expected_marker in after_key_probe,
        "标记未出现在笔记中" if expected_marker not in after_key_probe else "",
    )

    # ── 4. 追加是追加，不是替换 ──
    print("\n[4/7] 验证「追加」语义（原有内容是否保留）")
    length_before_json = len(await read_content(client, doc_id))
    await do_append(client, doc_id, EVENT_CONTENT, id_key)
    after_json = await read_content(client, doc_id)

    record(
        "追加后基础块仍在",
        BASE_JSON in after_json,
        "" if BASE_JSON in after_json else "基础块消失，说明是替换而非追加",
    )
    record(
        "追加后正文仍在",
        "解方程 x² - 5x + 6 = 0" in after_json,
        "" if "解方程" in after_json else "原正文消失",
    )
    record(
        "笔记长度增长",
        len(after_json) > length_before_json,
        f"{length_before_json} → {len(after_json)} 字符",
    )

    # ── 5. JSON 代码块是否被改写（关键）──
    print("\n[5/7] 验证追加的 JSON 代码块是否被 IMA 改写")
    json_ok = EVENT_JSON in after_json
    # 断言只针对追加的代码块本身：IMA 会改写代码块**之外**的 Markdown
    # （`_` → `\_`、`*` → `_`、`[` → `\[`），那些改写与本方案无关。
    if json_ok:
        record("追加的 JSON 代码块逐字符未变", True, "")
    else:
        anchor = after_json.find('{"type"')
        region = after_json[anchor:anchor + len(EVENT_JSON)] if anchor >= 0 else ""
        detail = (
            first_difference(EVENT_JSON, region)
            if region
            else "未能在笔记中定位到追加的事件块"
        )
        record("追加的 JSON 代码块逐字符未变", False, detail)

    record(
        "代码块内的下划线未被转义",
        json_ok,
        "" if json_ok else "事件块内容与写入时不一致",
    )

    # ── 6. 特殊字符与多次追加的顺序 ──
    print("\n[6/7] 特殊字符改写情况与追加顺序")
    await do_append(client, doc_id, SPECIAL_CONTENT, id_key)
    await do_append(client, doc_id, "\n\n@@marker-order1@@\n", id_key)
    await do_append(client, doc_id, "\n\n@@marker-order2@@\n", id_key)
    final = await read_content(client, doc_id)

    record("中文全角字符保留", "（括号）【方括号】、顿号、·间隔号" in final, "")
    record("emoji 保留", "👧🧒" in final, "")

    order_ok = -1 < final.find("@@marker-order1@@") < final.find("@@marker-order2@@")
    record("多次追加保持先后顺序", order_ok, "" if order_ok else "顺序错乱或标记未保留")

    # ── 7. 标题是否被影响 ──
    print("\n[7/7] 追加是否影响笔记标题")
    notes = await client.list_notes(limit=20)
    probe_note = next((n for n in notes if n.get("id") == doc_id), None)
    if probe_note:
        title = (probe_note.get("title") or "").strip()
        record(
            "标题仍为 H1 内容",
            "探针" in title,
            f"标题={title!r}",
        )
    else:
        record("能在列表中找到探针笔记", False, "list_notes 未返回该笔记（可能分页或索引延迟）")

    # ── 可选：大小上限探测 ──
    size_verdict = None
    if probe_size:
        print("\n[额外] 探测单篇笔记大小上限")
        size_verdict = await probe_note_size(client, doc_id, id_key)

    # ── 汇总 ──
    print("\n" + "=" * 72)
    failed = [r for r in results if not r[1]]
    print(f"结果：{len(results)} 项检查，通过 {len(results) - len(failed)}，失败 {len(failed)}")
    for name, _, detail in failed:
        print(f"  ✗ {name}")
        if detail:
            print(f"      {detail}")

    print("\n结论：")
    if not failed:
        print("  ✅ append_doc 可用，追加事件模型成立。")
        print("     下一步可以按 8.33 的设计改造 ima_storage 与解析器。")
    elif any("JSON 代码块" in name or "下划线" in name for name in (f[0] for f in failed)):
        print("  ⚠️  append_doc 可用，但会改写追加的内容——代码块方案不可靠。")
        print("     需要改用 base64 或转义方案承载追加的元数据。")
    else:
        print("  ❌ 存在失败项，追加事件模型需要在实现前重新评估。")

    if size_verdict:
        print(f"\n  单篇大小上限：{size_verdict}")

    print("\n⚠️  探针笔记无法通过 API 删除，请到 IMA 客户端手动删除标题含 [探针] 的笔记。")
    print("=" * 72)
    return 1 if failed else 0


async def probe_note_size(client: IMAClient, doc_id: str, id_key: str) -> str:
    """
    逐步追加内容，找出单篇笔记的大小上限。

    每轮追加 64KB（ASCII，字节数可预期），首次失败即停止。
    为避免占用过多存储，默认上限 1MB——真实上限可能更高，
    报告里会说明探测到哪一步为止。
    """
    step = 64 * 1024
    max_total = 1024 * 1024
    total = len(await read_content(client, doc_id))
    round_no = 0

    while total < max_total:
        round_no += 1
        chunk = f"\n<!-- pad-{round_no} -->\n" + ("x" * step)
        try:
            await do_append(client, doc_id, chunk, id_key)
        except Exception as exc:
            return (
                f"第 {round_no} 轮追加失败（累计约 {total // 1024}KB）：{exc}\n"
                f"     这很可能就是 100009「单篇笔记超过最大限制」的触发点"
            )
        total += len(chunk)
        print(f"        第 {round_no} 轮成功，累计约 {total // 1024}KB")

    return (
        f"追加到约 {total // 1024}KB 仍成功（探测上限 1024KB，未触顶）\n"
        f"     如需精确定位，可调高脚本里的 max_total 再跑一次"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="实测 IMA append_doc 行为")
    parser.add_argument(
        "--probe-size",
        action="store_true",
        help="额外探测单篇笔记大小上限（会写入较大内容，最多约 1MB）",
    )
    args = parser.parse_args()

    started = datetime.now(timezone.utc).isoformat()
    print(f"开始时间：{started}\n")
    return asyncio.run(run(args.probe_size))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断")
        sys.exit(130)
