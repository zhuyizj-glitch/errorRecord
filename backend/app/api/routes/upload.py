"""图片上传接口"""

import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File

from app.core.config import settings

router = APIRouter()

# 临时图片存储（分析完成后保存到 vault 或删除）
TEMP_DIR = Path("/tmp/mistakes_uploads")
TEMP_DIR.mkdir(exist_ok=True)


@router.post("/upload/images")
async def upload_images(files: list[UploadFile] = File(...)):
    """
    上传图片，返回临时 image_ids。
    前端拿到 image_ids 后调用 /api/analyze 进行分析。
    """
    image_ids = []
    for f in files:
        image_id = uuid.uuid4().hex[:8]
        suffix = Path(f.filename).suffix or ".jpg"
        temp_path = TEMP_DIR / f"{image_id}{suffix}"
        content = await f.read()
        temp_path.write_bytes(content)
        image_ids.append({"id": image_id, "path": str(temp_path), "filename": f.filename})
    return {"image_ids": image_ids}
