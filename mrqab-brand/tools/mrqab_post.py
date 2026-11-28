#!/usr/bin/env python3
"""Merqab post renderer: one spec (JSON) -> X image 4:5 PNG + 9:16 motion-graphics reel MP4
(no music; synthesized sound effects synced to the text). Rhythm: the big headline is TYPED letter by letter with a
soft keyboard sound per keystroke: the first three words type fast (slower than a burst) from ~0.1s, the rest of the headline types
calmly (short pauses at spaces and punctuation); then a pause; then the subtitle, then the chart
rows enter one by one and grow/count with a natural cadence; then footer + note. Last real motion lands ~15s on
average (row spacing is solved from the row count); video length = last motion + 1s hold.
+ <key>_cover.png: the reel frame at cover_ms = the moment the big headline is complete and NOTHING below it has
appeared yet (no subtitle/chart/note/footer): a teaser cover that makes people open the reel.

Usage:  python3 mrqab_post.py spec.json OUT_DIR [--brand BRAND_DIR]

spec = {
  "key": "daily_2026-11-26_activities",
  "kicker": "نبض السوق",
  "title": "رصدنا <em>36 متجــر</em> جديد",      # one <em> word (mint + kashida)
  "sub": "الأنشطة الأكثر رصد في 26 نوفمبر",    # optional
  "body": {"type": "hbars", "rows": [["الأزياء والعبايات", 7], ...], "suffix": "", "highlight": [0]}
        | {"type": "vbars", "rows": [["سبتمبر", 120], ...], "highlight": [2]}
        | {"type": "bignum", "value": 36, "prefix": "", "suffix": "", "label": "...", "note": "..."}
        | {"type": "cards", "items": [["1,420", "متجر منذ أكتوبر"], ...]},
  "note": "سطر تفسير يظهر بمؤثر كتابي",            # optional
  "source": "رصد مرقاب لـ36 متجر جديد · 26 نوفمبر 2026",
  "duration": 16          # optional; default = last motion + 1s
}
Numbers inside Arabic text must be wrapped as <span class="num">42.5%</span>.
Latin words / domain extensions inside Arabic text too, or the dot jumps: <span class="num">.com</span>, <span class="num">.sa</span>.
Owner rule: numbers sit on the RIGHT (RTL) — the bignum value is right-aligned by the tool; never override alignment.
"highlight" is a list of row indexes (e.g. [1]); do not set "duration" in daily specs (computed).
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
.hrow .lab{width:330px;font-weight:700;font-size:32px;line-height:1.75;padding:2px 0 8px;margin:-2px 0 -8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hrow .trk{flex:1;height:34px;background:#1C1030;border-radius:17px;overflow:hidden;display:flex}
.hrow .fil{height:100%;background:#7B45DA;border-radius:17px}
.hrow.hl .fil{background:#5FD3BF}
.hrow .val{width:110px;font-family:'SG';font-weight:700;font-size:38px;text-align:left;direction:ltr}
.hrow.hl .val{color:#5FD3BF}
.vwrap{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;height:620px}
.vcol{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.vcol .v{font-family:'SG';font-weight:700;font-size:34px;margin-bottom:12px}
.vcol .bar{width:100%;background:#3A2366;border-radius:14px 14px 0 0}
.vcol.hl .bar{background:#5FD3BF}.vcol.hl .v{color:#5FD3BF}
.vcol .l{margin-top:14px;font-weight:500;font-size:26px;color:#9A8FB5;white-space:nowrap}
.big{font-family:'SG';font-weight:700;font-size:300px;line-height:1;color:#5FD3BF;direction:ltr;text-align:right}
.bigl{font-weight:700;font-size:40px;margin-top:20px;line-height:1.4}
.bign{font-weight:500;font-size:30px;color:#9A8FB5;margin-top:12px}
.cards{display:flex;flex-direction:column;gap:22px}
.card{background:#150A24;border:2px solid #2A1B45;border-radius:24px;padding:30px 40px;display:flex;align-items:center;gap:30px}
.card .cn{font-family:'SG';font-weight:700;font-size:56px;color:#F2EEFF;direction:ltr;min-width:240px;text-align:right}
.card:first-child .cn{color:#5FD3BF}
.card .cd{font-weight:500;font-size:27px;color:#9A8FB5;line-height:1.5}
"""

