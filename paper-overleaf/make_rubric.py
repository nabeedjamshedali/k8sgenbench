"""Put the CEP handout (all 4 pages) in front of the report, with the group's names and roll numbers in the rubric.

    python paper-overleaf/make_rubric.py "<path to Complex Engineering Problem_CC_Fall26.pdf>"

Writes figures/rubric_filled.pdf, which main.tex places in front of the report. The rubric page's course title
("Network & Information Security" in the handout) is set to the course's actual title, Cloud Computing.
"""
import os
import sys

import fitz  # PyMuPDF

MEMBERS = [("Nabeed Ali", "SE-23054"), ("Talha Hussain", "SE-23062")]  # (name, roll number)
HERE = os.path.dirname(os.path.abspath(__file__))

doc = fitz.open(sys.argv[1])
page = doc[2]  # the rubric page
# Course title line, found with page.get_text("dict"): Times New Roman Bold, 12 pt.
page.add_redact_annot(fitz.Rect(150, 109.2, 420, 121.8), fill=(1, 1, 1))
# The group has two members: remove the empty rows S3 and S4 (y 216.0-242.4, below S2's bottom border).
page.add_redact_annot(fitz.Rect(80, 216.1, 530, 242.8), fill=(1, 1, 1))
page.apply_redactions()
title = "Course Title: Cloud Computing"
width = fitz.get_text_length(title, fontname="Times-Bold", fontsize=12)
page.insert_text(((page.rect.width - width) / 2, 119.3), title, fontname="Times-Bold", fontsize=12)
# Rows S1, S2 of the "Group Members" table: text baselines found with page.get_text("words").
for (name, roll), y in zip(MEMBERS, (199.0, 212.0)):
    page.insert_text((160, y), name, fontname="Times-Roman", fontsize=10)
    page.insert_text((455, y), roll, fontname="Times-Roman", fontsize=10)
doc.save(os.path.join(HERE, "figures", "rubric_filled.pdf"))
print("figures/rubric_filled.pdf written:", doc.page_count, "pages")
