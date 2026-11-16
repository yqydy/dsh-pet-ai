"""AI-video route: plan -> import/key/normalise/encode -> verify -> complete pack.
Raw source videos and intermediates stay under ignored video/ and build/.
The existing procedural build_assets.py route remains available independently.
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
import numpy as np
from PIL import Image
import spec
from media_tools import find_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "build" / "video" / "chibi-v2"
OUTPUT = WORK / "step04"
FPS = 24
SIZE = (640, 360)
SOURCE_SIZE = (1280, 720)
DRAG = "被鼠标拖拽悬空反馈"
IDS = [c["id"] for c in spec.CHARACTERS]
NAMES = [a[0] for a in spec.ANIMATIONS]

def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def output_path(cid, action, output_root=OUTPUT):
    return Path(output_root) / cid / (action + ".webm")

def video_info(path, ffmpeg):
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True)
    text = result.stderr.decode("utf-8", errors="replace")
    stream = re.search(r"Video:\s*([^,\s]+)[^\n]*", text)
    if not stream:
        raise ValueError("No video stream: " + str(path))
    dimensions = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", stream.group(0))
    frame_rate = re.search(r"(\d+(?:\.\d+)?)\s*fps", stream.group(0))
    return {
        "codec": stream.group(1),
        "width": int(dimensions.group(1)) if dimensions else None,
        "height": int(dimensions.group(2)) if dimensions else None,
        "fps": float(frame_rate.group(1)) if frame_rate else None,
        "audio": bool(re.search(r"Stream #[^\n]*Audio:", text)),
        "alpha_tag": bool(re.search(r"alpha_mode\s*:\s*1", text, re.I)),
    }

def exact_read(stream, count):
    parts = []
    left = count
    while left:
        part = stream.read(left)
        if not part:
            if left != count:
                raise ValueError("Truncated raw video frame")
            return b""
        parts.append(part)
        left -= len(part)
    return b"".join(parts)

def frames(path, ffmpeg, size, fit_source=False):
    info = video_info(path, ffmpeg)
    decoder = ["-c:v", "libvpx-vp9"] if info["codec"] == "vp9" else []
    command = [ffmpeg, "-hide_banner", "-loglevel", "error"] + decoder + ["-i", str(path)]
    if fit_source:
        ratio = info["width"] / float(info["height"])
        if abs(ratio - 16.0 / 9) > 0.02:
            raise ValueError("Source must be 16:9; crop deliberately before importing")
        command += ["-vf", "fps=24,scale=1280:720"]
    command += ["-an", "-f", "rawvideo", "-pix_fmt", "rgba", "-"]
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                raw = exact_read(process.stdout, size[0] * size[1] * 4)
                if not raw:
                    break
                yield np.frombuffer(raw, dtype=np.uint8).reshape((size[1], size[0], 4)).copy()
            code = process.wait()
            if code:
                errors.seek(0)
                raise RuntimeError(errors.read().decode("utf-8", errors="replace")[-3000:])
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.terminate()
                process.wait()

def key_green(rgba):
    """Soft green-excess matte. Use alpha input for green costume details."""
    rgb = rgba[:, :, :3].astype(np.float32)
    excess = (rgb[:, :, 1] - np.maximum(rgb[:, :, 0], rgb[:, :, 2])) / 255.0
    opacity = 1.0 - np.clip((excess - 0.08) / 0.30, 0, 1)
    result = rgba.copy()
    result[:, :, 3] = np.round(rgba[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)
    edge = (opacity > 0) & (opacity < 1)
    result[:, :, 1][edge] = np.minimum(rgb[:, :, 1][edge], np.maximum(rgb[:, :, 0], rgb[:, :, 2])[edge]).astype(np.uint8)
    result[:, :, :3][result[:, :, 3] == 0] = 0
    return result

def bounds(rgba, threshold=24):
    yy, xx = np.nonzero(rgba[:, :, 3] > threshold)
    if not len(xx):
        raise ValueError("Empty frame after background removal")
    return np.array([xx.min(), yy.min(), xx.max() + 1, yy.max() + 1], dtype=float)

def normalise(rgba):
    # One fixed transform for the ENTIRE character library, never per-frame fitting.
    # Matches upstream 2160x1215 / body=900 / feet=1115, downscaled to 640x360.
    scale = (900.0 / 468) * (360.0 / 1215)
    tx = 320 - 640 * scale
    ty = 1115 * (360.0 / 1215) - 612 * scale
    box = bounds(rgba)
    projected = box * scale + np.array([tx, ty, tx, ty])
    if projected[0] < 1 or projected[1] < 1 or projected[2] > 639 or projected[3] > 359:
        raise ValueError("Action exceeds final canvas; regenerate with more source safety margin")
    return Image.fromarray(rgba, "RGBA").transform(
        SIZE, Image.AFFINE, (1 / scale, 0, -tx / scale, 0, 1 / scale, -ty / scale), Image.BICUBIC)

def endpoint_difference(first, last):
    union = (first[:, :, 3] > 24) | (last[:, :, 3] > 24)
    if not union.any():
        return 1.0
    a = first.astype(np.float32) / 255
    b = last.astype(np.float32) / 255
    a[:, :, :3] *= a[:, :, 3:4]
    b[:, :, :3] *= b[:, :, 3:4]
    return float(np.mean(np.abs(a[union] - b[union])))

def verify_video(path, ffmpeg, action, write_report=True, cid=None):
    path = Path(path)
    errors = []
    info = video_info(path, ffmpeg)
    if (info["width"], info["height"]) != SIZE:
        errors.append("Expected exactly 640x360")
    if info["codec"] != "vp9":
        errors.append("Expected VP9")
    if info["fps"] != FPS:
        errors.append("Expected 24fps")
    if info["audio"]:
        errors.append("Expected no audio stream")
    first = last = None
    count = 0
    min_transparent = 1.0
    boxes = []
    if not errors:
        for frame in frames(path, ffmpeg, SIZE):
            if first is None:
                first = frame.copy()
            last = frame.copy()
            count += 1
            try:
                box = bounds(frame)
                boxes.append(box)
                if box[0] < 1 or box[1] < 1 or box[2] > 639 or box[3] > 359:
                    errors.append("Visible content touches final frame edge")
            except ValueError:
                errors.append("Empty frame")
            fraction = float(np.mean(frame[:, :, 3] < 8))
            min_transparent = min(min_transparent, fraction)
        if min_transparent < 0.05:
            errors.append("Missing usable alpha background")
        if not 12 <= count <= 720:
            errors.append("Expected duration 0.5 to 30 seconds")
    endpoint_error = None
    if first is not None and last is not None:
        endpoint_error = endpoint_difference(first, last)
        if endpoint_error > 0.18:
            errors.append("First/last appearance discontinuity")
        first_box, last_box = bounds(first), bounds(last)
        if np.max(np.abs(first_box - last_box)) > 8:
            errors.append("First/last position or scale differs")
        expected_feet = (1115 - (22 * 900.0 / 468 if action == DRAG else 0)) * 360.0 / 1215
        for frame in (first, last):
            yy, xx = np.nonzero(frame[:, :, 3] > 32)
            band = yy >= yy.max() - 8
            pivot = (xx[band].min() + xx[band].max()) / 2.0
            if abs(pivot - 320) > 9:
                errors.append('First/last horizontal shoe anchor differs from S/H')
        expected_height = 900 * 360.0 / 1215
        if action == DRAG and cid in IDS:
            manifest = json.loads((ROOT / "reference/chibi-v2/manifest.json").read_text(encoding="utf-8"))
            source_height = manifest["characters"][cid]["drag_source_height"]
            expected_height *= source_height / 468.0
        for name, box in (("first", first_box), ("last", last_box)):
            if abs(box[3] - expected_feet) > 9:
                errors.append(name + " frame is not at S/H baseline")
            if abs((box[3] - box[1]) - expected_height) > 14:
                errors.append(name + " frame does not retain canonical character height")
    report = {
        "status": "pass" if not errors else "fail", "errors": sorted(set(errors)),
        "file": str(path), "sha256": digest(path), "info": info, "frames": count,
        "min_transparent_fraction": min_transparent, "endpoint_error": endpoint_error,
        "human_review_required": ["identity and anatomy", "all three view transitions",
                                  "edge halos on black/white backgrounds", "timing and motion seam"]
    }
    if first is not None:
        for label, frame in (("first", first), ("last", last)):
            for bg_name, colour in (("black", (0, 0, 0, 255)), ("white", (255, 255, 255, 255))):
                bg = Image.new("RGBA", SIZE, colour)
                bg.alpha_composite(Image.fromarray(frame, "RGBA"))
                target = path.parent / "review" / (path.stem + "-" + label + "-" + bg_name + ".png")
                target.parent.mkdir(parents=True, exist_ok=True)
                bg.convert("RGB").save(target)
    if write_report:
        save_json(path.with_suffix(".report.json"), report)
    return report

def import_video(source, cid, action, ffmpeg, background="green", output_root=OUTPUT):
    source = Path(source)
    target = output_path(cid, action, output_root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.stem + ".processing.webm")
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "640x360", "-r", "24", "-i", "-",
        "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
        "-b:v", "0", "-crf", "28", "-threads", "2", "-row-mt", "1",
        "-metadata:s:v:0", "alpha_mode=1", str(temp)
    ]
    with tempfile.TemporaryFile() as errors:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
        count = 0
        try:
            for rgba in frames(source, ffmpeg, SOURCE_SIZE, fit_source=True):
                keyed = key_green(rgba) if background == "green" else rgba
                frame = normalise(keyed)
                encoder.stdin.write(frame.tobytes())
                count += 1
            encoder.stdin.close()
            if encoder.wait() or count == 0:
                errors.seek(0)
                raise RuntimeError("Encoder failed: " + errors.read().decode("utf-8", errors="replace")[-2500:])
        except Exception:
            if not encoder.stdin.closed:
                encoder.stdin.close()
            if encoder.poll() is None:
                encoder.terminate()
                encoder.wait()
            if temp.exists():
                temp.unlink()
            raise
    report = verify_video(temp, ffmpeg, action, cid=cid)
    if report['status'] == 'pass':
        temp.replace(target)
    else:
        rejected = target.with_name(target.stem + '.rejected.webm')
        temp.replace(rejected)
        target = rejected
    report['file'] = str(target)
    report["source"] = {"path": str(source), "sha256": digest(source), "background": background}
    report["stages"] = ["decode/fps/size", "chroma-key or preserve alpha", "fixed anchor normalisation", "VP9-alpha encode", "decode and verify"]
    save_json(target.with_suffix(".report.json"), report)
    return report

def find_source(cid, action):
    for ext in (".mp4", ".mov", ".webm"):
        path = ROOT / "video" / "chibi-v2" / cid / (action + ext)
        if path.exists():
            return path
    return None

def plan():
    entries = []
    for char in spec.CHARACTERS:
        for action in NAMES:
            source = find_source(char["id"], action)
            target = output_path(char["id"], action)
            entries.append({
                "character": char["id"], "action": action,
                "expected_source": "video/chibi-v2/" + char["id"] + "/" + action + ".mp4",
                "source_exists": bool(source), "output_exists": target.exists(),
                "reference": "reference/chibi-v2/firstframes/" + char["id"] + ("-drag.png" if action == DRAG else ".png")
            })
    return {"expected": 136, "sources_present": sum(e["source_exists"] for e in entries), "entries": entries}

def pack(ffmpeg, write_plugin=False, output_root=OUTPUT):
    # Recheck every file; reports alone are insufficient if the video changed.
    missing = [str(output_path(cid, name, output_root)) for cid in IDS for name in NAMES
               if not output_path(cid, name, output_root).is_file()]
    if missing:
        raise ValueError("Incomplete set: missing %d/136 videos. First missing: %s" % (len(missing), missing[0]))
    for cid in IDS:
        for name in NAMES:
            report = verify_video(output_path(cid, name, output_root), ffmpeg, name, cid=cid)
            if report["status"] != "pass":
                raise ValueError("Verification failed: " + cid + "/" + name + ": " + "; ".join(report["errors"]))
    staged = WORK / "plugin" / "packs"
    staged.mkdir(parents=True, exist_ok=True)
    for char in spec.CHARACTERS:
        prefix, cid = char["prefix"], char["id"]
        cfg = ROOT / "plugin" / "packs" / (prefix + "-config.json")
        shutil.copyfile(cfg, staged / cfg.name)
        destination = staged / (prefix + "-animation")
        destination.mkdir(exist_ok=True)
        for name in NAMES:
            shutil.copyfile(output_path(cid, name, output_root), destination / (name + ".webm"))
    if write_plugin:
        package_path = ROOT / "plugin" / "package.json"
        package = json.loads(package_path.read_text(encoding="utf-8"))
        parts = package["version"].split(".")
        if len(parts) != 3 or not all(part.isdigit() for part in parts):
            raise ValueError("Update plugin version manually before replacing non-semver package")
        stamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        backup = WORK / "backups" / ("plugin-" + stamp + ".zip")
        backup.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(str(backup), "w", zipfile.ZIP_DEFLATED) as archive:
            for path in (ROOT / "plugin" / "packs").rglob("*"):
                if path.is_file():
                    archive.write(str(path), str(path.relative_to(ROOT / "plugin")))
            archive.write(str(package_path), "package.json")
        for char in spec.CHARACTERS:
            destination = ROOT / "plugin" / "packs" / (char["prefix"] + "-animation")
            destination.mkdir(exist_ok=True)
            for name in NAMES:
                shutil.copyfile(staged / destination.name / (name + ".webm"), destination / (name + ".webm"))
        package["version"] = ".".join(parts[:2] + [str(int(parts[2]) + 1)])
        save_json(package_path, package)
    return staged

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    imp = sub.add_parser("import")
    imp.add_argument("--character", choices=IDS, required=True)
    imp.add_argument("--action", choices=NAMES, required=True)
    imp.add_argument("--input", type=Path)
    imp.add_argument("--background", choices=("green", "alpha"), default="green")
    check = sub.add_parser("verify")
    check.add_argument("--character", choices=IDS, required=True)
    check.add_argument("--action", choices=NAMES, required=True)
    package = sub.add_parser("pack")
    package.add_argument("--write-plugin", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "plan":
        report = plan()
        save_json(WORK / "plan.json", report)
        print("sources: %d/136; plan: %s" % (report["sources_present"], WORK / "plan.json"))
        return 0
    ffmpeg = find_ffmpeg(args.ffmpeg)
    if args.command == "pack":
        print(pack(ffmpeg, args.write_plugin))
        return 0
    if args.command == "import":
        source = args.input or find_source(args.character, args.action)
        if not source or not source.is_file():
            raise ValueError("Source video missing; see video_pipeline.py plan")
        report = import_video(source, args.character, args.action, ffmpeg, args.background)
    else:
        report = verify_video(output_path(args.character, args.action), ffmpeg, args.action, cid=args.character)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(str(error))
