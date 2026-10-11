#!/usr/bin/env python3
"""Render docs/overview.<lang>.png from HTML with headless Chrome. usage: python3 docs/build_infographic.py"""
import pathlib, shutil, subprocess, sys

D = pathlib.Path(__file__).resolve().parent
CHROME = next((p for p in [shutil.which("google-chrome"), shutil.which("chromium"),
                           "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] if p and pathlib.Path(p).exists()), None)

T = {
 "en": dict(
  title="Three ways to use the ChatGPT web quota", sub="Measured: heavy web chat did not move Codex usage (5h window 0% → 0%, 1% resolution)",
  a=("1 · Writer", "ChatGPT → your repo", ["Web ChatGPT (phone / desktop)", "OpenAI Secure Tunnel", "stdio MCP writer · 9 tools", "chatgpt/* branch → PR"],
     "No shell. Writes only on chatgpt/*."),
  b=("2 · Handoff", "ChatGPT → your local agent", ["“pass this to my agent”", "handoff tool → queue + notify", "you send: approve #id", "local agent runs it"],
     "Nothing runs without your approval."),
  c=("3 · webgpt page", "you → web ChatGPT", ["local page: Ask · Code · Skills", "Aside repl (scripted, no LLM)", "temporary chat", "answer / solution.py tested here"],
     "Unofficial UI automation — your risk."),
  m=[("0 tokens", "of your API / CLI quota for paths 1 and 3"), ("219–327 s", "heavy answers received in full"),
     ("29 s", "pandas coding job, passed 1st round"), ("4 / 4", "guards caught by negative controls")]),
 "ko": dict(
  title="ChatGPT 웹 사용량을 쓰는 세 가지 길", sub="실측: 무거운 웹 채팅을 해도 Codex 사용률은 그대로 (5시간 창 0% → 0%, 1% 단위)",
  a=("1 · Writer", "ChatGPT → 내 레포", ["웹 ChatGPT (폰 / PC)", "OpenAI Secure Tunnel", "stdio MCP writer · 도구 9개", "chatgpt/* 브랜치 → PR"],
     "셸 없음. chatgpt/* 에만 씀."),
  b=("2 · Handoff", "ChatGPT → 내 로컬 에이전트", ["“내 에이전트한테 넘겨줘”", "handoff 도구 → 큐 + 알림", "내가 보냄: approve #번호", "로컬 에이전트가 실행"],
     "승인 없이는 아무것도 실행 안 됨."),
  c=("3 · webgpt 페이지", "나 → 웹 ChatGPT", ["로컬 페이지: Ask · Code · Skills", "Aside repl (스크립트, LLM 없음)", "임시 채팅", "답 / solution.py 내 컴퓨터에서 테스트"],
     "비공식 화면 자동조작 — 본인 책임."),
  m=[("토큰 0", "1·3번 길은 API·CLI 한도를 안 씀"), ("219–327초", "긴 답도 끝까지 받음"),
     ("29초", "pandas 코딩, 첫 회차 통과"), ("4 / 4", "고장 주입 시험을 모두 잡음")]),
}
COL = {"a": "#2563eb", "b": "#059669", "c": "#d97706"}


def card(k, v):
    head, sub, steps, note = v
    s = "".join(f"<div class=step>{x}</div>" + ("<div class=arr>↓</div>" if i < len(steps) - 1 else "") for i, x in enumerate(steps))
    return f"<div class=card style='--c:{COL[k]}'><div class=h>{head}</div><div class=s>{sub}</div>{s}<div class=note>{note}</div></div>"


def html(t):
    m = "".join(f"<div class=m><b>{a}</b><span>{b}</span></div>" for a, b in t["m"])
    return f"""<!doctype html><meta charset=utf-8><style>
*{{box-sizing:border-box}}body{{margin:0;width:1200px;font-family:Pretendard,'Apple SD Gothic Neo','Noto Sans KR',system-ui,sans-serif;background:#fafaf9;color:#1c1917}}
.wrap{{padding:44px 48px}}h1{{margin:0;font-size:34px}}.sub{{color:#57534e;margin:8px 0 28px;font-size:18px}}
.row{{display:flex;gap:22px}}.card{{flex:1;background:#fff;border:2px solid var(--c);border-radius:14px;padding:20px}}
.h{{font-size:22px;font-weight:800;color:var(--c)}}.s{{font-size:15px;color:#57534e;margin:4px 0 14px}}
.step{{background:#f5f5f4;border-radius:8px;padding:10px 12px;font-size:15px;text-align:center}}.arr{{text-align:center;color:var(--c);font-size:18px;line-height:22px}}
.note{{margin-top:14px;font-size:14px;font-weight:700;color:var(--c)}}
.ms{{display:flex;gap:16px;margin-top:26px}}.m{{flex:1;background:#1c1917;color:#fff;border-radius:12px;padding:16px}}
.m b{{display:block;font-size:26px}}.m span{{font-size:14px;color:#d6d3d1}}</style>
<div class=wrap><h1>{t['title']}</h1><div class=sub>{t['sub']}</div>
<div class=row>{card('a', t['a'])}{card('b', t['b'])}{card('c', t['c'])}</div><div class=ms>{m}</div></div>"""


if __name__ == "__main__":
    if not CHROME:
        sys.exit("Chrome not found")
    for lang, t in T.items():
        h = D / f"overview.{lang}.html"
        h.write_text(html(t))
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        "--window-size=1200,640", f"--screenshot={D / f'overview.{lang}.png'}", h.as_uri()],
                       check=True, capture_output=True, timeout=60)
        print("wrote", D / f"overview.{lang}.png")
