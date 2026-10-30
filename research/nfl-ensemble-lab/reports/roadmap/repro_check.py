"""Reproducibility: record versions, then rerun each real step twice into separate folders and compare output hashes (and against the saved outputs, ignoring git_head)."""
import hashlib
import importlib.metadata as md, os, shutil, subprocess, sys, tempfile
from common import *
res = header("repro_check")
res["versions"] = {p: md.version(p) for p in ("numpy", "pandas", "scipy", "pyarrow")}; res["versions"]["python"] = sys.version.split()[0]
res["seeds"] = {"real_steps": SEED, "step2_power": 1, "rehearsal_dataset_i": "1000 + offset + i"}
STEPS = [("run_real.py", ["2"], "real_step2.json"), ("run_real.py", ["3"], "real_step3.json"), ("run_real.py", ["5"], "real_step5.json"),
         ("run_real.py", ["6"], "real_step6.json"), ("run_real.py", ["7"], "real_step7.json"), ("step4_real.py", [], "step4_real.json")]
tmp = Path(tempfile.mkdtemp(prefix="roadmap_repro_"))
dirs = []
for tag in ("A", "B"):
    d = tmp / tag; d.mkdir()
    for f in OUT.glob("rehearsal_step*.json"): shutil.copy(f, d / f.name)
    dirs.append(d)
strip = lambda b: json.dumps({k: v for k, v in json.loads(b).items() if k != "git_head"}, sort_keys=True)
out = {}
for script, args, name in STEPS:
    for d in dirs:
        env = dict(os.environ, ROADMAP_OUT=str(d))
        subprocess.run([sys.executable, str(SRC / script), *args], cwd=SRC, env=env, capture_output=True, check=True)
    a, b = (d / name).read_bytes(), (dirs[1] / name).read_bytes()
    saved = (OUT / name).read_bytes()
    out[name] = {"run_A_sha256": hashlib.sha256(a).hexdigest(), "run_B_sha256": hashlib.sha256(b).hexdigest(), "A_equals_B": a == b,
                 "equals_saved_ignoring_git_head": strip(a) == strip(saved), "equals_saved_byte_for_byte": a == saved}
res["steps"] = out
res["all_pairs_identical"] = all(v["A_equals_B"] for v in out.values())
res["all_equal_saved_ignoring_git_head"] = all(v["equals_saved_ignoring_git_head"] for v in out.values())
write("repro_check.json", res)
print(json.dumps({k: {a: b for a, b in v.items() if "sha256" not in a} for k, v in out.items()}, indent=1)); print(res["versions"])
