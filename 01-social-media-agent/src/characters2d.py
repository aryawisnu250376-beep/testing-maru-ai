"""Original 2D story renderer. Nara is an original fictional vector character.

No reference images, creator assets, or generated stills are used. Static vector
parts are cached; motion is applied to the character and diagram elements. The
full 1080x1920 canvas is designed for phone viewing and TikTok safe areas.
"""
from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageDraw

from .anim import ease_out_cubic, fit, font, prog, text_block

INK = (24, 53, 48)
MUTED = (87, 111, 103)
TEAL = (31, 125, 108)
MINT = (219, 239, 225)
PAPER = (249, 248, 241)
WHITE = (255, 255, 253)
ORANGE = (238, 151, 92)
LAVENDER = (221, 216, 240)
SKIN = (208, 151, 109)
HAIR = (40, 44, 40)
STAGE_LABELS = {"tokoh": "01 · TOKOH", "masalah": "02 · MASALAH", "percobaan": "03 · PERCOBAAN",
                "titik_balik": "04 · TITIK BALIK", "batasan": "05 · BATASAN",
                "pelajaran": "06 · PELAJARAN", "cta": "07 · BAWA PULANG"}


@lru_cache(maxsize=24)
def character(emotion: str = "curious", pose: int = 0) -> Image.Image:
    """Original character, drawn at 2x then antialiased; 420x540 logical px."""
    im = Image.new("RGBA", (840, 1080))
    d = ImageDraw.Draw(im)

    def box(coords, fill, radius=0, outline=None, width=1):
        c = tuple(int(v * 2) for v in coords)
        if radius:
            d.rounded_rectangle(c, radius=radius * 2, fill=fill, outline=outline, width=width * 2)
        else:
            d.rectangle(c, fill=fill, outline=outline, width=width * 2)

    def ell(coords, fill):
        d.ellipse(tuple(int(v * 2) for v in coords), fill=fill)

    def line(points, fill, width):
        d.line([(int(x*2), int(y*2)) for x,y in points], fill=fill, width=width*2, joint="curve")

    # Grounding shadow, legs, shoes.
    ell((48, 492, 369, 526), (218, 227, 211))
    box((125, 348, 191, 487), (44, 65, 60), 24)
    box((222, 348, 286, 487), (44, 65, 60), 24)
    box((107, 465, 195, 505), WHITE, 18)
    box((220, 465, 316, 505), WHITE, 18)
    line([(117, 491), (188, 491)], (173, 191, 179), 3)
    line([(230, 491), (305, 491)], (173, 191, 179), 3)
    # Hair silhouette and neck.
    ell((91, 49, 316, 280), HAIR)
    box((98, 133, 311, 281), HAIR, 48)
    box((177, 225, 233, 282), SKIN, 18)
    # Sweatshirt and pocket.
    box((109, 262, 303, 389), TEAL, 42)
    d.polygon([(153*2,266*2),(205*2,294*2),(257*2,266*2)], fill=(43, 144, 124))
    box((164, 337, 248, 369), (27, 111, 97), 14)
    line([(204, 290), (204, 329)], (183, 220, 196), 3)
    # Arms: small frame-to-frame gestures, not a rigid zooming still.
    dy = (0, -9, -18, -10, 0, 7)[pose % 6]
    if emotion == "happy":
        line([(125, 286), (77, 300+dy), (53, 244+dy)], TEAL, 35)
        ell((36, 224+dy, 73, 262+dy), SKIN)
    else:
        line([(124, 286), (83, 333+dy), (118, 355+dy)], TEAL, 35)
        ell((105, 339+dy, 143, 376+dy), SKIN)
    line([(286, 286), (327, 323-dy), (351, 281-dy)], TEAL, 35)
    ell((335, 260-dy, 373, 299-dy), SKIN)
    # Ears, face, asymmetrical fringe.
    ell((109, 139, 143, 191), SKIN)
    ell((274, 139, 308, 191), SKIN)
    ell((128, 77, 287, 251), SKIN)
    d.pieslice((119*2, 61*2, 292*2, 205*2), 180, 355, fill=HAIR)
    d.polygon([(132*2,111*2),(205*2,76*2),(267*2,114*2),(239*2,135*2),(196*2,112*2),(145*2,146*2)], fill=HAIR)
    # Eyes and expressive eyebrows.
    blink = pose == 5
    for x in (169, 246):
        if blink or emotion == "happy":
            d.arc(((x-10)*2,155*2,(x+10)*2,173*2), 190, 350, fill=HAIR, width=6)
        else:
            ell((x-5, 157, x+5, 173), HAIR)
    brow = -7 if emotion == "worried" else 0
    line([(156, 145+brow), (178, 142-brow)], HAIR, 4)
    line([(235, 142-brow), (256, 145+brow)], HAIR, 4)
    ell((145, 184, 170, 195), (211, 127, 103))
    ell((245, 184, 270, 195), (211, 127, 103))
    line([(208, 173), (204, 189), (212, 190)], (167, 106, 76), 2)
    if emotion == "worried":
        d.arc((187*2,197*2,230*2,222*2), 195, 345, fill=(100, 57, 44), width=6)
    elif emotion == "happy":
        d.pieslice((186*2,193*2,232*2,227*2), 0, 180, fill=(111, 57, 46))
        box((193, 198, 224, 205), WHITE, 2)
    else:
        d.arc((188*2,190*2,232*2,219*2), 10, 160, fill=(100, 57, 44), width=6)
    # Small original brand mark on sweatshirt.
    ell((254, 291, 274, 311), (246, 203, 117))
    return im.resize((420, 540), Image.Resampling.LANCZOS)


