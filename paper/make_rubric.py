"""Write the group's names and roll numbers into the CEP grading rubric (pages 3-4 of the course handout).

    python paper/make_rubric.py "<path to Complex Engineering Problem_CC_Fall26.pdf>"

Writes figures/rubric_filled.pdf, which main.tex places in front of the report.
"""
import os
import sys

import fitz  # PyMuPDF

MEMBERS = [("Nabeed Ali", ""), ("Talha Hussain", "")]  # (name, roll number)
HERE = os.path.dirname(os.path.abspath(__file__))

src = fitz.open(sys.argv[1])
out = fitz.open()
out.insert_pdf(src, from_page=2, to_page=3)  # the rubric pages
page = out[0]
# Rows S1, S2 of the "Group Members" table: text baselines found with page.get_text("words").
for (name, roll), y in zip(MEMBERS, (199.0, 212.0)):
    page.insert_text((160, y), name, fontname="Times-Roman", fontsize=10)
    page.insert_text((455, y), roll, fontname="Times-Roman", fontsize=10)
out.save(os.path.join(HERE, "figures", "rubric_filled.pdf"))
print("figures/rubric_filled.pdf written")
