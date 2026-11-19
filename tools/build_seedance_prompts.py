"""Build Seedance 2.0 v3 prompts with stronger full-body acting.
Uses actual pack config names, the v2.1 expression refs and 17 verified upstream clips.
"""
import csv
import hashlib
import json
from pathlib import Path
import spec
from build_video_prompts import field_paths

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/"prompts/chibi-v3"
FENCE=chr(96)*3

def action_for_role(action, role):
    return {**action, **role.get("actions", {}).get(action["id"], {})}

def make_prompt(char,action,recipe,with_motion):
    cid=char["id"]
    role=recipe["roles"][cid]
    if with_motion:
        lead=("用图片1锁定角色外观。"+role["identity"]+"视频1提供动作类别和重心变化，表情与节奏按下文。")
    else:
        lead="让图片1角色做"+action["name"]+"："+role["identity"]
    secondary=role["calm"] if action["id"] in ("idle","nap","whisper","thinking","error") else role["accent"]
    ending=("首尾为图片1悬空姿势，摆动相位连续。" if action["endpoint_mode"]=="H-H"
            else "第10秒恢复图片1正面站姿并自然收住。")
    technical="10秒16:9，图片1的二维画风与比例构图，固定全身单镜头、#00FF00绿幕；尾翼、手脚及图形距画边至少10%，无字幕。"
    prompt="\n".join(filter(None, (lead, " ".join(action["timeline"]), role.get("performance"), secondary,
                                    action["effects"], action["spatial_rule"], ending, technical)))
    if len(prompt)>recipe["prompt_budget_characters"]:
        raise ValueError("Prompt exceeds 500 characters: "+cid+"/"+action["id"]+" "+str(len(prompt)))
    return prompt

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_jobs(jobs,recipe):
    wanted={(c["id"],a[0]) for c in spec.CHARACTERS for a in spec.ANIMATIONS}
    if len(jobs)!=136 or {(j["character_id"],j["animation_name"]) for j in jobs}!=wanted:
        raise ValueError("136-job/config coverage mismatch")
    for j in jobs:
        for field in ("reference_image","turnaround_reference","motion_reference"):
            if not (ROOT/j[field]).is_file(): raise ValueError("Missing "+j[field])
        for field in ("prompt","prompt_with_motion"):
            if len(j[field])>recipe["prompt_budget_characters"]: raise ValueError("Prompt budget")
        if not j["config_fields"]: raise ValueError("Unreferenced animation")
        if j["last_frame"] is not None: raise ValueError("Pilot must not hard-lock last frame by default")
        if j["endpoint_mode"]=="H-H" and "-drag.png" not in j["reference_image"]:
            raise ValueError("Hanging reference mismatch")

def section(j,action,prefix):
    return [
        "## "+str(j["action_index"]).zfill(2)+" "+j["animation_name"]+"\n",
        "幅度目标："+action["amplitude"]+"。表演重点："+action["acting_key"]+"\n",
        "图片1：[单人角色图]("+prefix+j["reference_image"]+")；视频1：[官方动作MP4]("+prefix+j["motion_reference"]+")。\n",
        "### 有视频参考入口：图片1 + 视频1\n",
        FENCE+"text\n"+j["prompt_with_motion"]+"\n"+FENCE+"\n",
        "### 只有图生视频入口：仅图片1\n",
        FENCE+"text\n"+j["prompt"]+"\n"+FENCE+"\n",
        "验收："+action["review"]+"\n",
        "保存原片：`"+j["source_video"]+"`。配置："+ "；".join(j["config_fields"])+"\n"
    ]

