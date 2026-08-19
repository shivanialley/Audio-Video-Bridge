from __future__ import annotations

import mimetypes
import os
from google import genai
from google.genai import types

def transcribe(audio_path: str, language_hint: str = "auto"):
    """
    Fast direct-byte transcription using gemini-3.6-flash without using remote file queues.
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Input file not found at: {audio_path}")

    client = genai.Client()

    mime_type, _ = mimetypes.guess_type(audio_path)
    if not mime_type:
        mime_type = "video/mp4"

    print(f"[TRANSCRIBE] Reading file bytes ({os.path.getsize(audio_path)} bytes)...")
    with open(audio_path, "rb") as f:
        media_bytes = f.read()

    prompt = (
        f"Transcribe the spoken audio in this file clearly line by line. "
        f"The language is likely {language_hint}."
    )

    print("[TRANSCRIBE] Requesting Gemini 3.6 Flash response...")
    
    response = client.models.generate_content(
        model='gemini-3.7-flash',
        contents=[
            types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
            prompt
        ]
    )

    raw_text = (response.text or "").strip()
    print(f"[TRANSCRIBE] Response received: {raw_text[:50]}...")

    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    segments = []
    
    for idx, line in enumerate(lines):
        start_str = f"00:00:{idx*2:02d},000"
        end_str = f"00:00:{(idx+1)*2:02d},000"
        
        segments.append({
            "id": idx + 1,
            "start": parse_time_to_float(start_str),
            "end": parse_time_to_float(end_str),
            "text": line
        })

    if not segments:
        segments = [{
            "id": 1, 
            "start": parse_time_to_float("00:00:00,000"), 
            "end": parse_time_to_float("00:00:05,000"), 
            "text": raw_text or "No speech detected"
        }]

    return segments, language_hint


def parse_time_to_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if ":" in val:
            # Handles '00:00:00,000' format
            val = val.replace(",", ".")
            parts = val.split(":")
            try:
                if len(parts) == 3:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                elif len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
            except ValueError:
                pass
        try:
            return float(val)
        except ValueError:
            pass
    return 0.0