"""What has changed here since the last upload to GitHub.

    python scripts/since_upload.py          the summary
    python scripts/since_upload.py --files  with every file changed

Compares this copy with origin/main as this computer last saw it (a push or
a fetch brings that up to date; nothing here goes online). Shows the version
on GitHub and the one here, the changelog entries that are new or reworded,
the commits not uploaded yet, and anything changed but not committed.
Needs only Python 3 and git.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE = "origin/main"
ENTRY = re.compile(r"^\* \*\*([^*]+)\*\*", re.M)


def git(*args, ok=(0,)):
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    return r.stdout if r.returncode in ok else None


def at(rev, path):
    """A file's text at a commit ("" for the working copy), or None."""
    if rev:
        return git("show", f"{rev}:{path}")
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def version(rev):
    m = re.search(r'^version\s*=\s*"([^"]+)"', at(rev, "popup_pro/blender_manifest.toml") or "",
                  re.M)
    return m.group(1) if m else "?"


def entries(rev):
    """{version label: its text} from the changelog (or, before there was
    one, from the README's Version history)."""
    text = at(rev, "CHANGELOG.md")
    if text is None:
        text = (at(rev, "README.md") or "").partition("## Version history")[2]
        text = text.partition("\n## ")[0]
    starts = [m.start() for m in ENTRY.finditer(text)]
    out = {}
    for a, b in zip(starts, starts[1:] + [len(text)]):
        chunk = text[a:b].strip()
        chunk = chunk.split("\n\n")[0]  # (an entry ends at the first blank line)
        out[ENTRY.match(chunk).group(1)] = chunk
    return out


def squash(s):
    return " ".join(s.split())


def main():
    files = "--files" in sys.argv[1:]
    if git("rev-parse", "--verify", "-q", REMOTE) is None:
        print(f"No {REMOTE} here: this copy has never been pushed or fetched.")
        return 1
    when = (git("log", "-1", "--format=%cd", "--date=format:%d %b %Y", REMOTE) or "").strip()
    ahead = (git("log", "--format=%h %ad  %s", "--date=format:%d %b", f"{REMOTE}..HEAD")
             or "").splitlines()
    behind = (git("rev-list", "--count", f"HEAD..{REMOTE}") or "0").strip()
    dirty = [ln for ln in (git("status", "--porcelain") or "").splitlines() if ln.strip()]
    v_up, v_here = version(REMOTE), version("")

    print(f"On GitHub (as last seen here): v{v_up}, last commit {when}")
    print(f"Here:                          v{v_here}"
          + ("" if v_here != v_up else "  (same version)"))
    if not ahead and not dirty:
        print("\nNothing to upload: this copy matches the last upload.")
        return 0

    old, new = entries(REMOTE), entries("")
    fresh = [(k, v) for k, v in new.items() if k not in old]
    edited = [(k, v) for k, v in new.items() if k in old and squash(old[k]) != squash(v)]
    if fresh or edited:
        print("\nChangelog since the last upload:")
        for label, items in (("new", fresh), ("reworded", edited)):
            for _, text in items:
                print(f"\n  ({label})")
                for ln in text.splitlines():
                    print("  " + ln)
    else:
        print("\nNo changelog entries added since the last upload.")

    tags = [t for t in (git("tag", "--merged", "HEAD", "--no-merged", REMOTE,
                            "--sort=v:refname") or "").split()]
    if tags:
        print("\nTags not uploaded yet:", " ".join(tags), " (git push --tags)")

    print(f"\nCommits not uploaded yet: {len(ahead)}")
    for ln in ahead:
        print("  " + ln)
    if ahead:
        stat = (git("diff", "--shortstat", f"{REMOTE}..HEAD") or "").strip()
        print("  " + stat)
        if files:
            for ln in (git("diff", "--stat=100", f"{REMOTE}..HEAD") or "").splitlines()[:-1]:
                print("  " + ln)
    if dirty:
        print(f"\nChanged but not committed: {len(dirty)} file(s)")
        for ln in dirty[:20]:
            print("  " + ln)
        if len(dirty) > 20:
            print(f"  ... and {len(dirty) - 20} more")
    if behind != "0":
        print(f"\nGitHub has {behind} commit(s) this copy hasn't merged: pull before pushing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
