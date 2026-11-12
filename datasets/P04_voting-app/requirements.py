"""D4 requirement checks for P04, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

VOTE = "dockersamples/examplevotingapp_vote"
RESULT = "dockersamples/examplevotingapp_result"
WORKER = "dockersamples/examplevotingapp_worker"
REDIS = "redis"
DB = "postgres"


def check(docs):
    c = Checker(docs)
    c.image_deployed("R01-vote-deployed", VOTE)
    c.image_deployed("R02-result-deployed", RESULT)
    c.image_deployed("R03-worker-deployed", WORKER)
    c.image_deployed("R04-redis-deployed", REDIS)
    c.image_deployed("R05-db-deployed", DB)
    c.service_named("R06-redis-hostname", "redis", REDIS, 6379)
    c.service_named("R07-db-hostname", "db", DB, 5432)
    c.env_equals("R08-db-user", DB, "POSTGRES_USER", "postgres")
    c.env_equals("R09-db-password", DB, "POSTGRES_PASSWORD", "postgres")
    c.persistent("R10-db-persistent", DB, "/var/lib/postgresql/data")
    c.external("R11-vote-external", VOTE, 80)
    c.external("R12-result-external", RESULT, 80)
    return c.results
