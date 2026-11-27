#!/usr/bin/env python3
"""Merqab post renderer: one spec (JSON) -> X image 4:5 PNG + 9:16 motion-graphics reel MP4 (silent).

Usage:  python3 mrqab_post.py spec.json OUT_DIR [--brand BRAND_DIR]

spec = {
  "key": "daily_2026-11-26_activities",
  "kicker": "نبض السوق",
  "title": "رصدنا <em>36 متجــر</em> جديد",      # one <em> word (mint + kashida)
  "sub": "الأنشطة الأكثر افتتاح في 26 نوفمبر",    # optional
  "body": {"type": "hbars", "rows": [["الأزياء والعبايات", 7], ...], "suffix": ""}
        | {"type": "vbars", "rows": [["سبتمبر", 120], ...], "highlight": [2]}
        | {"type": "bignum", "value": 36, "prefix": "", "suffix": "", "label": "...", "note": "..."}
        | {"type": "cards", "items": [["1,420", "متجر منذ أكتوبر"], ...]},
  "note": "سطر تفسير يظهر بمؤثر كتابي",            # optional
  "source": "رصد مرقاب لـ36 متجر جديد · 26 نوفمبر 2026",
  "duration": 10
}
Numbers inside Arabic text must be wrapped as <span class="num">42.5%</span>.
"""
import json, sys, os, subprocess, shutil, tempfile, argparse, html as H

BASE_URL = "https://raw.githubusercontent.com/madhiwork-netizen/storesscraper/main/mrqab-brand"

