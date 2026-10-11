#!/usr/bin/env python3
"""Offline test: a fake `aside` CLI stands in for the browser. No network, no account.
usage: python3 webgpt/test_webgpt.py   -> prints "WEBGPT OFFLINE ALL PASS"
"""
import json, os, pathlib, sys, tempfile, threading, time, urllib.error, urllib.request

T = pathlib.Path(tempfile.mkdtemp(prefix="webgpt-test-"))
HERE = pathlib.Path(__file__).resolve().parent

# fake aside: remembers the nonce + prompt from SEND, answers POLL with a canned reply chosen by the prompt
FAKE = T / "aside"
FAKE.write_text(f"""#!{sys.executable}
import json, re, sys, pathlib
st = pathlib.Path({str(T)!r}) / "state.json"
code = sys.argv[-1]
if "listBrowserTabs" in code: print("__WJ__" + json.dumps(["TAB1"])); sys.exit()
if "__wjRead = " in code:
    nonce = re.search(r"id:'(\\d+)'", code).group(1)
    prompt = json.loads(re.search(r"const P = (.*?), EFFORT", code, re.S).group(1))
    st.write_text(json.dumps({{"nonce": nonce, "prompt": prompt}}))
    with open(st.with_name("sent.log"), "a") as f: f.write(prompt + "\\n=====\\n")
    print("__WJ__" + json.dumps({{"ok": True, "eff": None}})); sys.exit()
s = json.loads(st.read_text())
p = s["prompt"]
if "solution.py" in p:
    ans = "```python\\ndef double(x):\\n    return x * 2\\nopen('out.txt','w').write('hi')\\n```" if "failed the test" in p \\
          else "```python\\ndef double(x):\\n    return x + 2\\n```"
else:
    ans = "ANSWER:" + p[-20:]
print("__WJ__" + json.dumps({{"w": {{"id": s["nonce"], "first": 5, "done": 9}}, "r": {{"tx": ans, "state": "complete"}}}}))
""")
FAKE.chmod(0o755)

skills = T / "skills"
for name, body in {"pdf-tools": "---\nname: pdf-tools\ndescription: merge split pdf files\n---\nuse qpdf",
                   "secret-ops": "---\nname: secret-ops\ndescription: deploy\n---\nssh /Users/you/prod",
                   "acme-report": "---\nname: acme-report\ndescription: report\n---\nfor AcmeCorp clients"}.items():
    (skills / name).mkdir(parents=True)
    (skills / name / "SKILL.md").write_text(body)

cfgf = T / "webgpt.config.json"
cfgf.write_text(json.dumps({"aside": str(FAKE), "data_dir": str(T / "data"), "skill_dirs": [str(skills)]}))
os.environ["WEBGPT_CONFIG"] = str(cfgf)
sys.path.insert(0, str(HERE))
import webgpt  # noqa: E402

# 1. questionnaire: user's private word "AcmeCorp" holds that skill back; /Users/ path held by base rules
allowed = webgpt.skills_init({"dirs": [str(skills)], "words": ["AcmeCorp"], "mode": "all"})
assert allowed == ["pdf-tools"], allowed
assert json.loads(cfgf.read_text())["block_words"] == ["AcmeCorp"]

# 2. plain ask round trip
r = webgpt.ask("hello there #noskill")
assert r["ok"] and r["answer"] == "ANSWER:hello there", r

# 3. auto-pick attaches the allowed skill; text really went out with it
r = webgpt.ask("how do I merge pdf files")
assert r["ok"] and r["skills"] == ["pdf-tools"], r
assert "use qpdf" in (T / "sent.log").read_text().split("=====")[-2]

# 4. explicit tag of a held-back skill -> refused, nothing sent
n_sent = (T / "sent.log").read_text().count("=====")
r = webgpt.ask("do it #secret-ops")
assert not r["ok"] and "allowlist" in r["err"], r
assert (T / "sent.log").read_text().count("=====") == n_sent, "blocked skill must not be sent"

# 5. allowlisted skill that later gains private text -> still blocked at send time
(skills / "pdf-tools" / "SKILL.md").write_text("---\nname: pdf-tools\ndescription: merge pdf\n---\nmail bob@acme.io")
r = webgpt.ask("x #pdf-tools")
assert not r["ok"] and "private" in r["err"], r
(skills / "pdf-tools" / "SKILL.md").write_text("---\nname: pdf-tools\ndescription: merge split pdf files\n---\nuse qpdf")

# 6. code mode: round 1 fails the test, failure goes back, round 2 passes and leaves out.txt
test = "from solution import double\nassert double(5) == 10\nprint('ok')\n"
r = webgpt.code("double a number #noskill", test)
assert r["ok"] and len(r["rounds"]) == 2 and r["rounds"][0]["rc"] != 0 and r["files"] == ["out.txt"], r

# 7. web page: skills list, ask job, code job file download, path escape refused
import app  # noqa: E402
srv = app.ThreadingHTTPServer(("127.0.0.1", 0), app.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
get = lambda p: urllib.request.urlopen(base + p)
post = lambda p, b: json.loads(urllib.request.urlopen(urllib.request.Request(base + p, json.dumps(b).encode(),
                                                                             {"Content-Type": "application/json"})).read())
assert b"webgpt" in get("/").read()
assert json.loads(get("/api/skills").read())["allowed"] == ["pdf-tools"]


def wait(jid):
    for _ in range(100):
        j = json.loads(get("/api/jobs/" + jid).read())
        if j["status"] != "running":
            return j["result"]
        time.sleep(0.1)
    raise AssertionError("job hung")


assert wait(post("/api/ask", {"prompt": "web page #noskill"})["id"])["answer"] == "ANSWER:web page"
res = wait(post("/api/code", {"spec": "double #noskill", "test": test})["id"])
assert res["ok"], res
jid = res["dir"].rsplit("/", 1)[1]
assert get(f"/api/files/{jid}/out.txt").read() == b"hi"
for bad in (f"/api/files/{jid}/..%2F..%2Fask_log.jsonl", "/api/files/..%2F..%2F/ask_log.jsonl"):
    try:
        get(bad)
        raise AssertionError("path escape served: " + bad)
    except urllib.error.HTTPError as e:
        assert e.code == 404
try:
    post("/api/ask", {"prompt": "  "})
    raise AssertionError("empty prompt accepted")
except urllib.error.HTTPError as e:
    assert e.code == 400
srv.shutdown()
print("WEBGPT OFFLINE ALL PASS")
