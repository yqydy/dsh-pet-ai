"""Meaningful regression checks for the new AI-video production route."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import spec
import video_pipeline as pipeline
from cutout import cutout
from media_tools import find_ffmpeg

class ReferenceAndPromptTests(unittest.TestCase):
    def test_all_136_prompts_reference_real_images_and_exact_config_actions(self):
        data = json.loads((ROOT / "prompts/chibi/jobs.json").read_text(encoding="utf-8"))
        jobs = data["jobs"]
        expected = {(c["id"], a[0]) for c in spec.CHARACTERS for a in spec.ANIMATIONS}
        self.assertEqual({(j["character_id"], j["animation_name"]) for j in jobs}, expected)
        self.assertEqual(len(jobs), 136)
        for job in jobs:
            self.assertTrue((ROOT / job["reference_image"]).is_file())
            self.assertTrue((ROOT / job["turnaround_reference"]).is_file())
            self.assertTrue(job["config_fields"])
            self.assertIn("时间分段", job["prompt"])
            self.assertIn(job["animation_name"], job["prompt"])
            self.assertEqual(job["status"], "awaiting_video_generation")

    def test_all_prepared_references_have_real_alpha_and_shared_s_h_geometry(self):
        manifest = json.loads((ROOT / "reference/chibi/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["characters"]), 8)
        for cid, entry in manifest["characters"].items():
            raw = (ROOT / entry["source"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["source_sha256"])
            source = np.asarray(Image.open(ROOT / entry["source"]).convert("RGBA"))
            self.assertGreater(np.mean(source[:, :, 3] < 8), 0.05)
            self.assertGreater(np.mean(source[:, :, 3] > 240), 0.05)
            for view in entry["views"].values():
                image = Image.open(ROOT / view).convert("RGBA")
                self.assertEqual(image.size, (1200, 1200))
                box = pipeline.bounds(np.asarray(image))
                self.assertGreater(box[0], 0)
                self.assertLess(box[2], 1200)
            boxes = []
            for field in ("standing_reference", "drag_reference"):
                frame = np.asarray(Image.open(ROOT / entry[field]).convert("RGBA"))
                self.assertEqual(frame.shape, (720, 1280, 4))
                self.assertEqual(frame[0, 0].tolist(), [0, 255, 0, 255])
                boxes.append(pipeline.bounds(pipeline.key_green(frame)))
            self.assertAlmostEqual(boxes[0][3] - boxes[1][3], 22, delta=1)
            self.assertAlmostEqual(boxes[0][3] - boxes[0][1], 468, delta=2)
            self.assertAlmostEqual(boxes[1][3] - boxes[1][1], 468, delta=2)

    def test_alpha_cutout_keeps_white_foreground(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "white.png"
            output = Path(directory) / "cut.png"
            rgba = np.zeros((40, 40, 4), dtype=np.uint8)
            rgba[8:32, 10:30] = [255, 255, 255, 255]
            Image.fromarray(rgba, "RGBA").save(source)
            result = cutout(str(source), str(output))
            self.assertEqual(result.size, (20, 24))
            self.assertEqual(np.asarray(result)[10, 10].tolist(), [255, 255, 255, 255])

    def test_keying_removes_green_without_removing_white_or_blue(self):
        pixels = np.array([[[0, 255, 0, 255], [255, 255, 255, 255], [40, 80, 240, 255]]], dtype=np.uint8)
        actual = pipeline.key_green(pixels)
        self.assertEqual(actual[0, 0, 3], 0)
        self.assertEqual(actual[0, 1].tolist(), [255, 255, 255, 255])
        self.assertEqual(actual[0, 2].tolist(), [40, 80, 240, 255])

    def test_fixed_transform_preserves_movement_instead_of_refitting_each_frame(self):
        a = np.zeros((720, 1280, 4), dtype=np.uint8)
        b = np.zeros_like(a)
        a[144:612, 520:760] = [240, 240, 255, 255]
        b[124:592, 520:760] = [240, 240, 255, 255]
        first = pipeline.bounds(np.asarray(pipeline.normalise(a)))
        moved = pipeline.bounds(np.asarray(pipeline.normalise(b)))
        self.assertAlmostEqual(first[3] - first[1], moved[3] - moved[1], delta=1)
        self.assertGreater(first[3] - moved[3], 10)

class RealFFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Missing FFmpeg is a setup error, not a silently skipped integration check.
        cls.ffmpeg = find_ffmpeg()

    def make_source(self, folder, cid="gpt", drag=False, transparent=False, bad_end=False):
        reference = ROOT / "reference/chibi/firstframes" / (cid + ("-drag.png" if drag else ".png"))
        frame = np.asarray(Image.open(reference).convert("RGBA")).copy()
        if transparent:
            frame = pipeline.key_green(frame)
        path = Path(folder) / ("source.webm" if transparent else "source.mp4")
        codec = (["-c:v", "libvpx-vp9", "-auto-alt-ref", "0", "-pix_fmt", "yuva420p", "-metadata:s:v:0", "alpha_mode=1"]
                 if transparent else ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16"])
        command = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1280x720", "-r", "24", "-i", "-",
                   "-an"] + codec + [str(path)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_frames = []
        for index in range(24):
            item = frame
            if bad_end and index >= 12:
                item = np.roll(frame, 100, axis=1)
            raw_frames.append(item.tobytes())
        _, error = process.communicate(b"".join(raw_frames))
        self.assertEqual(process.returncode, 0, error.decode("utf-8", errors="replace"))
        return path

    def test_green_mp4_is_keyed_encoded_and_decoded_with_real_alpha(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.make_source(directory)
            report = pipeline.import_video(source, "gpt", "待机呼吸", self.ffmpeg, output_root=Path(directory) / "out")
            self.assertEqual(report["status"], "pass", report["errors"])
            self.assertEqual(report["frames"], 24)
            self.assertGreater(report["min_transparent_fraction"], 0.5)
            self.assertEqual(report["info"]["codec"], "vp9")

    def test_alpha_input_retains_white_character(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.make_source(directory, transparent=True)
            report = pipeline.import_video(source, "gpt", "待机呼吸", self.ffmpeg, "alpha", Path(directory) / "out")
            self.assertEqual(report["status"], "pass", report["errors"])
            decoded = next(pipeline.frames(Path(report["file"]), self.ffmpeg, pipeline.SIZE))
            white = np.min(decoded[:, :, :3], axis=2) > 200
            self.assertGreater(int(np.sum(white & (decoded[:, :, 3] > 240))), 1000)

    def test_drag_keeps_hanging_height(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.make_source(directory, drag=True)
            report = pipeline.import_video(source, "gpt", pipeline.DRAG, self.ffmpeg, output_root=Path(directory) / "out")
            self.assertEqual(report["status"], "pass", report["errors"])

    def test_bad_endpoint_is_rejected_without_overwriting_verified_video(self):
        with tempfile.TemporaryDirectory() as directory:
            good = self.make_source(directory)
            output = Path(directory) / "out"
            valid = pipeline.import_video(good, "gpt", "待机呼吸", self.ffmpeg, output_root=output)
            self.assertEqual(valid["status"], "pass", valid["errors"])
            target = pipeline.output_path("gpt", "待机呼吸", output)
            previous = target.read_bytes()
            bad = self.make_source(directory, bad_end=True)
            rejected = pipeline.import_video(bad, "gpt", "待机呼吸", self.ffmpeg, output_root=output)
            self.assertEqual(rejected["status"], "fail")
            self.assertTrue(any("First/last" in error for error in rejected["errors"]))
            self.assertEqual(target.read_bytes(), previous)

    def test_incomplete_136_set_blocks_pack_before_touching_plugin(self):
        before = (ROOT / "plugin/package.json").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Incomplete set"):
                pipeline.pack(self.ffmpeg, write_plugin=True, output_root=directory)
        self.assertEqual((ROOT / "plugin/package.json").read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