CSS = r"""
@font-face{font-family:'TS';src:url('B/thmanyah-sans-Medium.woff2');font-weight:500}
@font-face{font-family:'TS';src:url('B/thmanyah-sans-Bold.woff2');font-weight:700}
@font-face{font-family:'TS';src:url('B/thmanyah-sans-Black.woff2');font-weight:900}
@font-face{font-family:'SG';src:url('B/space-grotesk-latin-700-normal.woff2');font-weight:700}
@font-face{font-family:'SG';src:url('B/space-grotesk-latin-500-normal.woff2');font-weight:500}
*{box-sizing:border-box;margin:0;padding:0}
html{overflow:hidden}
body{width:1080px;height:HPX;background:#0D0118;color:#F2EEFF;font-family:'TS';direction:rtl;overflow:hidden;position:relative}
.glow{position:absolute;top:-260px;left:-260px;width:900px;height:900px;border-radius:50%;background:radial-gradient(circle,rgba(123,69,218,.24),rgba(123,69,218,0) 65%);pointer-events:none}
.eye{position:absolute;left:50%;bottom:-330px;width:1100px;height:1100px;margin-left:-550px;opacity:.42;
 -webkit-mask-image:radial-gradient(circle at 50% 50%,#000 38%,transparent 68%),linear-gradient(to bottom,transparent 0%,#000 45%);
 -webkit-mask-composite:source-in;mask-composite:intersect;background:url('B/eye.png') center/cover;border-radius:50%}
.post{position:relative;width:1080px;height:HPX;padding:PAD;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;height:76px}
.brand{display:flex;align-items:center;gap:22px}
.brand img{width:74px;height:74px;border-radius:50%;border:2px solid #2A1B45}
.brand span{font-weight:900;font-size:58px;font-feature-settings:'salt','ss04'}
.handle{font-family:'SG';font-weight:500;font-size:30px;color:#9A8FB5;direction:ltr}
.kicker{margin-top:56px;display:inline-flex;align-self:flex-start;gap:12px;align-items:center;font-weight:700;font-size:30px;color:#5FD3BF;border:2px solid rgba(95,211,191,.35);border-radius:40px;padding:8px 26px 10px}
.kicker i{width:12px;height:12px;border-radius:50%;background:#5FD3BF;display:block}
h1{margin-top:30px;font-weight:900;font-size:H1PX;line-height:1.22;font-feature-settings:'salt','ss04'}
h1 .w{display:inline-block}
h1 em{font-style:normal;color:#5FD3BF;display:inline-block}
.sub{margin-top:18px;font-weight:500;font-size:34px;line-height:1.55;color:#C9B0FF}
.num{font-family:'SG';font-weight:700;direction:ltr;unicode-bidi:isolate;display:inline-block}
.body{flex:1;display:flex;flex-direction:column;justify-content:center;min-height:0;padding:30px 0}
.foot{border-top:2px solid #241638;padding-top:28px;display:flex;justify-content:space-between;align-items:center;gap:30px}
.src{font-weight:500;font-size:22px;color:#9A8FB5;line-height:1.5}
.tag{font-family:'SG';font-weight:700;font-size:26px;direction:ltr;white-space:nowrap}
.tag b{color:#5FD3BF}
.note{margin-top:34px;font-weight:500;font-size:28px;color:#9A8FB5;line-height:1.6}
.hrow{display:flex;align-items:center;gap:22px;margin:13px 0}
.hrow .lab{width:330px;font-weight:700;font-size:32px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hrow .trk{flex:1;height:34px;background:#1C1030;border-radius:17px;overflow:hidden;display:flex}
.hrow .fil{height:100%;background:#7B45DA;border-radius:17px}
.hrow.first .fil{background:#5FD3BF}
.hrow .val{width:110px;font-family:'SG';font-weight:700;font-size:38px;text-align:left;direction:ltr}
.hrow.first .val{color:#5FD3BF}
.vwrap{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;height:620px}
.vcol{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.vcol .v{font-family:'SG';font-weight:700;font-size:34px;margin-bottom:12px}
.vcol .bar{width:100%;background:#3A2366;border-radius:14px 14px 0 0}
.vcol.hl .bar{background:#5FD3BF}.vcol.hl .v{color:#5FD3BF}
.vcol .l{margin-top:14px;font-weight:500;font-size:26px;color:#9A8FB5;white-space:nowrap}
.big{font-family:'SG';font-weight:700;font-size:300px;line-height:1;color:#5FD3BF;direction:ltr}
.bigl{font-weight:700;font-size:40px;margin-top:20px;line-height:1.4}
.bign{font-weight:500;font-size:30px;color:#9A8FB5;margin-top:12px}
.cards{display:flex;flex-direction:column;gap:22px}
.card{background:#150A24;border:2px solid #2A1B45;border-radius:24px;padding:30px 40px;display:flex;align-items:center;gap:30px}
.card .cn{font-family:'SG';font-weight:700;font-size:56px;color:#F2EEFF;direction:ltr;min-width:240px;text-align:right}
.card:first-child .cn{color:#5FD3BF}
.card .cd{font-weight:500;font-size:27px;color:#9A8FB5;line-height:1.5}
"""

