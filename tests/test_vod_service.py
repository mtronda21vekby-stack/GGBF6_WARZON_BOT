import json

from app.services.vod.service import (
    FrameSample,
    VODAnalysisService,
    VisionVODAnalyzer,
    format_timecode,
    parse_timecode,
    select_sample_timestamps,
    telegram_media_from_message,
)


def test_timecode_parser_and_formatter():
    assert parse_timecode("01:23") == 83.0
    assert parse_timecode("1:02:03") == 3723.0
    assert parse_timecode("00:10.500") == 10.5
    assert parse_timecode("bad") is None
    assert format_timecode(83) == "01:23"


def test_sample_timestamps_preserve_requested_and_are_bounded():
    values = select_sample_timestamps(
        duration_s=100,
        requested_timecodes=["00:12", "01:30"],
        max_frames=6,
    )
    assert 12.0 in values
    assert 90.0 in values
    assert len(values) <= 6
    assert all(0 <= x <= 100 for x in values)


def test_telegram_video_and_video_document_detection():
    video = telegram_media_from_message({
        "video": {
            "file_id": "v1",
            "file_unique_id": "u1",
            "duration": 15,
            "file_size": 123,
            "width": 1920,
            "height": 1080,
            "mime_type": "video/mp4",
        }
    })
    assert video is not None
    assert video.file_id == "v1"
    assert video.kind == "video"

    doc = telegram_media_from_message({
        "document": {
            "file_id": "d1",
            "file_name": "clip.mp4",
            "mime_type": "video/mp4",
        }
    })
    assert doc is not None
    assert doc.kind == "document"

    assert telegram_media_from_message({
        "document": {"file_id": "x", "file_name": "notes.pdf", "mime_type": "application/pdf"}
    }) is None


class _FakeMessage:
    content = json.dumps({
        "summary": "Позиция сильная, но выход слишком открытый.",
        "timeline": [{
            "timestamp": "00:12",
            "observation": "Игрок вне укрытия.",
            "decision": "Продолжает пик.",
            "issue": "Открытый репик.",
            "correction": "Сбросить LOS и перепикнуть с другого угла.",
            "category": "positioning",
            "confidence": 0.88,
        }],
        "mistakes": [{
            "key": "open repeek",
            "label": "Повторный пик без смены угла",
            "category": "positioning",
            "confidence": 0.86,
        }],
        "strengths": ["Хороший кроссхейр-плейсмент"],
        "next_drill": "10 повторов: контакт → break LOS → новый угол.",
        "limitations": "Нет аудио и непрерывного контекста между кадрами.",
    })


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


class _FakeCompletions:
    def create(self, **kwargs):
        assert kwargs["response_format"] == {"type": "json_object"}
        content = kwargs["messages"][1]["content"]
        assert any(x.get("type") == "image_url" for x in content)
        return _FakeResponse()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


def test_vision_analyzer_parses_structured_evidence():
    analyzer = VisionVODAnalyzer(
        api_key="test",
        model="vision-test",
        client_factory=lambda: _FakeClient(),
    )
    result = analyzer.analyze(
        samples=[FrameSample(timestamp_s=12.0, jpeg_bytes=b"\xff\xd8fakejpeg")],
        profile={"game": "Warzone", "input": "Controller", "role": "Entry"},
        note="проверить репик",
    )
    assert result.summary.startswith("Позиция")
    assert result.mistakes[0].key == "open_repeek"
    assert result.mistakes[0].confidence == 0.86
    assert result.sampled_timestamps == ["00:12"]

    report = VODAnalysisService.format_report(result)
    assert "выборочных кадров" in report
    assert "Повторный пик" in report
