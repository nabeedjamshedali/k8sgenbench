"""Pre-submission consistency check: undefined references, missing citation keys, missing figures, open TODOs.

Usage: python paper/check_paper.py
"""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

files = ["main.tex"] + sorted(glob.glob("sections/*.tex")) + sorted(glob.glob("tables/*.tex"))
raw = "\n".join(open(f, encoding="utf-8").read() for f in files)
code = "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in raw.splitlines())  # drop comments

labels = set(re.findall(r"\\label\{([^}]+)\}", code))
refs = set(re.findall(r"\\(?:ref|autoref|eqref|cref)\{([^}]+)\}", code))
cites = {k.strip() for grp in re.findall(r"\\cite[a-z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}", code) for k in grp.split(",")}
bib = set(re.findall(r"@\w+\{([^,\s]+),", open("references.bib", encoding="utf-8").read()))
figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", code)

print("undefined refs      :", sorted(refs - labels) or "none")
print("missing bib keys    :", sorted(cites - bib) or "none")
print("missing figures     :", [f for f in figs if not os.path.exists(f)] or "none")
print("labels never ref'd  :", sorted(labels - refs))
print("bib never cited     :", len(bib - cites), sorted(bib - cites))
print("TODO-FINAL markers  :", raw.count("TODO-FINAL"))
