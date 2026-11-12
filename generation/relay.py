"""Manual web-chat relay for the models with no API route (DeepSeek, GPT web).

  python generation/relay.py export
      Writes one paste-ready prompt per project x variant to generation/relay/prompts/
      (system line + docs_bundle + instruction, exactly what the API models receive).
  python generation/relay.py import
      Imports every reply saved as generation/relay/inbox/<model>/<project>__<variant>__s<k>.txt
      that is not yet in generation/outputs/, recording it like the pilot relays.
  python generation/relay.py status
      Lists which relay replies are still missing for the decided scope.
"""
import datetime
import hashlib
import json
import sys

from generate import CONFIG, HERE, build_user_prompt, extract_yaml

PROJECTS = ["P02_n8n", "P03_grafana", "P04_voting-app", "P05_emojivoto",
            "P07_online-boutique", "P08_sock-shop", "P10_k8s-dashboard"]
VARIANTS = ["neutral", "production"]
SAMPLES = [1, 2, 3]
RELAY_MODELS = {"deepseek": "via DeepSeek web chat (chat.deepseek.com), DeepThink off, Search off, fresh chat per prompt.",
                "gpt": "via ChatGPT web (default model on Pro account), browsing/tools off, fresh chat per prompt; operated by a third party."}
RELAY = HERE / "relay"


def full_prompt(project, variant):
    return CONFIG["system_prompt"].strip() + "\n\n" + build_user_prompt(project, variant)


def export():
    (RELAY / "prompts").mkdir(parents=True, exist_ok=True)
    for p in PROJECTS:
        for v in VARIANTS:
            text = full_prompt(p, v)
            (RELAY / "prompts" / f"{p}__{v}.txt").write_text(text, encoding="utf-8")
            print(f"{p}__{v}.txt  {len(text):>7,} chars")
    for m in RELAY_MODELS:
        (RELAY / "inbox" / m).mkdir(parents=True, exist_ok=True)


def out_dir(m, p, v, k):
    return HERE / "outputs" / m / p / v / f"s{k}"


def import_all():
    n = 0
    for m, note in RELAY_MODELS.items():
        for f in sorted((RELAY / "inbox" / m).glob("*__*__s*.txt")):
            p, v, s = f.stem.split("__")
            k = int(s.lstrip("s"))
            d = out_dir(m, p, v, k)
            if (d / "manifest.yaml").exists():
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            manifest, status = extract_yaml(text)
            d.mkdir(parents=True, exist_ok=True)
            (d / "request.json").write_text(json.dumps({
                "model_id": CONFIG["models"][m]["model_id"], "provider": "manual_web_chat",
                "temperature": None, "max_tokens": None,
                "prompt_hash": hashlib.sha256(build_user_prompt(p, v).encode()).hexdigest()[:16],
                "timestamp": datetime.datetime.fromtimestamp(f.stat().st_mtime, datetime.timezone.utc).isoformat(),
            }, indent=2))
            (d / "response_raw.json").write_text(json.dumps({"raw": text}, indent=2))
            (d / "manifest.yaml").write_text(manifest, encoding="utf-8")
            (d / "extraction.json").write_text(json.dumps({"status": status, "note": note}, indent=2))
            print(f"imported {m}/{p}/{v}/s{k}: {status}")
            n += 1
    print(f"{n} imported")


def status():
    missing = [(m, p, v, k) for m in RELAY_MODELS for p in PROJECTS for v in VARIANTS for k in SAMPLES
               if not (out_dir(m, p, v, k) / "manifest.yaml").exists()]
    for m in RELAY_MODELS:
        mine = [x for x in missing if x[0] == m]
        print(f"{m}: {len(mine)} missing")
        for _, p, v, k in mine:
            print(f"  {p}__{v}__s{k}.txt")


if __name__ == "__main__":
    {"export": export, "import": import_all, "status": status}[sys.argv[1]]()
