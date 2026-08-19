from backend.app.services.srt_utils import seconds_to_srt_time, generate_srt

def test_time_formatting():
    assert seconds_to_srt_time(0.0) == "00:00:00,000"
    assert seconds_to_srt_time(65.5) == "00:01:05,500"
    assert seconds_to_srt_time(59.9999) == "00:01:00,000"
    assert seconds_to_srt_time(-1) == "00:00:00,000"

def test_srt_generation():
    segments = [{"id": 0, "start": 0.0, "end": 2.5, "text": "Hello world"}]
    srt = generate_srt(segments)
    assert "00:00:00,000 --> 00:00:02,500" in srt
    assert "Hello world" in srt
