# Writes RoboTwin/script/eval_policy_client_lingbotvla.py = official client + per-episode TIMING prints only
# (no logic change; LB_TEST_NUM can shorten subset evals, default 100). The launcher copies the client only if the destination is missing, so this copy is used.
import re, sys
LB = "/path/to/lingbot"
src = open(f"{LB}/src/lingbot-vla-v2/experiment/robotwin/eval_policy_client_lingbotvla.py").read()
def sub(old, new, count=1):
    global src
    assert src.count(old) >= 1, old
    src = src.replace(old, new, count)
sub("    while succ_seed < test_num:\n",
    "    import time as _t\n    _T = dict(expert=0.0, n_expert=0)\n    while succ_seed < test_num:\n")
sub("        if expert_check:\n            try:\n",
    "        if expert_check:\n            _t0 = _t.time(); _T['n_expert'] += 1\n            try:\n")
sub("        if (not expert_check) or (TASK_ENV.plan_success and TASK_ENV.check_success()):\n",
    "        _T['expert'] += _t.time() - _t0\n        if (not expert_check) or (TASK_ENV.plan_success and TASK_ENV.check_success()):\n")
# failed-seed `continue` branches inside the try/except skip the line above; account for them too
src = src.replace("                TASK_ENV.close_env()\n                now_seed += 1\n                args[\"render_freq\"] = render_freq\n",
                  "                TASK_ENV.close_env()\n                _T['expert'] += _t.time() - _t0\n                now_seed += 1\n                args[\"render_freq\"] = render_freq\n")
sub("        TASK_ENV.setup_demo(now_ep_num=now_id, seed=now_seed, is_test=True, **args)\n        episode_info_list",
    "        _t1 = _t.time()\n        TASK_ENV.setup_demo(now_ep_num=now_id, seed=now_seed, is_test=True, **args)\n        _setup = _t.time() - _t1\n        episode_info_list")
sub("        while TASK_ENV.take_action_cnt<TASK_ENV.step_lim and not succ:\n",
    "        _ti = _ta = _to = 0.0; _ni = 0; _t2 = _t.time()\n        while TASK_ENV.take_action_cnt<TASK_ENV.step_lim and not succ:\n            _a = _t.time()\n")
sub("            ret = model.infer(formatted_observation) #(TASK_ENV, model, observation)\n",
    "            _b = _t.time(); _to += _b - _a\n            ret = model.infer(formatted_observation) #(TASK_ENV, model, observation)\n            _c = _t.time(); _ti += _c - _b; _ni += 1\n")
sub("            print(f\"infer time {latency}\")\n",
    "            _ta += _t.time() - _c\n            print(f\"infer time {latency}\")\n")
sub("        result_tag = \"success\" if succ else \"failure\"\n",
    "        result_tag = \"success\" if succ else \"failure\"\n"
    "        print(f\"TIMING task={task_name} seed={now_seed} succ={int(succ)} steps={TASK_ENV.take_action_cnt}/{TASK_ENV.step_lim} \"\n"
    "              f\"expert_total={_T['expert']:.1f}s expert_runs={_T['n_expert']} setup={_setup:.1f}s rollout={_t.time()-_t2:.1f}s \"\n"
    "              f\"obs={_to:.1f}s infer={_ti:.1f}s n_infer={_ni} act={_ta:.1f}s\", flush=True)\n"
    "        _T = dict(expert=0.0, n_expert=0)\n")
sub("    test_num = 100\n", "    test_num = int(os.environ.get(\"LB_TEST_NUM\", \"100\"))  # lingbot: subset evals; official = 100\n")

# --- crash-resume (ARM SAPIEN can lose the Vulkan device mid-episode, e.g. move_stapler_pad; the process dies and
#     the launcher restarts the task from scratch, so it never reaches test_num). Every finished episode is appended
#     to <output_dir>/<task>/lb_resume.jsonl; a restarted process continues after the last seed, and the episode that
#     was running when the process died is recorded as a FAILURE (conservative).
sub("    now_seed = st_seed\n",
    "    now_seed = st_seed\n"
    "    import json as _json\n"
    "    _rdir = Path(usr_args['output_dir']) / task_name if (usr_args and usr_args.get('output_dir')) else None\n"
    "    _rfile = (_rdir / 'lb_resume.jsonl') if _rdir else None\n"
    "    _pfile = (_rdir / 'lb_pending_seed') if _rdir else None\n"
    "    if _rdir is not None:\n"
    "        _rdir.mkdir(parents=True, exist_ok=True)\n"
    "        if _pfile.exists():\n"
    "            _s = int(_pfile.read_text().strip())\n"
    "            with open(_rfile, 'a') as _f: _f.write(_json.dumps({'seed': _s, 'succ': 0, 'crash': True}) + '\\n')\n"
    "            _pfile.unlink()\n"
    "            print(f'[lb_resume] episode at seed {_s} crashed in the previous process -> counted as failure', flush=True)\n"
    "        if _rfile.exists():\n"
    "            _recs = [_json.loads(l) for l in open(_rfile) if l.strip()]\n"
    "            if _recs:\n"
    "                TASK_ENV.suc = sum(r['succ'] for r in _recs); TASK_ENV.test_num = len(_recs)\n"
    "                succ_seed = len(_recs); now_id = len(_recs); now_seed = max(r['seed'] for r in _recs) + 1\n"
    "                print(f'[lb_resume] {task_name}: resuming at {TASK_ENV.suc}/{TASK_ENV.test_num}, next seed {now_seed}', flush=True)\n")
