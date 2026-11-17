"""Export the v2 two-head sprites without redrawing their pixels.
Run from repo root: python tools/prepare_chibi_v2.py
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
import spec
from prepare_chibi import place, bbox

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "reference/chibi-v2"
SOURCE_SIZE = (1280, 720)
HEIGHT, FEET, DRAG_OFFSET = 468, 612, 22

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def split_four(path):
    image = Image.open(path).convert("RGBA")
    raw = np.array(image)
    if np.mean(raw[:, :, 3] < 8) < .1:
        raise ValueError("Expected genuine transparent sheet: " + str(path))
    labels, count = ndimage.label(raw[:, :, 3] > 24)
    sizes = np.bincount(labels.ravel())
    if count < 4:
        raise ValueError("Expected four separated figures")
    bodies = list(np.argsort(sizes[1:])[-4:] + 1)
    bodies.sort(key=lambda n: ndimage.center_of_mass(labels == n)[1])
    centres = [ndimage.center_of_mass(labels == n) for n in bodies]
    if any(sizes[n] < raw.shape[0] * raw.shape[1] * .018 for n in bodies):
        raise ValueError("One of the four poses is missing")
    assigned = {}
    for label in range(1, count + 1):
        if sizes[label] < 32:  # discard isolated alpha dust, not drawn silhouette
            continue
        cy, cx = ndimage.center_of_mass(labels == label)
        assigned[label] = min(range(4), key=lambda i: (cx-centres[i][1])**2 + .1*(cy-centres[i][0])**2)
    crops = []
    for i in range(4):
        mask = np.zeros(labels.shape, dtype=bool)
        for label, group in assigned.items():
            if group == i:
                mask |= labels == label
        allowed = ndimage.binary_dilation(mask, iterations=2)
        item = raw.copy()
        item[:, :, 3] = np.where(allowed, item[:, :, 3], 0)
        item[item[:, :, 3] < 4] = 0
        isolated = Image.fromarray(item, "RGBA")
        crops.append(isolated.crop(bbox(isolated, 1)))
    return crops

def overview():
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    sheet = Image.new("RGB", (1600, 920), (246, 247, 251))
    small = Image.new("RGB", (1600, 250), (246, 247, 251))
    for i, char in enumerate(spec.CHARACTERS):
        cid = char["id"]
        original = Image.open(ART / "views" / (cid + "-front.png")).convert("RGBA")
        original = original.crop(bbox(original))
        scaled = original.resize((round(original.width*330/original.height), 330), Image.LANCZOS)
        x, y = (i%4)*400, (i//4)*460
        sheet.paste(scaled, (x+(400-scaled.width)//2, y+28), scaled)
        ImageDraw.Draw(sheet).text((x+145,y+390), cid, font=font, fill=(40,44,62))
        tiny = original.resize((round(original.width*128/original.height),128), Image.LANCZOS)
        small.paste(tiny, (i*200+(200-tiny.width)//2,28), tiny)
        ImageDraw.Draw(small).text((i*200+52,185), cid, font=font, fill=(40,44,62))
    screenshots = ROOT / "docs/screenshots"
    sheet.save(screenshots / "chibi-v2-all8.png")
    small.save(screenshots / "chibi-v2-small.png")
    # Comparison at the same actual silhouette height, never stretched.
    compare = Image.new("RGB", (600, 240), (255,255,255))
    for i, path in enumerate((ART / "style-target.png", ROOT / "reference/chibi/portraits/deepseek.png", ART / "portraits/deepseek.png")):
        pic = Image.open(path).convert("RGBA")
        if i == 0:
            a = np.array(pic)
            ink = (np.min(a[:,:,:3],axis=2)<235)&(a[:,:,3]>16)
            yy,xx=np.nonzero(ink)
            pic = pic.crop((xx.min(),yy.min(),xx.max()+1,yy.max()+1))
        else:
            pic = pic.crop(bbox(pic))
        pic = pic.resize((round(pic.width*140/pic.height),140),Image.LANCZOS)
        compare.paste(pic,(i*200+(200-pic.width)//2,25),pic)
        ImageDraw.Draw(compare).text((i*200+62,190),("target","v1","v2")[i],font=font,fill=(40,44,62))
    compare.save(screenshots / "chibi-v2-comparison.png")

def main():
    for d in ("portraits", "views", "firstframes", "turnarounds"):
        (ART/d).mkdir(parents=True, exist_ok=True)
    generation = json.loads((ART / "image-generation.json").read_text(encoding="utf-8"))
    manifest = {"schema_version":2, "style_version":generation.get("style_version","two-head-v2"), "characters":{}}
    for char in spec.CHARACTERS:
        cid = char["id"]
        source = ART / "sheets" / (cid + ".png")
        front, side, back, hanging = split_four(source)
        entries = {}
        for name,crop in (("front",front),("side",side),("back",back),("drag",hanging)):
            target = ART / "views" / (cid+"-"+name+".png")
            place(crop,(1200,1200),1000,1100).save(target)
            entries[name] = target.relative_to(ROOT).as_posix()
        portrait = ART / "portraits" / (cid+".png")
        place(front,(1200,1200),1000,1100).save(portrait)
        # The drag pose uses the standing SOURCE scale, not a fresh bounding-box fit.
        front_height = bbox(front)[3]-bbox(front)[1]
        drag_height = round((bbox(hanging)[3]-bbox(hanging)[1])*HEIGHT/front_height)
        for label,crop,height,feet in (("",front,HEIGHT,FEET),("-drag",hanging,drag_height,FEET-DRAG_OFFSET)):
            frame = place(crop,SOURCE_SIZE,height,feet,(0,255,0,255)).convert("RGB")
            frame.save(ART / "firstframes" / (cid+label+".png"))
            white = place(crop,SOURCE_SIZE,height,feet,(255,255,255,255)).convert("RGB")
            white.save(ART / "firstframes" / (cid+label+"-white.png"))
        turnaround = Image.new("RGBA",(1500,600),(0,0,0,0))
        for i,crop in enumerate((front,side,back)):
            view = place(crop,(500,600),500,550)
            turnaround.alpha_composite(view,(i*500,0))
        triptych = ART / "turnarounds" / (cid+".png")
        turnaround.save(triptych)
        manifest["characters"][cid] = {
             "name":char["name"],"expression":generation["characters"][cid].get("expression",""),
            "source":source.relative_to(ROOT).as_posix(),
            "source_sha256":digest(source),"portrait":portrait.relative_to(ROOT).as_posix(),
            "views":entries,"turnaround":triptych.relative_to(ROOT).as_posix(),
            "standing_reference":"reference/chibi-v2/firstframes/"+cid+".png",
            "drag_reference":"reference/chibi-v2/firstframes/"+cid+"-drag.png",
            "drag_pose_origin":"independently_drawn_fourth_pose",
            "standing_source_height":HEIGHT,"drag_source_height":drag_height,
            "drag_scale":"same pixel scale as standing source; no independent height fit"
        }
        print("v2 prepared",cid,"S height",HEIGHT,"H height",drag_height)
    manifest["geometry"] = {"source_size":[1280,720],"standing_height":468,
        "standing_feet_y":612,"drag_offset_y":22,"output_size":[640,360],"fps":24,
        "normalised_master":[2160,1215],"normalised_character_height":900,"normalised_feet_y":1115}
    (ART/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    overview()

if __name__=="__main__":
    main()
