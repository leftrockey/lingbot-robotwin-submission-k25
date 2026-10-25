#!/usr/bin/env python3
"""summarize_eval.py EVAL_DIR [OUT_PREFIX]
Per-task / per-setting success from the authoritative per-episode records (<setting>/run/eval_results/<task>/lb_resume.jsonl).
Two views: (a) crashes counted as failures (conservative); (b) crashed episodes excluded (ARM Vulkan device loss is an
environment fault, absent on the official x86 stack). Writes <prefix>_per_task.csv and <prefix>_results.json (draft schema:
{setting: {task: {"test_num", "success_num", "crash_num"}}} -- to be mapped onto the official Tianchi template)."""
import json, glob, os, sys, csv
E = sys.argv[1]; P = sys.argv[2] if len(sys.argv) > 2 else os.path.join(E, "final")
res, rows = {}, []
for setting in ("clean", "randomized"):
    res[setting] = {}
    for d in sorted(glob.glob(f"{E}/{setting}/run/eval_results/*/")):
        task = os.path.basename(os.path.dirname(d))
        # merge the sequential file and any seed-strided worker files; keep the first 100 valid seeds in seed order
        by_seed = {}
        for f in sorted(glob.glob(f"{d}lb_resume*.jsonl")):
            for l in open(f):
                if l.strip():
                    r = json.loads(l); by_seed.setdefault(r["seed"], r)
        if not by_seed: continue
        recs = [by_seed[k] for k in sorted(by_seed)][:100]
        n, s, c = len(recs), sum(r["succ"] for r in recs), sum(1 for r in recs if r.get("crash"))
        res[setting][task] = {"test_num": n, "success_num": s, "crash_num": c}
        rows.append([setting, task, n, s, c, round(100 * s / n, 1) if n else 0, round(100 * s / (n - c), 1) if n - c else 0])
with open(P + "_per_task.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["setting", "task", "episodes", "success", "crashes", "sr_crash_as_fail", "sr_crash_excluded"]); w.writerows(rows)
json.dump(res, open(P + "_results.json", "w"), indent=2, ensure_ascii=False)
for setting, d in res.items():
    n = sum(v["test_num"] for v in d.values()); s = sum(v["success_num"] for v in d.values()); c = sum(v["crash_num"] for v in d.values())
    full = sum(1 for v in d.values() if v["test_num"] >= 100)
    per_task_a = [v["success_num"] / v["test_num"] for v in d.values() if v["test_num"]]
    per_task_b = [v["success_num"] / (v["test_num"] - v["crash_num"]) for v in d.values() if v["test_num"] - v["crash_num"]]
    print(f"{setting:10s} tasks {len(d)} (complete {full}) | episodes {n} success {s} crashes {c} | "
          f"SR crash=fail {100*s/max(n,1):.2f}% (task-mean {100*sum(per_task_a)/max(len(per_task_a),1):.2f}%) | "
          f"SR crash-excluded {100*s/max(n-c,1):.2f}% (task-mean {100*sum(per_task_b)/max(len(per_task_b),1):.2f}%)")
print("wrote", P + "_per_task.csv", P + "_results.json")
