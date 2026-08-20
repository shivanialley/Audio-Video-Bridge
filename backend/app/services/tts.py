from pathlib import Path
from gtts import gTTS


def generate_tts_audio(
    translated_segments: list[dict], target_language: str, output_audio_path: Path
) -> Path:
    """Generates translated speech audio from segments using Google Text-to-Speech (gTTS)."""
    full_text = " ".join([seg.get("text", "") for seg in translated_segments if seg.get("text")])

    if not full_text.strip():
        full_text = "Translation context empty."

    # Normalize language codes (e.g., 'en-US' or 'English' -> 'en')
    lang_code = target_language.lower().split("-")[0].strip()
    if len(lang_code) > 2 and lang_code not in ["zh-cn", "zh-tw"]:
        lang_code = "en"  # Fallback to default if string name passed

    try:
        tts = gTTS(text=full_text, lang=lang_code, slow=False)
        tts.save(str(output_audio_path))
        print(f"[TTS SUCCESS] Audio generated in '{lang_code}' at: {output_audio_path}")
    except Exception as e:
        print(f"[TTS WARNING] Primary TTS failed for language '{lang_code}': {e}. Falling back to English.")
        tts = gTTS(text=full_text, lang="en", slow=False)
        tts.save(str(output_audio_path))

    return output_audio_path