JS = r"""
const cl=x=>Math.min(Math.max(x,0),1);
const eOut=x=>1-Math.pow(1-cl(x),3);
const eSoft=x=>{x=cl(x);return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;};
const seg=(t,a,b)=>eOut((t-a)/(b-a));
const sseg=(t,a,b)=>eSoft((t-a)/(b-a));
const fmt=(v,d)=>Number(v).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
function set(el,o,y,s){if(!el)return;el.style.opacity=o;el.style.transform=`translateY(${y}px) scale(${s??1})`;}
window.render=function(t){
  const D=window.DUR, L=window.TL, fin=t>=D;
  const eye=document.querySelector('.eye'); if(eye){eye.style.transform=`scale(${1+0.05*t/D})`; eye.style.opacity=.42*seg(t,0,.6);}
  const g=document.querySelector('.glow'); if(g) g.style.opacity=.75+.25*Math.sin(t*1.3);
  let p=seg(t,L.top[0],L.top[1]); set(document.querySelector('.top'),p,(1-p)*-24);
  p=seg(t,L.kick[0],L.kick[1]); set(document.querySelector('.kicker'),p,0,.85+.15*p);
  const dot=document.querySelector('.kicker i'); dot.style.opacity=.45+.55*Math.abs(Math.cos(t*2.4));
  document.querySelectorAll('h1 .c').forEach((c,i)=>{const q=cl((t-L.cAt[i])/L.cFade);
    c.style.color=c.dataset.m?`rgba(95,211,191,${q})`:`rgba(242,238,255,${q})`;});
  const em=document.querySelector('h1 em'); if(em){const st=L.tEnd, q=seg(t,st,st+.4);
    const pulse=t>st? .5+.5*Math.sin((t-st)*2.0):0;
    em.style.textShadow=`0 0 ${16+24*pulse}px rgba(95,211,191,${(.25+.4*pulse)*q})`;}
  p=seg(t,L.sub[0],L.sub[1]); set(document.querySelector('.sub'),p,(1-p)*16);
  const at=i=>L.rowAt[Math.min(i,L.rowAt.length-1)];
  document.querySelectorAll('[data-in]').forEach(el=>{const a=at(+el.dataset.i||0), q=seg(t,a,a+L.rin); set(el,q,(1-q)*22);});
  document.querySelectorAll('[data-count]').forEach(el=>{const a=at(+el.dataset.i||0)+L.rin*.6, v=+el.dataset.count, d=+el.dataset.dec||0;
    const q=sseg(t,a,a+L.cnt); el.textContent=(el.dataset.pre||'')+fmt(v*q,d)+(el.dataset.suf||'');});
  document.querySelectorAll('[data-grow]').forEach(el=>{const a=at(+el.dataset.i||0)+L.rin*.6, q=sseg(t,a,a+L.cnt);
    el.style[el.dataset.axis||'width']=(+el.dataset.grow*q)+'%';});
  const lead=document.querySelector('.hrow.hl .fil, .vcol.hl .bar, .big, .card:first-child');
  if(lead && t>L.glow){const s=.5+.5*Math.sin((t-L.glow)*2.0); lead.style.filter=`drop-shadow(0 0 ${8+14*s}px rgba(95,211,191,.45))`;}
  const note=document.querySelector('.note'); if(note){const c=cl((t-L.note[0])/(L.note[1]-L.note[0]));
    note.style.clipPath=`inset(0 0 0 ${100-100*c}%)`; note.style.opacity=c>0?1:0;}
  p=seg(t,L.foot[0],L.foot[1]); set(document.querySelector('.foot'),p,(1-p)*14);
  const tag=document.querySelector('.tag b'); if(tag) tag.style.textShadow=`0 0 ${10+10*Math.abs(Math.sin(t*1.7))}px rgba(95,211,191,.5)`;
  if(fin){document.querySelectorAll('*').forEach(e=>{e.style.filter='';});
    document.querySelectorAll('h1 em,.tag b').forEach(e=>e.style.textShadow='');
    document.querySelectorAll('h1 .c').forEach(c=>c.style.color='');}
};
"""

