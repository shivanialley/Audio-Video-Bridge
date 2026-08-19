from __future__ import annotations

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app import database
from app.config import (
    ALLOWED_UPLOAD_EXTENSIONS,
    BASE_DIR,
    MAX_UPLOAD_MB,
    OUTPUT_DIR,
    SUPPORTED_LANGUAGES,
    UPLOAD_DIR,
)
from app.schemas import JobCreatedResponse, JobStatusResponse, LanguageOption
from app.services.pipeline import run_job

from pydantic import BaseModel
from google import genai
import os

executor = ThreadPoolExecutor(max_workers=2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield

app = FastAPI(
    title="Audio-Bridge Transcription, Translation & Dubbing System",
    description="Production backend for automated media subtitling, localization, and AI voice dubbing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/api/languages", response_model=list[LanguageOption])
def list_languages() -> list[dict]:
    return SUPPORTED_LANGUAGES

@app.post("/api/jobs", response_model=JobCreatedResponse, status_code=201)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    source_language: str = Form("auto"),
    target_language: str = Form("en"),
) -> dict:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File exceeds the {MAX_UPLOAD_MB}MB limit for this demo.")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )
    
    if target_language not in {l["code"] for l in SUPPORTED_LANGUAGES} and target_language != "auto":
        raise HTTPException(400, f"Unsupported target language '{target_language}'.")

    job_id = str(uuid.uuid4())[:8]
    dest_path = UPLOAD_DIR / f"{job_id}{suffix}"
    
    with open(dest_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    conn = database.get_db()
    conn.execute(
        "INSERT INTO jobs (id, status, stage_message, progress, original_filename, source_language, target_language, artifacts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, "queued", "Job queued in background pool", 0, file.filename, source_language, target_language, "{}")
    )
    conn.commit()

    # Pass both source and target language to the background processing pipeline
    executor.submit(run_job, job_id, dest_path, target_language, source_language)
    return {"job_id": job_id, "status": "processing"}

@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> dict:
    conn = database.get_db()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Job not found.")

    import ast
    try:
        artifacts_dict = ast.literal_eval(row["artifacts"]) if row["artifacts"] else {}
    except Exception:
        artifacts_dict = {}

    artifact_urls = {name: f"/api/jobs/{job_id}/artifacts/{name}" for name in artifacts_dict}
    
    return {
        "job_id": row["id"],
        "status": row["status"],
        "stage_message": row["stage_message"] or "",
        "progress": row["progress"],
        "original_filename": row["original_filename"],
        "source_language": row["source_language"],
        "target_language": row["target_language"],
        "has_video": bool(row["has_video"]),
        "error": row["error"],
        "artifacts": artifact_urls,
    }

@app.get("/api/jobs/{job_id}/artifacts/{artifact_name}")
def download_artifact(job_id: str, artifact_name: str):
    conn = database.get_db()
    row = conn.execute("SELECT artifacts FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Job not found.")

    import ast
    artifacts_dict = ast.literal_eval(row["artifacts"]) if row["artifacts"] else {}
    filename = artifacts_dict.get(artifact_name)
    if not filename:
        raise HTTPException(404, "Artifact not found for this job.")

    path = OUTPUT_DIR / job_id / filename
    if not path.exists():
        raise HTTPException(404, "Artifact file is missing on disk.")
    return FileResponse(path, filename=f"{job_id}_{filename}")

@app.get("/api/jobs/{job_id}/summary")
def get_video_summary(job_id: str) -> dict:
    try:

        conn = database.get_db()
        row = conn.execute("SELECT artifacts FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Job not found.")
    
        import ast
        artifacts_dict = ast.literal_eval(row["artifacts"]) if row["artifacts"] else {}
        srt_filename = artifacts_dict.get("translated_srt") or artifacts_dict.get("original_srt")
    
        if not srt_filename:
            raise HTTPException(400, "No transcript available yet to summarize.")
        
        srt_path = OUTPUT_DIR / job_id / srt_filename
        if not srt_path.exists():
            raise HTTPException(404, "Subtitle file missing on disk.")
        
        transcript_text = srt_path.read_text(encoding="utf-8")
    
        # Initialize the modern Google GenAI client (automatically picks up GEMINI_API_KEY)
        client = genai.Client()
    
        prompt = f"Provide a comprehensive, clear, and structured summary of the key insights from this video transcript:\n\n{transcript_text}"
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
        )
    
        return {"summary": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    job_id: str
    question: str

@app.post("/api/jobs/chat")
def chat_with_video(payload: ChatRequest) -> dict:
    conn = database.get_db()
    row = conn.execute("SELECT artifacts FROM jobs WHERE id=?", (payload.job_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Job not found.")
    
    import ast
    artifacts_dict = ast.literal_eval(row["artifacts"]) if row["artifacts"] else {}
    srt_filename = artifacts_dict.get("translated_srt") or artifacts_dict.get("original_srt")
    
    if not srt_filename:
        raise HTTPException(400, "Transcript/Translation not ready yet.")
    
    srt_path = OUTPUT_DIR / payload.job_id / srt_filename
    if not srt_path.exists():
        raise HTTPException(404, "Subtitle file missing on disk.")
    
    transcript_text = srt_path.read_text(encoding="utf-8")
    
    # Initialize the modern Google GenAI client
    client = genai.Client()
    
    prompt = f"You are a helpful video intelligence assistant. Answer the user's question accurately using only information derived from the provided video transcript context.\n\nTranscript Context:\n{transcript_text}\n\nUser Question: {payload.question}"
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=prompt,
    )
    
    return {"answer": response.text}

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# Serve Frontend Static UI at the very bottom
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    