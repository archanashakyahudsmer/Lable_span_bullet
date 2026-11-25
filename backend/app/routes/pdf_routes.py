from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.services.pdf_service import inspect_pdf, process_pdf

router = APIRouter()
MAX_BYTES = 40 * 1024 * 1024


async def save_upload(file: UploadFile, folder: Path) -> Path:
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="PDF exceeds the 40 MB upload limit.")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")
    path = folder / "input.pdf"
    path.write_bytes(data)
    return path


@router.post("/inspect")
async def inspect(file: UploadFile = File(...)):
    with TemporaryDirectory(prefix="actual_text_") as temp:
        path = await save_upload(file, Path(temp))
        try:
            return inspect_pdf(path)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not inspect PDF: {exc}") from exc


@router.post("/process")
async def process(file: UploadFile = File(...)):
    # Keep the temp directory alive until FileResponse has finished streaming.
    # Without the BackgroundTask the TemporaryDirectory may be removed as soon
    # as this endpoint returns, causing a broken/missing PDF download.
    temp = TemporaryDirectory(prefix="actual_text_")
    try:
        input_path = await save_upload(file, Path(temp.name))
        output_path = Path(temp.name) / "processed.pdf"
        result = process_pdf(input_path, output_path)
    except HTTPException:
        temp.cleanup()
        raise
    except Exception as exc:
        temp.cleanup()
        raise HTTPException(status_code=422, detail=f"Could not process PDF: {exc}") from exc

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{Path(file.filename).stem}_actual_text.pdf",
        headers={
            "X-Repair-Created-Spans": str(result["created_spans"]),
            "X-Repair-Unchanged-Spans": str(result["unchanged_spans"]),
            "X-Repair-Skipped": str(result["skipped"]),
        },
        background=BackgroundTask(temp.cleanup),
    )
