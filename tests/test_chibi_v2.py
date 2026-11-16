"""Regression checks for source/version isolation and v2 pose/prompt problems."""
import json
import sys
import unittest
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import video_pipeline as pipeline

class ChibiV2Tests(unittest.TestCase):
    def test_plan_uses_same_v2_inputs_as_published_jobs(self):
        jobs=json.loads((ROOT/"prompts/chibi/jobs.json").read_text(encoding="utf-8"))["jobs"]
        plan=pipeline.plan()
        by_key={(j["character_id"],j["animation_name"]):j for j in jobs}
        self.assertEqual(len(plan["entries"]),136)
        for entry in plan["entries"]:
            job=by_key[(entry["character"],entry["action"])]
            self.assertEqual(entry["reference"],job["reference_image"])
            self.assertEqual(entry["expected_source"],job["source_video"])
            self.assertTrue(job["reference_image"].startswith("reference/chibi-v2/"))
            self.assertTrue(job["source_video"].startswith("video/chibi-v2/"))

    def test_hanging_pose_is_redrawn_instead_of_translated_standing_pixels(self):
        manifest=json.loads((ROOT/"reference/chibi-v2/manifest.json").read_text(encoding="utf-8"))
        for cid,entry in manifest["characters"].items():
            a=np.asarray(Image.open(ROOT/entry["views"]["front"]).convert("RGBA"))
            b=np.asarray(Image.open(ROOT/entry["views"]["drag"]).convert("RGBA"))
            # Both are normalised to the same height and feet: a mere upward
            # translation of S would disappear here and produce near-zero error.
            self.assertGreater(pipeline.endpoint_difference(a,b),.025,cid)

    def test_reaction_prompts_do_not_reintroduce_jump_plus_spin_or_bad_endpoints(self):
        data=json.loads((ROOT/"prompts/chibi/jobs.json").read_text(encoding="utf-8"))
        for job in data["jobs"]:
            self.assertLessEqual(len(job["prompt"]),650)
            self.assertEqual(job["start_frame"],job["end_frame"])
            if job["animation_name"]==pipeline.DRAG:
                self.assertEqual(job["endpoint_mode"],"H-H")
                self.assertIn("-drag.png",job["reference_image"])
                self.assertNotIn("落回原足点",job["prompt"])
            else:
                self.assertEqual(job["endpoint_mode"],"S-S")
            if job["animation_name"] in ("点击回应-开心跃动","工作状态-雀跃庆祝"):
                self.assertNotIn("360",job["prompt"])
                self.assertNotIn("一圈",job["prompt"])
                self.assertNotIn("双刃戟",job["prompt"])
            if job["animation_name"]=="工作状态-忙碌点按":
                self.assertIn("虚空",job["prompt"])
                self.assertNotIn("虚拟键盘",job["prompt"])
                self.assertIn("第5–6秒渐显",job["prompt"])
                self.assertNotIn("第2–3秒渐显",job["prompt"])

if __name__=="__main__":
    unittest.main()
