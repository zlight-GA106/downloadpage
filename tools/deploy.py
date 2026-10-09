#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deploy the 工具下载 site as an nginx container on the configured host.

Everything about the target (host, user, password, directory, container name,
ports, upstream) comes from tools/deploy.env - see tools/config.py.

Non-destructive by design:
  * uploads only into DEPLOY_DIR, a directory this project owns,
  * never touches any pre-existing container, image, volume or file,
  * only ever removes/recreates the container literally named DEPLOY_CONTAINER.
"""
import os
import posixpath
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config                                                 # noqa: E402
from sshrun import connect, run, put_dir, sftp_makedirs       # noqa: E402

# Assets this project previously shipped and no longer references. Only these
# exact names, only inside our own directory, are ever removed from the host.
SUPERSEDED = ("site/images/logo.gif", "site/images/tile.gif",
              "site/images/tile_s.gif", "site/images/arrow.gif")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SITE = os.path.join(ROOT, "site")
CONF = os.path.join(ROOT, "deploy", "nginx.conf")


def render_conf():
    """deploy/nginx.conf with the upstream address substituted in."""
    with open(CONF, encoding="utf-8") as f:
        text = f.read()
    return text.replace("{{EU_UPSTREAM}}", config.get("EU_UPSTREAM"))


def step(c, cmd, label, timeout=300):
    rc, out, err = run(c, cmd, timeout)
    tail = (out or "").strip()
    if err.strip():
        tail += ("\n" if tail else "") + err.strip()
    print("\n$ %s\n%s" % (label, tail))
    return rc, out, err


def main():
    host = config.get("DEPLOY_HOST")
    host_dir = config.get("DEPLOY_DIR")
    name = config.get("DEPLOY_CONTAINER")
    image = config.get("DEPLOY_IMAGE")
    port = config.get_int("SITE_PORT")
    upstream = config.get("EU_UPSTREAM")

    print("target: %s" % config.summary())

    c = connect()
    try:
        # 1. host directory + upload ------------------------------------
        sftp = c.open_sftp()
        sftp_makedirs(sftp, host_dir)
        sftp.close()

        n = put_dir(c, SITE, host_dir + "/site")
        sftp = c.open_sftp()
        with sftp.open(host_dir + "/nginx.conf", "wb") as fh:
            fh.write(render_conf().encode("utf-8"))
        sftp.chmod(host_dir + "/nginx.conf", 0o644)
        sftp.close()
        print("uploaded %d site file(s) + nginx.conf -> %s" % (n, host_dir))

        # 2. retire assets this project itself shipped earlier -------------
        for rel in SUPERSEDED:
            step(c, "test -e %s/%s && rm -f %s/%s && echo removed %s || echo absent %s"
                 % (host_dir, rel, host_dir, rel, rel, rel), "retire %s" % rel)

        # 3. permissions: the nginx worker (uid 101) must be able to read.
        #    a+rX gives every directory the execute bit and leaves regular
        #    files non-executable. (Do NOT use `chmod 644 dir/*`: the glob
        #    also matches sub-directories and strips their execute bit.)
        step(c, "chmod -R a+rX %s" % host_dir, "fix permissions")
        step(c, "ls -l %s && echo --- && ls -l %s/site && echo --- && ls -l %s/site/images | head -4"
             % (host_dir, host_dir, host_dir), "list")

        # 4. (re)create only our own container --------------------------
        rc, out, _ = run(c, "docker inspect -f '{{.Name}}' %s 2>/dev/null" % name)
        if out.strip():
            print("\ncontainer %s exists -> recreating it (ours only)" % name)
            step(c, "docker rm -f %s" % name, "docker rm -f %s" % name)

        docker_run = (
            "docker run -d --name {n} --restart unless-stopped "
            "-p {p}:80 "
            "-v {d}/site:/usr/share/nginx/html:ro "
            "-v {d}/nginx.conf:/etc/nginx/conf.d/default.conf:ro "
            "{img}"
        ).format(n=name, p=port, d=host_dir, img=image)
        step(c, docker_run, "docker run")

        # 5. verify ------------------------------------------------------
        step(c, "sleep 3; docker ps --filter name=%s --format '{{.Names}} | {{.Image}} | {{.Status}} | {{.Ports}}'" % name,
             "docker ps")

        rc, out, err = run(c, "docker logs %s 2>&1 | tail -20" % name)
        print("\n--- container log ---\n%s%s" % (out, err))

        # 6. in-container reachability of the upstream -------------------
        step(c, "docker exec %s wget -qO- 'http://%s/api/v1/announcements' | head -c 200"
             % (name, upstream), "container -> EasyUpdate API")

        # 7. host-side reachability --------------------------------------
        checks = "".join(
            "curl -s -o /dev/null -w '%s %%{http_code} %%{size_download}\\n' "
            "http://127.0.0.1:%d%s ; " % (label, port, path)
            for label, path in (
                ("index.html", "/"), ("style.css", "/style.css"),
                ("catalog.js", "/catalog.js"), ("logo.png", "/images/logo.png"),
                ("favicon", "/favicon.ico"), ("api json", "/api/v1/announcements")))
        step(c, checks, "host -> site")

        print("\ndeployed: http://%s:%d/" % (host, port))
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
