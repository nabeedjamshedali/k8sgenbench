"""D4 requirement checks for P03, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

GRAFANA = "grafana/grafana"


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-grafana-deployed", GRAFANA)
    c.persistent("R02-data-persistent", GRAFANA, "/var/lib/grafana")
    c.external("R03-ui-external", GRAFANA, 3000)
    return c.results
