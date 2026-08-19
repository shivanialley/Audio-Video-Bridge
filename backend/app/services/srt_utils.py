def seconds_to_srt_time(seconds):
    # Work in integer milliseconds so rounding carries correctly across seconds,
    # minutes, and hours (for example, 59.9999 becomes 00:01:00,000).
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        seconds = 0.0
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def generate_srt(segments: list[dict]) -> str:
    lines = []
    for idx, seg in enumerate(segments, start=1):
        start_str = seconds_to_srt_time(seg["start"])
        end_str = seconds_to_srt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
    return "\n".join(lines)

def generate_bilingual_srt(orig_segments: list[dict], trans_segments: list[dict]) -> str:
    lines = []
    for idx, (orig, trans) in enumerate(zip(orig_segments, trans_segments), start=1):
        start_str = seconds_to_srt_time(orig["start"])
        end_str = seconds_to_srt_time(orig["end"])
        text = f"{orig['text'].strip()}\n{trans['text'].strip()}"
        lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
    return "\n".join(lines)
