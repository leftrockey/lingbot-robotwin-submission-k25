#!/usr/bin/env python3
"""Build the official Tianchi results.json (schema_version 1) from an eval.sh output directory.

Usage: make_results_json.py EVAL_OUT TEAM_ID OUT_JSON [N=100]

EVAL_OUT/<setting>/run/eval_results/<task>/lb_resume*.jsonl hold one record per finished episode
({"seed": s, "succ": 0|1[, "crash": true]}); several files exist when a task was split over seed-strided workers.
Per task we keep the first N valid seeds in seed order (= the official sequential protocol) and count crashed
episodes as failures. Task order follows the official template.
"""
import glob
import json
import sys

TASKS = ["lift_pot", "hanging_mug", "stack_bowls_three", "scan_object", "handover_block", "click_bell",
         "put_object_cabinet", "open_microwave", "stack_blocks_three", "place_shoe", "adjust_bottle",
         "beat_block_hammer", "blocks_ranking_rgb", "blocks_ranking_size", "click_alarmclock", "dump_bin_bigbin",
         "grab_roller", "handover_mic", "move_can_pot", "move_pillbottle_pad", "move_playingcard_away",
         "place_cans_plasticbox", "place_container_plate", "place_dual_shoes", "place_empty_cup", "place_fan",
         "place_mouse_pad", "place_object_basket", "place_object_scale", "place_object_stand", "place_phone_stand",
         "move_stapler_pad", "open_laptop", "pick_diverse_bottles", "pick_dual_bottles", "place_a2b_left",
         "place_a2b_right", "place_bread_basket", "place_bread_skillet", "place_burger_fries", "place_can_basket",
         "press_stapler", "rotate_qrcode", "shake_bottle_horizontally", "shake_bottle", "stack_blocks_two",
         "stack_bowls_two", "stamp_seal", "turn_switch", "put_bottles_dustbin"]


def task_records(root, setting, task):
    by_seed = {}
    for f in sorted(glob.glob(f"{root}/{setting}/run/eval_results/{task}/lb_resume*.jsonl")):
        for line in open(f):
            if line.strip():
                r = json.loads(line)
                by_seed.setdefault(r["seed"], int(r.get("succ", 0)))
    return by_seed


def main():
    root, team_id, out = sys.argv[1], sys.argv[2], sys.argv[3]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 100
    results, incomplete = {}, []
    for setting in ("clean", "randomized"):
        results[setting] = {}
        for task in TASKS:
            recs = task_records(root, setting, task)
            seeds = sorted(recs)[:n]
            if len(seeds) < n:
                incomplete.append(f"{setting}/{task}: {len(seeds)}/{n}")
            results[setting][task] = {"attempts": len(seeds), "successes": sum(recs[s] for s in seeds)}
    json.dump({"schema_version": 1, "team_id": team_id, "results": results}, open(out, "w"), ensure_ascii=False, indent=2)
    for setting in ("clean", "randomized"):
        a = sum(v["attempts"] for v in results[setting].values())
        s = sum(v["successes"] for v in results[setting].values())
        mean = sum(v["successes"] / v["attempts"] for v in results[setting].values() if v["attempts"]) / len(TASKS)
        print(f"{setting}: {s}/{a} episodes, mean task success {100 * mean:.2f}%")
    if incomplete:
        print("INCOMPLETE:", "; ".join(incomplete))
    print("written", out)


if __name__ == "__main__":
    main()
