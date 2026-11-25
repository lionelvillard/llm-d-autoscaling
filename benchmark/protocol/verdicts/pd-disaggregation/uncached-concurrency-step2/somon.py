"""Every 10 s: ScaledObject conditions (Ready, Active, Fallback), the highest trigger failure count
and the Deployment's replicas. Usage: somon.py OUT.csv NAMESPACE CONTEXT SECONDS ID_LABEL"""
import json, subprocess, sys, time

out, ns, ctx, secs, idl = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]


def kj(*a):
    r = subprocess.run(["kubectl", "--context", ctx, "-n", ns, *a, "-o", "json"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else {}


with open(out, "a", buffering=1) as f:
    if f.tell() == 0:
        f.write("t_epoch,role,ready,active,fallback,max_failures,failing_triggers,spec_replicas\n")
    end = time.time() + secs
    while time.time() < end:
        t = int(time.time())
        for role in ("prefill", "decode"):
            so = kj("get", "so", f"{idl}-{role}")
            dep = kj("get", "deploy", f"{idl}-{role}")
            c = {x["type"]: x["status"] for x in so.get("status", {}).get("conditions", [])}
            h = so.get("status", {}).get("health", {}) or {}
            fails = {k: v.get("numberOfFailures", 0) for k, v in h.items()}
            f.write(f'{t},{role},{c.get("Ready","")},{c.get("Active","")},{c.get("Fallback","")},{max(fails.values()) if fails else 0},'
                    f'{";".join(k for k, v in fails.items() if v > 0)},{dep.get("spec", {}).get("replicas","")}\n')
        time.sleep(max(0, 10 - (time.time() - t)))