JS = r"""
const ease=x=>1-Math.pow(1-Math.min(Math.max(x,0),1),3);
const seg=(t,a,b)=>ease((t-a)/(b-a));
const fmt=(v,d)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
function set(el,o,y,s){el.style.opacity=o;el.style.transform=`translateY(${y}px) scale(${s??1})`;}
window.render=function(t){
  const D=window.DUR, fin=t>=D;
  const eye=document.querySelector('.eye'); if(eye){eye.style.transform=`scale(${1+0.05*t/D})`; eye.style.opacity=.42*seg(t,0,1.2);}
  const g=document.querySelector('.glow'); if(g) g.style.opacity=.75+.25*Math.sin(t*1.3);
  let p=seg(t,.2,.8); set(document.querySelector('.top'),p,(1-p)*-30);
  p=seg(t,.6,1.1); set(document.querySelector('.kicker'),p,0,.85+.15*p);
  const dot=document.querySelector('.kicker i'); dot.style.opacity=.45+.55*Math.abs(Math.cos(t*2.4));
  document.querySelectorAll('h1 .w').forEach((w,i)=>{const q=seg(t,1.0+i*.14,1.45+i*.14); set(w,q,(1-q)*40);});
  const em=document.querySelector('h1 em'); if(em){const n=document.querySelectorAll('h1 .w').length;
    const st=1.0+n*.14+.2, q=seg(t,st,st+.5);
    const pulse=t>st+.5? .5+.5*Math.sin((t-st)*2.2):0;
    em.style.textShadow=`0 0 ${18+22*pulse}px rgba(95,211,191,${.25+.35*pulse*q})`;}
  const tb=1.0+document.querySelectorAll('h1 .w').length*.14+.3;
  const sub=document.querySelector('.sub'); if(sub){p=seg(t,tb,tb+.5); set(sub,p,(1-p)*20);}
  const b0=tb+.4;
  document.querySelectorAll('[data-count]').forEach(el=>{const a=+el.dataset.at||0, v=+el.dataset.count, d=+el.dataset.dec||0;
    const q=seg(t,b0+a,b0+a+1.3); el.textContent=(el.dataset.pre||'')+fmt(v*q,d)+(el.dataset.suf||'');});
  document.querySelectorAll('[data-grow]').forEach(el=>{const a=+el.dataset.at||0, q=seg(t,b0+a,b0+a+1.3);
    el.style[el.dataset.axis||'width']=(+el.dataset.grow*q)+'%';});
  document.querySelectorAll('[data-in]').forEach(el=>{const a=+el.dataset.at||0, q=seg(t,b0+a,b0+a+.5); set(el,q,(1-q)*24);});
  const lead=document.querySelector('.hrow.first .fil, .vcol.hl .bar, .big, .card:first-child');
  if(lead && t>b0+2.5){const s=.5+.5*Math.sin((t-b0)*2.2); lead.style.filter=`drop-shadow(0 0 ${8+14*s}px rgba(95,211,191,.45))`;}
  const note=document.querySelector('.note'); if(note){const q=seg(t,b0+2.6,b0+4.2);
    note.style.clipPath=`inset(0 0 0 ${100-100*q}%)`; note.style.opacity=q>0?1:0;}
  p=seg(t,b0+1.2,b0+1.8); set(document.querySelector('.foot'),p,(1-p)*16);
  const tag=document.querySelector('.tag b'); if(tag) tag.style.textShadow=`0 0 ${10+10*Math.abs(Math.sin(t*1.7))}px rgba(95,211,191,.5)`;
  if(fin){document.querySelectorAll('*').forEach(e=>{e.style.filter='';});
    document.querySelectorAll('h1 em,.tag b').forEach(e=>e.style.textShadow='');}
};
"""

def title_html(t):
    # split into words; keep <em>...</em> and <span class="num">..</span> as single units
    out, i = [], 0
    import re
    toks = re.findall(r'<em>.*?</em>|<span class="num">.*?</span>|[^\s<]+', t)
    return " ".join(f'<span class="w">{x}</span>' for x in toks)

def body_html(b):
    t = b["type"]
    if t == "hbars":
        mx = max(v for _, v in b["rows"]); suf = b.get("suffix", "")
        rows = []
        for i, (lab, v) in enumerate(b["rows"]):
            dec = 1 if isinstance(v, float) and v != int(v) else 0
            rows.append(f'<div class="hrow{" first" if i==0 else ""}" data-in data-at="{i*.18:.2f}"><div class="lab">{H.escape(lab)}</div>'
                        f'<div class="trk"><div class="fil" data-grow="{100*v/mx:.2f}" data-at="{i*.18:.2f}"></div></div>'
                        f'<div class="val" data-count="{v}" data-dec="{dec}" data-suf="{suf}" data-at="{i*.18:.2f}">0</div></div>')
        return "".join(rows)
    if t == "vbars":
        mx = max(v for _, v in b["rows"]); hl = set(b.get("highlight", []))
        if not hl: hl = {max(range(len(b["rows"])), key=lambda i: b["rows"][i][1])}
        cols = [f'<div class="vcol{" hl" if i in hl else ""}" data-in data-at="{i*.12:.2f}"><div class="v" data-count="{v}" data-at="{i*.12:.2f}">0</div>'
                f'<div class="bar" data-axis="height" data-grow="{85*v/mx:.2f}" data-at="{i*.12:.2f}"></div><div class="l">{H.escape(l)}</div></div>'
                for i, (l, v) in enumerate(b["rows"])]
        return f'<div class="vwrap">{"".join(cols)}</div>'
    if t == "bignum":
        dec = b.get("dec", 0)
        return (f'<div class="big" data-count="{b["value"]}" data-dec="{dec}" data-pre="{b.get("prefix","")}" data-suf="{b.get("suffix","")}">0</div>'
                f'<div class="bigl" data-in data-at=".6">{b.get("label","")}</div>'
                + (f'<div class="bign" data-in data-at=".9">{b["note"]}</div>' if b.get("note") else ""))
    if t == "cards":
        return '<div class="cards">' + "".join(
            f'<div class="card" data-in data-at="{i*.25:.2f}"><div class="cn">{H.escape(n)}</div><div class="cd">{d}</div></div>'
            for i, (n, d) in enumerate(b["items"])) + '</div>'
    raise ValueError(t)