sub("        ret = model.infer(dict(reset = True, robo_name=usr_args['robo_name'], path_to_pi_model=path_to_pi_model))\n",
    "        if _pfile is not None: _pfile.write_text(str(now_seed))\n"
    "        ret = model.infer(dict(reset = True, robo_name=usr_args['robo_name'], path_to_pi_model=path_to_pi_model))\n")
sub("        TASK_ENV.test_num += 1\n",
    "        TASK_ENV.test_num += 1\n"
    "        if _rfile is not None:\n"
    "            with open(_rfile, 'a') as _f: _f.write(_json.dumps({'seed': now_seed, 'succ': int(succ)}) + '\\n')\n"
    "            _pfile.unlink(missing_ok=True)\n")

# --- seed-strided workers (10-16): one slow task (put_bottles_dustbin, ~7 min/episode) can be split over K processes.
#     LB_SEED_START=<abs seed> LB_SEED_STRIDE=K LB_RESUME_TAG=_wJ: this process visits seeds START, START+K, ... and keeps
#     its own lb_resume<TAG>.jsonl; summarize_eval.py merges all files and keeps the first 100 valid seeds in seed order.
#     Defaults (unset) = official sequential behaviour.
src = src.replace("now_seed += 1", "now_seed += _LB_STRIDE")
sub("    import json as _json\n",
    "    import json as _json\n"
    "    _LB_STRIDE = int(os.environ.get('LB_SEED_STRIDE', '1')); _LB_TAG = os.environ.get('LB_RESUME_TAG', '')\n"
    "    if os.environ.get('LB_SEED_START'): now_seed = int(os.environ['LB_SEED_START'])\n")
src = src.replace("(_rdir / 'lb_resume.jsonl')", "(_rdir / f'lb_resume{_LB_TAG}.jsonl')").replace("(_rdir / 'lb_pending_seed')", "(_rdir / f'lb_pending_seed{_LB_TAG}')")
src = src.replace("now_seed = max(r['seed'] for r in _recs) + 1", "now_seed = max(r['seed'] for r in _recs) + _LB_STRIDE")
# --- temporal ensembling (10-18, inference-side improvements): LB_TE_EXEC=k>0 executes only k actions per inference
#     call and, at every step t, executes the exp-weighted mean of all buffered chunk predictions covering t
#     (ACT-style: weight exp(-LB_TE_M * i), i=0 = oldest prediction). Server must return the full chunk (--use_length 50).
#     Unset/0 = official behaviour (execute the whole returned chunk).
sub("        _ti = _ta = _to = 0.0; _ni = 0; _t2 = _t.time()\n",
    "        _ti = _ta = _to = 0.0; _ni = 0; _t2 = _t.time()\n"
    "        _TE_K = int(os.environ.get('LB_TE_EXEC', '0')); _TE_M = float(os.environ.get('LB_TE_M', '0.1')); _te_buf = []\n")
sub("            if len(action.shape) == 2:\n                initial_obs = False\n",
    "            if _TE_K > 0 and len(action.shape) == 2:\n"
    "                _te_buf.append((TASK_ENV.take_action_cnt, np.asarray(action, dtype=np.float64)))\n"
    "                _te_buf = [(s0, c) for s0, c in _te_buf if s0 + len(c) > TASK_ENV.take_action_cnt]\n"
    "                for _k in range(_TE_K):\n"
    "                    _tt = TASK_ENV.take_action_cnt\n"
    "                    _p = [c[_tt - s0] for s0, c in _te_buf if s0 <= _tt < s0 + len(c)]\n"
    "                    if not _p: break\n"
    "                    _w = np.exp(-_TE_M * np.arange(len(_p)))\n"
    "                    TASK_ENV.take_action((_w[:, None] * np.stack(_p)).sum(0) / _w.sum())\n"
    "                    if TASK_ENV.eval_success:\n"
    "                        succ = True\n"
    "                        break\n"
    "            elif len(action.shape) == 2:\n                initial_obs = False\n")
open(f"{LB}/src/RoboTwin/script/eval_policy_client_lingbotvla.py", "w").write(src)
print("written")
