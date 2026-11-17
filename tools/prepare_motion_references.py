"""Prepare verified dsh-pet motion references as opaque MP4s for video models.
python tools/prepare_motion_references.py [--ids wave jump typing]
Original VP9-alpha sources remain in ignored work/evidence/dsh-pet-v3.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
import numpy as np
from PIL import Image, ImageDraw
from media_tools import find_ffmpeg
from video_pipeline import video_info, frames

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/"reference/motion-dsh-pet"
CACHE=ROOT/"work/evidence/dsh-pet-v3/webm"

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def acquire(item):
    path=CACHE/(item["id"]+".webm")
    valid=path.exists() and hashlib.sha1(b"blob "+str(path.stat().st_size).encode()+b"\0"+path.read_bytes()).hexdigest()==item["source_git_blob_sha1"]
    if not valid:
        url=quote(item["source_url"],safe=":/")
        with urlopen(url,timeout=45) as response:
            data=response.read()
        actual=hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
        if actual!=item["source_git_blob_sha1"]:
            raise ValueError("Upstream Git blob checksum mismatch: "+item["id"])
        path.write_bytes(data)
    return item,path

def prepare(pair,ffmpeg):
    item,source=pair
    info=video_info(source,ffmpeg)
    first=next(frames(source,ffmpeg,(info["width"],info["height"])))
    if np.mean(first[:,:,3]<8)<.05:
        raise ValueError("Upstream VP9 alpha was not decoded: "+item["id"])
    target=ROOT/item["clip"]
    target.parent.mkdir(parents=True,exist_ok=True)
    cmd=[ffmpeg,"-y","-hide_banner","-loglevel","error",
         "-f","lavfi","-i","color=c=0xEDEFF3:s=640x360:r=24"]
    if item["trim_start"]:
        cmd+=["-ss",str(item["trim_start"])]
    cmd+=["-c:v","libvpx-vp9","-i",str(source),
          "-filter_complex","[1:v]fps=24,scale=640:360[pet];[0:v][pet]overlay=shortest=1:format=auto,format=yuv420p[out]",
          "-map","[out]","-an","-c:v","libx264","-preset","fast","-crf","18",
          "-movflags","+faststart"]
    if item["trim_duration"]:
        cmd+=["-t",str(item["trim_duration"])]
    cmd+=[str(target)]
    run=subprocess.run(cmd,capture_output=True)
    if run.returncode:
        raise RuntimeError(item["id"]+": "+run.stderr.decode("utf-8",errors="replace")[-1200:])
    out_info=video_info(target,ffmpeg)
    if (out_info["width"],out_info["height"],out_info["fps"],out_info["audio"])!=(640,360,24.0,False):
        raise ValueError("Bad reference MP4 spec: "+item["id"])
    # Decode the whole short reference: metadata alone cannot show a damaged clip.
    count=sum(1 for _ in frames(target,ffmpeg,(640,360)))
    if count<24:
        raise ValueError("Empty or too short reference clip: "+item["id"])
    return dict(item,source_sha256=sha256(source),clip_sha256=sha256(target),
                clip_bytes=target.stat().st_size,frames=count,duration_sec=round(count/24,3),
                codec=out_info["codec"],background="#EDEFF3",audio=False,status="verified",
                trim_note=("仅截取原片3–7秒悬空中段；不参考起落动作" if item["id"]=="drag" else "保留官方动作与原始时间节奏"))

def contact_sheet(items,ffmpeg):
    selected=[i for i in items if i["id"] in ("wave","jump","typing","celebrate","drag","turn")]
    board=Image.new("RGB",(1200,165*len(selected)),(237,239,243))
    draw=ImageDraw.Draw(board)
    for row,item in enumerate(selected):
        wanted=[round((item["frames"]-1)*x) for x in (.05,.25,.5,.75,.95)]
        frame_map={}
        for index,frame in enumerate(frames(ROOT/item["clip"],ffmpeg,(640,360))):
            if index in wanted:
                frame_map[index]=frame
        for col,index in enumerate(wanted):
            pic=Image.fromarray(frame_map[index],"RGBA")
            pic.thumbnail((235,133),Image.LANCZOS)
            board.paste(pic,(col*240,row*165+24),pic)
        draw.text((8,row*165+5),item["id"],fill=(20,25,35))
    board.save(ROOT/"work/evidence/dsh-pet-v3/actual-motion-contact.png")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids",nargs="+")
    parser.add_argument("--ffmpeg")
    args=parser.parse_args()
    spec=json.loads((REF/"sources.json").read_text(encoding="utf-8"))
    wanted=[i for i in spec["items"] if not args.ids or i["id"] in args.ids]
    if args.ids and set(args.ids)-{i["id"] for i in wanted}:
        raise ValueError("Unknown reference id")
    CACHE.mkdir(parents=True,exist_ok=True)
    ffmpeg=find_ffmpeg(args.ffmpeg)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        acquired=list(pool.map(acquire,wanted))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        prepared=list(pool.map(lambda pair:prepare(pair,ffmpeg),acquired))
    old_path=REF/"manifest.json"
    old=json.loads(old_path.read_text(encoding="utf-8")) if old_path.exists() else {}
    by_id={i["id"]:i for i in old.get("items",[])}
    by_id.update({i["id"]:i for i in prepared})
    spec["items"]=[by_id[i["id"]] for i in spec["items"] if i["id"] in by_id]
    spec["content_type"]="官方角色动作参考，非本项目8角色生成成片"
    spec["complete"]=len(spec["items"])==17
    old_path.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    contact_sheet(spec["items"],ffmpeg)
    for item in prepared:
        print(item["id"],item["duration_sec"],item["clip_bytes"])
    print("Verified MP4 references:",len(spec["items"]))

if __name__=="__main__":
    main()
