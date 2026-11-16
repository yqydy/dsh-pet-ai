"""Build 136 v2 video jobs from actual pack configs, pinned upstream recipes and refs."""
import csv
import json
from pathlib import Path
import spec

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "prompts/chibi"
FENCE = chr(96)*3

def field_paths(config,value):
    found=[]
    def visit(item,path):
        if isinstance(item,dict):
            for key,child in item.items(): visit(child,path+"."+key)
        elif isinstance(item,list):
            for i,child in enumerate(item): visit(child,path+"["+str(i)+"]")
        elif item==value: found.append(path)
    visit(config["animations"],"animations")
    return found

def make_prompt(char,recipe,action,clean=False,detailed=False):
    cid=char["id"]
    hanging=action["endpoint_mode"]=="H-H"
    endpoint=("首尾都是所附悬空H：双手脚自然下垂，嘴型、表情和摆动相位与参考一致。全程悬空，不落地。"
              if hanging else "第0–1秒与第9–10秒保持所附站姿S，空手、睁眼、闭嘴，无道具或特效残留。首尾姿势、位置和尺寸一致。")
    # H is genuinely drawn separately, with the same pixel scale as S.
    common=recipe["COMMON"]
    if hanging:
        common=common.replace("站姿最高点约20%、脚底85%","悬空脚底约82%，大小沿用站姿")
    timeline=action["clean_timeline"] if clean else action["timeline"]
    summary=action["clean_summary"] if clean else action["summary"]
    effect=action["effects"]
    if clean:
        effect_text=("附加图形：无。不生成头顶图标、粒子、字幕或汗珠；只保留归档动作必需的两张纸卡。" if action["name"]=="工作状态-清点归档"
                     else "附加图形：无。不要图标、气泡、粒子、字幕或临时道具。")
    elif effect=="无":
        effect_text="图形与道具：无，不增加图标、气泡、文字或粒子。"
    elif effect=="2张无字纸卡":
        effect_text="道具只用两张无字纸卡：第1–2秒渐显，第7–9秒渐隐，保持在胸前、下巴以下，不遮脸。"
    else:
        effect_text=("图形只用"+effect+"，不再加其他图标。"+action["effect_timing"]+"；"
                    "头顶图形仅放画高12%–18%、宽45%–55%的空隙，尺寸不超过画高3%，不遮发饰。"
                    if "汗" not in effect else "只在额边添加一滴小蓝汗珠：第3秒渐显，第5秒前滑落一点并淡去，不生成乌云或红叉。")
    prefix="《"+char["name"]+" / "+action["name"]+"》\n"
    text=prefix+recipe["STYLE"]+"\n角色："+recipe["DESIGNS"][cid]+"\n"+common+"\n"+endpoint+"\n"
    text+="动作："+summary+"\n时间分段："+(" ".join(timeline))+"\n"+effect_text+"\n"
    text+="次级动作："+recipe["SECONDARY"][cid]
    if detailed:
        text+="\n验收重点："+action["check"]+"\n逐段核对：\n"+"\n".join("- "+step for step in timeline)
        text+="\n以双脚中点为固定根节点，手、肘、肩、膝真实弯曲，发梢裙摆稍晚回落；不把整张静态PNG当纸片晃动。"
    return text

