from __future__ import annotations

import traceback
from pathlib import Path
from backend.app.database import get_db, update_job_stage
from backend.app.services import transcribe, translate
from backend.app.services.srt_utils import generate_srt
from app.services.quality import evaluate_translation_quality
from app.config import OUTPUT_DIR

def run_job(job_id: str, file_path: str, source_language: str, target_language: str):
    """
    Main job executor triggered asynchronously.
    Updates database status and saves SRT artifacts at each processing milestone.
    """
    print(f"\n[JOB {job_id}] Execution started for file: {file_path}")
    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Video/Audio Transcription using Gemini
        print(f"[JOB {job_id}] Step 1: Uploading and transcribing via Gemini...")
        update_job_stage(job_id, "Running AI multimodal transcription (Gemini)...", progress=25)
        
        segments, detected_lang = transcribe.transcribe(
            audio_path=file_path, 
            language_hint=source_language
        )
        print(f"[JOB {job_id}] Transcription complete! Detected language: {detected_lang}, Requested target: {target_language}")
        
        # Generate and save original SRT file (always in the native/detected source language)
        original_srt_filename = "original.srt"
        original_srt_path = job_output_dir / original_srt_filename
        original_srt_content = generate_srt(segments)
        original_srt_path.write_text(original_srt_content, encoding="utf-8")

        # Step 2: Translation using Gemini (forces translation even if source and target look similar)
        print(f"[JOB {job_id}] Step 2: Translating transcript from {detected_lang} to {target_language}...")
        update_job_stage(job_id, f"Translating lines into {target_language}...", progress=60)
        
        translated_segments = translate.translate_segments(
            segments=segments,
            source_language=detected_lang,
            target_language=target_language
        )
        print(f"[JOB {job_id}] Translation complete!")
        
        # Generate and save translated SRT file dynamically matching the target language code
        translated_srt_filename = f"translated_{target_language}.srt"
        translated_srt_path = job_output_dir / translated_srt_filename
        translated_srt_content = generate_srt(translated_segments)
        translated_srt_path.write_text(translated_srt_content, encoding="utf-8")

        # Step 2.5: Run Quality & Accuracy Evaluation Audit
        print(f"[JOB {job_id}] Step 2.5: Running AI Quality Audit...")
        full_original_text = " ".join([seg["text"] for seg in segments])
        full_translated_text = " ".join([seg["text"] for seg in translated_segments])
        
        quality_report = evaluate_translation_quality(
            original_text=full_original_text, 
            translated_text=full_translated_text, 
            target_language=target_language
        )
        
        # Save quality audit report as a text artifact file
        quality_report_filename = "quality_audit.md"
        quality_report_path = job_output_dir / quality_report_filename
        quality_report_path.write_text(quality_report, encoding="utf-8")
        print(f"[JOB {job_id}] Quality Audit Report generated successfully.")

        # Step 3: Package artifacts and complete processing pipeline
        artifacts = {
            "original_srt": original_srt_filename,
            "translated_srt": translated_srt_filename,
            "quality_report": quality_report_filename
        }

        conn = get_db()
        conn.execute(
            """
            UPDATE jobs 
            SET stage_message = ?, progress = ?, status = ?, artifacts = ?
            WHERE id = ?
            """,
            ("Pipeline finished successfully!", 100, "completed", str(artifacts), job_id)
        )
        conn.commit()
        print(f"[JOB {job_id}] Job finished successfully with artifacts saved!\n")

    except Exception as e:
        err_msg = str(e)
        print(f"[JOB {job_id}] ERROR ENCOUNTERED: {err_msg}")
        traceback.print_exc()
        
        update_job_stage(
            job_id=job_id, 
            stage_message=f"Pipeline failed: {err_msg}", 
            progress=0, 
            status="failed", 
            error=err_msg
        )