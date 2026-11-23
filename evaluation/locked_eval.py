"""eval_runner.py --runtime under the shared cluster lock (the one repair_loop.evaluate takes), so a baseline evaluation
never deploys while a guided round is deployed.

Usage: python evaluation/locked_eval.py <source> <project> <variant> <sample_k>
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, "cluster.lock")

src, project, variant, k = sys.argv[1:5]
while True:
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"{src} {project} {variant} s{k} pid {os.getpid()}".encode())
        os.close(fd)
        break
    except FileExistsError:
        time.sleep(10)
try:
    r = subprocess.run([sys.executable, os.path.join(HERE, "eval_runner.py"), src, project, variant, k, "--runtime"],
                       cwd=HERE, timeout=3600)
    sys.exit(r.returncode)
finally:
    os.unlink(LOCK)
