from __future__ import annotations

from pathlib import Path
import traceback

from app.config import OUTPUT_DIR
from backend.app.database import get_db, update_job_stage
from backend.app.services import transcribe, translate
from backend.app.services.quality import (
    evaluate_translation_accuracy,
    evaluate_translation_quality,
)
from backend.app.services.srt_utils import generate_srt
from backend.app.services.tts import generate_tts_audio
from backend.app.services.video_utils import rebuild_dubbed_video


def run_job(
    job_id: str, file_path: str, source_language: str, target_language: str
):
    """Main job executor triggered asynchronously.

    Executes Transcription -> Translation -> Audit -> Target Voice TTS -> Video
    Rendering.
    """
    print(f"\n[JOB {job_id}] Execution started for file: {file_path}")
    job_output_dir = OUTPUT_DIR / job_id
    job_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Video/Audio Transcription using Gemini
        print(
            f"[JOB {job_id}] Step 1: Uploading and transcribing via Gemini..."
        )
        update_job_stage(
            job_id, "Running AI multimodal transcription (Gemini)...", progress=20
        )

        segments, detected_lang = transcribe.transcribe(
            audio_path=file_path, language_hint=source_language
        )
        print(
            f"[JOB {job_id}] Transcription complete! Detected language:"
            f" {detected_lang}, Requested target: {target_language}"
        )

        # Save original SRT
        original_srt_filename = "original.srt"
        original_srt_path = job_output_dir / original_srt_filename
        original_srt_content = generate_srt(segments)
        original_srt_path.write_text(original_srt_content, encoding="utf-8")

        # Step 2: Translation using Gemini
        print(
            f"[JOB {job_id}] Step 2: Translating transcript from"
            f" {detected_lang} to {target_language}..."
        )
        update_job_stage(
            job_id, f"Translating lines into {target_language}...", progress=40
        )

        translated_segments = translate.translate_segments(
            segments=segments,
            source_language=detected_lang,
            target_language=target_language,
        )
        print(f"[JOB {job_id}] Translation complete!")

        # Save translated SRT
        translated_srt_filename = f"translated_{target_language}.srt"
        translated_srt_path = job_output_dir / translated_srt_filename
        translated_srt_content = generate_srt(translated_segments)
        translated_srt_path.write_text(translated_srt_content, encoding="utf-8")

        # Step 2.5: Run Gemini Quality & Accuracy Audit
        print(f"[JOB {job_id}] Step 2.5: Running AI Quality & Accuracy Audit...")
        update_job_stage(
            job_id, "Evaluating translation accuracy...", progress=60
        )

        full_original_text = " ".join([seg["text"] for seg in segments])
        full_translated_text = " ".join(
            [seg["text"] for seg in translated_segments]
        )

        # 1. Evaluate accuracy score and structured audit using Gemini
        audit_result = evaluate_translation_accuracy(
            original_text=original_srt_content,
            translated_text=translated_srt_content,
            target_lang=target_language,
        )
        accuracy_score = audit_result.get("accuracy_score", 0)
        print(
            f"[JOB {job_id}] Quality Audit Complete! Accuracy Score:"
            f" {accuracy_score}%"
        )

        # 2. Write Markdown audit summary artifact
        quality_report = evaluate_translation_quality(
            original_text=full_original_text,
            translated_text=full_translated_text,
            target_language=target_language,
        )
        quality_report_filename = "quality_audit.md"
        quality_report_path = job_output_dir / quality_report_filename
        quality_report_path.write_text(quality_report, encoding="utf-8")

        # Step 3: Generate Translated Audio (TTS)
        print(
            f"[JOB {job_id}] Step 3: Synthesizing voice audio in"
            f" {target_language}..."
        )
        update_job_stage(
            job_id,
            f"Generating translated voice audio ({target_language})...",
            progress=75,
        )

        tts_audio_filename = "generated_tts_audio.mp3"
        tts_audio_path = job_output_dir / tts_audio_filename

        generate_tts_audio(
            translated_segments=translated_segments,
            target_language=target_language,
            output_audio_path=tts_audio_path,
        )

        # Step 4: Rebuild Video with Translated Audio & Subtitles
        print(
            f"[JOB {job_id}] Step 4: Multiplexing translated audio & SRT"
            " onto video..."
        )
        update_job_stage(
            job_id, "Rendering final dubbed video file...", progress=90
        )

        output_video_filename = f"dubbed_{job_id}.mp4"
        output_video_path = str(job_output_dir / output_video_filename)

        rebuild_dubbed_video(
            video_path=str(file_path),
            translated_audio_path=str(tts_audio_path),
            srt_path=str(translated_srt_path),
            output_path=output_video_path,
        )
        print(f"[JOB {job_id}] Video rendering completed successfully!")

        # Step 5: Package artifacts and complete processing pipeline
        artifacts = {
            "original_srt": original_srt_filename,
            "translated_srt": translated_srt_filename,
            "quality_report": quality_report_filename,
            "output_video": output_video_filename,
        }

        conn = get_db()
        # Save accuracy_score directly in DB
        conn.execute(
            """
            UPDATE jobs 
            SET stage_message = ?, progress = ?, status = ?, artifacts = ?, accuracy_score = ?, has_video = 1
            WHERE id = ?
            """,
            (
                "Pipeline finished successfully!",
                100,
                "completed",
                str(artifacts),
                accuracy_score,
                job_id,
            ),
        )
        conn.commit()
        print(
            f"[JOB {job_id}] Job finished successfully with artifacts saved!\n"
        )

    except Exception as e:
        err_msg = str(e)
        print(f"[JOB {job_id}] ERROR ENCOUNTERED: {err_msg}")
        traceback.print_exc()

        update_job_stage(
            job_id=job_id,
            stage_message=f"Pipeline failed: {err_msg}",
            progress=0,
            status="failed",
            error=err_msg,
        )