def main():
    recipe=json.loads((DEST/"recipes.json").read_text(encoding="utf-8"))
    manifest=json.loads((ROOT/"reference/chibi-v2/manifest.json").read_text(encoding="utf-8"))
    actions=recipe["ACTIONS"]
    if [a["name"] for a in actions]!=spec.ANIM_NAMES:
        raise ValueError("Recipe action order differs from spec")
    overview=["# 两头身桌宠：136条优化动作提示词（v2）\n",
      "先用对应角色的**单人绿幕首帧**图生视频。默认10秒、16:9、固定镜头；支持首尾帧时，两端上传同一张S（站姿）或H（悬空）。",
      "每条先复制「精简投喂版」；「详细分镜版」是替代稿，二选一。图形画不好时用「无叠加图形版」，后期再加图标，归档保留必要纸卡。",
      "三视图仅作外观辅助；不要把三人/四姿势图直接当首帧，否则容易生成多个人。只有转圈必须加三视图。",
      "第一轮先做DeepSeek的待机、挥手、跳跃、忙碌点按、悬空5条，通过后再扩展其余角色。建议先做没有转身的动作。",
      "上游并非只靠提示词：其成片使用PR手工抠像，再统一大小/足线并编码。提示词无法保证消除绿边或让任意模型逐帧复现。",
      "\n[重绘与上游对照](../../docs/CHIBI-V2-REVISION.md) · [制作与导入](../../docs/MAKE-CHIBI-PET.md)\n",
      "|角色|17条优化提示词|S|H|三视图|",
      "|---|---|---|---|---|"]
    all_docs=["# 136条两头身桌宠动作提示词 v2\n"]
    jobs=[]
    mapping=[]
    source_base=recipe["upstream"]["repository"]+"/blob/"+recipe["upstream"]["commit"]+"/"+recipe["upstream"]["prompt_path"]
    for char in spec.CHARACTERS:
        cid=char["id"]
        refs=manifest["characters"][cid]
        config=json.loads((ROOT/"plugin/packs"/(char["prefix"]+"-config.json")).read_text(encoding="utf-8"))
        for field in ("standing_reference","drag_reference","turnaround","portrait"):
            if not (ROOT/refs[field]).is_file(): raise ValueError("Missing "+refs[field])
        overview.append("|"+char["name"]+"|[打开](roles/"+cid+".md)|[PNG](../../"+refs["standing_reference"]+")|[PNG](../../"+refs["drag_reference"]+")|[PNG](../../"+refs["turnaround"]+")|")
        sections=["# "+char["name"]+"：两头身v2动作提示词\n",
            "角色识别："+recipe["DESIGNS"][cid]+"\n",
            "[站立首帧S](../../../"+refs["standing_reference"]+") · [悬空首帧H](../../../"+refs["drag_reference"]+") · [三视图](../../../"+refs["turnaround"]+")\n",
            "设置：图生视频，10秒，16:9。支持首尾控制时上传同一S或H；单首帧平台需后期检查回位。复制精简版即可，不与详细版叠加。",
            "主动画做好后再补图标。源片不机械加速到旧程序动画时长；按动作实际节奏剪出完整闭环。\n"]
        for i,(action,anim) in enumerate(zip(actions,spec.ANIMATIONS)):
            name,duration,loop,category,_=anim
            ref=refs["drag_reference"] if action["endpoint_mode"]=="H-H" else refs["standing_reference"]
            fields=field_paths(config,name)
            if not fields: raise ValueError("Unmapped "+name)
            prompt=make_prompt(char,recipe,action)
            detailed=make_prompt(char,recipe,action,detailed=True)
            clean=make_prompt(char,recipe,action,clean=True)
            job={"character_id":cid,"character_name":char["name"],"animation_name":name,
                "source_video":"video/chibi-v2/"+cid+"/"+name+".mp4",
                "reference_image":ref,"start_frame":ref,"end_frame":ref,
                "turnaround_reference":refs["turnaround"],"requires_turnaround":name=="转圈展示",
                "output":"plugin/packs/"+char["prefix"]+"-animation/"+name+".webm",
                "generation_duration_sec":10,"existing_duration_sec":duration,
                "loop_metadata":loop,"config_fields":fields,"endpoint_mode":action["endpoint_mode"],
                "upstream_heading":action["upstream_heading"],"upstream_source":source_base,
                "upstream_commit":recipe["upstream"]["commit"],
                "status":"awaiting_video_generation","prompt":prompt,"negative_prompt":recipe["NEG"],
                "storyboard_prompt":detailed,"clean_prompt":clean,"timeline":action["timeline"],
                "review_focus":action["check"]}
            jobs.append(job)
            mapping.append([cid,name,action["upstream_heading"],action["endpoint_mode"],"; ".join(fields),job["source_video"],job["output"]])
            sections += ["## "+str(i+1).zfill(2)+" "+name+"\n",
                "上传：[单人首帧](../../../"+ref+")（"+action["endpoint_mode"]+"）。源片保存："+job["source_video"]+"\n",
                "上游对应："+action["upstream_heading"]+"。验收："+action["check"]+"\n",
                "### 精简投喂版\n",FENCE+"text\n"+prompt+"\n"+FENCE+"\n",
                "负面词："+recipe["NEG"]+"\n",
                "<details><summary>详细分镜版（替代精简版）</summary>\n\n"+FENCE+"text\n"+detailed+"\n"+FENCE+"\n\n</details>\n",
                "<details><summary>无叠加图形版（图标不稳定时用）</summary>\n\n"+FENCE+"text\n"+clean+"\n"+FENCE+"\n\n</details>\n",
                "配置引用："+ "；".join(fields)+"\n"]
        (DEST/"roles"/(cid+".md")).write_text("\n".join(sections),encoding="utf-8")
        all_docs.append("\n".join(sections).replace("../../../reference/","../../reference/"))
    if len(jobs)!=136 or len({(j["character_id"],j["animation_name"]) for j in jobs})!=136:
        raise ValueError("Expected 136 unique jobs")
    (DEST/"README.md").write_text("\n\n".join(overview)+"\n\nQ版AI动作视频尚待生成；当前plugin/packs是旧程序动画。v1图片在reference/chibi保留，新任务只使用reference/chibi-v2。\n",encoding="utf-8")
    (DEST/"ALL-PROMPTS.md").write_text("\n".join(all_docs),encoding="utf-8")
    data={"schema_version":2,"style_version":"two-head-v2","reference_status":"prepared",
          "video_status":"awaiting_video_generation","upstream":recipe["upstream"],"jobs":jobs}
    (DEST/"jobs.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (DEST/"config-mapping.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.writer(f)
        writer.writerow(["character_id","animation_name","upstream_heading","endpoint_mode","config_fields","source_video","output"])
        writer.writerows(mapping)
    print("Prepared",len(jobs),"v2 jobs; compact prompt max",max(len(j["prompt"]) for j in jobs),"characters")

if __name__=="__main__":
    main()
