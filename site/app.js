/* 工具下载 - 客户端脚本
   仅使用 IE6 的 JScript 5.6 语法：
   不使用 JSON 对象、Array.prototype.indexOf、String.prototype.trim、
   addEventListener、console、尾随逗号。XMLHttpRequest 通过
   ActiveXObject 创建，接口地址与页面同源（由 nginx 反向代理）。 */

var EU = (function () {

	var CAT = null;
	var state = { cat: "*", kw: "", sort: "def" };
	var stat = { ok: 0, total: 0 };

	/* ------------------------------------------------------------ 工具 */
	function $(id) { return document.getElementById(id); }

	function esc(s) {
		s = "" + s;
		return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	}

	function setText(id, txt) {
		var el = $(id);
		if (el) { el.innerHTML = esc(txt); }
	}

	function setHtml(id, html) {
		var el = $(id);
		if (el) { el.innerHTML = html; }
	}

	function show(id, on) {
		var el = $(id);
		if (el) { el.style.display = on ? "" : "none"; }
	}

	function hasClass(el, cls) {
		return (" " + el.className + " ").indexOf(" " + cls + " ") >= 0;
	}

	function pad2(n) { return n < 10 ? "0" + n : "" + n; }

	function fmtSize(b) {
		b = parseInt(b, 10);
		if (!b || isNaN(b) || b <= 0) { return "-"; }
		if (b >= 1048576) { return (b / 1048576).toFixed(1) + " MB"; }
		return (b / 1024).toFixed(1) + " KB";
	}

	function shortDate(s) {
		s = "" + (s || "");
		if (s.length >= 10 && s.charAt(4) === "-") { return s.substring(0, 10); }
		return s || "-";
	}

	/* -------------------------------------------------- 最小 JSON 解析器 */
	function parseJSON(text) {
		var i = 0, n = text.length;

		function bad() { throw new Error("bad json"); }

		function ws() {
			while (i < n) {
				var c = text.charAt(i);
				if (c === " " || c === "\t" || c === "\n" || c === "\r") { i++; }
				else { break; }
			}
		}

		function literal(word, value) {
			if (text.substr(i, word.length) === word) { i += word.length; return value; }
			bad();
		}

		function str() {
			i++;
			var out = "", c;
			while (i < n) {
				c = text.charAt(i++);
				if (c === '"') { return out; }
				if (c === "\\") {
					c = text.charAt(i++);
					if (c === "u") {
						out += String.fromCharCode(parseInt(text.substr(i, 4), 16));
						i += 4;
					} else if (c === "n") { out += "\n"; }
					else if (c === "t") { out += "\t"; }
					else if (c === "r") { out += "\r"; }
					else if (c === "b") { out += "\b"; }
					else if (c === "f") { out += "\f"; }
					else { out += c; }
				} else { out += c; }
			}
			bad();
		}

		function num() {
			var start = i, c;
			while (i < n) {
				c = text.charAt(i);
				if ((c >= "0" && c <= "9") || c === "-" || c === "+" ||
					c === "." || c === "e" || c === "E") { i++; }
				else { break; }
			}
			var v = parseFloat(text.substring(start, i));
			if (isNaN(v)) { bad(); }
			return v;
		}

		function arr() {
			i++;
			var out = [], c;
			ws();
			if (text.charAt(i) === "]") { i++; return out; }
			for (;;) {
				out[out.length] = val();
				ws();
				c = text.charAt(i++);
				if (c === "]") { return out; }
				if (c !== ",") { bad(); }
			}
		}

		function obj() {
			i++;
			var out = {}, c, k;
			ws();
			if (text.charAt(i) === "}") { i++; return out; }
			for (;;) {
				ws();
				if (text.charAt(i) !== '"') { bad(); }
				k = str();
				ws();
				if (text.charAt(i++) !== ":") { bad(); }
				out[k] = val();
				ws();
				c = text.charAt(i++);
				if (c === "}") { return out; }
				if (c !== ",") { bad(); }
			}
		}

		function val() {
			ws();
			var c = text.charAt(i);
			if (c === "{") { return obj(); }
			if (c === "[") { return arr(); }
			if (c === '"') { return str(); }
			if (c === "t") { return literal("true", true); }
			if (c === "f") { return literal("false", false); }
			if (c === "n") { return literal("null", null); }
			return num();
		}

		return val();
	}

	function decode(body) {
		if (!body) { return null; }
		try { return parseJSON(body); } catch (e) { return null; }
	}

	/* ----------------------------------------------------------- 通信 */
	function xhr() {
		var x = null;
		try { x = new ActiveXObject("Msxml2.XMLHTTP"); }
		catch (e1) {
			try { x = new ActiveXObject("Microsoft.XMLHTTP"); }
			catch (e2) {
				try { x = new XMLHttpRequest(); }
				catch (e3) { x = null; }
			}
		}
		return x;
	}

	function request(url, done) {
		var x = xhr();
		if (!x) { done(null); return; }
		try {
			x.open("GET", url, true);
			x.onreadystatechange = function () {
				if (x.readyState !== 4) { return; }
				x.onreadystatechange = function () {};
				var code = 0, body = null;
				try { code = x.status; } catch (e1) { code = 0; }
				if (code >= 200 && code < 300) {
					try { body = x.responseText; } catch (e2) { body = null; }
				}
				done(body);
			};
			x.send(null);
		} catch (e3) {
			done(null);
		}
	}

	/* ------------------------------------------------- 版本实时校验 */
	function updateOne(app, body) {
		var info = decode(body);
		if (!info || !info.package_name) { return false; }
		if (!info.update_available) { return true; }
		setText("ver" + app.id, info.version_name);
		setText("siz" + app.id, fmtSize(info.size));
		setText("dat" + app.id, shortDate(info.published_at));
		var dl = $("dl" + app.id);
		if (dl) {
			dl.href = "/api/v1/apps/" + app.pkg + "/releases/" +
				info.version_code + "/download";
		}
		if (parseInt(info.version_code, 10) !== parseInt(app.latest_code, 10)) {
			show("bdg" + app.id, true);
		}
		return true;
	}

	function checkAt(list, i) {
		if (i >= list.length) { finishCheck(); return; }
		var app = list[i];
		request("/api/v1/apps/" + app.pkg + "/latest?version_code=0",
			function (body) {
				if (updateOne(app, body)) { stat.ok++; }
				checkAt(list, i + 1);
			});
	}

	function finishCheck() {
		var d = new Date();
		var txt;
		if (stat.total > 0 && stat.ok === stat.total) {
			txt = "服务器在线 (" + stat.ok + "/" + stat.total + ")";
		} else if (stat.ok > 0) {
			txt = "部分接口异常 (" + stat.ok + "/" + stat.total + ")";
		} else {
			txt = "服务器无响应";
		}
		var dot = $("statDot");
		if (dot) {
			dot.src = stat.ok > 0 ? "images/dot_on.gif" : "images/dot_off.gif";
		}
		setText("statTx", txt);
		setText("sideStat", stat.ok > 0 ? "在线 " + stat.ok + "/" + stat.total : "无响应");
		setText("sideTime", pad2(d.getHours()) + ":" + pad2(d.getMinutes()) +
			":" + pad2(d.getSeconds()));
	}

	function refresh() {
		if (!CAT) { return; }
		var list = scope();
		stat.ok = 0;
		stat.total = list.length;
		setText("statTx", "正在校验版本");
		checkAt(list, 0);
	}

	/* Detail pages set EU_SCOPE so only their own application is queried. */
	function scope() {
		var out = [], i, j, s = window.EU_SCOPE;
		for (i = 0; i < CAT.apps.length; i++) {
			if (!s) { out[out.length] = CAT.apps[i]; continue; }
			for (j = 0; j < s.length; j++) {
				if (CAT.apps[i].id === s[j]) { out[out.length] = CAT.apps[i]; break; }
			}
		}
		return out;
	}

	/* -------------------------------------------------------- 服务公告 */
	function loadAnnouncements() {
		request("/api/v1/announcements", function (body) {
			var o = decode(body);
			if (!o || !o.items) { return; }
			var items = o.items, html = "", i, a, when;
			if (items.length === 0) {
				html = '<div class="ann"><div class="c">暂无公告</div></div>';
			}
			for (i = 0; i < items.length; i++) {
				a = items[i];
				when = shortDate(a.created_at);
				html += '<div class="ann"><div class="t">' + esc(a.title) +
					'</div><div class="d">' + esc(when) +
					'</div><div class="c">' +
					esc(a.content).replace(/\n/g, "<br>") + "</div></div>";
			}
			setHtml("annBox", html);
			setText("annCnt", "" + items.length);
		});
	}

	/* ------------------------------------------------------ 排序与筛选 */
	function match(app) {
		if (state.cat !== "*" && app.cat !== state.cat) { return false; }
		if (state.kw !== "") {
			var hay = (app.name + " " + app.pkg + " " + app.desc).toLowerCase();
			if (hay.indexOf(state.kw) < 0) { return false; }
		}
		return true;
	}

	function sortList(list) {
		var i, j, t;
		for (i = 1; i < list.length; i++) {
			t = list[i];
			j = i - 1;
			while (j >= 0 && before(t, list[j])) { list[j + 1] = list[j]; j--; }
			list[j + 1] = t;
		}
	}

	function before(a, b) {
		if (state.sort === "size") { return a.latest_bytes > b.latest_bytes; }
		if (state.sort === "date") { return a.latest_date > b.latest_date; }
		if (state.sort === "name") { return a.name.toLowerCase() < b.name.toLowerCase(); }
		return false;
	}

	function buildTable(list) {
		var cols = CAT && CAT.cols ? CAT.cols : 3;
		var out = ['<table id="grid" cellspacing="0" cellpadding="0" border="0">'];
		var i, j, app, cls;
		for (i = 0; i < list.length; i += cols) {
			out[out.length] = "<tr>";
			for (j = 0; j < cols; j++) {
				app = list[i + j];
				cls = (j === cols - 1) ? "cell last" : "cell";
				out[out.length] = '<td class="' + cls +
					'" width="33%" valign="top">' + (app ? app.card : "") + "</td>";
			}
			out[out.length] = "</tr>";
		}
		out[out.length] = "</table>";
		return out.join("");
	}

	function render() {
		if (!CAT) { return; }
		var list = [], i;
		for (i = 0; i < CAT.apps.length; i++) {
			if (match(CAT.apps[i])) { list[list.length] = CAT.apps[i]; }
		}
		sortList(list);
		var html;
		if (list.length === 0) {
			html = '<div class="pnl"><div class="bd"><div class="empty">' +
				'没有符合条件的资源，请调整分类或关键字。</div></div></div>';
		} else {
			html = buildTable(list);
		}
		var wrap = $("gridWrap");
		if (wrap) { wrap.innerHTML = html; }
		var hint = $("pgHint");
		if (hint) {
			hint.innerHTML = "显示 " + list.length + " / " + CAT.apps.length + " 个应用";
		}
	}

	function clearNav() {
		var links = document.getElementsByTagName("a"), i;
		for (i = 0; i < links.length; i++) {
			if (hasClass(links[i], "nvi")) { links[i].className = "nvi"; }
		}
	}

	function markOn(box, el) {
		var links = box.getElementsByTagName("a"), i;
		for (i = 0; i < links.length; i++) { links[i].className = ""; }
		if (el) { el.className = "on"; }
	}

	function tick() {
		var d = new Date();
		setText("clock", pad2(d.getHours()) + ":" + pad2(d.getMinutes()) +
			":" + pad2(d.getSeconds()));
	}

	return {
		filter: function (cat, el) {
			state.cat = cat;
			clearNav();
			if (el) { el.className = "nvi on"; }
			render();
		},
		filterAll: function (el) {
			state.cat = "*";
			state.kw = "";
			var kw = $("kw");
			if (kw) { kw.value = ""; }
			clearNav();
			if (el) { el.className = "nvi on"; }
			render();
		},
		search: function (kw) {
			state.kw = ("" + (kw || "")).toLowerCase();
			render();
		},
		sortBy: function (kind, el) {
			state.sort = kind;
			var bar = $("sortbar");
			if (bar) { markOn(bar, el); }
			render();
		},
		refresh: refresh,
		init: function () {
			CAT = window.EU_CATALOG || null;
			if (!CAT) { return; }
			tick();
			setInterval(tick, 1000);
			refresh();
			loadAnnouncements();
		}
	};

})();

EU.init();
