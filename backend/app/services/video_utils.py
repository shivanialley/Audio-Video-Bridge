import os
import subprocess


def rebuild_dubbed_video(
    video_path: str,
    translated_audio_path: str | None,
    srt_path: str,
    output_path: str,
) -> str:
    """Combines original video with translated subtitles (and optional audio) using FFmpeg."""
    try:
        # Format path slashes properly for FFmpeg filter syntax on Windows
        clean_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")

        if translated_audio_path and os.path.exists(translated_audio_path):
            # Overlay translated TTS audio and burn SRT subtitles
            ffmpeg_cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-i",
                translated_audio_path,
                "-vf",
                f"subtitles='{clean_srt_path}'",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                output_path,
                "-y",
            ]
        else:
            # Keep original video audio, burn SRT subtitles directly
            ffmpeg_cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                f"subtitles='{clean_srt_path}'",
                "-c:a",
                "copy",
                output_path,
                "-y",
            ]

        subprocess.run(ffmpeg_cmd, check=True)
        print(f"[VIDEO UTILS] Video successfully generated at: {output_path}")
        return output_path

    except Exception as e:
        print(f"[VIDEO UTILS ERROR]: {e}")
        # Return source video as fallback if ffmpeg is missing or fails
        return video_path