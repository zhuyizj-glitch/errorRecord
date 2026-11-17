"""图片上传接口

上传的图片只是 LLM 分析的输入：分析完、错题保存后就没有用了，
不落盘到 vault，也不进 markdown。因此这里负责它们的生命周期——
超过 TTL 的临时文件自动回收。
"""

import logging
import time
import uuid
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.api.deps import get_active_account
from app.models.auth import Account

logger = logging.getLogger(__name__)

router = APIRouter()

# 临时图片存储（分析完成后即可丢弃）
TEMP_DIR = Path("/tmp/mistakes_uploads")
TEMP_DIR.mkdir(exist_ok=True)

# 临时文件保留时长。够覆盖「上传 → 分析 → 保存」以及中途的重新生成/反馈优化；
# 没保存的任务也会在到期后自动清掉，不会永久堆积。
TEMP_TTL_HOURS = 24
TEMP_TTL_SECONDS = TEMP_TTL_HOURS * 3600

# ── 上传校验规则（与前端 ImageUploader 的提示保持一致）──
MAX_FILES_PER_UPLOAD = 10
MAX_FILE_BYTES = 20 * 1024 * 1024  # 单张 20MB
MIN_DIMENSION = 200  # 最短边低于此值只告警，不拦截
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".pdf"}

# v2.0：PDF 真题卷支持。单个 PDF 最多 30 页，一次请求展开后总图片数 ≤ 40。
MAX_PDF_PAGES = 30
MAX_TOTAL_IMAGES = 40

# ISO-BMFF 容器中代表 HEIF 家族的 brand
_HEIF_BRANDS = {
    b"heic", b"heix", b"hevc", b"hevx",
    b"heim", b"heis", b"hevm", b"hevs",
    b"mif1", b"msf1",
}


def sweep_expired_uploads(now: float | None = None) -> int:
    """
    回收超过 TTL 的临时图片，返回清理的数量。

    保存流程不再负责清理（它现在已经不碰图片了），所以由这里按时间回收：
    应用启动时扫一次，之后每次上传时顺带扫一次。目录规模很小
    （单账号最多几十个文件），这部分开销可以忽略。
    """
    if not TEMP_DIR.exists():
        return 0

    cutoff = (time.time() if now is None else now) - TEMP_TTL_SECONDS
    removed = 0

    for path in TEMP_DIR.rglob("*"):
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError as exc:
            logger.warning(f"清理临时文件失败 {path}: {exc}")

    # 顺手清掉空目录，避免账号目录越积越多
    for directory in sorted(TEMP_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if directory.is_dir():
            try:
                directory.rmdir()
            except OSError:
                pass  # 非空就留着

    if removed:
        logger.info(f"已清理 {removed} 个过期临时图片（TTL {TEMP_TTL_HOURS} 小时）")
    return removed


def _pdf_to_page_images(data: bytes, original_name: str, account_dir: Path) -> list[dict]:
    """把 PDF 逐页渲染成 PNG 临时图片（v2.0 真题卷导入）。

    用 pypdfium2（自带 pdfium 二进制，无系统依赖），150 DPI 足够 AI 识别。
    每页独立成图，后续与拍照上传走完全相同的「每图一个任务」链路。
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="服务器未安装 PDF 支持（pypdfium2），请先更新后端依赖",
        ) from None

    try:
        pdf = pdfium.PdfDocument(data)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{original_name} 不是有效的 PDF 文件") from None

    page_count = len(pdf)
    if page_count == 0:
        raise HTTPException(status_code=400, detail=f"{original_name} 是空 PDF")
    if page_count > MAX_PDF_PAGES:
        raise HTTPException(
            status_code=400,
            detail=f"{original_name} 有 {page_count} 页，超过单个 PDF {MAX_PDF_PAGES} 页上限，请拆分后上传",
        )

    images: list[dict] = []
    for index in range(page_count):
        bitmap = pdf[index].render(scale=150 / 72)
        pil_image = bitmap.to_pil()
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        image_id = uuid.uuid4().hex[:8]
        temp_path = account_dir / f"{image_id}.png"
        temp_path.write_bytes(buffer.getvalue())
        images.append({
            "id": image_id,
            "path": str(temp_path),
            "filename": f"{original_name}-第{index + 1}页.png",
        })
    pdf.close()
    return images


def _sniff_image_format(data: bytes) -> str | None:
    """
    按文件头判断真实图片格式。

    仅凭扩展名校验会被改名后的任意文件绕过，因此这里同时做内容嗅探。
    无法识别时返回 None。
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if len(data) >= 12 and data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS:
        return "heic"
    return None


def _resolution_warning(data: bytes, original_name: str) -> str | None:
    """
    分辨率过低只提示不拦截。

    HEIC 需要额外解码器，Pillow 打不开时静默跳过，不做误判。
    """
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None
    if min(width, height) < MIN_DIMENSION:
        return f"{original_name} 分辨率偏低（{width}×{height}），可能影响识别效果"
    return None


@router.post("/upload/images")
async def upload_images(
    files: list[UploadFile] = File(...),
    account: Account = Depends(get_active_account),
):
    """
    上传图片/PDF 到临时目录，返回 image_ids 供 /api/tasks 或 /api/zhenti/import 创建分析任务。
    PDF 会逐页渲染成 PNG（v2.0 真题卷导入）。

    图片不会进入 vault，只在分析期间存在，由 TTL 自动回收。
    """
    sweep_expired_uploads()

    if not files:
        raise HTTPException(status_code=400, detail="请至少选择一张图片")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400, detail=f"一次最多上传 {MAX_FILES_PER_UPLOAD} 张图片"
        )

    account_dir = TEMP_DIR / account.id
    account_dir.mkdir(parents=True, exist_ok=True)

    image_ids: list[dict] = []
    warnings: list[str] = []

    for upload in files:
        original_name = upload.filename or "image"
        suffix = Path(original_name).suffix.lower()

        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"{original_name} 格式不受支持，请上传 jpg / png / heic / webp 图片或 PDF",
            )

        content = await upload.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"{original_name} 是空文件")
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400, detail=f"{original_name} 超过 20MB，请压缩后重试"
            )

        # PDF：逐页转图后并入 image_ids（v2.0 真题卷）
        if suffix == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise HTTPException(status_code=400, detail=f"{original_name} 不是有效的 PDF 文件")
            page_images = _pdf_to_page_images(content, original_name, account_dir)
            if len(image_ids) + len(page_images) > MAX_TOTAL_IMAGES:
                raise HTTPException(
                    status_code=400,
                    detail=f"展开后图片总数超过 {MAX_TOTAL_IMAGES} 张上限，请减少文件数量",
                )
            image_ids.extend(page_images)
            continue

        if _sniff_image_format(content) is None:
            raise HTTPException(
                status_code=400, detail=f"{original_name} 不是有效的图片文件"
            )

        warning = _resolution_warning(content, original_name)
        if warning:
            warnings.append(warning)

        if len(image_ids) >= MAX_TOTAL_IMAGES:
            raise HTTPException(
                status_code=400,
                detail=f"展开后图片总数超过 {MAX_TOTAL_IMAGES} 张上限，请减少文件数量",
            )
        image_id = uuid.uuid4().hex[:8]
        temp_path = account_dir / f"{image_id}{suffix}"
        temp_path.write_bytes(content)
        image_ids.append({"id": image_id, "path": str(temp_path), "filename": original_name})

    return {"image_ids": image_ids, "warnings": warnings}
