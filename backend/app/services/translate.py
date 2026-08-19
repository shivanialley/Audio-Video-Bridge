from __future__ import annotations
import re
from google import genai
from google.genai import types
from backend.app.config import GOOGLE_API_KEY

client = genai.Client(api_key=GOOGLE_API_KEY) if 'GOOGLE_API_KEY' in globals() or 'GOOGLE_API_KEY' in locals() else genai.Client()

def translate_segments(segments: list[dict], source_language: str, target_language: str) -> list[dict]:
    """
    Translates transcription segments line-by-line into the target language using Gemini,
    guaranteeing that start and end timestamps are permanently preserved.
    """
    if not segments:
        return []

    print(f"[TRANSLATE] Translating {len(segments)} segments from {source_language} to {target_language}...")

    # Extract just the text lines with explicit numbering
    lines_text = "\n".join([f"[{i}] {seg['text']}" for i, seg in enumerate(segments)])
    
    prompt = f"""You are a professional subtitle translator. 
Translate each bracketed text line below from {source_language} into fluent, natural {target_language}.

RULES:
1. Keep the exact same bracketed index numbers (e.g., [0], [1], [2]).
2. Translate only the text inside or after the index into {target_language}.
3. Do not omit any lines.

Lines to translate:
{lines_text}"""

    try:
        response = client.models.generate_content(
            model='gemini-3.7-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2
            ),
        )
        
        raw_text = response.text.strip()
        print(f"[TRANSLATE] Raw response received successfully.")
        
        # Parse indexed lines using regex (e.g., [0] Translated text)
        translated_map = {}
        for match in re.finditer(r'\[(\d+)\]\s*(.*)', raw_text):
            idx = int(match.group(1))
            text = match.group(2).strip()
            translated_map[idx] = text

        translated_segments = []
        for i, original_seg in enumerate(segments):
            # Fallback to original text only if that specific index wasn't found
            new_text = translated_map.get(i, original_seg["text"])

            translated_segments.append({
                "start": float(original_seg["start"]),
                "end": float(original_seg["end"]),
                "text": new_text
            })

        print("[TRANSLATE] Translation & timestamp synchronization completed successfully.")
        return translated_segments

    except Exception as e:
        print(f"[TRANSLATE ERROR] Translation processing failed: {e}")
        return [
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": seg["text"]
            } 
            for seg in segments
        ]