PUNCT = set("؟?!،,.:؛")
def title_tokens(t):
    """Words of the headline; <em>..</em> and <span class="num">..</span> stay whole; a lone punctuation mark sticks to the word before it."""
    import re
    out = []
    for x in re.findall(r'<em>.*?</em>|<span class="num">.*?</span>|[^\s<]+', t):
        if out and x and all(c in PUNCT for c in x): out[-1] += x
        else: out.append(x)
    return out

def title_chars(t):
    """Per token: list of typed characters (combining marks stay with their base letter)."""
    import re, unicodedata
    out = []
    for tok in title_tokens(t):
        txt = re.sub(r"<[^>]+>", "", tok); cs = []
        for ch in txt:
            if cs and unicodedata.combining(ch): cs[-1] += ch
            else: cs.append(ch)
        out.append(cs)
    return out

def type_schedule(t, start=.1, fast=.05, calm=.072, nfast=3, seed=11):
    """Keystroke times for the headline: [(time, kind)] kind in {'key','space'}; chars -> list of times per typed char."""
    import random
    rnd = random.Random(seed); ev = []; ct = []; x = start
    words = title_chars(t)
    for w, cs in enumerate(words):
        for ch in cs:
            ct.append(round(x, 3)); ev.append((round(x, 3), "key"))
            dt = fast if w < nfast else calm
            x += dt * rnd.uniform(.82, 1.18)
            if w >= nfast and ch in PUNCT: x += .12
        if w < len(words) - 1:
            ev.append((round(x, 3), "space"))
            x += (fast * 1.2) if w < nfast - 1 else (.13 if w == nfast - 1 else .1)
    return ct, ev

def timeline(spec):
    """Shared timing for animation (JS) and typing sound (audio).
    Headline: first word pops in fast, the rest types in calmly; a pause (the cover lives in it); subtitle; chart rows
    one by one with a natural cadence; footer + note. Row spacing is solved so the last motion lands near TARGET."""
    import re
    TARGET = 15.0
    nw = len(title_tokens(spec["title"]))
    b = spec["body"]; ty = b["type"]
    if ty == "bignum": n = 1 + bool(b.get("label")) + bool(b.get("note"))
    else: n = len(b.get("rows", b.get("items", [1])))
    L = {"top": [0.0, .25], "kick": [0.0, .25], "cFade": .05}
    L["cAt"], L["keys"] = type_schedule(spec["title"])
    nf = sum(len(c) for c in title_chars(spec["title"])[:3])
    L["fastEnd"] = round(L["cAt"][min(nf, len(L["cAt"])) - 1], 3)               # last key of the first three words
    L["tEnd"] = round(L["cAt"][-1] + L["cFade"] + .02, 3)                       # headline fully typed
    L["cover"] = round(L["tEnd"] + .3, 3)                                       # teaser cover: headline only
    gap = .9
    hasSub, hasNote = bool(spec.get("sub")), bool(spec.get("note"))
    L["sub"] = [L["tEnd"] + gap, L["tEnd"] + gap + .6]
    b0 = (L["sub"][1] + .35) if hasSub else (L["tEnd"] + gap)
    L["rin"] = .4                                                                # row entrance
    L["cnt"] = {"bignum": 2.8, "cards": .5, "vbars": 1.2}.get(ty, 1.3)          # growth / count duration
    noteDur = 1.8 if hasNote else 0
    tail = (.4 + noteDur) if hasNote else .8                                     # after rowsEnd
    budget = TARGET - tail - b0 - L["cnt"] - L["rin"] * .6
    lo, hi = {"vbars": (.7, 1.8), "cards": (1.0, 2.4), "bignum": (1.0, 2.6)}.get(ty, (.9, 2.2))
    if ty == "bignum":   # the count first, then label, then the small note line
        stag = min(hi, max(lo, (TARGET - tail - b0 - L["rin"] - L["cnt"] - .3 - L["rin"]) / max(1, n - 1))) if n > 1 else 0
        L["rowAt"] = [round(b0, 3)] + [round(b0 + L["rin"] + L["cnt"] + .3 + k * stag, 3) for k in range(n - 1)]
        L["rowsEnd"] = round(max(b0 + L["rin"] * .6 + L["cnt"], L["rowAt"][-1] + L["rin"]), 3)
    else:
        stag = min(hi, max(lo, budget / (n - 1))) if n > 1 else 0
        L["rowAt"] = [round(b0 + i * stag, 3) for i in range(n)]
        L["rowsEnd"] = round(L["rowAt"][-1] + L["rin"] * .6 + L["cnt"], 3)
    L["b0"] = round(b0, 3); L["stag"] = round(stag, 3); L["n"] = n; L["nw"] = nw; L["type"] = ty
    L["foot"] = [round(L["rowsEnd"] + .2, 3), round(L["rowsEnd"] + .8, 3)]
    L["note"] = [round(L["rowsEnd"] + .4, 3), round(L["rowsEnd"] + .4 + noteDur, 3)] if hasNote else [0, 0]
    L["glow"] = L["rowsEnd"]
    L["hasSub"] = hasSub; L["hasNote"] = hasNote
    L["last"] = round(max(L["foot"][1], L["note"][1]), 3)
    L["vals"] = [r[1] for r in b.get("rows", [])] if ty in ("hbars", "vbars") else ([b["value"]] if ty == "bignum" else [])
    return L

