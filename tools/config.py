#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deployment configuration.

Nothing here is secret: every value can be overridden by an environment
variable or by a deploy.env file sitting next to this script. deploy.env is
git-ignored on purpose - it is where the SSH password and the EasyUpdate admin
password belong, never in the source tree.

Lookup order for a key:

    1. os.environ[KEY]
    2. tools/deploy.env          (git-ignored, copy deploy.env.example)
    3. the built-in default below

Copy deploy.env.example to deploy.env and fill it in before deploying:

    Copy-Item tools\\deploy.env.example tools\\deploy.env
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(HERE, "deploy.env")

# key -> (default, comment). A default of None means "must be provided";
# an empty string means "optional, absence is fine".
DEFAULTS = {
    # --- ssh target -------------------------------------------------------
    "DEPLOY_HOST": (None, "SSH host of the server that runs the site"),
    "DEPLOY_USER": (None, "SSH user"),
    "DEPLOY_PASS": ("", "SSH password, or leave empty and use a key"),
    "DEPLOY_KEY": ("", "path to a private key file (alternative to DEPLOY_PASS)"),
    "DEPLOY_PORT": ("22", "SSH port"),

    # --- where the site lives on that server ------------------------------
    "DEPLOY_DIR": ("/home/%(user)s/tools-download",
                   "host directory bind-mounted into the container"),
    "DEPLOY_CONTAINER": ("tools-download-nginx",
                         "name of the container this project owns"),
    "DEPLOY_IMAGE": ("nginx:alpine", "image used for the container"),
    "SITE_PORT": ("8080", "host port the site is published on"),

    # --- the EasyUpdate service the site fronts ---------------------------
    "EU_BASE": ("http://127.0.0.1:19910",
                "base URL of EasyUpdate, as reachable from this build machine"),
    "EU_UPSTREAM": ("127.0.0.1:19910",
                    "same service as reachable from inside the container"),
    "EU_USER": ("admin", "EasyUpdate admin user (catalogue harvesting only)"),
    "EU_PASS": ("", "EasyUpdate admin password"),

    # --- local preview ----------------------------------------------------
    "DEV_PORT": ("8099", "port used by tools/devserver.py"),
}

_cache = None


def _read_env_file():
    data = {}
    if not os.path.exists(ENV_FILE):
        return data
    with open(ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            data[k.strip()] = v
    return data


def get(key):
    global _cache
    if _cache is None:
        _cache = _read_env_file()
    if key in os.environ and os.environ[key] != "":
        return os.environ[key]
    if key in _cache and _cache[key] != "":
        return _cache[key]
    default = DEFAULTS.get(key, (None, ""))[0]
    if default is None:
        raise SystemExit(
            "missing configuration: %s\n"
            "Copy tools/deploy.env.example to tools/deploy.env and fill it in, "
            "or set the %s environment variable." % (key, key))
    return default.replace("%(user)s", get("DEPLOY_USER") or "user")


def get_int(key):
    return int(get(key))


def has_password():
    """True when a password is configured; otherwise a key or the ssh-agent
    is expected to satisfy authentication."""
    global _cache
    if _cache is None:
        _cache = _read_env_file()
    return bool(os.environ.get("DEPLOY_PASS") or _cache.get("DEPLOY_PASS"))


def summary():
    """One-line description of the target, safe to print (no secrets)."""
    return "%s@%s:%s  dir=%s  container=%s  port=%s" % (
        get("DEPLOY_USER"), get("DEPLOY_HOST"), get("DEPLOY_PORT"),
        get("DEPLOY_DIR"), get("DEPLOY_CONTAINER"), get("SITE_PORT"))
