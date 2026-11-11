"""Run the test suite, several tests at a time, and say what passed.

    python tests/run_all.py                 every test
    python tests/run_all.py collars loops   only those families
    python tests/run_all.py v76 roofs       a family or part of a file's name
    python tests/run_all.py --list          the families and their tests

Run it with a Python that has bpy (`pip install bpy`). Each test is its own
script and runs in its own process; its output goes to tests/out/logs/. The
exit code is 0 only if every test passed.

Tests are named test_<family>_v<release>.py after the family they are mostly
about, and each has a `# families: a, b, c` line under its docstring naming
every family it touches (that line is what the filters above read).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
LOGS = os.path.join(OUT, "logs")
TIMES = os.path.join(OUT, "durations.json")
TAG = re.compile(r"^# families:\s*(.+)$", re.M)


def families(path):
    with open(path, encoding="utf-8") as f:
        m = TAG.search(f.read(4000))
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def discover():
    tests = {}
    for name in sorted(os.listdir(HERE)):
        if name.startswith("test_") and name.endswith(".py"):
            tests[name] = families(os.path.join(HERE, name))
    return tests


def wanted(tests, filters):
    if not filters:
        return list(tests)
    fl = [f.lower() for f in filters]
    known = {f for fams in tests.values() for f in fams}
    out = []
    for name, fams in tests.items():
        stem = name[len("test_"):-len(".py")]
        if any(f in fams if f in known else f in stem for f in fl):
            out.append(name)
    return out


def run_one(name, python, timeout):
    log = os.path.join(LOGS, name[:-3] + ".log")
    t0 = time.time()
    with open(log, "w", encoding="utf-8") as f:
        try:
            rc = subprocess.run([python, os.path.join(HERE, name)], stdout=f,
                                stderr=subprocess.STDOUT, timeout=timeout,
                                cwd=os.path.dirname(HERE)).returncode
        except subprocess.TimeoutExpired:
            f.write(f"\nTIMED OUT after {timeout:g} s\n")
            rc = -1
    return name, rc, time.time() - t0, log


def tail(path, n):
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip() for ln in f if ln.strip()]
    return lines[-n:]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("filters", nargs="*", help="families, or parts of test names")
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 2,
                    help="tests to run at once (default: one per CPU)")
    ap.add_argument("--list", action="store_true", help="list families and tests")
    ap.add_argument("--python", default=sys.executable,
                    help="the Python to run tests with (default: this one)")
    ap.add_argument("--timeout", type=float, default=1800.0,
                    help="seconds before a test is stopped (default 1800)")
    ap.add_argument("--tail", type=int, default=15,
                    help="lines of a failed test's log to show (default 15)")
    a = ap.parse_args()

    tests = discover()
    untagged = [n for n, fams in tests.items() if not fams]
    if a.list:
        by = {}
        for name, fams in tests.items():
            for f in fams:
                by.setdefault(f, []).append(name)
        for f in sorted(by):
            print(f"{f} ({len(by[f])})")
            for name in by[f]:
                print("   ", name)
        for name in untagged:
            print("no '# families:' line:", name)
        return 1 if untagged else 0

    names = wanted(tests, a.filters)
    if not names:
        print("No tests match", " ".join(a.filters), "(see --list)")
        return 2
    try:
        with open(TIMES, encoding="utf-8") as f:
            last = json.load(f)
    except (OSError, ValueError):
        last = {}
    names.sort(key=lambda n: -last.get(n, 1e9))  # slowest (and new) first
    os.makedirs(LOGS, exist_ok=True)
    jobs = max(1, min(a.jobs, len(names)))
    print(f"{len(names)} tests, {jobs} at a time, logs in {os.path.relpath(LOGS)}")

    t0 = time.time()
    failed, done = [], 0
    with ThreadPoolExecutor(jobs) as pool:
        futs = [pool.submit(run_one, n, a.python, a.timeout) for n in names]
        for fut in as_completed(futs):
            name, rc, secs, log = fut.result()
            done += 1
            last[name] = round(secs, 1)
            print(f"[{done:>{len(str(len(names)))}}/{len(names)}] "
                  f"{'ok  ' if rc == 0 else 'FAIL'} {secs:6.1f} s  {name}", flush=True)
            if rc != 0:
                failed.append((name, log))
    with open(TIMES, "w", encoding="utf-8") as f:
        json.dump(last, f, indent=0, sort_keys=True)

    for name, log in sorted(failed):
        print(f"\n---- {name} ({os.path.relpath(log)})")
        for ln in tail(log, a.tail):
            print("   ", ln)
    print(f"\n{len(names) - len(failed)} passed, {len(failed)} failed "
          f"in {time.time() - t0:.0f} s")
    if failed:
        print("Failed:", " ".join(n for n, _ in sorted(failed)))
    if untagged:
        print("No '# families:' line (add one):", " ".join(untagged))
    return 1 if failed or untagged else 0


if __name__ == "__main__":
    sys.exit(main())