def duration(spec, L=None):
    L = L or timeline(spec)
    return float(spec.get("duration") or round(L["last"] + 1.0, 2))

def cover_time(L, D):
    """Teaser cover: the big headline is complete and still; nothing below it (subtitle/chart/note/footer) is visible yet."""
    return round(min(L["cover"], D - 0.5), 2)

def typing_audio(L, D, path, sr=44100, seed=7):
    """Typewriter / keyboard sound effect synced to the text animation (no music)."""
    import numpy as np, wave
    rng = np.random.default_rng(seed); N = int(D * sr); out = np.zeros(N)
    title_chars_cache = [0] * L["nw"]
    def click(t, amp=1.0, bright=1.0):
        i = int(t * sr)
        if i >= N: return
        ln = int(.045 * sr); tt = np.arange(ln) / sr
        nz = rng.standard_normal(ln); nz = np.diff(nz, prepend=0) * bright + nz * (1 - bright) * .4
        env = np.exp(-tt / .006); body = np.sin(2 * np.pi * rng.uniform(140, 220) * tt) * np.exp(-tt / .012) * .5
        tick = np.sin(2 * np.pi * rng.uniform(2600, 3600) * tt) * np.exp(-tt / .003) * .35
        x = (nz * env * .55 + body + tick) * amp * rng.uniform(.7, 1.0)
        e = min(N, i + ln); out[i:e] += x[:e - i]
    def burst(a, b, rate, amp=1.0, bright=1.0):
        t = a
        while t < b:
            click(t, amp, bright); t += max(.025, rng.normal(1 / rate, .25 / rate))
    def bell(t):
        i = int(t * sr); ln = int(.9 * sr); tt = np.arange(ln) / sr
        x = (np.sin(2 * np.pi * 2093 * tt) + .4 * np.sin(2 * np.pi * 4186 * tt)) * np.exp(-tt / .25) * .22
        e = min(N, i + ln); out[i:e] += x[:e - i]
    # reference level: the previous mix's headline sounds (only used so the lower elements keep their old loudness)
    ref = out.copy(); out_below_start = out
    def headline_old(buf):
        nonlocal out
        keep = out; out = buf
        burst(L["kick"][0], L["kick"][1], 22, .6)
        t0 = .1
        for k in range(len(title_chars_cache)):
            a = t0 + (0 if k == 0 else .45 + (k - 1) * .4)
            if k == 0: burst(a, a + .18, 34, 1.0)
            else: burst(a, a + .22, 20, .85); click(a + .3, .5, .4)
        click(L["tEnd"] - .02, 1.2, .3); bell(L["tEnd"] + .02)
        out = keep
    if L["hasSub"]: burst(L["sub"][0], L["sub"][1] - .05, 20, .55)
    for k in range(L["n"]):
        a = L["rowAt"][k]; burst(a, a + .16, 22, .65)                    # a row arrives
        counted = (L["type"] in ("hbars", "vbars") and k < len(L["vals"])) or (L["type"] == "bignum" and k == 0)
        if counted:
            v = L["vals"][k]; steps = min(14, max(4, int(abs(v)))); c0 = a + L["rin"] * .6
            for j in range(steps):                                    # ticks follow the eased count
                x = (j + 1) / steps
                f = (x / 4) ** (1 / 3) if x < .5 else 1 - ((2 - 2 * x) ** (1 / 3)) / 2   # inverse ease-in-out-cubic
                click(c0 + L["cnt"] * f * .98, .3, 1.0)
    burst(L["foot"][0], L["foot"][1], 16, .4)
    if L["hasNote"]: burst(L["note"][0], L["note"][1], 14, .6)
    ref = out.copy(); headline_old(ref)
    pk = np.max(np.abs(ref)) or 1; out = out / pk * .85                 # lower elements: same level as before
    # soft, slightly muted keyboard for the big headline: press + short release, varied per key; space bar heavier
    kb = np.zeros(N); krng = np.random.default_rng(seed + 101)
    def lp(x, a):                                                       # one-pole low-pass (muting)
        y = np.empty_like(x); s = 0.0
        for i, v in enumerate(x): s += a * (v - s); y[i] = s
        return y
    def key(t, amp, space=False):
        i = int(t * sr)
        if i >= N: return
        ln = int(.09 * sr); tt = np.arange(ln) / sr
        nz = krng.standard_normal(ln)
        hi = lp(nz, krng.uniform(.28, .38) if not space else .16)       # muted click
        press = hi * np.exp(-tt / (.0035 if not space else .006))
        f0 = krng.uniform(260, 380) if not space else krng.uniform(120, 170)
        thock = np.sin(2 * np.pi * f0 * tt) * np.exp(-tt / (.010 if not space else .022)) * (.55 if not space else .9)
        rel_d = int(krng.uniform(.045, .07) * sr)                       # key release, quieter
        rel = np.zeros(ln); r = lp(krng.standard_normal(ln - rel_d), .4) * np.exp(-tt[:ln - rel_d] / .0025) * .35
        rel[rel_d:] = r
        x = (press + thock + rel) * amp * krng.uniform(.78, 1.0)
        e = min(N, i + ln); kb[i:e] += x[:e - i]
    for (t0, kind) in L["keys"]:
        key(t0, 1.0, kind == "space")
    kpk = np.max(np.abs(kb)) or 1; kb = kb / kpk * .40                  # quieter than the old headline sounds
    out = out + kb
    tot = np.max(np.abs(out))
    if tot > .5: out = out / tot * .5                                   # overall peak <= -6 dB
    fade = int(.3 * sr); out[-fade:] *= np.linspace(1, 0, fade)
    pcm = np.int16(np.stack([out, out], 1) * 32767)
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def title_html(t):
    """Every typed character in its own inline span (shaping/joining is kept across inline spans of the same font);
    untyped characters are transparent, so the layout never moves while typing."""
    import re, unicodedata
    words = []
    for tok in title_tokens(t):
        parts = re.split(r"(<[^>]+>)", tok); html = []; in_em = False
        for pt in parts:
            if not pt: continue
            if pt.startswith("<"):
                if pt.startswith("<em"): in_em = True
                elif pt.startswith("</em"): in_em = False
                html.append(pt); continue
            for ch in pt:
                if html and unicodedata.combining(ch) and html[-1].endswith("</span>") and 'class="c"' in html[-1]:
                    html[-1] = html[-1][:-7] + ch + "</span>"
                else:
                    html.append(f'<span class="c"{" data-m=1" if in_em else ""}>{H.escape(ch)}</span>')
        words.append('<span class="w">' + "".join(html) + "</span>")
    return " ".join(words)

