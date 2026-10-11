#!/usr/bin/env python3
"""Local web page for webgpt: Ask tab + Code tab + skill picker. stdlib only.

  python3 app.py [--port 8790] [--host 127.0.0.1]
  open http://127.0.0.1:8790

Binds to localhost by default. Code mode runs model-written code on this machine; if you expose this page
beyond localhost, set WEBGPT_TOKEN (sent as header X-Token) and use a venv/container for "python".
"""
import json, os, sys, threading, time, uuid, pathlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import webgpt  # noqa: E402

TOKEN = os.environ.get("WEBGPT_TOKEN")
JOBS = {}  # ponytail: in-memory job table, lost on restart; results are also in data_dir logs

PAGE = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>webgpt</title><style>
body{font:15px system-ui,sans-serif;max-width:860px;margin:2em auto;padding:0 1em;color:#222}
textarea{width:100%;box-sizing:border-box;font:14px ui-monospace,monospace;padding:.6em}
button{padding:.5em 1.2em;margin:.4em .4em .4em 0;cursor:pointer}nav button.on{background:#222;color:#fff}
pre{white-space:pre-wrap;background:#f5f5f5;padding:1em;border-radius:6px}.muted{color:#777;font-size:13px}
</style></head><body>
<h2>webgpt</h2>
<nav><button id=t-ask class=on onclick="tab('ask')">Ask</button><button id=t-code onclick="tab('code')">Code</button></nav>
<div id=ask><textarea id=q rows=6 placeholder="Question. #skill-name attaches one of your allowed skills, #noskill turns auto-pick off."></textarea></div>
<div id=code hidden><textarea id=spec rows=5 placeholder="What solution.py should do"></textarea>
<textarea id=test rows=8 placeholder="test_main.py (written by you; runs here)&#10;from solution import f&#10;assert f(2) == 4&#10;print('ok')"></textarea></div>
<div>Skills: <select id=sk><option value="">auto</option><option value="#noskill">none</option></select>
<button onclick="go()">Send</button> <span id=st class=muted></span></div>
<pre id=out hidden></pre><div id=files></div>
<script>
let mode='ask';const H={'Content-Type':'application/json','X-Token':localStorage.tok||''};
function tab(m){mode=m;for(const x of['ask','code']){document.getElementById(x).hidden=x!==m;document.getElementById('t-'+x).className=x===m?'on':''}}
fetch('/api/skills',{headers:H}).then(r=>r.json()).then(j=>{for(const n of j.allowed){const o=document.createElement('option');o.value='#'+n;o.textContent=n;sk.appendChild(o)}});
async function go(){const tag=sk.value?' '+sk.value:'';
 const body=mode==='ask'?{prompt:q.value+tag}:{spec:spec.value+tag,test:test.value};
 out.hidden=true;files.innerHTML='';st.textContent='sending...';
 const r=await fetch('/api/'+mode,{method:'POST',headers:H,body:JSON.stringify(body)});const j=await r.json();
 if(!r.ok){st.textContent=j.err;return}const t0=Date.now();
 while(true){await new Promise(s=>setTimeout(s,2000));const s=await (await fetch('/api/jobs/'+j.id,{headers:H})).json();
  st.textContent=s.status+' '+Math.round((Date.now()-t0)/1000)+'s';if(s.status!=='running'){show(s.result);break}}}
function show(r){out.hidden=false;
 if(mode==='ask'){out.textContent=r.ok?r.answer:'error: '+r.err;st.textContent+=r.skills&&r.skills.length?' · skills: '+r.skills.join(', '):'';return}
 const last=r.rounds[r.rounds.length-1]||{};out.textContent=(r.ok?'PASS':'FAIL')+' after '+r.rounds.length+' round(s)\\n\\n'+(last.out||last.err||'');
 const id=r.dir.split('/').pop();files.innerHTML=['solution.py',...r.files].map(f=>`<a href="/api/files/${id}/${encodeURIComponent(f)}">${f}</a>`).join(' · ')}
</script></body></html>"""


def run(job_id, fn, *args):
    try:
        JOBS[job_id] = {"status": "done", "result": fn(*args)}
    except Exception as e:
        JOBS[job_id] = {"status": "done", "result": {"ok": False, "err": repr(e)[:300], "rounds": [], "files": [], "dir": ""}}


class H(BaseHTTPRequestHandler):
    def reply(self, code, obj, ctype="application/json"):
        b = obj if isinstance(obj, bytes) else (obj.encode() if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode())
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def authed(self):
        if TOKEN and self.headers.get("X-Token") != TOKEN:
            self.reply(401, {"err": "token"})
            return False
        return True

    def do_GET(self):
        if self.path == "/":
            return self.reply(200, PAGE, "text/html; charset=utf-8")
        if not self.authed():
            return
        if self.path == "/api/skills":
            return self.reply(200, {"allowed": sorted(webgpt.allowlist())})
        if self.path.startswith("/api/jobs/"):
            j = JOBS.get(self.path.rsplit("/", 1)[1])
            return self.reply(200, j) if j else self.reply(404, {"err": "no such job"})
        if self.path.startswith("/api/files/"):
            _, _, _, job, name = self.path.split("/", 4)
            root = (webgpt.data_dir() / "code_jobs").resolve()
            f = (root / unquote(job) / unquote(name)).resolve()
            if f.parent.parent != root or not f.is_file():  # no path escape
                return self.reply(404, {"err": "not found"})
            self.send_response(200)
            self.send_header("Content-Disposition", f'attachment; filename="{f.name}"')
            self.send_header("Content-Length", str(f.stat().st_size))
            self.end_headers()
            return self.wfile.write(f.read_bytes())
        self.reply(404, {"err": "not found"})

    def do_POST(self):
        if not self.authed():
            return
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self.reply(400, {"err": "bad json"})
        if self.path == "/api/ask" and body.get("prompt", "").strip():
            fn, args = webgpt.ask, (body["prompt"],)
        elif self.path == "/api/code" and body.get("spec", "").strip() and body.get("test", "").strip():
            fn, args = webgpt.code, (body["spec"], body["test"])
        else:
            return self.reply(400, {"err": "empty or unknown request"})
        job_id = uuid.uuid4().hex[:12]
        JOBS[job_id] = {"status": "running", "started": time.time()}
        threading.Thread(target=run, args=(job_id, fn, *args), daemon=True).start()
        self.reply(202, {"id": job_id})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    a = sys.argv[1:]
    port = int(a[a.index("--port") + 1]) if "--port" in a else 8790
    host = a[a.index("--host") + 1] if "--host" in a else "127.0.0.1"
    print(f"webgpt page: http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()
