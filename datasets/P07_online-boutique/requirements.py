"""D4 requirement checks for P07, derived from fact_sheet.md only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "common"))
from reqlib import Checker

PREFIX = "us-central1-docker.pkg.dev/online-boutique-ci/microservices-demo/"
FRONTEND = PREFIX + "frontend"
CART = PREFIX + "cartservice"
CATALOG = PREFIX + "productcatalogservice"
CURRENCY = PREFIX + "currencyservice"
PAYMENT = PREFIX + "paymentservice"
SHIPPING = PREFIX + "shippingservice"
EMAIL = PREFIX + "emailservice"
CHECKOUT = PREFIX + "checkoutservice"
RECOMMENDATION = PREFIX + "recommendationservice"
AD = PREFIX + "adservice"
LOADGEN = PREFIX + "loadgenerator"
REDIS = "redis"

PORTS = {FRONTEND: 8080, CART: 7070, CATALOG: 3550, CURRENCY: 7000, PAYMENT: 50051, SHIPPING: 50051,
         EMAIL: 8080, CHECKOUT: 5050, RECOMMENDATION: 8080, AD: 9555, REDIS: 6379}


def addr_routes(c, rid, image, var, target):
    """`var` in `image` is host:port of a Service that routes to `target` on its documented port.

    oracle: the exact env var NAME (e.g. PRODUCT_CATALOG_SERVICE_ADDR) that each service reads is
    hardcoded in its Go/Java/Python/C# source, which is not part of docs_bundle/ (only Dockerfiles
    and the README are bundled). A model cannot discover this name from what it was given.
    """
    found = [c.m.env(w, ct, var) for w, ct in c.m.workloads_with_image(image)]
    if not found:
        return c.check(rid, False, f"no workload runs {image}", oracle=True)
    pairs = c.m.exposed(target, PORTS[target])
    bad = []
    for v in found:
        if not v or v == "?" or ":" not in v:
            bad.append(repr(v))
            continue
        host, port = v.rsplit(":", 1)
        host = host.split(".")[0]
        if not any(s["metadata"]["name"] == host and str(p.get("port")) == port for s, p in pairs):
            bad.append(v)
    c.check(rid, not bad, f"{var}={found}" + (f" does not reach {target.rsplit('/', 1)[-1]}:{PORTS[target]}" if bad else ""),
            oracle=True)


def check(docs):
    c = Checker(docs)
    # oracle=True below: PREFIX (the real us-central1-docker.pkg.dev/... registry path) is NOT
    # recoverable from docs_bundle/. provenance.md traces it to docs/releasing/README.md and
    # make-release.sh in the real repo, neither of which is included in docs_bundle/ (which only
    # has the per-service Dockerfiles and README.md, with no final push-image declaration
    # anywhere). A model given only docs_bundle/ cannot discover this exact registry path, so
    # matching against it is diagnostic-only ("did it happen to guess/know the real production
    # registry"), never a scored D4 requirement. This mirrors the same oracle reasoning already
    # applied to addr_routes() below for env var names. See PROGRESS.md Phase R1 for the pipeline
    # run that surfaced this (every model except one that reproduced the real registry from prior
    # knowledge scored near-zero on these checks before this fix).
    for i, img in enumerate([FRONTEND, CART, CATALOG, CURRENCY, PAYMENT, SHIPPING, EMAIL, CHECKOUT,
                             RECOMMENDATION, AD, LOADGEN, REDIS], 1):
        c.image_deployed(f"R{i:02d}-{img.rsplit('/', 1)[-1]}-deployed", img, oracle=True)

    # Scored (non-oracle) counterpart: the canonical service name itself (e.g. "frontend",
    # "cartservice") IS recoverable from docs_bundle/ -- it's literally the Dockerfile filename
    # (<name>.Dockerfile) -- even though the exact production image path above is not. This still
    # requires a real, identifiable workload per component; it just doesn't demand the un-knowable
    # registry.
    for token in ["frontend", "cartservice", "productcatalogservice", "currencyservice",
                 "paymentservice", "shippingservice", "emailservice", "checkoutservice",
                 "recommendationservice", "adservice", "loadgenerator"]:
        c.component_present(f"R{token}-component-present", token)

    for i, img in enumerate([FRONTEND, CART, CATALOG, CURRENCY, PAYMENT, SHIPPING, EMAIL, CHECKOUT,
                             RECOMMENDATION, AD, REDIS], 13):
        c.exposed(f"R{i:02d}-{img.rsplit('/', 1)[-1]}-port-{PORTS[img]}", img, PORTS[img], oracle=True)

    c.env_equals("R24-currency-port", CURRENCY, "PORT", "7000", oracle=True)
    c.env_equals("R25-payment-port", PAYMENT, "PORT", "50051", oracle=True)

    n = 26
    for var, target in [("PRODUCT_CATALOG_SERVICE_ADDR", CATALOG), ("CURRENCY_SERVICE_ADDR", CURRENCY),
                        ("CART_SERVICE_ADDR", CART), ("RECOMMENDATION_SERVICE_ADDR", RECOMMENDATION),
                        ("CHECKOUT_SERVICE_ADDR", CHECKOUT), ("SHIPPING_SERVICE_ADDR", SHIPPING),
                        ("AD_SERVICE_ADDR", AD)]:
        addr_routes(c, f"R{n:02d}-frontend-{var}", FRONTEND, var, target)
        n += 1
    c.env_set(f"R{n:02d}-frontend-SHOPPING_ASSISTANT_SERVICE_ADDR", FRONTEND, "SHOPPING_ASSISTANT_SERVICE_ADDR", oracle=True)
    n += 1
    for var, target in [("PRODUCT_CATALOG_SERVICE_ADDR", CATALOG), ("SHIPPING_SERVICE_ADDR", SHIPPING),
                        ("PAYMENT_SERVICE_ADDR", PAYMENT), ("EMAIL_SERVICE_ADDR", EMAIL),
                        ("CURRENCY_SERVICE_ADDR", CURRENCY), ("CART_SERVICE_ADDR", CART)]:
        addr_routes(c, f"R{n:02d}-checkout-{var}", CHECKOUT, var, target)
        n += 1
    addr_routes(c, f"R{n:02d}-recommendation-PRODUCT_CATALOG_SERVICE_ADDR", RECOMMENDATION,
                "PRODUCT_CATALOG_SERVICE_ADDR", CATALOG)
    n += 1
    addr_routes(c, f"R{n:02d}-cart-REDIS_ADDR", CART, "REDIS_ADDR", REDIS)
    n += 1
    addr_routes(c, f"R{n:02d}-loadgenerator-FRONTEND_ADDR", LOADGEN, "FRONTEND_ADDR", FRONTEND)
    n += 1
    c.external(f"R{n:02d}-frontend-external", FRONTEND, 8080, oracle=True)
    return c.results


if __name__ == "__main__":
    import yaml
    docs = []
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            docs += list(yaml.safe_load_all(f))
    for r in check(docs):
        print(f"{'PASS' if r['passed'] else 'FAIL'} {r['id']}: {r['detail']}")
