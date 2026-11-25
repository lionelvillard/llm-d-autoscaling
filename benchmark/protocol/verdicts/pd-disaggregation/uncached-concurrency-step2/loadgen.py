"""Step 2 load generator (stdlib only): open-loop Poisson arrivals through the EPP service.

    loadgen.py OUT.csv STAGES MIXES [SEED]

STAGES  "rate:seconds,rate:seconds,..."  (requests/s; rate 0 idles)
MIXES   "ISL:OSL[,ISL:OSL...]"  each request draws one mix with equal weight; ISL is
        a number of random words (about one token each), OSL is max_tokens
        (ignore_eos, so every request runs to OSL).
Prompts are random words, so there is no prefix reuse. One CSV line per request:
t_send (s since start), mix, status, latency_s, prompt_tokens, completion_tokens.
"""
import json
import os
import random
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

URL = os.environ.get("URL", "http://deepseek-8f161440--v2-lite-router-epp:80/v1/completions")
MODEL = os.environ.get("MODEL", "deepseek-ai/DeepSeek-V2-Lite")
WORDS = ("time year people way day man thing woman life child world school state family student "
         "group country problem hand part place case week company system program question work "
         "government number night point home water room mother area money story fact month lot "
         "right study book eye job word business issue side kind head house service friend father "
         "power hour game line end member law car city community name president team minute idea "
         "kitchen river garden window mountain silver copper engine bridge letter market winter "
         "summer planet forest island desert valley harbor castle tunnel signal ribbon candle").split()

out_path, stages_s, mixes_s = sys.argv[1], sys.argv[2], sys.argv[3]
seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
rng = random.Random(seed)
stages = [(float(a), float(b)) for a, b in (s.split(":") for s in stages_s.split(","))]
mixes = [tuple(int(x) for x in m.split(":")) for m in mixes_s.split(",")]
lock = threading.Lock()
fout = open(out_path, "w", buffering=1)
fout.write("t_send,mix,status,latency_s,prompt_tokens,completion_tokens\n")
t0 = time.time()


def send(tsend, mix, prompt, osl):
    body = json.dumps({"model": MODEL, "prompt": prompt, "max_tokens": osl, "temperature": 0,
                       "ignore_eos": True}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    start = time.time()
    pt = ct = ""
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.loads(r.read()); status = r.status
            pt = d.get("usage", {}).get("prompt_tokens", ""); ct = d.get("usage", {}).get("completion_tokens", "")
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:  # noqa: BLE001
        status = "err:" + type(e).__name__
    with lock:
        fout.write(f"{tsend:.2f},{mix[0]}:{mix[1]},{status},{time.time()-start:.2f},{pt},{ct}\n")


pool = ThreadPoolExecutor(max_workers=800)
for rate, dur in stages:
    end = time.time() + dur
    if rate <= 0:
        time.sleep(dur); continue
    while True:
        time.sleep(rng.expovariate(rate))
        if time.time() >= end:
            break
        mix = rng.choice(mixes)
        prompt = " ".join(rng.choice(WORDS) for _ in range(mix[0]))
        pool.submit(send, time.time() - t0, mix, prompt, mix[1])
pool.shutdown(wait=True)
fout.close()
print("done", time.time() - t0, flush=True)