def _text(d, text, xy, width, size=40, max_lines=3, color=INK, bold=False):
    f, lines = fit(str(text), "bold" if bold else "body", width, max_lines, size, max(24, size-12),
                   weight=750 if bold else 500)
    return text_block(d._image, lines, f, xy, color, 1.22)


def _panel(d, coords, fill=WHITE, radius=32):
    d.rounded_rectangle(coords, radius=radius, fill=fill)


def draw_clock(d, box, t, label="Waktu untuk memeriksa"):
    x,y,w,h = box
    cx,cy = x+w*.30, y+h*.51
    r = min(h*.36,w*.21)
    d.ellipse((cx-r-9,cy-r-9,cx+r+9,cy+r+9), fill=ORANGE)
    d.ellipse((cx-r,cy-r,cx+r,cy+r), fill=WHITE)
    for i in range(12):
        a = i*math.tau/12
        d.line((cx+math.sin(a)*r*.80,cy-math.cos(a)*r*.80,
                cx+math.sin(a)*r*.9,cy-math.cos(a)*r*.9), fill=MUTED,width=4)
    a = t*.6
    d.line((cx,cy,cx+math.sin(a)*r*.68,cy-math.cos(a)*r*.68), fill=TEAL,width=7)
    d.line((cx,cy,cx-r*.40,cy-r*.32), fill=INK,width=9)
    d.ellipse((cx-7,cy-7,cx+7,cy+7), fill=INK)
    _text(d,label,(x+w*.56,y+h*.32),w*.38,36,3,bold=True)


def draw_thermometer(d, box, t, level=.6, label="Tetap perlu verifikasi"):
    x,y,w,h = box
    tx,ty = x+w*.28,y+h*.14
    d.rounded_rectangle((tx-24,ty,tx+24,ty+h*.62),radius=24,fill=MINT)
    d.ellipse((tx-44,ty+h*.52,tx+44,ty+h*.62+70),fill=ORANGE)
    rise = h*.48*max(0,min(1,level))*ease_out_cubic(prog(t,.3,1))
    d.rounded_rectangle((tx-11,ty+h*.58-rise,tx+11,ty+h*.62+25),radius=10,fill=ORANGE)
    _text(d,label,(x+w*.47,y+h*.32),w*.45,36,3,bold=True)


def draw_bars(d, box, t, items, unit=""):
    x,y,w,h = box
    items = items[:4]
    if not items:
        return
    vals = [max(0,float(i.get("value",0))) for i in items]
    peak = max(vals) or 1
    bw = min(125,w/(len(items)*1.7))
    gap = (w-bw*len(items))/(len(items)+1)
    for i,(item,val) in enumerate(zip(items,vals)):
        bx=x+gap+i*(bw+gap)
        bh=(h-100)*val/peak*ease_out_cubic(prog(t,.2+i*.15,.9))
        d.rounded_rectangle((bx,y+h-60-bh,bx+bw,y+h-60),radius=14,fill=[TEAL,ORANGE,(153,144,196),MUTED][i])
        f=font("bold",28,700)
        d.text((bx+bw/2,y+h-80-bh),str(item.get("value","")),font=f,fill=INK,anchor="mm")
        _text(d,item.get("label",""),(bx-8,y+h-43),bw+16,23,2)
    if unit:
        d.text((x+w,y+12),unit,font=font("body",24),fill=MUTED,anchor="ra")


