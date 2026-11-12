"""Inline sections/*.tex into a single main.tex and copy the files Overleaf needs into overleaf_files/."""
import io
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "overleaf_files")
FILES = ["references.bib", "cas-dc.cls", "cas-common.sty", "cas-model2-names.bst"]

os.makedirs(OUT, exist_ok=True)
main = io.open(os.path.join(HERE, "main.tex"), encoding="utf-8").read()


def inline(match):
    path = os.path.join(HERE, match.group(1) + ".tex")
    return io.open(path, encoding="utf-8").read().strip()


# Repeat: sections themselves \input generated tables. Commented-out \input lines are left alone.
while re.search(r"(?m)^[^%\n]*\\input\{", main):
    main = re.sub(r"(?m)^([^%\n]*)\\input\{([^}]+)\}",
                  lambda m: m.group(1) + io.open(os.path.join(HERE, m.group(2) + ".tex"), encoding="utf-8").read().strip(),
                  main)
io.open(os.path.join(OUT, "main.tex"), "w", encoding="utf-8").write(main)
for f in FILES:
    shutil.copy(os.path.join(HERE, f), os.path.join(OUT, f))
figs = os.path.join(HERE, "figures")
if os.path.isdir(figs):
    os.makedirs(os.path.join(OUT, "figures"), exist_ok=True)
    for f in os.listdir(figs):
        if f.endswith(".pdf"):
            shutil.copy(os.path.join(figs, f), os.path.join(OUT, "figures", f))
print("overleaf_files/ updated:", ", ".join(["main.tex"] + FILES + ["figures/*.pdf"]))
