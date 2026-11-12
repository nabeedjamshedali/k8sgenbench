"""
Runs one (model, project, prompt_variant, sample) generation and stores it at
generation/outputs/<model>/<project>/<variant>/s<k>/{request.json,response_raw.json,
manifest.yaml,extraction.json}, per the design doc section 5.5.

Usage: python generation/generate.py <model_slot> <project> <neutral|production> <sample_k>
Example: python generation/generate.py gemini P05_emojivoto neutral 1
"""
import datetime
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent
DATASETS = ROOT / "datasets"

CONFIG = yaml.safe_load((HERE / "models.yaml").read_text())


def load_env():
    env = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    return env


def build_user_prompt(project, variant):
    bundle_dir = DATASETS / project / "docs_bundle"
    parts = []
    for f in sorted(bundle_dir.iterdir()):
        if f.is_file():
            parts.append(f"--- {f.name} ---\n{f.read_text(encoding='utf-8', errors='replace')}")
    instruction = (HERE / "prompts" / f"{variant}.md").read_text().strip()
    return "\n\n".join(parts) + "\n\n" + instruction


def extract_yaml(text):
    """All ```yaml/```yml blocks, plus unlabelled blocks that contain apiVersion, joined as one
    multi-document stream (long responses often split manifests across blocks); other-language
    blocks (bash, etc.) are ignored."""
    blocks = [body.strip() for lang, body in re.findall(r"```([A-Za-z0-9_-]*)[^\n]*\n(.*?)```", text, re.DOTALL)
              if lang.lower() in ("yaml", "yml") or (not lang and "apiVersion" in body)]
    if blocks:
        return "\n---\n".join(blocks), "fenced_block" if len(blocks) == 1 else f"fenced_blocks_joined({len(blocks)})"
    return text.strip(), "whole_text_fallback"


def post_with_retry(url, **kwargs):
    # Design doc 5.3: no retries on content, only on transport errors (429/5xx), with backoff.
    delays = [5, 15, 40]
    for i, delay in enumerate([0] + delays):
        if delay:
            time.sleep(delay)
        r = httpx.post(url, **kwargs)
        if r.status_code not in (429, 500, 502, 503, 504):
            return r
        last = r
    return last


def call_gemini(env, prompt):
    model_id = CONFIG["models"]["gemini"]["model_id"]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": CONFIG["system_prompt"]}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": CONFIG["temperature"],
            "maxOutputTokens": CONFIG["max_tokens"],
        },
    }
    t0 = time.time()
    # Key in a header, not the query string: httpx error messages print the URL, which leaked it into logs.
    # GEMINI_KEY_VAR picks which .env key to use (a second project's key when the first's daily quota is spent);
    # the model and parameters are unchanged.
    key = env[env.get("GEMINI_KEY_VAR", "GEMINI_API_KEY")]
    r = post_with_retry(url, headers={"x-goog-api-key": key}, json=payload, timeout=180)
    latency = time.time() - t0
    r.raise_for_status()
    data = r.json()
    # A reply can carry no text parts (e.g. MAX_TOKENS spent entirely on thinking); record it as empty, don't crash.
    parts = data["candidates"][0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    usage = data.get("usageMetadata", {})
    return text, data, latency, usage.get("promptTokenCount"), usage.get("candidatesTokenCount")


def call_groq(env, prompt, model_id):
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": CONFIG["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        "temperature": CONFIG["temperature"],
        "max_tokens": CONFIG["max_tokens"],
    }
    t0 = time.time()
    r = post_with_retry(url, headers={"Authorization": f"Bearer {env['GROQ_API_KEY']}"}, json=payload, timeout=180)
    latency = time.time() - t0
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, data, latency, usage.get("prompt_tokens"), usage.get("completion_tokens")


def call_openai(env, prompt, model_id):
    """OpenAI Chat Completions. Reasoning models take max_completion_tokens (reasoning tokens count against it,
    as with Gemini's thinking) and may reject a non-default temperature; in that case the request is re-sent
    once without it and the response is tagged, so the deviation is recorded rather than hidden."""
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": CONFIG["system_prompt"]},
            {"role": "user", "content": prompt},
        ],
        "temperature": CONFIG["temperature"],
        "max_completion_tokens": CONFIG["max_tokens"],
    }
    headers = {"Authorization": f"Bearer {env['OPENAI_API_KEY']}"}
    t0 = time.time()
    r = post_with_retry(url, headers=headers, json=payload, timeout=600)
    temperature_applied = True
    if r.status_code == 400 and "temperature" in r.text:
        payload.pop("temperature")
        temperature_applied = False
        r = post_with_retry(url, headers=headers, json=payload, timeout=600)
    latency = time.time() - t0
    r.raise_for_status()
    data = r.json()
    data["_k8sgen_temperature_applied"] = temperature_applied
    text = data["choices"][0]["message"].get("content") or ""
    usage = data.get("usage", {})
    return text, data, latency, usage.get("prompt_tokens"), usage.get("completion_tokens")


def main():
    model_slot, project, variant, k = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    assert variant in ("neutral", "production")
    model_cfg = CONFIG["models"][model_slot]
    if model_cfg["status"] != "active":
        print(f"SKIP: {model_slot} is status={model_cfg['status']}, not active")
        sys.exit(1)

    env = load_env()
    prompt = build_user_prompt(project, variant)
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

    provider = model_cfg["provider"]
    if provider == "gemini":
        text, raw, latency, tin, tout = call_gemini(env, prompt)
    elif provider == "groq":
        text, raw, latency, tin, tout = call_groq(env, prompt, model_cfg["model_id"])
    elif provider == "openai":
        text, raw, latency, tin, tout = call_openai(env, prompt, model_cfg["model_id"])
    else:
        print(f"SKIP: provider '{provider}' not handled by this script (handled separately)")
        sys.exit(1)

    manifest, status = extract_yaml(text)

    out_dir = HERE / "outputs" / model_slot / project / variant / f"s{k}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "request.json").write_text(json.dumps({
        "model_id": model_cfg["model_id"],
        "provider": provider,
        # None when the provider rejected a non-default temperature and the model's default was used
        "temperature": CONFIG["temperature"] if raw.get("_k8sgen_temperature_applied", True) else None,
        "max_tokens": CONFIG["max_tokens"],
        "prompt_hash": prompt_hash,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2))

    (out_dir / "response_raw.json").write_text(json.dumps({
        "raw": raw,
        "latency_s": latency,
        "tokens_in": tin,
        "tokens_out": tout,
    }, indent=2))

    (out_dir / "manifest.yaml").write_text(manifest)

    (out_dir / "extraction.json").write_text(json.dumps({
        "status": status,
    }, indent=2))

    print(f"OK: {model_slot}/{project}/{variant}/s{k} -> {out_dir}")


if __name__ == "__main__":
    main()
