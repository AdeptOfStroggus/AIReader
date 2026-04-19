import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="AIReader Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

state = {
    "client": None,
    "converter": None,
    "current_pdf_path": None,
    "converted_text": "",
    "converted_images": [],
    "total_pages": 0,
    "is_converting": False,
    "conversion_done": False,
}


@app.on_event("startup")
async def startup():
    from ai_client import AIClient
    from doc_converter import Converter
    state["converter"] = Converter()
    state["client"] = AIClient()


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "web_ui" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)):
    upload_dir = Path(tempfile.gettempdir()) / "aireader_web"
    upload_dir.mkdir(exist_ok=True)

    pdf_path = upload_dir / file.filename
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    state["current_pdf_path"] = str(pdf_path)
    state["converted_text"] = ""
    state["converted_images"] = []
    state["conversion_done"] = False
    state["is_converting"] = False

    state["client"].clear_history()

    total_pages = state["converter"].getPagesCount(str(pdf_path))
    state["total_pages"] = total_pages

    return {"filename": file.filename, "total_pages": total_pages}


@app.get("/api/convert")
async def convert_pdf():
    if not state["current_pdf_path"]:
        raise HTTPException(400, "No PDF uploaded")
    if state["is_converting"]:
        raise HTTPException(400, "Conversion already in progress")

    async def generate():
        state["is_converting"] = True
        converter = state["converter"]
        pdf_path = state["current_pdf_path"]
        total_pages = state["total_pages"]

        all_text = []
        all_images = []
        batch_size = 4

        for offset in range(0, total_pages, batch_size):
            pages_in_batch = min(batch_size, total_pages - offset)
            try:
                loop = asyncio.get_event_loop()
                text, html, images = await loop.run_in_executor(
                    None, converter.convertPdf, pdf_path, pages_in_batch, offset
                )
                all_text.append(text)
                all_images.extend(images or [])

                done = offset + pages_in_batch
                pct = int(done / total_pages * 100)
                yield f"data: {json.dumps({'type': 'progress', 'page': done, 'total': total_pages, 'pct': pct})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                state["is_converting"] = False
                return

        state["converted_text"] = "\n\n".join(all_text)
        state["converted_images"] = all_images
        state["conversion_done"] = True
        state["is_converting"] = False
        yield f"data: {json.dumps({'type': 'done', 'pages': total_pages})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/models")
async def get_models():
    models = await state["client"].GetModelsAsync()
    return {"models": models}


class ChatRequest(BaseModel):
    query: str
    model_id: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not state["converted_text"] and not state["converted_images"]:
        raise HTTPException(400, "No document loaded")

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'thinking'})}\n\n"
            response = await state["client"].CreateResponceAsync(
                req.model_id,
                req.query,
                state["converted_text"],
                state["converted_images"],
            )
            yield f"data: {json.dumps({'type': 'response', 'html': response})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/chat/reset")
async def reset_chat():
    state["client"].clear_history()
    return {"status": "ok"}


@app.get("/api/pdf")
async def serve_pdf():
    if not state["current_pdf_path"] or not Path(state["current_pdf_path"]).exists():
        raise HTTPException(404, "No PDF loaded")
    return FileResponse(state["current_pdf_path"], media_type="application/pdf",
                        headers={"Content-Disposition": "inline"})


@app.get("/api/status")
async def get_status():
    return {
        "has_pdf": bool(state["current_pdf_path"]),
        "total_pages": state["total_pages"],
        "conversion_done": state["conversion_done"],
        "is_converting": state["is_converting"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
