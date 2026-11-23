"""Close one dev iteration of the guided prompt: summarise its rounds and move them out of the live paths.

Usage: python generation/archive_dev_round.py v1 [--dry-run]
Writes prompts/guided_history/<v>_results.md and moves every guided round (outputs, results, raw results, loop
summaries) to outputs/_dev_<v>/ and evaluation/results_archive/phase2_dev_<v>/, so the next prompt version runs on
clean paths and each version keeps its own dev results next to its prompt.
"""
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "evaluation", "results")
DEV = ["P02_n8n", "P04_voting-app", "P08_sock-shop", "P10_k8s-dashboard"]
MODELS = ["claude", "gemini", "qwen"]


def summary(v):
    rows = ["| Model | Project | Rounds | Gate | Final Ready | Final smoke | Gate passed but smoke failed |",
            "|---|---|---|---|---|---|---|"]
    for m in MODELS:
        for p in DEV:
            f = os.path.join(HERE, "outputs", m, p, "guided_loop_s1.json")
            if not os.path.exists(f):
                rows.append(f"| {m} | {p} | -- | not run | | | |")
                continue
            s = json.load(open(f, encoding="utf-8"))
            last = s["rounds"][-1]
            rows.append(f"| {m} | {p} | {len(s['rounds'])} | {s['stopped']} | {last['ready_ok']} | {last['smoke_ok']} | "
                        f"{'yes' if last['gate_passed'] and not last['smoke_ok'] else ''} |")
    return f"# Dev results, guided prompt {v}\n\nOne sample per model and dev project (s1).\n\n" + "\n".join(rows) + "\n"


def main(v, dry):
    moves = []
    for m in MODELS:
        for p in DEV:
            base = os.path.join(HERE, "outputs", m, p)
            for d in glob.glob(os.path.join(base, "guided_r*")) + glob.glob(os.path.join(base, "guided_loop_s*.json")):
                moves.append((d, os.path.join(HERE, "outputs", f"_dev_{v}", m, p, os.path.basename(d))))
            for f in glob.glob(os.path.join(RESULTS, f"{m}__{p}__guided_r*")) + \
                    glob.glob(os.path.join(RESULTS, "raw", f"{m}__{p}__guided_r*")):
                sub = "raw" if os.sep + "raw" + os.sep in f else ""
                moves.append((f, os.path.join(ROOT, "evaluation", "results_archive", f"phase2_dev_{v}", sub,
                                              os.path.basename(f))))
    text = summary(v)
    print(text)
    print(f"{len(moves)} paths to move")
    if dry:
        return
    with open(os.path.join(HERE, "prompts", "guided_history", f"{v}_results.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    for src, dst in moves:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)


if __name__ == "__main__":
    main(sys.argv[1], "--dry-run" in sys.argv)
