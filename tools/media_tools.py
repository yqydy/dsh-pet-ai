"""Portable FFmpeg discovery shared by both asset-production routes."""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def find_ffmpeg(override=None):
    candidate = override or os.environ.get("PET_FFMPEG") or os.environ.get("FFMPEG_BIN")
    if candidate:
        found = shutil.which(candidate) or (str(Path(candidate)) if Path(candidate).is_file() else None)
        if not found:
            raise RuntimeError("Configured FFmpeg does not exist: " + str(candidate))
        return found
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in (ROOT / ".tools" / "ffmpeg.exe", ROOT / ".tools" / "ffmpeg" / "bin" / "ffmpeg.exe"):
        if candidate.is_file():
            return str(candidate)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError("Install tools/requirements.txt, put ffmpeg on PATH, or set PET_FFMPEG.") from exc