def _diagram(d, ctx, box, t):
    x,y,w,h=box
    typ=ctx.vtype
    p=ctx.props
    if typ=="clock":
        return draw_clock(d,box,t,p.get("label","Waktu untuk memeriksa"))
    if typ=="thermometer":
        return draw_thermometer(d,box,t,float(p.get("level",.6)),p.get("label","Tetap perlu verifikasi"))
    if typ=="bars":
        return draw_bars(d,box,t,p.get("items",[]),p.get("unit",""))
    if typ=="stat":
        f=font("display",132,800)
        d.text((x+w/2,y+h*.40),str(p.get("value","")),font=f,fill=TEAL,anchor="mm")
        _text(d,p.get("label",ctx.beat.get("headline","")),(x+50,y+h*.65),w-100,34,2,bold=True)
        return
    if typ=="compare":
        cw=(w-24)/2
        for i,side in enumerate(("left","right")):
            obj=p.get(side) or {}
            bx=x+i*(cw+24)
            _panel(d,(bx,y,bx+cw,y+h),MINT if i else LAVENDER,24)
            _text(d,obj.get("title",""),(bx+24,y+28),cw-48,35,2,bold=True)
            for j,item in enumerate((obj.get("items") or [])[:3]):
                _text(d,"• "+str(item),(bx+24,y+115+j*78),cw-48,29,2)
        return
    if typ in ("diagram","steps"):
        items=p.get("nodes") or p.get("items") or []
        items=items[:3]
        rh=min(112,(h-30)/max(1,len(items))-14)
        for i,item in enumerate(items):
            ry=y+i*(rh+20)
            _panel(d,(x,ry,x+w,ry+rh),MINT if i%2==0 else (241,235,220),22)
            d.ellipse((x+20,ry+rh/2-22,x+64,ry+rh/2+22),fill=TEAL)
            d.text((x+42,ry+rh/2),str(i+1),font=font("bold",26),fill=WHITE,anchor="mm")
            title=item.get("title","") if isinstance(item,dict) else str(item)
            _text(d,title,(x+86,ry+18),w-110,34,2,bold=True)
            if i<len(items)-1:
                ax=x+w/2
                d.line((ax,ry+rh+3,ax,ry+rh+15),fill=TEAL,width=3)
        return
    if typ=="code":
        _panel(d,box,INK,24)
        for i,line in enumerate((p.get("lines") or [])[:5]):
            _text(d,str(line),(x+30,y+30+i*70),w-60,29,1,color=(191,231,205))
        return
    # Character, card, quote and legacy types all retain a readable story panel.
    text=p.get("text") or ctx.beat.get("headline") or "Pahami dulu, baru coba."
    _text(d,text,(x+44,y+70),w-88,56,4,color=TEAL,bold=True)


def render_story_frame(ctx, t: float, size=(1080,1920)) -> Image.Image:
    img=Image.new("RGB",(1080,1920),PAPER)
    d=ImageDraw.Draw(img)
    # Environmental geometry, deliberately flat and original.
    d.ellipse((810,210,1190,590),fill=(234,238,218))
    d.ellipse((-190,1100,220,1510),fill=(234,238,218))
    brand=str(ctx.cfg.get("brand",{}).get("name","AI DALAM 60 DETIK"))
    _panel(d,(72,100,700,166),INK,33)
    d.text((100,133),brand,font=font("bold",27,750),fill=WHITE,anchor="lm")
    d.text((1004,133),f"{ctx.idx+1:02d}/{ctx.total:02d}",font=font("body",26),fill=MUTED,anchor="rm")
    for i in range(ctx.total):
        sx=76+i*928/ctx.total
        d.rounded_rectangle((sx,201,sx+928/ctx.total-10,207),radius=3,fill=TEAL if i<=ctx.idx else (218,226,211))
    stage=ctx.beat.get("story_stage") or ctx.beat.get("kind","point")
    d.text((76,274),STAGE_LABELS.get(stage,stage.upper()),font=font("bold",25,750),fill=TEAL)
    bbox=_text(d,ctx.beat.get("headline",""),(76,331),928,83,2,bold=True)
    ctx.bboxes.append(bbox)
    # Diagram panel.
    _panel(d,(72,548,1008,1058),WHITE,36)
    d.rounded_rectangle((72,548,1008,1058),radius=36,outline=(225,231,219),width=2)
    _diagram(d,ctx,(110,586,852,426),t)
    if ctx.props.get("illustrative") or ctx.vtype in ("clock","thermometer"):
        d.text((970,1026),"ILUSTRASI · BUKAN DATA PENGUKURAN",font=font("body",19),fill=MUTED,anchor="rs")
    # Character + short supporting text, leaving the subtitle area free.
    kind=ctx.beat.get("kind")
    emotion=ctx.props.get("emotion") or ("worried" if kind=="limit" or stage=="masalah" else "happy" if stage in ("titik_balik","cta") else "curious")
    pose=int(t*2.2)%6
    ch=character(emotion,pose)
    bob=int(3*math.sin(t*2.4))
    img.paste(ch,(49,1020+bob),ch)
    _panel(d,(472,1114,1008,1376),MINT,30)
    d.polygon([(472,1210),(442,1235),(472,1250)],fill=MINT)
    body=ctx.beat.get("body") or ctx.beat.get("narration","")
    # Body is deliberately shortened for the visual; complete text is narrated/captioned.
    words=body.split()
    short=" ".join(words[:16])+("…" if len(words)>16 else "")
    bbox=_text(d,short,(506,1145),462,34,5)
    ctx.bboxes.append(bbox)
    # Subtitles occupy y=1420..1570 (burned by libass).
    if ctx.sources:
        source="Sumber: "+" · ".join(ctx.sources[:2])
        f,lines=fit(source,"body",928,1,23,19)
        d.text((76,1640),lines[0],font=f,fill=MUTED)
    d.text((76,1684),str(ctx.cfg.get("brand",{}).get("handle","@aipelan60")),font=font("bold",26),fill=INK)
    if (ctx.cfg.get("video",{}).get("style")=="story2d"):
        d.text((76,1730),"Nara · tokoh fiksi untuk ilustrasi cerita",font=font("body",23),fill=MUTED)
    if size!=(1080,1920):
        img=img.resize(size,Image.Resampling.LANCZOS)
    return img
