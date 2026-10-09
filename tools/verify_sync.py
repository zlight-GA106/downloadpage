#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare the local site/ tree against what is actually deployed, by hash."""
import hashlib
import os
import posixpath
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config                                                      # noqa: E402
from sshrun import connect, run                                    # noqa: E402

HOST_DIR = config.get("DEPLOY_DIR")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SITE = os.path.join(ROOT, "site")

SKIP = {".DS_Store", "Thumbs.db"}


def local_hashes():
    out = {}
    for root, _dirs, files in os.walk(SITE):
        for f in files:
            if f in SKIP:
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, SITE).replace("\\", "/")
            with open(full, "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
    return out


def remote_hashes(c):
    rc, out, err = run(c, "cd %s/site && find . -type f -print0 | "
                          "xargs -0 sha256sum" % HOST_DIR)
    if rc != 0:
        raise SystemExit("remote hash failed: %s%s" % (out, err))
    res = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        h, _, name = line.partition("  ")
        if not name:
            continue
        res[name.lstrip("./")] = h
    return res


def main():
    c = connect()
    try:
        loc = local_hashes()
        rem = remote_hashes(c)
    finally:
        c.close()

    only_local = sorted(set(loc) - set(rem))
    only_remote = sorted(set(rem) - set(loc))
    differ = sorted(k for k in set(loc) & set(rem) if loc[k] != rem[k])

    print("local=%d remote=%d" % (len(loc), len(rem)))
    for k in only_local:
        print("  MISSING ON SERVER : %s" % k)
    for k in only_remote:
        print("  STALE ON SERVER   : %s" % k)
    for k in differ:
        print("  CONTENT DIFFERS   : %s" % k)
    if not (only_local or only_remote or differ):
        print("  in sync")
    return 0 if not (only_local or only_remote or differ) else 1


if __name__ == "__main__":
    sys.exit(main())
