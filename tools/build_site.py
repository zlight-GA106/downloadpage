#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the static site from build/catalog.json.

Outputs into site/:
  index.html      the resource grid (cards, filters, sorting)
  app-<id>.html   one detail page per application, where downloads happen
  catalog.js      the same card markup as data, for the client-side grid

Card markup is generated once, here, and handed to the browser twice: baked
into index.html (so the page works with scripting off) and embedded as a string
in catalog.js (so app.js can re-arrange it when the user sorts or filters).
One template, no drift.

Pages are assembled with {{PLACEHOLDER}} substitution rather than %-formatting:
the templates are full of CSS percentages and one stray '%' would be a bug.
"""
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SITE = os.path.join(ROOT, "site")
ICONS = os.path.join(SITE, "icons")
CATALOG_JSON = os.path.join(ROOT, "build", "catalog.json")

# package/name keyword -> category label. Edit freely; first match wins.
CATEGORY_RULES = [
    (("easycent",), "记账理财"),
    (("einform", "电子墨水"), "信息终端"),
    (("easytodo",), "效率便签"),
    (("nvvocab", "vocab"), "学习工具"),
    (("sendtosmb", "smb"), "文件传输"),
    (("easyupdate",), "更新服务"),
]
CATEGORY_FALLBACK = "其他应用"
CATEGORY_ORDER = [c for _, c in CATEGORY_RULES] + [CATEGORY_FALLBACK]

COLS = 3

# per-application icon lookup, tried in this order. PNG/GIF come first because
# IE6 cannot render an .ico inside <img>; an .ico is still picked up, and the
# client falls back to the generated letter tile if the browser cannot show it.
ICON_EXTS = ("png", "gif", "ico", "jpg", "jpeg")


# ------------------------------------------------------------------ helpers
def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def notes_html(s):
    return esc(s).replace("\n", "<br>")


def human_size(n):
    if n <= 0:
        return "-"
    if n >= 1024 * 1024:
        return "%.1f MB" % (n / 1048576.0)
    return "%.1f KB" % (n / 1024.0)


def short_date(s):
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return "%s-%s-%s" % m.groups() if m else (s or "-")


def iso_to_local(s):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", s or "")
    return "%s-%s-%s %s:%s" % m.groups() if m else (s or "")


def categorize(app):
    hay = (app["name"] + " " + app["pkg"]).lower()
    for keys, label in CATEGORY_RULES:
        for k in keys:
            if k in hay:
                return label
    return CATEGORY_FALLBACK


def find_icon(pkg):
    """Auto-detect icons/<package>.<ext>; returns a site-relative URL or None."""
    for ext in ICON_EXTS:
        if os.path.exists(os.path.join(ICONS, "%s.%s" % (pkg, ext))):
            return "icons/%s.%s" % (pkg, ext)
    return None


def corners():
    return ('<b class="cn tl"></b><b class="cn tr"></b>'
            '<b class="cn bl"></b><b class="cn br"></b>')


def panel(title, body, extra=""):
    head = ('<table class="hdtab" width="100%%" cellspacing="0" cellpadding="0" '
            'border="0"><tr><td>%s</td><td class="r">%s</td></tr></table>'
            % (esc(title), extra))
    return ('<div class="pnl">%s<div class="hd">%s</div>'
            '<div class="bd">%s</div></div>' % (corners(), head, body))


def icon_box(app, size=48):
    """Letter tile, or the auto-detected icon layered over it.

    The letter tile is always in the markup; the detected icon simply covers
    it. If the image fails the inline handler (pure DOM - it must not depend on
    app.js, which has not loaded yet when a broken image reports its error)
    drops the .real class, which brings the tile and the letter back.
    """
    if not app.get("icon"):
        return '<div class="cico"><span class="ltr">%s</span></div>' % esc(app["letter"])
    return ('<div class="cico real"><span class="ltr">%s</span>'
            '<img class="ico" src="%s" width="%d" height="%d" alt="" '
            'onerror="this.style.display=\'none\';this.parentNode.className=\'cico\';">'
            '</div>' % (esc(app["letter"]), esc(app["icon"]), size, size))


def published(app):
    return [r for r in app["releases"] if r.get("published")]


def latest_of(app):
    pub = published(app)
    return pub[0] if pub else (app["releases"][0] if app["releases"] else None)


def dl_url(app, rel):
    return "/api/v1/apps/%s/releases/%d/download" % (app["pkg"], rel["code"])


# -------------------------------------------------------------- card markup
def card_html(app):
    latest = latest_of(app)
    size_txt = (latest.get("size") or human_size(latest.get("bytes", 0))) if latest else "-"
    date_txt = short_date(latest["date"]) if latest else "-"
    ver_txt = latest["name"] if latest else "-"
    aid = app["id"]

    return (
        '<div class="card" id="card%(id)d">%(cn)s'
        '<div class="chd"><span class="ttl">%(name)s</span>'
        '<span class="bdg" id="bdg%(id)d" style="display:none">更新</span></div>'
        '<div class="cbody">'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td width="56" valign="top">%(icon)s</td>'
        '<td valign="top"><div class="cpkg">%(pkg)s</div>'
        '<div class="cdesc">%(desc)s</div></td>'
        '</tr></table>'
        '<table class="cmeta" width="100%%" cellspacing="0" cellpadding="0" border="0">'
        '<tr><td class="k">版本</td><td class="v" id="ver%(id)d">%(ver)s</td>'
        '<td class="k">大小</td><td class="v" id="siz%(id)d">%(size)s</td></tr>'
        '<tr><td class="k">更新</td><td class="v" id="dat%(id)d" colspan="3">%(date)s</td></tr>'
        '</table>'
        '<table class="cact" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td><a class="btn dl" id="dl%(id)d" href="%(dl)s">下载</a></td>'
        '<td width="8"></td>'
        '<td><a class="btn" href="app-%(id)d.html">详细信息</a></td>'
        '</tr></table>'
        '</div></div>'
        % {"id": aid, "cn": corners(), "name": esc(app["name"]),
           "icon": icon_box(app), "pkg": esc(app["pkg"]), "desc": esc(app["desc"]),
           "ver": esc(ver_txt), "size": esc(size_txt), "date": esc(date_txt),
           "dl": esc(dl_url(app, latest)) if latest else "#"})


def grid_html(apps):
    rows = []
    for i in range(0, len(apps), COLS):
        chunk = apps[i:i + COLS]
        tds = []
        for j, app in enumerate(chunk):
            cls = "cell last" if j == COLS - 1 else "cell"
            tds.append('<td class="%s" width="33%%" valign="top">%s</td>'
                       % (cls, app["card"]))
        while len(tds) < COLS:
            tds.append('<td class="%s" width="33%%"></td>'
                       % ("cell last" if len(tds) == COLS - 1 else "cell"))
        rows.append("<tr>%s</tr>" % "".join(tds))
    return ('<table id="grid" cellspacing="0" cellpadding="0" border="0">%s</table>'
            % "".join(rows))


# ------------------------------------------------------------- page assembly
def stats_table(ctx):
    return ('<table class="stat" cellspacing="0" cellpadding="0" border="0">'
            '<tr><td>应用总数</td><td class="n">%d</td></tr>'
            '<tr><td>已发布版本</td><td class="n">%d</td></tr>'
            '<tr><td>最新版总量</td><td class="n wide">%s</td></tr>'
            '<tr><td>最近更新</td><td class="n wide">%s</td></tr>'
            '<tr><td>目录生成</td><td class="n wide">%s</td></tr>'
            '</table>'
            % (ctx["app_count"], ctx["total_releases"],
               human_size(ctx["latest_bytes"]),
               esc(short_date(ctx["newest"])), esc(ctx["built"])))


def status_table(ctx):
    return ('<table class="stat" cellspacing="0" cellpadding="0" border="0">'
            '<tr><td>服务程序</td><td class="n wide">EasyUpdate v0.1</td></tr>'
            '<tr><td>服务地址</td><td class="n wide">%s</td></tr>'
            '<tr><td>接口前缀</td><td class="n wide">/api/v1</td></tr>'
            '<tr><td>连接状态</td><td class="n wide" id="sideStat">检测中</td></tr>'
            '<tr><td>本次校验</td><td class="n wide" id="sideTime">-</td></tr>'
            '</table>' % esc(ctx["server_host"]))


def announcements_html(ctx):
    anns = ctx["announcements"]
    if not anns:
        return '<div class="ann"><div class="c">暂无公告</div></div>'
    return "".join('<div class="ann"><div class="t">%s</div>'
                   '<div class="d">%s</div><div class="c">%s</div></div>'
                   % (esc(a.get("title", "")),
                      esc(iso_to_local(a.get("created_at", ""))),
                      notes_html(a.get("content", ""))) for a in anns)


def left_panels(apps, ctx, mode, active_id=None):
    if mode == "detail":
        items = []
        for a in apps:
            cls = "nvi on" if a["id"] == active_id else "nvi"
            items.append('<a class="%s" href="app-%d.html" title="%s %s">'
                         '<img src="images/bullet.gif" width="9" height="9" alt="">%s</a>'
                         % (cls, a["id"], esc(a["pkg"]), esc(a["latest_name"]),
                            esc(a["name"])))
        second = panel("应用导航", "".join(items), extra="<b>%d</b>" % len(apps))
    else:
        items = ['<a class="nvi on" href="#" onclick="EU.filterAll(this);return false;">'
                 '<img src="images/bullet.gif" width="9" height="9" alt="">全部资源'
                 '<b>%d</b></a>' % len(apps)]
        for c, n in ctx["cats"]:
            items.append('<a class="nvi" href="#" onclick="EU.filter(%s,this);return false;">'
                         '<img src="images/bullet.gif" width="9" height="9" alt="">%s'
                         '<b>%d</b></a>' % (js_str(c), esc(c), n))
        second = panel("资源分类", "".join(items), extra="<b>%d</b>" % len(ctx["cats"]))

    return (panel("资源统计", stats_table(ctx))
            + second
            + panel("服务公告", '<div id="annBox">%s</div>' % announcements_html(ctx),
                    extra='<b id="annCnt">%d</b>' % len(ctx["announcements"]))
            + panel("服务状态", status_table(ctx)))


def shell(title, crumb, main, nav, ctx, refresh_label="刷新目录", scope=None):
    scope_js = ""
    if scope is not None:
        scope_js = ('<script type="text/javascript">var EU_SCOPE = [%s];</script>'
                    % ",".join(str(i) for i in scope))
    return (TEMPLATE
            .replace("{{TITLE}}", esc(title))
            .replace("{{CRUMB}}", crumb)
            .replace("{{NAV}}", nav)
            .replace("{{MAIN}}", main)
            .replace("{{SERVER}}", esc(ctx["server"]))
            .replace("{{BUILT}}", esc(ctx["built"]))
            .replace("{{SCOPE}}", scope_js)
            .replace("{{REFRESH}}", esc(refresh_label)))


def detail_page(app, apps, ctx):
    latest = latest_of(app)
    pub = published(app)

    rows = []
    notes = []
    for r in pub:
        rows.append(
            '<tr><td class="v">%s</td><td>%d</td><td>%s</td><td>%s</td>'
            '<td>%s</td><td class="act">'
            '<a class="btn mini" href="%s" title="%s">下载</a></td></tr>'
            % (esc(r["name"]), r["code"],
               esc(r.get("size") or human_size(r.get("bytes", 0))),
               esc(r["date"]),
               "是" if r.get("mandatory") else "—",
               esc(dl_url(app, r)), esc(r.get("file") or r["name"])))
        if r.get("notes"):
            notes.append('<div class="rel"><div class="relhd">%s'
                         '<span>%s &middot; %s</span></div><div class="relbd">%s</div></div>'
                         % (esc(r["name"]), esc(r["date"]),
                            esc(r.get("size") or ""), notes_html(r["notes"])))

    sha = (latest or {}).get("sha256", "")
    sha_html = "<br>".join(esc(sha[i:i + 32]) for i in range(0, len(sha), 32)) or "—"
    fname = (latest or {}).get("file") or "-"

    head = (
        '<div class="apphead">%(cn)s'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td width="60" valign="top">%(icon)s</td>'
        '<td valign="top"><div class="appname">%(name)s</div>'
        '<div class="apppkg">%(pkg)s</div>'
        '<div class="appdesc">%(desc)s</div></td>'
        '<td width="132" class="appact">'
        '<a class="btn dl wide" id="dl%(id)d" href="%(dl)s">下载最新版</a>'
        '<a class="btn wide" href="index.html">返回资源列表</a></td>'
        '</tr></table></div>'
        % {"cn": corners(), "icon": icon_box(app), "name": esc(app["name"]),
           "pkg": esc(app["pkg"]), "desc": esc(app["desc"]), "id": app["id"],
           "dl": esc(dl_url(app, latest)) if latest else "#"})

    info = ('<table class="stat" cellspacing="0" cellpadding="0" border="0">'
            '<tr><td>最新版本</td><td class="n wide" id="ver%d">%s</td></tr>'
            '<tr><td>版本号</td><td class="n wide">%d</td></tr>'
            '<tr><td>文件大小</td><td class="n wide" id="siz%d">%s</td></tr>'
            '<tr><td>发布日期</td><td class="n wide" id="dat%d">%s</td></tr>'
            '<tr><td>APK 文件名</td><td class="n wide mono">%s</td></tr>'
            '<tr><td>强制更新</td><td class="n wide">%s</td></tr>'
            '<tr><td>SHA256</td><td class="n wide mono">%s</td></tr>'
            '</table>'
            % (app["id"], esc(latest["name"] if latest else "-"),
               latest["code"] if latest else 0,
               app["id"], esc((latest or {}).get("size") or "-"),
               app["id"], esc((latest or {}).get("date") or "-"),
               esc(fname),
               "是" if (latest or {}).get("mandatory") else "否",
               sha_html))

    vtab = ('<table class="vtab" width="100%%" cellspacing="0" cellpadding="0" border="0">'
            '<tr><th width="16%%">版本</th><th width="10%%">版本号</th>'
            '<th width="14%%">大小</th><th width="22%%">发布日期</th>'
            '<th width="12%%">强制更新</th><th width="26%%" class="act">操作</th></tr>'
            + "".join(rows) + '</table>') if rows else \
        '<div class="empty">该应用尚无已发布版本。</div>'

    cols = ('<table class="cols" width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
            '<td class="cl" width="42%%" valign="top">%s</td>'
            '<td class="cr" valign="top">%s</td>'
            '</tr></table>'
            % (panel("版本信息", info), panel("下载与校验", CHECK_HINT)))

    main = (head + cols
            + panel("版本列表", vtab, extra="<b>%d</b>" % len(pub))
            + panel("版本说明", "".join(notes) or
                    '<div class="ann"><div class="c">暂无版本说明。</div></div>'))

    crumb = ('<div id="crumb"><a href="index.html">工具下载</a> <span>&gt;</span> '
             '<a href="index.html">资源列表</a> <span>&gt;</span> %s</div>'
             % esc(app["name"]))

    return shell("%s - 工具下载" % app["name"], crumb, main,
                 left_panels(apps, ctx, "detail", app["id"]), ctx,
                 refresh_label="刷新版本", scope=[app["id"]])


CHECK_HINT = (
    '<div class="hintbox">'
    '<p>下载地址由本站同源反向代理转发到 EasyUpdate，链接可直接复制或交给客户端使用。</p>'
    '<p>校验方式：比对文件大小与 SHA256，再核对包名、版本号与安装签名；'
    '任一不符时应删除缓存后重新下载。</p>'
    '<p>接口返回 <b>size</b>（字节）与 <b>sha256</b>（64 位十六进制），可直接用于脚本校验。</p>'
    '</div>')


def index_page(apps, ctx):
    main = (
        '<table id="pghead" width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td><h2>资源列表</h2></td>'
        '<td class="hint" id="pgHint">共 %d 个应用 / %d 个已发布版本</td>'
        '</tr></table>'
        '<div id="sortbar">'
        '<span class="lbl">排序</span>'
        '<a href="#" class="on" onclick="EU.sortBy(\'def\',this);return false;">默认</a>'
        '<a href="#" onclick="EU.sortBy(\'date\',this);return false;">更新时间</a>'
        '<a href="#" onclick="EU.sortBy(\'size\',this);return false;">文件大小</a>'
        '<a href="#" onclick="EU.sortBy(\'name\',this);return false;">名称</a>'
        '<span class="lbl">&nbsp;筛选</span>'
        '<input type="text" id="kw" class="kw" size="10" maxlength="40" '
        'onkeyup="EU.search(this.value);">'
        '</div>'
        '<div id="gridWrap">%s</div>'
        % (len(apps), ctx["total_releases"], grid_html(apps)))

    crumb = '<div id="crumb">工具下载 <span>&gt;</span> 资源列表</div>'
    return shell("工具下载", crumb, main, left_panels(apps, ctx, "index"), ctx)


# ------------------------------------------------------------------ mobile
# Same constraint set as the desktop pages (tables, no floats, GIF/PNG-8
# strips, ES3), only the sizing differs. The pages live in site/mobile/, reuse
# ../style.css for the skin with mobile.css layered on top, and share
# ../app.js for the live version check - so nothing is duplicated.
def mobile_card_html(app):
    latest = latest_of(app)
    size_txt = (latest.get("size") or human_size(latest.get("bytes", 0))) if latest else "-"
    date_txt = short_date(latest["date"]) if latest else "-"
    ver_txt = latest["name"] if latest else "-"
    aid = app["id"]

    return (
        '<div class="mcard">%(cn)s'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td width="56" valign="top">%(icon)s</td>'
        '<td valign="top"><div class="mname">%(name)s</div>'
        '<div class="mpkg">%(pkg)s</div>'
        '<div class="mdesc">%(desc)s</div></td>'
        '</tr></table>'
        '<div class="mmeta">版本 <b id="ver%(id)d">%(ver)s</b>'
        ' &middot; <b id="siz%(id)d">%(size)s</b>'
        ' &middot; <b id="dat%(id)d">%(date)s</b></div>'
        '<table class="mact" width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td class="l"><a class="mbtn dl" id="dl%(id)d" href="%(dl)s">下载</a></td>'
        '<td class="r"><a class="mbtn" href="app-%(id)d.html">详细信息</a></td>'
        '</tr></table>'
        '</div>'
        % {"id": aid, "cn": corners(), "name": esc(app["name"]),
           "icon": icon_box(app), "pkg": esc(app["pkg"]), "desc": esc(app["desc"]),
           "ver": esc(ver_txt), "size": esc(size_txt), "date": esc(date_txt),
           "dl": esc(dl_url(app, latest)) if latest else "#"})


def mobile_shell(title, crumb, main, ctx, scope=None, footer=None):
    scope_js = ""
    if scope is not None:
        scope_js = ('<script type="text/javascript">var EU_SCOPE = [%s];</script>'
                    % ",".join(str(i) for i in scope))
    return (MOBILE_TEMPLATE
            .replace("{{TITLE}}", esc(title))
            .replace("{{CRUMB}}", crumb)
            .replace("{{MAIN}}", main)
            .replace("{{SCOPE}}", scope_js)
            .replace("{{FOOT}}", footer or esc("目录生成 " + ctx["built"])))


# 手机版以翻页为主：应用列表、历史版本、版本说明各自分页，
# 每屏尽量不出现长滚动。全部是构建期生成的静态页面，
# 不依赖脚本，翻页就是普通链接，IE6 与老式手机浏览器都能用。
MOBILE_LIST_SIZE = 3      # 应用列表每页条数（按 320px 宽实测，3 条约 610px 高，接近一屏）
MOBILE_VER_SIZE = 6       # 历史版本每页条数


def mobile_list_url(page):
    return "index.html" if page == 1 else "p%d.html" % page


def mobile_ver_url(app_id, page):
    return ("app-%d-v.html" % app_id if page == 1
            else "app-%d-v%d.html" % (app_id, page))


def mobile_notes_url(app, rel):
    return "app-%d-n%d.html" % (app["id"], rel["code"])


def mobile_note_entry(app):
    """Where the 版本说明 tab points: the newest version that has notes."""
    for r in published(app):                 # published() is newest-first
        if r.get("notes"):
            return mobile_notes_url(app, r)
    return "app-%d-n.html" % app["id"]


def mobile_pager(page, pages, url_fn, center=None):
    """上一页 / 中间说明 / 下一页，一行放下。

    页码直链只在页数多于 4 时才另起一行——页数少的时候前翻后翻就够了，
    多出来的那一行会把列表页顶高一截，与「减少滑动」的目标相反。
    """
    if pages <= 1:
        return ""
    prev = ('<a class="mpg" href="%s">上一页</a>' % url_fn(page - 1)
            if page > 1 else '<span class="mpgoff">上一页</span>')
    nxt = ('<a class="mpg" href="%s">下一页</a>' % url_fn(page + 1)
           if page < pages else '<span class="mpgoff">下一页</span>')
    mid = center if center is not None else "第 %d / %d 页" % (page, pages)
    numrow = ""
    if pages > 4:
        nums = []
        for i in range(1, pages + 1):
            nums.append('<b class="mpgon">%d</b>' % i if i == page
                        else '<a class="mpgn" href="%s">%d</a>' % (url_fn(i), i))
        numrow = '<div class="mpgnum">%s</div>' % "".join(nums)
    return ('<div class="mpager">'
            '<table width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
            '<td class="l">%s</td><td class="c">%s</td>'
            '<td class="r">%s</td></tr></table>%s</div>'
            # mid is not escaped: callers pass either a plain string or markup
            # they built themselves (it used to be escaped, which turned a
            # &middot; in the caller's string into a literal "&middot;")
            % (prev, mid, nxt, numrow))


def mobile_tabs(app, active):
    items = (("概览", "app-%d.html" % app["id"], "ov"),
             ("历史版本", "app-%d-v.html" % app["id"], "ver"),
             ("版本说明", mobile_note_entry(app), "note"))
    tds = []
    for label, href, key in items:
        if key == active:
            tds.append('<td class="on">%s</td>' % esc(label))
        else:
            tds.append('<td><a href="%s">%s</a></td>' % (esc(href), esc(label)))
    return ('<div class="mtabs"><table width="100%%" cellspacing="0" cellpadding="0" '
            'border="0"><tr>%s</tr></table></div>' % "".join(tds))


def mobile_crumb(parts):
    """parts: [(label, href or None), ...]"""
    out = []
    for label, href in parts:
        out.append('<a href="%s">%s</a>' % (esc(href), esc(label)) if href
                   else esc(label))
    return '<div id="mcrumb">%s</div>' % ' <span>&gt;</span> '.join(out)


def mobile_announcements(ctx):
    return panel("服务公告", '<div id="annBox">%s</div>' % announcements_html(ctx),
                 extra='<b id="annCnt">%d</b>' % len(ctx["announcements"]))


# 桌面版左侧栏那四块（资源统计 / 资源分类 / 服务公告 / 服务状态）在手机版上
# 各占一页，用这一排分区标签切换——同样是翻页，不靠滑动。
MOBILE_SECTIONS = (("应用", "index.html", "apps"),
                   ("分类", "cat.html", "cat"),
                   ("公告", "notice.html", "notice"),
                   ("状态", "info.html", "info"))


def mobile_section_tabs(active):
    tds = []
    for label, href, key in MOBILE_SECTIONS:
        if key == active:
            tds.append('<td class="on">%s</td>' % esc(label))
        else:
            tds.append('<td><a href="%s">%s</a></td>' % (esc(href), esc(label)))
    return ('<div class="mtabs sect"><table width="100%%" cellspacing="0" cellpadding="0" '
            'border="0"><tr>%s</tr></table></div>' % "".join(tds))


def mobile_nav_items(ctx, active=None):
    """与桌面版左栏一致：一条「全部资源」，后面按分类各一条带计数。"""
    items = ['<a class="nvi%s" href="index.html">'
             '<img src="images/bullet.gif" width="9" height="9" alt="">全部资源'
             '<b>%d</b></a>' % (" on" if active is None else "", ctx["app_count"])]
    for i, (name, members) in enumerate(ctx["cat_apps"]):
        items.append('<a class="nvi%s" href="cat-%d.html">'
                     '<img src="images/bullet.gif" width="9" height="9" alt="">%s'
                     '<b>%d</b></a>'
                     % (" on" if active == i else "", i, esc(name), len(members)))
    return "".join(items)


def mobile_cat_page(apps, ctx):
    main = mobile_section_tabs("cat") + panel(
        "资源分类", mobile_nav_items(ctx),
        extra="<b>%d</b>" % len(ctx["cat_apps"]))
    crumb = mobile_crumb([("资源列表", "index.html"), ("资源分类", None)])
    return mobile_shell("资源分类 - 工具下载", crumb, main, ctx)


def mobile_cat_apps_page(apps, ctx, idx, page, pages):
    name, members = ctx["cat_apps"][idx]
    chunk = members[(page - 1) * MOBILE_LIST_SIZE:page * MOBILE_LIST_SIZE]
    cards = "".join(mobile_card_html(a) for a in chunk)

    def url(p):
        return ("cat-%d.html" % idx if p == 1 else "cat-%d-%d.html" % (idx, p))

    main = mobile_section_tabs("cat") + mobile_pager(page, pages, url) + cards
    crumb = mobile_crumb([("资源列表", "index.html"),
                          ("资源分类", "cat.html"), (name, None)])
    foot = esc("分类「%s」· 共 %d 个应用 / %d 个版本 · 目录生成 %s"
               % (name, len(members), ctx["total_releases"], ctx["built"]))
    return mobile_shell("%s - 工具下载" % name, crumb, main, ctx, footer=foot)


def mobile_notice_page(apps, ctx):
    main = mobile_section_tabs("notice") + mobile_announcements(ctx)
    crumb = mobile_crumb([("资源列表", "index.html"), ("服务公告", None)])
    return mobile_shell("服务公告 - 工具下载", crumb, main, ctx)


def mobile_info_page(apps, ctx):
    main = (mobile_section_tabs("info")
            + panel("资源统计", stats_table(ctx))
            + panel("服务状态", status_table(ctx)))
    crumb = mobile_crumb([("资源列表", "index.html"), ("服务状态", None)])
    return mobile_shell("服务状态 - 工具下载", crumb, main, ctx)


def mobile_index_page(apps, ctx, page, pages):
    chunk = apps[(page - 1) * MOBILE_LIST_SIZE:page * MOBILE_LIST_SIZE]
    cards = "".join(mobile_card_html(a) for a in chunk)
    # 页码留在翻页控件中间那一格，总数挪到页脚——挤在一格里 240px 宽会折行
    pager = mobile_pager(page, pages, mobile_list_url)

    main = mobile_section_tabs("apps") + pager + cards
    foot = esc("共 %d 个应用 / %d 个版本 · 目录生成 %s"
               % (len(apps), ctx["total_releases"], ctx["built"]))
    return mobile_shell("工具下载", "", main, ctx, footer=foot)


def mobile_app_page(app, ctx):
    """详情 · 概览：应用信息 + 下载最新版 + 版本信息。"""
    latest = latest_of(app)

    # 16 hex chars per line: on a 240px screen a 32-char chunk would be clipped
    sha = (latest or {}).get("sha256", "")
    sha_html = "<br>".join(esc(sha[i:i + 16]) for i in range(0, len(sha), 16)) or "—"

    head = (
        '<div class="mcard mhead-card">%(cn)s'
        '<table width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
        '<td width="56" valign="top">%(icon)s</td>'
        '<td valign="top"><div class="mname">%(name)s</div>'
        '<div class="mpkg">%(pkg)s</div>'
        '<div class="mdesc">%(desc)s</div></td>'
        '</tr></table>'
        '<a class="mbtn dl big" id="dl%(id)d" href="%(dl)s">下载最新版 %(ver)s</a>'
        '<div class="mmeta">当前版本 <b id="ver%(id)d">%(ver)s</b></div>'
        '</div>'
        % {"cn": corners(), "icon": icon_box(app), "name": esc(app["name"]),
           "pkg": esc(app["pkg"]), "desc": esc(app["desc"]), "id": app["id"],
           "ver": esc(latest["name"] if latest else "-"),
           "dl": esc(dl_url(app, latest)) if latest else "#"})

    # 单列「标签 值」行：两列表格会先把标签列占满，窄屏上把日期和 SHA256 挤到裁掉
    def drow(label, value, mid=None):
        return ('<div class="drow"><b>%s</b><span%s>%s</span></div>'
                % (esc(label), ' id="%s"' % mid if mid else "", value))

    info = ('<div class="mdef">'
            + drow("版本号", str(latest["code"] if latest else 0))
            + drow("文件大小", esc((latest or {}).get("size") or "-"),
                   "siz%d" % app["id"])
            + drow("发布日期", esc((latest or {}).get("date") or "-"),
                   "dat%d" % app["id"])
            + drow("APK 文件名", esc((latest or {}).get("file") or "-"))
            + drow("强制更新", "是" if (latest or {}).get("mandatory") else "否")
            + drow("SHA256", '<span class="mono hash">%s</span>' % sha_html)
            + '</div>')

    crumb = mobile_crumb([("资源列表", "index.html"), (app["name"], None)])
    return mobile_shell("%s - 工具下载" % app["name"], crumb,
                        mobile_tabs(app, "ov") + head + panel("版本信息", info),
                        ctx, scope=[app["id"]])


def mobile_versions_page(app, ctx, page, pages):
    """详情 · 历史版本：每页若干版本，版本名指向该版本的说明页。"""
    pub = published(app)
    chunk = pub[(page - 1) * MOBILE_VER_SIZE:page * MOBILE_VER_SIZE]

    rows = []
    for r in chunk:
        name = (esc(r["name"]) if not r.get("notes")
                else '<a href="%s">%s</a>'
                     % (esc(mobile_notes_url(app, r)), esc(r["name"])))
        rows.append(
            '<div class="mrow"><table width="100%%" cellspacing="0" cellpadding="0" '
            'border="0"><tr>'
            '<td valign="middle"><span class="rv">%s</span>'
            '<span class="rs">%s &middot; %s &middot; #%d</span></td>'
            '<td width="74" class="ract" valign="middle">'
            '<a class="mbtn" href="%s" title="%s">下载</a></td>'
            '</tr></table></div>'
            % (name,
               esc(r.get("size") or human_size(r.get("bytes", 0))),
               esc(r["date"]), r["code"],
               esc(dl_url(app, r)), esc(r.get("file") or r["name"])))

    body = (mobile_pager(page, pages, lambda p: mobile_ver_url(app["id"], p))
            + ("".join(rows) or '<div class="empty">该应用尚无已发布版本。</div>')
            + mobile_pager(page, pages, lambda p: mobile_ver_url(app["id"], p)))

    crumb = mobile_crumb([("资源列表", "index.html"),
                          (app["name"], "app-%d.html" % app["id"]),
                          ("历史版本", None)])
    return mobile_shell("%s 历史版本 - 工具下载" % app["name"], crumb,
                        mobile_tabs(app, "ver")
                        + panel("历史版本", body, extra="<b>%d</b>" % len(pub)),
                        ctx, scope=[app["id"]])


def mobile_notes_page(app, ctx, rel, newer, older):
    """详情 · 版本说明：一次只放一个版本的说明，靠上一版/下一版翻页。"""
    if rel is None:
        body = '<div class="ann"><div class="c">暂无版本说明。</div></div>'
    else:
        body = ('<div class="rel"><div class="relhd">%s'
                '<span>%s &middot; %s &middot; #%d</span></div>'
                '<div class="relbd">%s</div></div>'
                % (esc(rel["name"]), esc(rel["date"]),
                   esc(rel.get("size") or ""), rel["code"],
                   notes_html(rel.get("notes", ""))))

    nav = ""
    if newer or older:
        left = ('<a class="mpg" href="%s">&larr; %s</a>'
                % (esc(mobile_notes_url(app, newer)), esc(newer["name"]))
                if newer else '<span class="mpgoff">最新版</span>')
        right = ('<a class="mpg" href="%s">%s &rarr;</a>'
                 % (esc(mobile_notes_url(app, older)), esc(older["name"]))
                 if older else '<span class="mpgoff">最早版</span>')
        nav = ('<div class="mpager pgnav">'
               '<table width="100%%" cellspacing="0" cellpadding="0" border="0"><tr>'
               '<td class="l">%s</td><td class="c">翻页</td>'
               '<td class="r">%s</td></tr></table></div>' % (left, right))

    title = ("%s %s 版本说明" % (app["name"], rel["name"]) if rel
             else "%s 版本说明" % app["name"])
    crumb = mobile_crumb([("资源列表", "index.html"),
                          (app["name"], "app-%d.html" % app["id"]),
                          ("版本说明", None)])
    # 不再另挂「返回概览 / 全部历史版本」面板：上面那排翻页标签就是这两个入口，
    # 多一块面板会把这一页顶过一屏
    return mobile_shell("%s - 工具下载" % title, crumb,
                        mobile_tabs(app, "note")
                        + panel("版本说明", body)
                        + nav,
                        ctx, scope=[app["id"]])


# ------------------------------------------------------------------- output
def js_str(s):
    return json.dumps(s, ensure_ascii=True).replace("</", "<\\/").replace('"', "&quot;")


def build():
    with open(CATALOG_JSON, encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(ICONS, exist_ok=True)
    apps = data["apps"]
    for a in apps:
        a["cat"] = categorize(a)
        a["icon"] = find_icon(a["pkg"])

    ctx = {
        "server": data["server"],
        "server_host": re.sub(r"^https?://", "", data["server"]).rstrip("/"),
        "built": time.strftime("%Y-%m-%d %H:%M"),
        "announcements": data.get("announcements") or [],
    }
    ctx["total_releases"] = sum(len(published(a)) for a in apps)
    ctx["latest_bytes"] = sum((latest_of(a) or {}).get("bytes", 0) for a in apps)
    ctx["newest"] = max([r["date"] for a in apps for r in a["releases"]] or ["-"])
    ctx["app_count"] = len(apps)
    ctx["cats"] = [(c, len([a for a in apps if a["cat"] == c]))
                   for c in CATEGORY_ORDER
                   if len([a for a in apps if a["cat"] == c])]
    ctx["cat_apps"] = [(c, [a for a in apps if a["cat"] == c]) for c, _ in ctx["cats"]]

    for a in apps:
        a["card"] = card_html(a)

    pages = {"index.html": index_page(apps, ctx)}
    for a in apps:
        pages["app-%d.html" % a["id"]] = detail_page(a, apps, ctx)

    # --- mobile: everything is paginated, nothing relies on scrolling ----
    list_pages = max(1, -(-len(apps) // MOBILE_LIST_SIZE))
    for p in range(1, list_pages + 1):
        pages["mobile/" + mobile_list_url(p)] = mobile_index_page(apps, ctx, p, list_pages)

    # 桌面版左侧栏的四个面板，在手机版上各占一页
    pages["mobile/cat.html"] = mobile_cat_page(apps, ctx)
    for i, (name, members) in enumerate(ctx["cat_apps"]):
        cat_pages = max(1, -(-len(members) // MOBILE_LIST_SIZE))
        for p in range(1, cat_pages + 1):
            key = ("cat-%d.html" % i if p == 1 else "cat-%d-%d.html" % (i, p))
            pages["mobile/" + key] = mobile_cat_apps_page(apps, ctx, i, p, cat_pages)
    pages["mobile/notice.html"] = mobile_notice_page(apps, ctx)
    pages["mobile/info.html"] = mobile_info_page(apps, ctx)

    for a in apps:
        pages["mobile/app-%d.html" % a["id"]] = mobile_app_page(a, ctx)

        pub = published(a)
        ver_pages = max(1, -(-len(pub) // MOBILE_VER_SIZE))
        for p in range(1, ver_pages + 1):
            pages["mobile/" + mobile_ver_url(a["id"], p)] = \
                mobile_versions_page(a, ctx, p, ver_pages)

        noted = [r for r in pub if r.get("notes")]
        if noted:
            for i, r in enumerate(noted):
                newer = noted[i - 1] if i > 0 else None
                older = noted[i + 1] if i + 1 < len(noted) else None
                pages["mobile/" + mobile_notes_url(a, r)] = \
                    mobile_notes_page(a, ctx, r, newer, older)
        else:
            pages["mobile/app-%d-n.html" % a["id"]] = \
                mobile_notes_page(a, ctx, None, None, None)

    total = 0
    for name, html in pages.items():
        path = os.path.join(SITE, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(html)
        total += os.path.getsize(path)

    payload = {
        "server": data["server"], "built": ctx["built"], "cols": COLS,
        "count": len(apps),
        "apps": [{
            "id": a["id"], "name": a["name"], "pkg": a["pkg"], "cat": a["cat"],
            "letter": a["letter"], "desc": a["desc"],
            "latest_code": (latest_of(a) or {}).get("code", 0),
            "latest_size": (latest_of(a) or {}).get("size", ""),
            "latest_bytes": (latest_of(a) or {}).get("bytes", 0),
            "latest_date": (latest_of(a) or {}).get("date", ""),
            "card": a["card"],
        } for a in apps],
    }
    with open(os.path.join(SITE, "catalog.js"), "w", encoding="ascii",
              newline="\n") as f:
        f.write("/* tools-download catalogue - generated by build_site.py */\n")
        f.write("var EU_CATALOG = ")
        f.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
                .replace("</", "<\\/"))
        f.write(";\n")

    found = [a["pkg"] for a in apps if a["icon"]]
    print("apps=%d releases=%d pages=%d" % (len(apps), ctx["total_releases"], len(pages)))
    print("auto-detected icons: %s" % (", ".join(found) if found else "none"))
    print("wrote %d page(s) (%d bytes) + catalog.js" % (len(pages), total))


TEMPLATE = r"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>{{TITLE}}</title>
<link rel="shortcut icon" href="favicon.ico">
<link rel="stylesheet" type="text/css" href="style.css">
</head>
<body>
<div id="page">

<div id="hero">
	<div id="heroArt"></div>
	<table id="brand" cellspacing="0" cellpadding="0" border="0"><tr>
		<td width="62" valign="middle"><a href="index.html"><img src="images/logo.png" width="48" height="48" alt=""></a></td>
		<td valign="middle">
			<h1><a href="index.html">工具下载</a></h1>
			<p>ZLIGHT106 Microsystems &middot; 软件分发中心</p>
		</td>
	</tr></table>
</div>

<div id="utilbar">
	<table width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
		<td>服务地址&nbsp;<b>{{SERVER}}</b></td>
		<td align="right">
			<img class="dot" id="statDot" src="images/dot_off.gif" width="11" height="11" alt=""><span id="statTx">正在连接服务</span>
			<span class="sep">|</span><span id="clock">--:--:--</span>
			<span class="sep">|</span><a href="mobile/">切换到手机版</a>
			<span class="sep">|</span><a href="#" onclick="EU.refresh();return false;">{{REFRESH}}</a>
		</td>
	</tr></table>
</div>

<table id="shell" cellspacing="0" cellpadding="0" border="0">
<tr>
	<td id="nav">
{{NAV}}
	</td>
	<td id="main">
		{{CRUMB}}
{{MAIN}}
	</td>
</tr>
</table>

<div id="statusbar">
	<table width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
		<td>工具下载 &middot; 静态分发页</td>
		<td class="c">目录生成 {{BUILT}}</td>
		<td class="r">ZLIGHT106 Microsystems</td>
	</tr></table>
</div>

</div>
{{SCOPE}}
<script type="text/javascript" src="catalog.js" charset="utf-8"></script>
<script type="text/javascript" src="app.js" charset="utf-8"></script>
</body>
</html>
"""

