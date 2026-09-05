"""孩子、学科相关接口"""

from fastapi import APIRouter

router = APIRouter()

# 孩子及其学科配置
CHILDREN = {
    "daughter": {
        "name": "女儿",
        "emoji": "👧",
        "subjects": ["语文", "数学", "英语", "历史", "地理", "政治"],
    },
    "son": {
        "name": "儿子",
        "emoji": "👦",
        "subjects": ["语文", "数学", "英语"],
    },
}


@router.get("/children")
async def list_children():
    """获取孩子列表及其学科"""
    return CHILDREN
