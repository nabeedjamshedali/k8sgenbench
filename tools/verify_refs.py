"""Verify every BibTeX entry cited in a .tex file.

Usage: python verify_refs.py references.bib paper.tex [more.tex ...]

DOI   -> Crossref (title, first author, year); falls back to doi.org handle resolution
arXiv -> arXiv abstract page metadata (title, first author)
URL   -> HTTP status 2xx/3xx
"""
import difflib
import io
import json
import re
import subprocess
import sys
import time


def fetch(url, timeout=40):
    """Return (http_code, body) using curl, which avoids arXiv/Crossref blocks on urllib."""
    out = subprocess.run(
        ["curl", "-sL", "-A", "Mozilla/5.0 (lit-review verifier)", "-m", str(timeout),
         "-w", "\n__HTTP__%{http_code}", url],
        capture_output=True,
    )
    raw = out.stdout.decode("utf-8", errors="ignore")
    body, _, code = raw.rpartition("\n__HTTP__")
    return int(code or 0), body


def norm(s):
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = re.sub(r"[{}\\'\"`^~]", "", s)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def surname(authors):
    first = authors.split(" and ")[0].strip()
    return norm(first.split(",")[0] if "," in first else first.split()[-1])


def author_in(authors, haystack):
    """Multi-word surnames ('Santos Vargas') may be reordered by the source, so any token counts."""
    return any(tok in haystack.split() for tok in surname(authors).split())


def parse_bib(text):
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", text, re.S):
        fields = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}", m.group(3)):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries[m.group(2)] = (m.group(1).lower(), fields)
    return entries


def meta(html, name):
    return [v for v in re.findall(r'<meta name="%s" content="([^"]*)"' % name, html)]


def check_doi(f):
    code, body = fetch("https://api.crossref.org/works/" + f["doi"])
    if code == 200:
        msg = json.loads(body)["message"]
        title = (msg.get("title") or [""])[0]
        year = str((msg.get("issued", {}).get("date-parts") or [[0]])[0][0])
        fams = norm(" ".join(a.get("family", "") for a in msg.get("author", [])))
        s = sim(f.get("title", ""), title)
        au = (not fams) or author_in(f.get("author", ""), fams)
        yr = not f.get("year") or abs(int(year or 0) - int(f["year"])) <= 1
        return s > 0.85 and au and yr, f"Crossref title~{s:.2f} author={au} year={year} | {title[:70]}"
    code, body = fetch("https://doi.org/api/handles/" + f["doi"])
    if code == 200 and '"responseCode":1' in body.replace(" ", ""):
        target = re.search(r'"type":"URL","data":\{"format":"string","value":"([^"]+)"', body.replace(" ", ""))
        return True, f"DOI registered (not in Crossref) -> {target.group(1) if target else '?'}; confirm title on that page"
    return False, f"DOI not found (Crossref {code})"


def check_arxiv(f):
    code, html = fetch("https://arxiv.org/abs/" + f["eprint"])
    if code != 200:
        return False, f"arXiv HTTP {code}"
    title = (meta(html, "citation_title") or [""])[0]
    authors = norm(" ".join(meta(html, "citation_author")))
    s = sim(f.get("title", ""), title)
    au = author_in(f.get("author", ""), authors)
    return s > 0.85 and au, f"arXiv title~{s:.2f} author={au} | {title[:70]}"


def check_url(url):
    code, _ = fetch(url)
    if code in (401, 403, 429):
        return False, f"HTTP {code} BLOCKED (bot protection) - open in a browser and verify manually: {url}"
    return 200 <= code < 400, f"HTTP {code} {url}"


def main():
    bib = parse_bib(io.open(sys.argv[1], encoding="utf-8").read())
    tex = " ".join(io.open(p, encoding="utf-8").read() for p in sys.argv[2:])
    cited = set()
    for m in re.finditer(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex):
        cited.update(k.strip() for k in m.group(1).split(",") if k.strip())

    failed, missing = [], sorted(cited - set(bib))
    for key in sorted(cited & set(bib)):
        _, f = bib[key]
        checks = []
        if f.get("doi"):
            checks.append(("DOI",) + check_doi(f))
            time.sleep(0.3)
        if f.get("eprint"):
            checks.append(("arXiv",) + check_arxiv(f))
            time.sleep(1.0)
        if not any(c[1] for c in checks):
            url = f.get("url") or next(iter(re.findall(r"\\url\{([^}]*)\}", f.get("howpublished", ""))), None)
            if url:
                checks.append(("URL",) + check_url(url))
        if not checks:
            checks.append(("NONE", False, "no doi/eprint/url - add one or remove the citation"))
        ok = any(c[1] for c in checks)
        if not ok:
            failed.append(key)
        print(f"[{'PASS' if ok else 'FAIL'}] {key}")
        for kind, good, info in checks:
            print(f"    {kind:5} {'ok ' if good else 'BAD'} {info}")

    print(f"\ncited={len(cited)} passed={len(cited & set(bib)) - len(failed)} "
          f"failed={failed} missing_from_bib={missing}")
    sys.exit(1 if failed or missing else 0)


if __name__ == "__main__":
    main()