MOBILE_TEMPLATE = r"""<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<link rel="shortcut icon" href="../favicon.ico">
<link rel="stylesheet" type="text/css" href="../style.css">
<link rel="stylesheet" type="text/css" href="mobile.css">
</head>
<body class="mob">
<div id="mwrap">

<div id="mhead">
	<table width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
		<td width="46" valign="middle"><a href="index.html"><img src="../images/logo.png" width="34" height="34" alt=""></a></td>
		<td valign="middle">
			<span class="mt">工具下载</span>
			<span class="ms">ZLIGHT106 Microsystems</span>
		</td>
		<td class="mr" valign="middle"><a href="../index.html">桌面版</a></td>
	</tr></table>
</div>

<div id="mstat">
	<table width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
		<td><img id="statDot" src="../images/dot_off.gif" width="11" height="11" alt=""><span id="statTx">正在连接服务</span></td>
		<td class="r"><span id="clock">--:--:--</span></td>
	</tr></table>
</div>

{{CRUMB}}

<div id="mmain">
{{MAIN}}
</div>

<div id="mfoot">工具下载 &middot; {{FOOT}}</div>

</div>
{{SCOPE}}
<script type="text/javascript" src="../catalog.js" charset="utf-8"></script>
<script type="text/javascript" src="../app.js" charset="utf-8"></script>
</body>
</html>
"""

# the shell template starts each page with no crumb; the index page supplies
# its own <div id="crumb"> and detail pages pass one in
if __name__ == "__main__":
    build()