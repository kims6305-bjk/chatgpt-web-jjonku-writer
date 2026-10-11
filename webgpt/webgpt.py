#!/usr/bin/env python3
"""webgpt: ask web ChatGPT through the Aside browser (`aside repl`, no LLM of Aside involved).

  python3 webgpt.py ask "question"          # answer on stdout
  python3 webgpt.py code SPEC.txt TEST.py   # web GPT writes solution.py, it runs here until TEST passes
  python3 webgpt.py skills init             # questionnaire: which of YOUR skills may be sent to the web
  python3 webgpt.py skills list
  python3 webgpt.py selftest                # live: "1+1" round trip
  python3 app.py                            # local web page (see README)

Config: webgpt.config.json next to this file (or $WEBGPT_CONFIG). Everything else is stdlib.
"""
import fcntl, json, os, re, shlex, subprocess, sys, time, pathlib

HERE = pathlib.Path(__file__).resolve().parent
CFG_PATH = pathlib.Path(os.environ.get("WEBGPT_CONFIG", HERE / "webgpt.config.json"))
DEFAULTS = {
    "aside": "aside",                    # Aside CLI path
    "account": None,                     # Aside account id (e.g. "u0"); None = Aside default
    "url": "https://chatgpt.com/?temporary-chat=true",
    "effort": None,                      # e.g. "Extra High"; None = leave the picker alone
    "model_button_label": None,          # aria-label of the model picker in YOUR UI language (needed for effort)
    "data_dir": "~/.local/share/webgpt",
    "timeout_s": 900,
    "notify": None,                      # optional command; message on stdin
    "skill_dirs": [],                    # folders containing <name>/SKILL.md
    "block_words": [],                   # your private words: name, company, hostnames...
    "python": sys.executable,            # interpreter for code mode (use a venv)
    "libs": "",                          # what that venv has, told to the model
}


def cfg() -> dict:
    c = dict(DEFAULTS)
    if CFG_PATH.exists():
        c.update(json.loads(CFG_PATH.read_text()))
    return c


