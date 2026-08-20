import asyncio
import edge_tts
from pathlib import Path
from pydub import AudioSegment
import subprocess
import asyncio
import edge_tts

VOICE_MAP = {
    "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural",
    "de": "de-DE-ConradNeural",
    "hi": "hi-IN-MadhurNeural",
    "zh": "zh-CN-YunxiNeural",
    "en": "en-US-ChristopherNeural"
}

async def synthesize_segment(text: str, voice: str, output_path: Path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))

def synthesize_all_sync(segments: list[dict], target_language: str, tmp_dir: Path) -> dict[int, Path]:
    voice = VOICE_MAP.get(target_language, "en-US-ChristopherNeural")
    paths = {}
    
    async def run_all():
        for seg in segments:
            out_path = tmp_dir / f"seg_{seg['id']}.mp3"
            if seg["text"].strip():
                await synthesize_segment(seg["text"], voice, out_path)
                if out_path.exists():
                    paths[seg["id"]] = out_path

    asyncio.run(run_all())
    return paths

def build_dubbed_audio(segments: list[dict], audio_paths: dict[int, Path], total_duration_ms: int) -> AudioSegment:
    combined = AudioSegment.silent(duration=total_duration_ms)
    
    for seg in segments:
        seg_id = seg["id"]
        if seg_id not in audio_paths:
            continue
        
        clip = AudioSegment.from_file(str(audio_paths[seg_id]))
        target_start_ms = int(seg["start"] * 1000)
        target_duration_ms = int((seg["end"] - seg["start"]) * 1000)
        
        # Time stretching / fitting logic to prevent timestamp clipping overflow
        if len(clip) > target_duration_ms and target_duration_ms > 500:
            # Fast-speed compression fit if speech is longer than video window
            speed_factor = len(clip) / target_duration_ms
            if speed_factor < 1.5: # safety threshold
                try:
                    import librosa
                    import numpy as np
                    # Advanced time stretching placeholder or simple crop safeguard
                    clip = clip[:target_duration_ms]
                except ImportError:
                    clip = clip[:target_duration_ms]
        
        combined = combined.overlay(clip, position=target_start_ms)
    return combined

async def generate_dubbed_video(translated_segments: list[dict], input_video_path: str, output_video_path: str):
    full_text = " ".join([seg["text"] for seg in translated_segments])
    temp_audio = "temp_english_audio.mp3"
    
    # Generate English voice track using Microsoft Edge TTS
    communicate = edge_tts.Communicate(full_text, "en-US-AriaNeural")
    await communicate.save(temp_audio)
    
    # Merge audio into video using FFmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", input_video_path,
        "-i", temp_audio,
        "-c:v", "copy",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_video_path
    ]
    subprocess.run(cmd, check=True)