def main():
    recipe=json.loads((DEST/"recipes.json").read_text(encoding="utf-8"))
    refs=json.loads((ROOT/"reference/chibi-v2/manifest.json").read_text(encoding="utf-8"))
    motion=json.loads((ROOT/"reference/motion-dsh-pet/manifest.json").read_text(encoding="utf-8"))
    by_id={i["id"]:i for i in motion["items"]}
    if not motion["complete"] or set(by_id)!={a["id"] for a in recipe["actions"]}:
        raise ValueError("Prepare all 17 official motion references first")
    if [a["name"] for a in recipe["actions"]]!=spec.ANIM_NAMES:
        raise ValueError("17-action order differs from current configuration")
    for item in motion["items"]:
        if sha256(ROOT/item["clip"])!=item["clip_sha256"]:
            raise ValueError("Motion reference checksum mismatch")
    jobs=[]
    all_doc=["# Seedance 2.0：136条dsh-pet动作提示词 v3\n","两种入口各选一段复制；不要把两段合并。建议先看[PILOT-DEEPSEEK.md](PILOT-DEEPSEEK.md)。\n"]
    overview=["# 豆包 Seedance 2.0：dsh-pet动作提示词 v3\n",
        "八位角色使用配套的正眼立绘和首帧。每位角色的 17 个动作都按人设分别编排，涉及起势、视线、节奏和收势。\n",
        "[DeepSeek 试样流程](PILOT-DEEPSEEK.md)涵盖挥手、跳跃、忙碌点按。新版绿幕原片各 17 条，见[大肥鱼](../../video/chibi-v2/deepseek/)与[龙娘](../../video/chibi-v2/gpt/)。\n",
        "有全能参考/视频参考入口：图片1选本角色单人绿幕图，视频1选本动作MP4，复制「图片＋视频」版本。只有图生视频入口：只上传该角色图，复制「仅图片」版本。两种模式不要混成一个API请求。\n",
        "默认 10 秒、16:9。站姿先用单张角色图试拍，拖拽可用相同的悬空首尾帧帮助接回循环。多模态参考模式中把图片作为外观参考。\n",
        "主体会蓄力、抬臂、扭肩、屈膝和回弹，固定的是镜头与画幅。不是所有动作都变成大跳：待机舒缓，挥手/跳跃/庆祝明显舒展。\n",
        "[使用与诊断指南](../../docs/SEEDANCE-V3-ACTIONS.md) · [17段上游参考](../../reference/motion-dsh-pet/README.md) · [全部提示词](ALL-PROMPTS.md)\n",
        "|角色|17条双模式提示词|站姿S|悬空H|",
        "|---|---|---|---|"]
    for char in spec.CHARACTERS:
        cid=char["id"]
        r=refs["characters"][cid]
        config=json.loads((ROOT/"plugin/packs"/(char["prefix"]+"-config.json")).read_text(encoding="utf-8"))
        parts=["# "+char["name"]+"：Seedance 2.0动作 v3\n",
            "图片只用当前单人图。图片1负责外观，视频1只负责动作；优先做挥手、跳跃、忙碌点按，检查幅度后再批量。\n",
            "两种入口的提示词二选一，不叠加。固定镜头不代表冻结身体，最后一帧要收回原姿势，但不用前后各站着不动一秒。\n"]
        overview.append("|"+char["name"]+"|[打开](roles/"+cid+".md)|[S](../../"+r["standing_reference"]+")|[H](../../"+r["drag_reference"]+")|")
        for i,(action,anim) in enumerate(zip(recipe["actions"],spec.ANIMATIONS)):
            action=action_for_role(action,recipe["roles"][cid])
            name,duration,loop,category,_=anim
            reference=r["drag_reference"] if action["endpoint_mode"]=="H-H" else r["standing_reference"]
            job={"id":cid+"-"+action["id"],"action_id":action["id"],"action_index":i+1,
                "character_id":cid,"character_name":char["name"],"animation_name":name,
                "source_video":"video/chibi-v2/"+cid+"/"+name+".mp4",
                "reference_image":reference,"reference_image_sha256":sha256(ROOT/reference),
                "turnaround_reference":r["turnaround"],"motion_reference":by_id[action["id"]]["clip"],
                "motion_reference_sha256":by_id[action["id"]]["clip_sha256"],
                "motion_reference_duration_sec":by_id[action["id"]]["duration_sec"],
                "preferred_mode":"image_and_motion_reference_if_available",
                "last_frame":None,"optional_end_frame_after_motion_pilot":reference,
                "endpoint_mode":action["endpoint_mode"],
                "generation_duration_sec":10,"existing_duration_sec":duration,"loop_metadata":loop,
                "config_fields":field_paths(config,name),
                "output":"plugin/packs/"+char["prefix"]+"-animation/"+name+".webm",
                "upstream_heading":action["upstream_heading"],"upstream_commit":recipe["upstream"]["commit"],
                "status":"awaiting_video_generation","validation_status":"awaiting_seedance_pilot",
                "priority":"pilot" if cid=="deepseek" and action["id"] in recipe["pilot_ids"] else "after_pilot",
                "amplitude_goal":action["amplitude"],"review_focus":action["review"],
                "prompt":make_prompt(char,action,recipe,False),
                "prompt_with_motion":make_prompt(char,action,recipe,True),
                "negative_prompt":"运镜、切镜、换装、裁切、整张图片平移缩放。"}
            jobs.append(job)
            parts+=section(job,action,"../../../")
        (DEST/"roles"/(cid+".md")).write_text("\n".join(parts),encoding="utf-8")
        all_doc.append("\n".join(parts).replace("../../../reference/","../../reference/"))
    check_jobs(jobs,recipe)
    data={"schema_version":3,"prompt_version":recipe["version"],"style_version":refs["style_version"],
        "user_model_label":recipe["user_model_label"],"user_failure":recipe["user_failure"],
        "reference_status":"prepared","video_status":"awaiting_video_generation",
        "validation_status":"awaiting_seedance_pilot","upstream":recipe["upstream"],"jobs":jobs}
    (DEST/"jobs.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (DEST/"README.md").write_text("\n".join(overview)+"\n",encoding="utf-8")
    (DEST/"ALL-PROMPTS.md").write_text("\n".join(all_doc),encoding="utf-8")
    with (DEST/"config-mapping.csv").open("w",encoding="utf-8-sig",newline="") as f:
        out=csv.writer(f)
        out.writerow(["character_id","animation_name","config_fields","reference_image","motion_reference","source_video"])
        out.writerows([j["character_id"],j["animation_name"],"; ".join(j["config_fields"]),j["reference_image"],j["motion_reference"],j["source_video"]] for j in jobs)
    pilot=["# 先在豆包试这三条：DeepSeek v3\n",
        "反馈目标：动作更生动、更舒展。先用同一角色和同一入口检验，以下不是已生成的视频结果。\n",
        "设置10秒、16:9；图片1用每条所附S。有全能参考入口再加对应视频1。仅图模式不上传视频；先不额外锁同一张尾帧。\n",
        "每条只复制一个代码块。视频参考模式与首尾帧模式是不同入口，不把reference_video与first_frame/last_frame字段混成一次请求。\n"]
    for pilot_id in recipe["pilot_ids"]:
        j=next(j for j in jobs if j["character_id"]=="deepseek" and j["action_id"]==pilot_id)
        if j["priority"]=="pilot":
            action=action_for_role(next(a for a in recipe["actions"] if a["id"]==j["action_id"]),recipe["roles"]["deepseek"])
            pilot+=section(j,action,"../../")
    pilot+=["## 如何判定幅度是否解决\n",
        "- 挥手：手掌从肩外侧摆到耳旁，轨迹至少半个头宽，肩肘和躯干一起动。",
        "- 跳跃：看到压低蓄力、脚下空隙与落地缓冲，不能只是鞋尖一抖。",
        "- 点按：前臂从胸口下方往腰前往返，肩背跟着回弹，不能只有手指抖。",
        "- 再检查脸型、耳角翼尾和服装是否稳定；大动作不以变形换取。\n",
        "若仍偏小：只替换该动作的幅度句，保持其他输入不变。挥手可写“双臂从肩下到头两侧完整展开”；点按可写“每次抬前臂再按下，躯干跟着前俯回弹”。不要只追加‘更生动’。\n",
        "若身体已好但首尾接不上，再单独试尾帧约束或补回位片段；先不要同时改变时长、参考输入和整条文案。\n",
        "用[试样记录表](PILOT-RESULTS.csv)记录新首帧与动作配方的实际结果。"]
    (DEST/"PILOT-DEEPSEEK.md").write_text("\n".join(pilot),encoding="utf-8")
    results=DEST/"PILOT-RESULTS.csv"
    if not results.exists():
        with results.open("w",encoding="utf-8-sig",newline="") as f:
            out=csv.writer(f)
            out.writerow(["角色","动作","模型界面名","模式","幅度是否够","面部手脚是否稳定","尾帧是否回位","结果路径","备注"])
            out.writerows([["deepseek",j["animation_name"],recipe["user_model_label"],"","","","","",""] for j in jobs if j["priority"]=="pilot"])
    maximum=max(max(len(j["prompt"]),len(j["prompt_with_motion"])) for j in jobs)
    print("Built",len(jobs),"v3 jobs x 2 modes; max",maximum,"characters")
    print("All config mappings, first-frame hashes and 17 motion-reference hashes verified")

if __name__=="__main__":
    main()