def data_dir() -> pathlib.Path:
    d = pathlib.Path(os.path.expanduser(cfg()["data_dir"]))
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(name: str, rec: dict):
    with (data_dir() / name).open("a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- browser (aside repl = scripted, no LLM)
FIND_TAB = "console.log('__WJ__'+JSON.stringify((await listBrowserTabs()).filter(t=>t.url.startsWith('https://chatgpt.com')).map(t=>t.targetId)))"

SEND = r"""
const P = __PROMPT__, EFFORT = __EFFORT__, LABEL = __LABEL__;
const pg = await attachBrowserTab(__TAB__);
await pg.goto(__URL__);
const ed = () => pg.evaluate(()=>!!document.querySelector('.ProseMirror[contenteditable=true][role=textbox]'));
for (let i=0;i<20 && !(await ed());i++) await sleep(500);
let eff = null;
if (EFFORT && LABEL) {
  const trig = () => pg.evaluate((L)=>[...document.querySelectorAll('button')].find(e=>e.getAttribute('aria-label')===L)?.innerText.trim()||null, LABEL);
  eff = await trig();
  if (eff !== EFFORT) {
    await pg.evaluate((L)=>[...document.querySelectorAll('button')].find(e=>e.getAttribute('aria-label')===L)?.click(), LABEL);
    await sleep(1000);
    await pg.evaluate(()=>document.querySelector('[data-reasoning-slider]')?.focus());
    const order = ['Instant','Medium','High','Extra High'];
    const cur = (await pg.evaluate(()=>[...document.querySelectorAll('[role=status]')].map(e=>e.innerText).join('|'))).match(/(Instant|Medium|Extra High|High),/);
    const steps = order.indexOf(EFFORT) - (cur ? order.indexOf(cur[1]) : 0);
    for (let i=0;i<Math.abs(steps);i++){ await pg.keyboard.press(steps>0?'ArrowRight':'ArrowLeft'); await sleep(400); }
    await pg.keyboard.press('Escape'); await sleep(400);
    eff = await trig();
  }
}
if (EFFORT && LABEL && eff !== EFFORT) { console.log('__WJ__'+JSON.stringify({ok:false, err:'effort_not_set', eff})); }
else {
  await pg.evaluate(()=>{
    window.__wj = {t0:null, first:null, done:null, id:'__NONCE__'};
    window.__wjRead = ()=>{ const h=[...document.querySelectorAll('h4[data-conversation-role=assistant]')].pop(); if(!h) return {tx:'',state:null};
      const turn=h.closest('[data-talvt-turn-state]'); let tx=h.parentElement.innerText;
      for (const cb of h.parentElement.querySelectorAll('[data-markdown-copy="code-block"]')) {
        const cm=cb.querySelector('.cm-content'); if(!cm) continue;
        const code=[...cm.querySelectorAll('.cm-line')].map(l=>l.textContent).join('\n');
        tx=tx.replace(cb.innerText, '```'+(cm.getAttribute('data-language')||'')+'\n'+code+'\n```');
      }
      return {tx:tx.replace(h.innerText,'').trim(), state: turn?turn.getAttribute('data-talvt-turn-state'):null}; };
    new MutationObserver(()=>{ const w=window.__wj; if(w.t0===null||w.done) return; const r=window.__wjRead(); const now=Date.now()-w.t0;
      if(r.tx && w.first===null) w.first=now; if(r.tx && r.state==='complete') w.done=now; }).observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true});
  });
  // paste event: fill() breaks on multi-line contenteditable
  const pasted = await pg.evaluate((P)=>{ const ed=document.querySelector('.ProseMirror[contenteditable=true][role=textbox]'); if(!ed) return -1; ed.focus();
    const dt=new DataTransfer(); dt.setData('text/plain', P);
    ed.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));
    return ed.innerText.replace(/\s/g,'').length; }, P);
  if (pasted < P.replace(/\s/g,'').length * 0.95) { console.log('__WJ__'+JSON.stringify({ok:false, err:'paste_failed '+pasted, eff})); }
  else {
    await sleep(300);
    await pg.evaluate(()=>{window.__wj.t0=Date.now();});
    await pg.keyboard.press('Enter');
    console.log('__WJ__'+JSON.stringify({ok:true, eff}));
  }
}
"""

POLL = r"""
const pg = await attachBrowserTab(__TAB__);
const t = Date.now(); let w = {};
while (Date.now()-t < 60000) { w = await pg.evaluate(()=>window.__wj||null); if (!w || w.done!==null) break; await sleep(1000); }
let out = {w};
if (w && w.done!==null) {  // text keeps animating after "complete": wait until stable 1.5s (max 10s)
  let r = await pg.evaluate(()=>window.__wjRead());
  for (let i=0, same=0; i<20 && same<3; i++){ await sleep(500); const n = await pg.evaluate(()=>window.__wjRead()); same = n.tx===r.tx ? same+1 : 0; r = n; }
  out.r = r;
}
console.log('__WJ__'+JSON.stringify(out));
"""

SENT_CHECK = "const pg = await attachBrowserTab(__TAB__); console.log('__WJ__'+JSON.stringify(await pg.evaluate(()=>!!(window.__wj&&window.__wj.id==='__NONCE__'&&window.__wj.t0))))"
FLAKY = (RuntimeError, subprocess.TimeoutExpired)  # aside daemon hiccups / ~120s per-call cut


def repl(code: str, timeout: int = 110):
    c = cfg()
    acct = ["--account", c["account"]] if c["account"] else []
    p = subprocess.run([c["aside"], "repl", *acct, code], capture_output=True, text=True, timeout=timeout)
    line = next((l for l in p.stdout.splitlines() if l.startswith("__WJ__")), None)
    if line is None:
        raise RuntimeError("aside: " + (p.stdout + p.stderr)[-500:])
    return json.loads(line[6:])


def _ask(prompt: str) -> dict:
    c = cfg()
    tabs = repl(FIND_TAB, 60)
    if not tabs:
        raise RuntimeError("no chatgpt.com tab: open one in Aside and log in")
    tab, nonce = json.dumps(tabs[0]), str(time.time_ns())  # nonce: never mistake a previous answer for this one
    send = (SEND.replace("__NONCE__", nonce).replace("__PROMPT__", json.dumps(prompt)).replace("__TAB__", tab)
            .replace("__URL__", json.dumps(c["url"])).replace("__EFFORT__", json.dumps(c["effort"]))
            .replace("__LABEL__", json.dumps(c["model_button_label"])))
    try:
        sent = repl(send)
    except FLAKY:  # already pressed Enter? then don't resend (no duplicate question)
        sent = {"ok": True, "eff": None} if repl(SENT_CHECK.replace("__TAB__", tab).replace("__NONCE__", nonce)) else repl(send)
    if not sent.get("ok"):
        return sent
    t0, errs = time.time(), 0
    while time.time() - t0 < c["timeout_s"]:
        try:
            o = repl(POLL.replace("__TAB__", tab))
        except FLAKY:  # polling only reads, so just retry
            errs += 1
            if errs > 3:
                raise
            time.sleep(3)
            continue
        w = o.get("w")
        if not w or w.get("id") != nonce:
            return {**sent, "ok": False, "err": "page_reset"}
        if w.get("done") is not None:
            return {"ok": True, "eff": sent.get("eff"), "first_ms": w["first"], "done_ms": w["done"], "answer": o["r"]["tx"]}
    return {**sent, "ok": False, "err": "timeout"}


# ---------------------------------------------------------------- skills (yours, filtered before they leave)
BASE_LEAK = [r"/Users/[^/\s]+", r"/home/[^/\s]+", r"[\w.+-]+@[\w-]+\.[\w.]+", r"sk-[A-Za-z0-9_-]{20,}", r"ghp_[A-Za-z0-9]{20,}",
             r"xox[bp]-[\w-]{10,}", r"\d{8,10}:AA[\w-]{30,}", r"PRIVATE KEY", r"\b(?:10|192\.168|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d+\.\d+"]


def leak_re() -> re.Pattern:
    words = [re.escape(w) for w in cfg()["block_words"] if w.strip()]
    return re.compile("|".join(BASE_LEAK + words), re.I)


def all_skills() -> dict:
    out = {}
    for d in cfg()["skill_dirs"]:
        for p in pathlib.Path(os.path.expanduser(d)).glob("**/SKILL.md"):
            if ".archive" not in p.parts:
                out.setdefault(p.parent.name, p)  # first dir wins on duplicate names
    return out


def allowlist() -> set:
    f = data_dir() / "skill_allowlist.txt"
    return {l.strip() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")} if f.exists() else set()


def scan() -> dict:
    """name -> None if clean, else first leaking match (so the user sees WHY it is held back)."""
    rx = leak_re()
    return {n: (m.group(0) if (m := rx.search(p.read_text(errors="ignore"))) else None) for n, p in sorted(all_skills().items())}


STOP = {"the", "and", "for", "with", "use", "when", "skill", "skills", "this", "that", "from", "your", "into"}


def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]{3,}|[^\W\d_a-z]{2,}", s.lower()) if w not in STOP}


def auto_pick(prompt: str, k: int = 2, need: int = 2) -> list:
    """No #tag given: pick up to k allowed skills whose name (x3) / description words appear in the prompt.
    ponytail: word-overlap heuristic, zero tokens; misses paraphrases -> user writes #skill-name."""
    ql, allow, scored = prompt.lower(), allowlist(), []
    for name, p in all_skills().items():
        if name not in allow:
            continue
        m = re.search(r"^description:\s*(.+)$", p.read_text(errors="ignore")[:3000], re.M)
        s = 3 * sum(t in ql for t in name.split("-") if len(t) >= 3) + sum(w in ql for w in _words(m.group(1) if m else ""))
        if s >= need:
            scored.append((s, name))
    return [n for _, n in sorted(scored, reverse=True)[:k]]


def expand_skills(prompt: str, max_chars: int = 30000) -> tuple[str, list]:
    """'#name' (or auto pick) -> prepend that SKILL.md. Not allowed / leaking -> ValueError, nothing is sent."""
    tags = re.findall(r"#([a-z0-9][a-z0-9_-]+)", prompt)
    if "noskill" in tags:
        return prompt.replace("#noskill", "").strip(), []
    skills, allow, rx = all_skills(), allowlist(), leak_re()
    names = list(dict.fromkeys([t for t in tags if t in skills] or auto_pick(prompt)))
    blocks = []
    for n in names:
        if n not in allow:
            raise ValueError(f"skill #{n} is not in the allowlist (run: webgpt.py skills init)")
        text = skills[n].read_text()
        if rx.search(text):
            raise ValueError(f"skill #{n} contains private-looking text; blocked")
        blocks.append(f"[reference skill: {n}]\n{text[:max_chars]}")
    return ("\n\n".join(blocks) + "\n\n---\n[request]\n" + prompt if blocks else prompt), names


def skills_init(answers=None):
    """Questionnaire. answers (for tests): {"dirs": [...], "words": [...], "mode": "all"|"none"|"pick", "pick": [...]}."""
    a = answers or {}
    c = cfg()
    found = [d for d in ("~/.claude/skills", "~/.codex/skills", "~/.hermes/skills", "~/.agents/skills")
             if pathlib.Path(os.path.expanduser(d)).is_dir()]
    if "dirs" in a:
        dirs = a["dirs"]
    else:
        print("Skill folders found:", ", ".join(found) or "(none)")
        s = input("Folders to use (comma separated, Enter = found ones): ").strip()
        dirs = [x.strip() for x in s.split(",") if x.strip()] or found
    if "words" in a:
        words = a["words"]
    else:
        print("Private words that must never leave this machine (your name, company, client, hostnames).")
        words = [x.strip() for x in input("Comma separated: ").split(",") if x.strip()]
    c.update(skill_dirs=dirs, block_words=sorted(set(c["block_words"]) | set(words)))
    CFG_PATH.write_text(json.dumps({k: v for k, v in c.items() if v != DEFAULTS.get(k) or k in ("skill_dirs", "block_words")},
                                   ensure_ascii=False, indent=2))
    res = scan()
    clean = [n for n, hit in res.items() if hit is None]
    held = {n: hit for n, hit in res.items() if hit}
    print(f"{len(res)} skills scanned: {len(clean)} clean, {len(held)} held back (private-looking text).")
    for n, hit in list(held.items())[:20]:
        print(f"  held: {n}  ({hit[:40]!r})")
    mode = a.get("mode") or input("Allow [a]ll clean / [p]ick / [n]one? ").strip()[:1].lower()
    if mode.startswith("a"):
        allow = clean
    elif mode.startswith("p"):
        pick = a.get("pick") or [x.strip() for x in input("Names (comma separated): ").split(",")]
        allow = [n for n in pick if n in clean]
    else:
        allow = []
    (data_dir() / "skill_allowlist.txt").write_text("# one skill per line; checked again on every send\n" + "\n".join(allow) + "\n")
    print(f"allowlist: {len(allow)} skills -> {data_dir() / 'skill_allowlist.txt'}")
    return allow


# ---------------------------------------------------------------- public API
def ask(prompt: str) -> dict:
    t = time.time()
    try:
        full, used = expand_skills(prompt)
    except ValueError as e:  # blocked skill -> nothing goes to the web
        res = {"ok": False, "err": str(e), "skills": []}
        log("ask_log.jsonl", {"prompt": prompt, **res})
        return res
    with (data_dir() / "ask.lock").open("w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)  # one shared tab -> queue concurrent requests
        try:
            res = _ask(full)
        except Exception as e:
            res = {"ok": False, "err": str(e)[-300:] + (" (is Aside running?)" if "not reachable" in str(e) else "")}
    res.update(skills=used, wall_s=round(time.time() - t, 1))
    log("ask_log.jsonl", {"prompt": prompt, **res})
    return res


def first_block(answer: str):
    m = re.search(r"```[\w+-]*\n(.*?)\n```", answer, re.S)
    return m.group(1) if m else None


KEEP = {"solution.py", "test_main.py", "__pycache__"}


def code(spec: str, test: str, rounds: int = 3) -> dict:
    """Coding mode: web GPT writes solution.py; YOUR test_main.py runs here; failures go back (max `rounds`).
    The test is written by you, not the model, so the model never grades itself."""
    c = cfg()
    d = data_dir() / "code_jobs" / time.strftime("%Y%m%d-%H%M%S")
    d.mkdir(parents=True, exist_ok=True)
    (d / "test_main.py").write_text(test)
    libs = f"standard library + {c['libs']}" if c["libs"] else "standard library only"
    base = (f"{spec}\n\n(Write ONE file solution.py. Python, {libs}. Save any output files in the current folder. "
            f"This test must pass:)\n```python\n{test}\n```\nAnswer with the full solution.py in a single code block.")
    prompt, hist = base, []
    for i in range(1, rounds + 1):
        r = ask(prompt)
        src = first_block(r.get("answer", "")) if r.get("ok") else None
        if src is None:
            hist.append({"round": i, "err": r.get("err") or "no_code_block"})
            continue
        (d / "solution.py").write_text(src + "\n")
        t = subprocess.run([c["python"], "test_main.py"], cwd=d, capture_output=True, text=True, timeout=300,
                           env={**os.environ, "MPLBACKEND": "Agg"})
        out = (t.stdout + t.stderr)[-2000:]
        hist.append({"round": i, "done_ms": r.get("done_ms"), "rc": t.returncode, "out": out[-800:]})
        if t.returncode == 0:
            break
        # temporary chat has no memory -> resend code + failure
        prompt = f"{base}\n\nThis attempt failed the test:\n```python\n{src}\n```\nOutput:\n```\n{out}\n```\nFix it."
    ok = bool(hist) and hist[-1].get("rc") == 0
    files = sorted(p.name for p in d.iterdir() if p.is_file() and p.name not in KEEP)
    res = {"ok": ok, "dir": str(d), "rounds": hist, "files": files}
    log("code_log.jsonl", {"spec": spec, **res})
    return res


def notify(title: str, body: str):
    cmd = cfg()["notify"]
    if cmd:
        subprocess.run(cmd, input=f"{title}\n\n{body}", text=True, timeout=60)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["ask"]:
        r = ask(" ".join(a[1:]) or sys.stdin.read())
        if not r["ok"]:
            sys.exit(json.dumps(r, ensure_ascii=False))
        print(r["answer"])
        notify("webgpt", r["answer"])
    elif a[:1] == ["code"] and len(a) == 3:
        r = code(pathlib.Path(a[1]).read_text(), pathlib.Path(a[2]).read_text())
        print(json.dumps(r, ensure_ascii=False, indent=1))
        notify("webgpt code " + ("PASS" if r["ok"] else "FAIL"), r["dir"])
        sys.exit(0 if r["ok"] else 1)
    elif a == ["skills", "init"]:
        skills_init()
    elif a == ["skills", "list"]:
        al = allowlist()
        for n, hit in scan().items():
            print(("ALLOW " if n in al else "held  " if hit else "off   ") + n + (f"  ({hit[:40]!r})" if hit else ""))
    elif a == ["selftest"]:
        r = ask("1+1? Answer with the number only. #noskill")
        assert r["ok"] and r["answer"].strip() == "2", r
        print("selftest ok", {k: r[k] for k in ("first_ms", "done_ms", "wall_s")})
    else:
        sys.exit(__doc__)