def body_html(b):
    t = b["type"]
    if t == "hbars":
        mx = max(v for _, v in b["rows"]); suf = b.get("suffix", "")
        hl = set(b.get("highlight", [0]))
        rows = []
        for i, (lab, v) in enumerate(b["rows"]):
            dec = 1 if isinstance(v, float) and v != int(v) else 0
            rows.append(f'<div class="hrow{" hl" if i in hl else ""}" data-in data-i="{i}"><div class="lab">{H.escape(lab)}</div>'
                        f'<div class="trk"><div class="fil" data-grow="{100*v/mx:.2f}" data-i="{i}"></div></div>'
                        f'<div class="val" data-count="{v}" data-dec="{dec}" data-suf="{suf}" data-i="{i}">0</div></div>')
        return "".join(rows)
    if t == "vbars":
        mx = max(v for _, v in b["rows"]); hl = set(b.get("highlight", []))
        if not hl: hl = {max(range(len(b["rows"])), key=lambda i: b["rows"][i][1])}
        cols = [f'<div class="vcol{" hl" if i in hl else ""}" data-in data-i="{i}"><div class="v" data-count="{v}" data-i="{i}">0</div>'
                f'<div class="bar" data-axis="height" data-grow="{85*v/mx:.2f}" data-i="{i}"></div><div class="l">{H.escape(l)}</div></div>'
                for i, (l, v) in enumerate(b["rows"])]
        return f'<div class="vwrap">{"".join(cols)}</div>'
    if t == "bignum":
        dec = b.get("dec", 0); k = 1
        out = (f'<div class="big" data-in data-i="0" data-count="{b["value"]}" data-dec="{dec}" '
               f'data-pre="{b.get("prefix","")}" data-suf="{b.get("suffix","")}">0</div>')
        if b.get("label"): out += f'<div class="bigl" data-in data-i="{k}">{b["label"]}</div>'; k += 1
        if b.get("note"): out += f'<div class="bign" data-in data-i="{k}">{b["note"]}</div>'
        return out
    if t == "cards":
        return '<div class="cards">' + "".join(
            f'<div class="card" data-in data-i="{i}"><div class="cn">{H.escape(n)}</div><div class="cd">{d}</div></div>'
            for i, (n, d) in enumerate(b["items"])) + '</div>'
    raise ValueError(t)