def page(spec, ratio, brand):
    h = 1350 if ratio == "45" else 1920
    pad = "84px 90px 70px" if ratio == "45" else "210px 150px 430px 70px"
    css = CSS.replace("B/", brand + "/").replace("HPX", f"{h}px").replace("PAD", pad).replace("H1PX", "78px" if ratio == "45" else "82px")
    deco = '<div class="glow"></div><div class="eye"></div>' if ratio == "916" else ""
    sub = f'<p class="sub">{spec["sub"]}</p>' if spec.get("sub") else ""
    note = f'<p class="note">{spec["note"]}</p>' if spec.get("note") else ""
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{css}</style></head><body>{deco}
<div class="post"><div class="top"><div class="brand"><img src="{brand}/eye.png"><span>مرقاب</span></div><div class="handle">@mrqabco</div></div>
<div class="kicker"><i></i>{spec["kicker"]}</div><h1>{title_html(spec["title"])}</h1>{sub}
<div class="body">{body_html(spec["body"])}{note}</div>
<div class="foot"><div class="src">{spec["source"]}</div><div class="tag">monitor data, turn into <b>insight</b></div></div></div>
<script>window.DUR={spec.get("duration",10)};{JS}</script></body></html>"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("out"); ap.add_argument("--brand", default=BASE_URL)
    ap.add_argument("--fps", type=int, default=30); a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8")); os.makedirs(a.out, exist_ok=True)
    brand = a.brand if a.brand.startswith("http") else "file://" + os.path.abspath(a.brand)
    key, D = spec["key"], spec.get("duration", 10)
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp()
    with sync_playwright() as p:
        br = p.chromium.launch(args=["--allow-file-access-from-files"], executable_path=shutil.which("google-chrome") or None)
        res = {}
        for ratio in ("45", "916"):
            h = 1350 if ratio == "45" else 1920
            f = os.path.join(tmp, f"{ratio}.html"); open(f, "w", encoding="utf-8").write(page(spec, ratio, brand))
            pg = br.new_page(viewport={"width": 1080, "height": h}); pg.goto("file://" + f); pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(400)
            over = pg.evaluate("""()=>{const b=document.querySelector('.body');const f=document.querySelector('.foot');
               return {bodyOverflow:b.scrollHeight>b.clientHeight+2, footBottom:f.getBoundingClientRect().bottom}}""")
            res[ratio] = over
            pg.evaluate(f"render({D})")
            suffix = "" if ratio == "45" else "_916"
            pg.screenshot(path=os.path.join(a.out, f"{key}{suffix}.png"))
            if ratio == "916":
                fr = os.path.join(tmp, "fr"); os.makedirs(fr)
                n = int(D * a.fps)
                for i in range(n):
                    pg.evaluate(f"render({i / a.fps})"); pg.screenshot(path=os.path.join(fr, f"{i:04d}.png"))
            pg.close()
        br.close()
    out = os.path.join(a.out, f"{key}_reel.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", os.path.join(tmp, "fr", "%04d.png"),
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a", "-t", str(D),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(tmp)
    print(json.dumps({"key": key, "layout": res, "files": [f"{key}.png", f"{key}_916.png", f"{key}_reel.mp4"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
