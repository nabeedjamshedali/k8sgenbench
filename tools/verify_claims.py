"""Check that every number/phrase quoted in the review appears in the cited PDF.

Usage: python verify_claims.py <papers_dir> <claims.json>
claims.json: {"2023_Rahman_Title.pdf": ["1,051", "13.9", "exact phrase"], ...}

Matching ignores whitespace and thousands separators, so "5,138" also matches
text extracted as "5, 138" or "5138".
"""
import io
import json
import os
import re
import sys

import fitz  # PyMuPDF


def squash(s):
    return re.sub(r"[\s,]", "", s.lower())


def main():
    papers, claims = sys.argv[1], json.load(io.open(sys.argv[2], encoding="utf-8"))
    missing = 0
    for pdf, needles in claims.items():
        path = os.path.join(papers, pdf)
        if not os.path.exists(path):
            print(f"NO-PDF  {pdf}")
            missing += len(needles)
            continue
        text = squash("".join(page.get_text() for page in fitz.open(path)))
        for n in needles:
            ok = squash(n) in text
            missing += not ok
            print(f"{'ok     ' if ok else 'MISSING'} {n:45} {pdf}")
    total = sum(len(v) for v in claims.values())
    print(f"\nclaims={total} found={total - missing} missing={missing}")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
