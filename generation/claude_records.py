"""Write pilot-style request/extraction/response_raw records for Claude subagent outputs that lack them.

Usage: python generation/claude_records.py
"""
import datetime
import hashlib
import json

from generate import HERE, build_user_prompt

NOTE = ("Generated via a fresh Claude Code subagent (no fork), not the Anthropic API -- temperature/max_tokens "
        "were not controllable this way. The subagent read only generation/relay/prompts/<project>__<variant>.txt "
        "and wrote only manifest.yaml. See generation/models.yaml for the full methodology-deviation note.")

for m in sorted((HERE / "outputs" / "claude").glob("*/*/s*/manifest.yaml")):
    d = m.parent
    if (d / "request.json").exists():
        continue
    project, variant = d.parent.parent.name, d.parent.name
    (d / "request.json").write_text(json.dumps({
        "model_id": "claude-sonnet-5-5", "provider": "claude_code_subagent", "temperature": None, "max_tokens": None,
        "prompt_hash": hashlib.sha256(build_user_prompt(project, variant).encode()).hexdigest()[:16],
        "timestamp": datetime.datetime.fromtimestamp(m.stat().st_mtime, datetime.timezone.utc).isoformat(),
        "note": NOTE}, indent=2))
    (d / "extraction.json").write_text(json.dumps({"status": "subagent_hand_back"}, indent=2))
    (d / "response_raw.json").write_text(json.dumps({"raw": None, "note": "Subagent wrote manifest.yaml directly; no provider-level usage/latency metadata available."}, indent=2))
    print("recorded", d.relative_to(HERE))
