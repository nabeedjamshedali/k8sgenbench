"""D4 requirement checks for P05, derived from fact_sheet.md only."""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

WEB = "buoyantio/emojivoto-web"
EMOJI = "buoyantio/emojivoto-emoji-svc"
VOTING = "buoyantio/emojivoto-voting-svc"
BOT_CMD = "emojivoto-vote-bot"
MIRROR = "docker.l5d.io/"


def normalise(docs):
    """Strip the docker.l5d.io/ registry prefix so both published registries match."""
    docs = copy.deepcopy(docs)
    for d in docs:
        if not isinstance(d, dict):
            continue
        stack = [d]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                img = node.get("image")
                if isinstance(img, str) and img.startswith(MIRROR):
                    node["image"] = img[len(MIRROR):]
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    return docs


def is_bot(c):
    return any(BOT_CMD in str(x) for x in (c.get("command") or []) + (c.get("args") or []))


def web_containers(m, bot):
    return [(w, c) for w, c in m.workloads_with_image(WEB) if is_bot(c) == bot]


def env_values(m, pairs, name):
    return [m.env(w, c, name) for w, c in pairs]


def points_to(m, value, image, container_port):
    """True if `value` is host:port naming a Service whose port routes to `container_port` of `image`."""
    if not value or value == "?":
        return False
    v = value.split("://", 1)[-1].lstrip("/")
    host, _, port = v.rpartition(":")
    if not host or not port.isdigit():
        return False
    labels = host.split(".")
    name, ns = labels[0], (labels[1] if len(labels) > 1 and labels[1] != "svc" else None)
    for s, p in m.exposed(image, container_port):
        sns = s.get("metadata", {}).get("namespace")
        if s["metadata"]["name"] == name and p.get("port") == int(port) and (ns is None or sns in (None, ns)):
            return True
    return False


def check(docs):
    c = Checker(normalise(docs))
    m = c.m
    web = web_containers(m, bot=False)
    bot = web_containers(m, bot=True)

    c.check("R01-web-deployed", web, f"{len(web)} web server container(s)")
    c.image_deployed("R02-emoji-deployed", EMOJI)
    c.image_deployed("R03-voting-deployed", VOTING)
    c.check("R04-vote-bot-deployed", bot, f"{len(bot)} container(s) of {WEB} running {BOT_CMD}")

    v = env_values(m, web, "WEB_PORT")
    c.check("R05-web-port", web and all(x == "8080" for x in v), f"WEB_PORT={v}")
    c.env_equals("R06-emoji-grpc-port", EMOJI, "GRPC_PORT", "8080")
    c.env_equals("R07-voting-grpc-port", VOTING, "GRPC_PORT", "8080")

    v = env_values(m, web, "EMOJISVC_HOST")
    c.check("R08-emojisvc-host", web and all(points_to(m, x, EMOJI, 8080) for x in v), f"EMOJISVC_HOST={v}")
    v = env_values(m, web, "VOTINGSVC_HOST")
    c.check("R09-votingsvc-host", web and all(points_to(m, x, VOTING, 8080) for x in v), f"VOTINGSVC_HOST={v}")
    v = env_values(m, web, "INDEX_BUNDLE")
    c.check("R10-index-bundle", web and all(x == "dist/index_bundle.js" for x in v), f"INDEX_BUNDLE={v}")

    v = env_values(m, bot, "WEB_HOST")
    c.check("R11-bot-web-host", bot and all(points_to(m, x, WEB, 8080) for x in v), f"WEB_HOST={v}")

    c.external("R12-web-external", WEB, 8080)
    return c.results

