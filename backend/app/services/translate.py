from __future__ import annotations
import json
import re
from google import genai
from google.genai import types
from backend.app.config import GOOGLE_API_KEY  # Or pass explicitly if loaded from env

# Initialize client using your configuration key safely
client = genai.Client(api_key=GOOGLE_API_KEY) if 'GOOGLE_API_KEY' in globals() or 'GOOGLE_API_KEY' in locals() else genai.Client()

def translate_segments(segments: list[dict], source_language: str, target_language: str) -> list[dict]:
    """
    Translates transcription segments into the target language using Gemini,
    guaranteeing that start and end timestamps are permanently preserved.
    """
    if not segments:
        return []

    print(f"[TRANSLATE] Translating {len(segments)} segments from {source_language} to {target_language}...")

    # Build payload mapping indices to text elements
    payload = [{"id": i, "text": seg["text"]} for i, seg in enumerate(segments)]
    
    prompt = f"""
    You are an expert multilingual subtitle translator. 
    Translate the 'text' field of each object in the JSON array below from source language '{source_language}' completely and accurately into fluent, natural target language '{target_language}'.
    
    RULES:
    1. Output ONLY a valid JSON array matching the exact structure given, containing the corresponding 'id' numbers.
    2. Do NOT omit, modify, or reorder the array items.
    3. Translate all text completely into {target_language}. Do not leave it in the source language.
    
    Input JSON:
    {json.dumps(payload, ensure_ascii=False)}
    """

    try:
        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            ),
        )
        
        raw_text = response.text.strip()
        
        # Clean any markdown block formatting tags returned by the model
        if raw_text.startswith("```"):
            raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
            
        translated_data = json.loads(raw_text)
        
        # Rebuild segments carefully locking in original float start/end times
        translated_segments = []
        for i, original_seg in enumerate(segments):
            new_text = original_seg["text"]  # Default fallback to original text if missing
            
            # Match translation text safely by ID index or position fallback
            matched = None
            if isinstance(translated_data, list):
                # Try finding by explicit ID first
                matched = next((item for item in translated_data if isinstance(item, dict) and item.get("id") == i), None)
                # Fallback to positional index if ID lookup fails
                if not matched and i < len(translated_data):
                    matched = translated_data[i]

            if matched and isinstance(matched, dict) and "text" in matched:
                new_text = matched["text"]

            translated_segments.append({
                "start": float(original_seg["start"]),
                "end": float(original_seg["end"]),
                "text": new_text
            })

        print("[TRANSLATE] Translation & timestamp synchronization completed successfully.")
        return translated_segments

    except Exception as e:
        print(f"[TRANSLATE ERROR] Failed to parse translation JSON: {e}")
        print(f"[DEBUG] Raw response was: {response.text if 'response' in locals() else 'No response'}")
        
        # Fallback safety: ensures timestamps are never lost even if the API errors out
        return [
            {
                "start": float(seg["start"]),
                "end": float(seg["end"]),
                "text": seg["text"]
            } 
            for seg in segments
        ]