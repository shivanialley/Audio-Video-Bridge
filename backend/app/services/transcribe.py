from __future__ import annotations

import json
import mimetypes
import os
from google import genai
from google.genai import types

def transcribe(audio_path: str, language_hint: str = "auto"):
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Input file not found at: {audio_path}")

    client = genai.Client()

    mime_type, _ = mimetypes.guess_type(audio_path)
    if not mime_type:
        mime_type = "video/mp4"

    print(f"[TRANSCRIBE] Reading file bytes ({os.path.getsize(audio_path)} bytes)...")
    with open(audio_path, "rb") as f:
        media_bytes = f.read()

    # Prompt Gemini to transcribe the audio in its original native spoken language and detect the language code
    prompt = (
        f"Transcribe the spoken audio in this file line by line in its original spoken language. "
        f"The spoken language hint provided by user is {language_hint}. "
        f"Provide the exact start time and end time in seconds (float) for each spoken segment, along with the text, "
        f"and return the ISO code of the detected language (e.g., 'hi', 'en', 'es', 'fr')."
    )

    print("[TRANSCRIBE] Requesting Gemini transcript with timestamps and language detection...")
    
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=[
            types.Part.from_bytes(data=media_bytes, mime_type=mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "detected_language": {"type": "STRING", "description": "ISO language code like hi, en, es, fr"},
                    "segments": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "start": {"type": "NUMBER", "description": "Start time in seconds"},
                                "end": {"type": "NUMBER", "description": "End time in seconds"},
                                "text": {"type": "STRING", "description": "Spoken text line in original language"}
                            },
                            "required": ["start", "end", "text"]
                        }
                    }
                },
                "required": ["detected_language", "segments"]
            }
        )
    )

    segments = []
    detected_lang = language_hint if language_hint and language_hint != "auto" else "en"
    
    try:
        data = json.loads(response.text.strip())
        detected_lang = data.get("detected_language", detected_lang)
        raw_segments = data.get("segments", [])
        for idx, item in enumerate(raw_segments):
            segments.append({
                "id": idx + 1,
                "start": float(item["start"]),
                "end": float(item["end"]),
                "text": item["text"].strip()
            })
    except Exception as e:
        print(f"[TRANSCRIBE PARSE ERROR]: {e}")

    if not segments:
        segments = [{
            "id": 1, 
            "start": 0.0, 
            "end": 5.0, 
            "text": (response.text or "No speech detected").strip()
        }]

    return segments, detected_lang

def parse_time_to_float(val):
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if ":" in val:
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