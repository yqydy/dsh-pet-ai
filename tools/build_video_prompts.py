"""Build all 136 concrete prompts from current spec.py and the checked chibi refs."""
import csv
import json
from pathlib import Path
import spec

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "prompts" / "chibi"
FENCE = chr(96) * 3

def field_paths(config, value):
    found = []
    def visit(item, path):
        if isinstance(item, dict):
            for key, child in item.items():
                visit(child, path + "." + key)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, path + "[" + str(index) + "]")
        elif item == value:
            found.append(path)
    visit(config["animations"], "animations")
    return found

def main():
    recipe = json.loads((DEST / "recipes.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "reference" / "chibi" / "manifest.json").read_text(encoding="utf-8"))
    jobs = []
    rows = []
    (DEST / "roles").mkdir(parents=True, exist_ok=True)
    overview = ["# Q版角色动画提示词\n",
                "已保存8个角色单人透明立绘、正侧背三视图、站立首帧S和悬空首帧H。"
                "本目录的136条提示词均已展开，可独立复制；每次给视频模型上传对应角色的单人首帧。\n",
                "普通动作首尾用同一张S；拖拽首尾用同一张H。转身再补充三视图。"
                "10秒是源视频方案，后续可按交互需求剪短；不支持10秒的平台可按比例压缩时间分段。\n",
                "源视频按 video/chibi/<角色id>/<原动画名>.mp4 保存，再依照[制作指南](../../docs/MAKE-CHIBI-PET.md)导入。\n",
                "| 角色 | 17条提示词 | 立绘 | 三视图 | S | H |",
                "| --- | --- | --- | --- | --- | --- |"]
    all_prompts = ["# 136条Q版动画完整提示词\n"]
    for char in spec.CHARACTERS:
        cid = char["id"]
        refs = manifest["characters"][cid]
        config = spec.config_for(char)
        for path in (refs["portrait"], refs["source"], refs["standing_reference"], refs["drag_reference"]):
            if not (ROOT / path).is_file():
                raise ValueError("Missing prepared Q reference: " + path)
        overview.append("| " + char["name"] + " | [打开](roles/" + cid + ".md) | [PNG](../../" + refs["portrait"] +
                        ") | [PNG](../../" + refs["source"] + ") | [站立](../../" + refs["standing_reference"] +
                        ") | [悬空](../../" + refs["drag_reference"] + ") |")
        sections = ["# " + char["name"] + "：17条Q版动作提示词\n",
                    "角色外观：" + recipe["DESIGNS"][cid] + "\n",
                    "所有图均已准备好：[单人立绘](../../../" + refs["portrait"] + ")、[三视图](../../../" + refs["source"] +
                    ")、[站立首帧S](../../../" + refs["standing_reference"] + ")、[悬空首帧H](../../../" + refs["drag_reference"] + ")。\n"]
        if len(recipe["DETAILS"][cid]) != len(spec.ANIMATIONS):
            raise ValueError("Incomplete character action definitions: " + cid)
        for index, anim in enumerate(spec.ANIMATIONS):
            name, duration, loop, category, description = anim
            drag = name == "被鼠标拖拽悬空反馈"
            reference = refs["drag_reference"] if drag else refs["standing_reference"]
            reference_name = "H（悬空）" if drag else "S（正面站立）"
            endpoints = ("全程悬空，第一帧和最后一帧均为所附H，禁止落地，也不包含被拎起过程。" if drag else
                         "第一帧和最后一帧均为所附S，位置、大小、五官和姿势一致，空手，无临时道具或特效残留。")
            prompt = (
                "任务：" + char["name"] + "桌宠动作《" + name + "》。\n"
                "必须上传本条附带的本角色单人Q版" + reference_name + "首帧，转身再补充Q版三视图。\n" +
                recipe["STYLE"] + "\n角色锁定：" + recipe["DESIGNS"][cid] + "\n" +
                recipe["COMMON"] + "\n首尾约束：" + endpoints +
                "模型支持首尾帧控制时，两端都上传该同一张" + reference_name + "。\n" +
                "本角色专属动作：" + recipe["DETAILS"][cid][index] +
                "\n时间分段：" + recipe["TIMINGS"][index]
            )
            negative = recipe["NEG"].replace("可读文字", "新增可读文字")
            fields = field_paths(config, name)
            if not fields:
                raise ValueError("Animation is not referenced by the configuration: " + name)
            job = {
                "character_id": cid, "character_name": char["name"], "animation_name": name,
                "source_video": "video/chibi/" + cid + "/" + name + ".mp4",
                "reference_image": reference, "turnaround_reference": refs["source"],
                "output": "plugin/packs/" + char["prefix"] + "-animation/" + name + ".webm",
                "generation_duration_sec": 10, "existing_duration_sec": duration,
                "loop_metadata": loop, "config_fields": fields,
                "status": "awaiting_video_generation", "prompt": prompt, "negative_prompt": negative
            }
            jobs.append(job)
            rows.append([cid, name, "; ".join(fields), job["source_video"], job["output"]])
            sections.append("## " + str(index + 1).zfill(2) + " " + name + "\n\n"
                            "上传首帧：[打开](../../../" + reference + ")。原片保存：" + job["source_video"] + "\n\n"
                            "现有参考时长：" + str(duration) + "秒；本源片方案：10秒。配置：" + "；".join(fields) + "\n\n"
                            + FENCE + "text\n" + prompt + "\n" + FENCE +
                            "\n\n负面提示词：\n\n" + FENCE + "text\n" + negative + "\n" + FENCE + "\n")
        (DEST / "roles" / (cid + ".md")).write_text("\n".join(sections), encoding="utf-8")
        # Keep the combined document's relative image links correct.
        all_prompts.append("\n".join(sections).replace("../../../reference/", "../../reference/"))
    if len(jobs) != 136 or len({(job["character_id"], job["animation_name"]) for job in jobs}) != 136:
        raise ValueError("Expected 136 unique jobs")
    (DEST / "README.md").write_text("\n".join(overview) +
        "\n\njobs.json是厂商无关的任务清单，不是某个平台的直接API请求格式。"
        "当前Q版AI动作视频尚待生成；仓库原有plugin/packs动画保持可用。\n", encoding="utf-8")
    (DEST / "ALL-PROMPTS.md").write_text("\n".join(all_prompts), encoding="utf-8")
    (DEST / "jobs.json").write_text(json.dumps({
        "schema_version": 1, "reference_status": "prepared",
        "video_status": "awaiting_video_generation", "jobs": jobs
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (DEST / "config-mapping.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["character_id", "animation_name", "config_fields", "source_video", "output"])
        writer.writerows(rows)
    print("Prepared 8 role prompt files and 136 jobs")

if __name__ == "__main__":
    main()
