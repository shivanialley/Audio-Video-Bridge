from __future__ import annotations
import re
from google import genai
from google.genai import types
from backend.app.config import GOOGLE_API_KEY

client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else genai.Client()

def translate_segments(segments: list[dict], source_language: str, target_language: str) -> list[dict]:
    if not segments:
        return []

    # Map short language codes to full names for better LLM context if desired
    lang_map = {
        "en": "English", "hi": "Hindi", "es": "Spanish", "fr": "French", 
        "de": "German", "zh": "Chinese", "ja": "Japanese", "ar": "Arabic", "auto": "English"
    }
    target_lang_name = lang_map.get(target_language.lower(), target_language)
    source_lang_name = lang_map.get(source_language.lower(), source_language)

    lines_text = "\n".join([f"[{i}] {seg['text']}" for i, seg in enumerate(segments)])
    
    prompt = f"""You are a professional subtitle translator. Translate each bracketed line below from {source_lang_name} into fluent, natural {target_lang_name}.
Keep the exact same bracketed index numbers (e.g., [0], [1]). Do not omit any lines.

Lines to translate:
{lines_text}"""

    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        
        raw_text = response.text.strip()
        translated_map = {}
        for match in re.finditer(r'\[(\d+)\]\s*(.*)', raw_text):
            idx = int(match.group(1))
            text = match.group(2).strip()
            translated_map[idx] = text

        translated_segments = []
        for i, original_seg in enumerate(segments):
            new_text = translated_map.get(i, original_seg["text"])
            translated_segments.append({
                "start": float(original_seg["start"]),
                "end": float(original_seg["end"]),
                "text": new_text
            })
        return translated_segments

    except Exception as e:
        print(f"[TRANSLATE CRITICAL ERROR]: {e}")
        raise e