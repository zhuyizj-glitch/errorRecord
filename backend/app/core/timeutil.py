"""统一的时区处理

背景
----
项目里原本各处直接用 ``date.today()`` / ``datetime.now()``，取的是"运行环境的本地日期"。
在 Mac 上开发时没问题（宿主机是中国时区），但后端实际跑在 Docker 容器里，
而容器默认是 UTC —— ``python:3.12-slim`` 基础镜像不设置时区，docker-compose.yml 里也没有 TZ。
实测对照：

    宿主机   CST  2026-10-07 17:05
    容器内   UTC  2026-10-07 09:05

于是北京时间每天 00:00–08:00 之间，容器里的 ``date.today()`` 会比中国的"今天"晚一天，
表现为：那段时间打开「今日复习」拿到的是昨天的计划；新录入错题的 error_date 记成前一天。

修复分两层，互为保险：

1. **本模块**提供显式的北京时间函数，业务代码统一改用它（不依赖运行环境）；
2. ``docker-compose.yml`` 设置 ``TZ=Asia/Shanghai``，让日志时间戳也跟着正确。

为什么用固定 UTC+8 偏移，而不是 ``zoneinfo.ZoneInfo("Asia/Shanghai")``
----------------------------------------------------------------------
中国自 1991 年起不再实行夏令时，UTC+8 常年恒定。
而 ``slim`` 系列镜像不含 tzdata 时区数据库，用 ``zoneinfo`` 需要额外安装 tzdata 包
（或 pip install tzdata）。固定偏移既准确又少一个依赖，也避免了
"镜像里恰好吃不到时区数据、于是静默回退到 UTC" 这类难查的问题。
"""

from datetime import date, datetime, timedelta, timezone

#: 北京时间（UTC+8，中国无夏令时，偏移恒定）
CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now() -> datetime:
    """当前北京时间（带时区信息）"""
    return datetime.now(CHINA_TZ)


def today() -> date:
    """北京时间的今天。

    凡是涉及"今天是几号"的判断都应该用它，不要用 ``date.today()``。
    """
    return now().date()


def today_iso() -> str:
    """北京时间的今天，YYYY-MM-DD 字符串（与项目里日期字段的存储格式一致）"""
    return today().isoformat()
