import subprocess

import imageio_ffmpeg

from app.services.vod.service import FrameExtractor


def test_frame_extractor_works_with_bundled_ffmpeg(tmp_path):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = tmp_path / "tiny.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=2",
            "-t",
            "3",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(video),
        ],
        check=True,
        timeout=20,
    )
    extractor = FrameExtractor(max_frames=3, max_width=320, timeout_s=10)
    samples = extractor.extract(str(video), duration_s=3)
    assert len(samples) >= 2
    assert all(x.jpeg_bytes.startswith(b"\xff\xd8") for x in samples)