def page(spec, ratio, brand):
    h = 1350 if ratio == "45" else 1920
    pad = "84px 90px 70px" if ratio == "45" else "310px 150px 430px 80px"
    css = CSS.replace("B/", brand + "/").replace("HPX", f"{h}px").replace("PAD", pad).replace("H1PX", "78px" if ratio == "45" else "82px")
    deco = '<div class="glow"></div><div class="eye"></div>' if ratio == "916" else ""
    sub = f'<p class="sub">{spec["sub"]}</p>' if spec.get("sub") else ""
    note = f'<p class="note">{spec["note"]}</p>' if spec.get("note") else ""
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{css}</style></head><body>{deco}
<div class="post"><div class="top"><div class="brand"><img src="{brand}/eye.png"><span>مرقاب</span></div><div class="handle">@mrqabco</div></div>
<div class="kicker"><i></i>{spec["kicker"]}</div><h1>{title_html(spec["title"])}</h1>{sub}
<div class="body">{body_html(spec["body"])}{note}</div>
<div class="foot"><div class="src">{spec["source"]}</div><div class="tag">monitor data, turn into <b>insight</b></div></div></div>
<script>window.DUR={duration(spec)};window.TL={json.dumps(timeline(spec))};{JS}</script></body></html>"""

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("spec"); ap.add_argument("out"); ap.add_argument("--brand", default=BASE_URL)
    ap.add_argument("--fps", type=int, default=30); a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8")); os.makedirs(a.out, exist_ok=True)
    brand = a.brand if a.brand.startswith("http") else "file://" + os.path.abspath(a.brand)
    key = spec["key"]; TL = timeline(spec); D = duration(spec, TL)
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
                ct = cover_time(TL, D)
                pg.evaluate(f"render({ct})"); pg.screenshot(path=os.path.join(a.out, f"{key}_cover.png"))
                fr = os.path.join(tmp, "fr"); os.makedirs(fr)
                n = int(D * a.fps)
                for i in range(n):
                    pg.evaluate(f"render({i / a.fps})"); pg.screenshot(path=os.path.join(fr, f"{i:04d}.png"))
            pg.close()
        br.close()
    out = os.path.join(a.out, f"{key}_reel.mp4")
    wav = os.path.join(tmp, "typing.wav"); typing_audio(TL, D, wav)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(a.fps), "-i", os.path.join(tmp, "fr", "%04d.png"),
                    "-i", wav, "-map", "0:v", "-map", "1:a", "-t", str(D),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                    "-shortest", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(tmp)
    ct = cover_time(TL, D)
    print(json.dumps({"key": key, "layout": res, "cover_ms": int(round(ct * 1000)), "duration": D, "last_motion": TL["last"],
                      "files": [f"{key}.png", f"{key}_916.png", f"{key}_reel.mp4", f"{key}_cover.png"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
