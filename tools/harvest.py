#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harvest the EasyUpdate catalogue into a baked, IE6-safe JS data file.

The public EasyUpdate API has no "list every app" endpoint, so the app list is
read from the authenticated admin pages at deploy time and emitted as a plain
JS object literal (no JSON.parse needed on the client).
Every non-ASCII character is emitted as a \\uXXXX escape so the generated file
is pure ASCII and immune to the browser's script-charset guessing.
"""
import json
import re
import os
import sys
import html as htmllib
import urllib.request
import urllib.parse
import http.cookiejar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config                                                     # noqa: E402

BASE = config.get("EU_BASE")
USER = config.get("EU_USER")
PWD = config.get("EU_PASS")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "build")


def make_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "easymarket-harvester/1.0")]
    return op


def get(op, path):
    with op.open(BASE + path, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    return htmllib.unescape(s).strip()


def parse_size(txt):
    """'15.3 MB' -> bytes (approx). Returns 0 when unparsable."""
    m = re.match(r"^\s*([\d.]+)\s*(B|KB|MB|GB)?\s*$", txt or "", re.I)
    if not m:
        return 0
    v = float(m.group(1))
    unit = (m.group(2) or "B").upper()
    return int(v * {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[unit])


def login(op):
    page = get(op, "/")
    m = re.search(r'name="csrf" value="([0-9a-f]+)"', page)
    if not m:
        raise SystemExit("could not find csrf token on login page")
    data = urllib.parse.urlencode(
        {"csrf": m.group(1), "username": USER, "password": PWD}).encode()
    with op.open(BASE + "/login", data=data, timeout=30) as r:
        body = r.read().decode("utf-8", "replace")
    if "退出" not in body:
        raise SystemExit("login failed")


def harvest_apps(op):
    page = get(op, "/admin/apps")
    body = page[page.find("<tbody"):]
    apps = []
    for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
        m = re.search(r'href="/admin/apps/(\d+)"><span class="app-icon">'
                      r'(.*?)</span>(.*?)</a>', row, re.S)
        if not m:
            continue
        pkg = re.search(r'data-label="包名"[^>]*>(.*?)</td>', row, re.S)
        latest = re.search(r'data-label="最新版本">(.*?)</td>', row, re.S)
        count = re.search(r'data-label="版本数">(.*?)</td>', row, re.S)
        apps.append({
            "id": int(m.group(1)),
            "letter": clean(m.group(2))[:1].upper(),
            "name": clean(m.group(3)),
            "pkg": clean(pkg.group(1)) if pkg else "",
            "latest_name": clean(latest.group(1)) if latest else "",
            "release_count": int(clean(count.group(1)) or 0) if count else 0,
            "desc": "",
            "releases": [],
        })
    return apps


def harvest_app_detail(op, app):
    page = get(op, "/admin/apps/%d" % app["id"])
    m = re.search(r'<p class="description">(.*?)</p>', page, re.S)
    app["desc"] = clean(m.group(1)) if m else ""

    idx = page.find("版本历史")
    if idx < 0:
        return
    body = page[idx:]
    tb = body.find("<tbody")
    te = body.find("</tbody>", tb)
    if tb < 0 or te < 0:
        return
    for row in re.findall(r"<tr>(.*?)</tr>", body[tb:te], re.S):
        rid = re.search(r'href="/admin/releases/(\d+)"', row)
        if not rid:
            continue
        ver = re.search(r'data-label="版本">.*?>(.*?)</a>', row, re.S)
        code = re.search(r'data-label="版本号"[^>]*>(.*?)</td>', row, re.S)
        stat = re.search(r'data-label="状态">(.*?)</td>', row, re.S)
        mand = re.search(r'data-label="强制更新">(.*?)</td>', row, re.S)
        size = re.search(r'data-label="大小">(.*?)</td>', row, re.S)
        when = re.search(r'data-label="创建时间">(.*?)</td>', row, re.S)
        app["releases"].append({
            "rid": int(rid.group(1)),
            "name": clean(ver.group(1)) if ver else "",
            "code": int(clean(code.group(1)) or 0) if code else 0,
            "published": "published" in (stat.group(1) if stat else ""),
            "mandatory": clean(mand.group(1)) not in ("", "—") if mand else False,
            "size": clean(size.group(1)) if size else "",
            "bytes": parse_size(clean(size.group(1))) if size else 0,
            "date": clean(when.group(1)) if when else "",
            "notes": "",
            "sha256": "",
            "file": "",
            "file_type": "",
        })


def harvest_release_detail(op, rel):
    page = get(op, "/admin/releases/%d" % rel["rid"])
    ta = re.search(r'<textarea name="release_notes"[^>]*>(.*?)</textarea>', page, re.S)
    if ta:
        rel["notes"] = htmllib.unescape(ta.group(1)).strip()
    # 版本信息面板的第一个 <dt>/<dd> 就是「文件类型 / 文件名」，标签跟着类型走
    # （APK、ZIP……），所以按位置取，不要写死成 APK——写死的话 zip 版本会读不到文件名
    m = re.search(r"<dt>([^<]*)</dt><dd[^>]*>(.*?)</dd>", page, re.S)
    if m:
        rel["file_type"] = clean(m.group(1))
        rel["file"] = clean(m.group(2))
    m = re.search(r"<dt>SHA256</dt><dd[^>]*>(.*?)</dd>", page, re.S)
    if m:
        rel["sha256"] = clean(m.group(1))
    m = re.search(r'id="release-mandatory"[^>]*\bchecked\b', page)
    if m:
        rel["mandatory"] = True


def live_latest(pkg):
    """Public API: authoritative current version + exact byte size."""
    try:
        with urllib.request.urlopen(
                "%s/api/v1/apps/%s/latest?version_code=0" % (BASE, pkg),
                timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                    # noqa: BLE001
        sys.stderr.write("  ! latest(%s): %s\n" % (pkg, e))
        return None


def js_dumps(obj, indent=0):
    """json.dumps with every non-ASCII char escaped, safe to embed in <script>."""
    txt = json.dumps(obj, ensure_ascii=True, indent=1, separators=(",", ":"))
    return txt.replace("</", "<\\/")


def main():
    op = make_opener()
    login(op)
    print("logged in to %s" % BASE)

    apps = harvest_apps(op)
    print("found %d app(s)" % len(apps))

    for app in apps:
        harvest_app_detail(op, app)
        for rel in app["releases"]:
            harvest_release_detail(op, rel)
        app["releases"].sort(key=lambda r: r["code"], reverse=True)
        pub = [r for r in app["releases"] if r["published"]]
        app["pub_count"] = len(pub)

        info = live_latest(app["pkg"])
        app["api_ok"] = bool(info and info.get("update_available") is not None)
        if info and info.get("update_available"):
            for rel in app["releases"]:
                if rel["code"] == info.get("version_code"):
                    rel["bytes"] = info.get("size") or rel["bytes"]
                    if info.get("release_notes"):
                        rel["notes"] = info["release_notes"]
                    rel["mandatory"] = bool(info.get("mandatory"))
                    rel["published_at"] = info.get("published_at", "")
                    # 公开接口带 artifact_type / file_name，比后台页面更权威
                    if info.get("artifact_type"):
                        rel["file_type"] = str(info["artifact_type"]).upper()
                    if info.get("file_name"):
                        rel["file"] = info["file_name"]
        kinds = sorted(set(r["file_type"] for r in app["releases"] if r["file_type"]))
        print("  %-22s %-34s %d release(s)  %s" %
              (app["name"], app["pkg"], len(app["releases"]),
               "/".join(kinds) or "?"))

    try:
        ann = json.loads(urllib.request.urlopen(
            BASE + "/api/v1/announcements", timeout=20).read().decode("utf-8"))
        announcements = ann.get("items", [])
    except Exception as e:                                    # noqa: BLE001
        sys.stderr.write("! announcements: %s\n" % e)
        announcements = []
    print("announcements: %d" % len(announcements))

    payload = {
        "server": BASE,
        "apps": apps,
        "announcements": announcements,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "catalog.js"), "w", encoding="ascii",
              newline="\n") as f:
        f.write("/* EasyUpdate catalogue - generated, do not edit by hand */\n")
        f.write("var EU_CATALOG = ")
        f.write(js_dumps(payload))
        f.write(";\n")
    print("wrote build/catalog.js and build/catalog.json")


if __name__ == "__main__":
    main()
