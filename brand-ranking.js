/* 브랜드 랭킹 탭 — 사용자 레퍼런스(아마존 뷰티 브랜드 랭킹 시계열) 구성을 따른다.
   데이터: data/brands.json (build/brands.py). 숫자는 모두 빌드에서 계산된 값이다. */
(function () {
  "use strict";
  var BR = null, VIEW = null, locked = null, range = 0;
  var CCOL = ["#FFCB05", "#5B9BD5", "#ED7D31", "#FFFFFF", "#3f6f9e", "#a4611d"];
  var C = { g: "#2a3540", m: "#8b98a5", gray: "#323f4c" };
  var SHORT = {"L'Oréal Paris": "L'Oréal", "Maybelline New York": "Maybelline", "La Roche-Posay": "La Roche-P",
    "Essence Cosmetics": "Essence", "Rimmel London": "Rimmel L.", "NYX Professional Makeup": "NYX",
    "Beauty of Joseon": "조선미녀", "Revlon Professional": "Revlon Pro", "The Ordinary": "Ordinary",
    "Amazon Basics": "Amz Basics", "HAWAIIAN Tropic": "Hawaiian T.", "Dr. Scholl's": "Dr.Scholl",
    "Paula's Choice": "Paula's", "L'Oréal Professionnel": "L'Oréal Pro"};
  var BC = {}, KB = [];
  var $ = function (s) { return document.querySelector(s); };
  function sh(n) { return SHORT[n] || n; }
  function isKB(n) { return !!BC[n]; }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;"); }

  /* ---- 기간 선택: 보이는 시점만 잘라낸 뷰 ---- */
  function makeView() {
    var n = BR.points.length, from = range ? Math.max(0, n - range) : 0;
    var sl = function (a) { return a.slice(from); };
    var series = {};
    Object.keys(BR.series).forEach(function (b) {
      var s = BR.series[b], v = {}, r = {};
      Object.keys(s.values).forEach(function (k) { v[k] = sl(s.values[k]); r[k] = sl(s.ranks[k]); });
      series[b] = { values: v, ranks: r };
    });
    var ranks = {};
    Object.keys(BR.ranks).forEach(function (k) { ranks[k] = sl(BR.ranks[k]); });
    var pts = sl(BR.points);
    VIEW = {
      pts: pts, n: pts.length, series: series, ranks: ranks, names: Object.keys(series),
      labels: pts.map(function (p) { return (+p.date.slice(5, 7)) + "/" + (+p.date.slice(8, 10)); }),
      firstAuto: pts.findIndex(function (p) { return p.source === "auto"; })
    };
  }
  function val(n, t, k) { var s = VIEW.series[n]; return s ? s.values[k][t] : null; }
  function rankOf(n, t, k) { var s = VIEW.series[n]; return s ? s.ranks[k][t] : null; }
  function every(n, px, min) { return Math.max(1, Math.ceil(n / Math.max(1, Math.floor(px / min)))); }

  /* ---- 차트 ---- */
  function sv(w, h) { return '<svg viewBox="0 0 ' + w + " " + h + '" width="100%" xmlns="http://www.w3.org/2000/svg" style="display:block">'; }
  function tx(x, y, s, o) {
    o = o || {};
    return '<text x="' + x + '" y="' + y + '" text-anchor="' + (o.a || "middle") + '" fill="' + (o.f || C.m) + '" font-size="' + (o.s || 18) + '"' + (o.w ? ' font-weight="' + o.w + '"' : "") + ">" + esc(s) + "</text>";
  }
  function frame(W, H, L, R, T, B, ymax) {
    var n = VIEW.n, iw = W - L - R, ih = H - T - B;
    var X = function (i) { return L + (n > 1 ? iw * (i / (n - 1)) : iw / 2); };
    var Y = function (v) { return T + ih - (v / ymax) * ih; };
    var o = sv(W, H);
    for (var k = 0; k <= 4; k++) {
      var gv = ymax * k / 4, gy = Y(gv);
      o += '<line x1="' + L + '" y1="' + gy + '" x2="' + (W - R) + '" y2="' + gy + '" stroke="' + C.g + '"/>' + tx(L - 12, gy + 6, Math.round(gv), { a: "end" });
    }
    var ev = every(n, iw, 70);
    VIEW.labels.forEach(function (d, i) {
      if ((n - 1 - i) % ev) return;
      var last = i === n - 1;
      o += tx(X(i), H - B + 30, d, { f: last ? "#fff" : C.m, w: last ? 800 : 400 });
    });
    if (VIEW.firstAuto > 0) { // 여기부터 자동 수집
      var fx = (X(VIEW.firstAuto - 1) + X(VIEW.firstAuto)) / 2;
      o += '<line x1="' + fx + '" y1="' + T + '" x2="' + fx + '" y2="' + (T + ih) + '" stroke="#FFFFFF" stroke-dasharray="3 5" opacity=".55"/>' +
        tx(fx + 8, T + 16, "자동 수집 →", { a: "start", f: "#fff", s: 17, w: 800 });
    }
    return { o: o, X: X, Y: Y };
  }
  function drawLine(F, n, k, color, width, labels, W, R) {
    var prev = null, last = null, s = "", N = VIEW.n;
    for (var i = 0; i < N; i++) {
      var v = val(n, i, k); if (v == null) continue;
      if (prev) {
        var dash = (i - prev.i > 1) ? ' stroke-dasharray="4 4" opacity=".5"' : "";
        s += '<line x1="' + F.X(prev.i) + '" y1="' + F.Y(prev.v) + '" x2="' + F.X(i) + '" y2="' + F.Y(v) + '" stroke="' + color + '" stroke-width="' + width + '"' + dash + "/>";
      }
      prev = { i: i, v: v }; last = prev;
    }
    if (labels && last) {
      var ev = every(N, W, 56);
      for (var j = 0; j < N; j++) {
        var vv = val(n, j, k); if (vv == null) continue;
        s += '<circle cx="' + F.X(j) + '" cy="' + F.Y(vv) + '" r="5" fill="' + color + '"/>';
        if (j === last.i || (N - 1 - j) % ev === 0) s += tx(F.X(j), F.Y(vv) - 12, vv, { f: color, s: 18, w: 800 });
      }
      s += tx(W - R + 12, F.Y(last.v) + 6, sh(n), { a: "start", f: color, s: 18, w: 800 });
    }
    return s;
  }
  function chart(k, hi) {
    var W = 1360, H = 460, L = 58, R = 180, T = 30, B = 56, max = 0;
    VIEW.names.forEach(function (n) { for (var t = 0; t < VIEW.n; t++) { var v = val(n, t, k); if (v != null && v > max) max = v; } });
    var ymax = Math.max(4, Math.ceil(max * 1.15 / 4) * 4);
    var F = frame(W, H, L, R, T, B, ymax), o = F.o;
    VIEW.names.forEach(function (n) { if (isKB(n) || n === hi) return; o += drawLine(F, n, k, C.gray, 1.3, false, W, R); });
    KB.forEach(function (n) { if (n === hi) return; o += drawLine(F, n, k, BC[n].fg, 3, true, W, R); });
    if (hi) o += drawLine(F, hi, k, isKB(hi) ? BC[hi].fg : "#FFFFFF", 3.4, true, W, R);
    return o + "</svg>";
  }
  function countryChart(brand) {
    var W = 1360, H = 440, L = 58, R = 130, T = 30, B = 56, max = 0;
    BR.countries.forEach(function (c) { for (var t = 0; t < VIEW.n; t++) { var v = val(brand, t, c.cc); if (v != null && v > max) max = v; } });
    var ymax = Math.max(4, Math.ceil(max * 1.2 / 4) * 4);
    var F = frame(W, H, L, R, T, B, ymax), o = F.o;
    BR.countries.forEach(function (c, ci) {
      var prev = null, last = null;
      for (var i = 0; i < VIEW.n; i++) {
        var v = val(brand, i, c.cc); if (v == null) continue;
        if (prev) {
          var dash = (i - prev.i > 1) ? ' stroke-dasharray="4 4" opacity=".5"' : "";
          o += '<line x1="' + F.X(prev.i) + '" y1="' + F.Y(prev.v) + '" x2="' + F.X(i) + '" y2="' + F.Y(v) + '" stroke="' + CCOL[ci] + '" stroke-width="2.6"' + dash + "/>";
        }
        prev = { i: i, v: v }; last = prev;
      }
      var ev = every(VIEW.n, W, 56);
      for (var j = 0; j < VIEW.n; j++) {
        var vv = val(brand, j, c.cc); if (vv == null) continue;
        o += '<circle cx="' + F.X(j) + '" cy="' + F.Y(vv) + '" r="4.5" fill="' + CCOL[ci] + '"/>';
        if ((last && j === last.i) || (VIEW.n - 1 - j) % ev === 0) o += tx(F.X(j), F.Y(vv) - 11, vv, { f: CCOL[ci], s: 17, w: 800 });
      }
      if (last) o += tx(W - R + 10, F.Y(last.v) + 6, c.name, { a: "start", f: CCOL[ci], s: 18, w: 800 });
    });
    return o + "</svg>";
  }

  /* ---- 표 ---- */
  function dateHead() {
    return VIEW.labels.map(function (d, i) {
      var p = VIEW.pts[i], cls = (i === VIEW.n - 1 ? "last" : "") + (p.source === "capture" ? " cap" : "");
      return '<th class="' + cls + '" title="' + (p.source === "capture" ? "캡처 집계표" : "자동 수집") + '">' + d + "</th>";
    }).join("");
  }
  function rankGrid(k) {
    var rk = VIEW.ranks[k], RN = 12;
    var h = "<tr><th>순위</th>" + dateHead() + "</tr>";
    for (var r = 0; r < RN; r++) {
      h += '<tr><td class="rk">' + (r + 1) + "</td>";
      for (var t = 0; t < VIEW.n; t++) {
        var b = rk[t][r];
        if (!b) { h += "<td></td>"; continue; }
        var st = isKB(b.b) ? ' style="background:' + BC[b.b].bg + ";color:" + BC[b.b].fg + ';font-weight:800"' : "";
        h += '<td class="cell" data-b="' + esc(b.b) + '" data-t="' + t + '" data-k="' + k + '"' + st + ">" + esc(sh(b.b)) + "<small>" + b.v + "</small></td>";
      }
      h += "</tr>";
    }
    return h;
  }
  function namesFor(k) {
    var N = VIEW.n;
    var names = VIEW.names.filter(function (n) { for (var t = 0; t < N; t++) { var v = val(n, t, k); if (v) return true; } return false; });
    names.sort(function (a, b) {
      var la = val(a, N - 1, k) || 0, lb = val(b, N - 1, k) || 0;
      if (lb !== la) return lb - la;
      var ma = 0, mb = 0;
      for (var t = 0; t < N; t++) { ma = Math.max(ma, val(a, t, k) || 0); mb = Math.max(mb, val(b, t, k) || 0); }
      return mb - ma || a.localeCompare(b);
    });
    return names;
  }
  function valTable(k) {
    var N = VIEW.n;
    var h = '<thead><tr><th class="name">브랜드</th>' + dateHead() + "<th>최대</th></tr></thead><tbody>";
    namesFor(k).forEach(function (n) {
      var mx = 0; for (var t = 0; t < N; t++) mx = Math.max(mx, val(n, t, k) || 0);
      var st = isKB(n) ? ' style="background:' + BC[n].bg + ";color:" + BC[n].fg + ';font-weight:800"' : "";
      h += '<tr class="brow" data-b="' + esc(n) + '"><td class="name"' + st + ">" + esc(n) + "</td>";
      for (var t2 = 0; t2 < N; t2++) {
        var v = val(n, t2, k), cls = (t2 === N - 1 ? "last " : "") + (v == null ? "dim" : (v === 0 ? "z" : ""));
        h += '<td class="' + cls + '"' + st + ">" + (v == null ? "·" : v) + "</td>";
      }
      h += '<td class="mx">' + mx + "</td></tr>";
    });
    return h + "</tbody>";
  }

  /* ---- 섹션 ---- */
  function secs() {
    return [{ k: "total", name: "총합계 (6개국)", short: "총합계", id: "br-tot" }]
      .concat(BR.countries.map(function (c) { return { k: c.cc, name: c.name, short: c.name, id: "br-" + c.cc }; }));
  }
  function render() {
    makeView();
    var out = "";
    secs().forEach(function (s, si) {
      var unit = s.k === "total" ? "6개국 합계" : s.name;
      out += '<section id="' + s.id + '">' +
        '<h2><span class="n">0' + (si + 1) + "</span>" + esc(s.name) + "</h2>" +
        '<p class="h2sub">브랜드 랭킹 → 추이 차트 → 브랜드별 값</p>' +
        '<div class="bcard"><p class="chart-title">브랜드 랭킹</p>' +
        '<p class="chart-note">단위: ' + unit + " 진입 개수 · 칸 아래 작은 숫자가 값 · 색칠된 칸 = K뷰티</p>" +
        '<div class="scroll"><table class="gridtbl">' + rankGrid(s.k) + "</table></div></div>" +
        '<div class="bcard"><p class="chart-title">' + (s.k === "total" ? "6개국 합계" : esc(s.name)) + " 추이</p>" +
        '<p class="chart-note">K뷰티만 색으로 표시 · 회색 = 기타 브랜드 · 점 위 숫자는 실제 값 · 점선 구간은 그 시점 표 밖</p>' +
        '<div id="ch-' + s.id + '"></div></div>' +
        '<div class="bcard"><button type="button" class="mini" data-csv="' + s.k + '">이 표 CSV</button>' +
        '<p class="chart-title">브랜드 × 시점</p>' +
        '<p class="chart-note">단위: ' + unit + " 진입 개수 · · = 그 시점 기록 없음 · 줄을 누르면 하이라이트 고정</p>" +
        '<div class="scroll" style="max-height:62vh"><table class="vtbl">' + valTable(s.k) + "</table></div></div>" +
        "</section>";
    });
    $("#br-sections").innerHTML = out;
    // 표는 최신 시점(오른쪽 끝)이 먼저 보이게
    document.querySelectorAll("#br-sections .scroll").forEach(function (el) { el.scrollLeft = el.scrollWidth; });
    drawCharts(locked);
    showSel(locked);
    setHL(locked);
  }
  function drawCharts(hi) { secs().forEach(function (s) { $("#ch-" + s.id).innerHTML = chart(s.k, hi); }); }

  /* ---- 하이라이트 · 툴팁 ---- */
  var hlStyle = document.createElement("style"); document.head.appendChild(hlStyle);
  function cssq(n) { return '[data-b="' + n.replace(/&/g, "&amp;").replace(/"/g, '\\"') + '"]'; }
  function setHL(n) {
    var root = $("#tab-brands");
    if (!n) { hlStyle.textContent = ""; root.classList.remove("hl"); return; }
    var q = cssq(n);
    hlStyle.textContent = "#tab-brands.hl " + q + ".cell{opacity:1;box-shadow:inset 0 0 0 2px #fff}" +
      "#tab-brands.hl tr" + q + " td{opacity:1}#tab-brands.hl tr" + q + " td.name{box-shadow:inset 3px 0 0 #fff}";
    root.classList.add("hl");
  }
  function showSel(n) {
    var c = $("#br-sel-card");
    if (!n || !VIEW.series[n]) { c.style.display = "none"; return; }
    c.style.display = "block";
    $("#br-sel-title").innerHTML = '<span style="color:' + (isKB(n) ? BC[n].fg : "#fff") + '">' + esc(n) + "</span>" + (isKB(n) ? " · K뷰티" : "");
    $("#br-ch-sel").innerHTML = countryChart(n);
  }
  function lock(n) { locked = (locked === n ? null : n); setHL(locked); showSel(locked); drawCharts(locked); }
  var tip = $("#br-tip");
  function tipFor(n, t, k) {
    var where = k === "total" ? "6개국 합계" : BR.countries.find(function (c) { return c.cc === k; }).name;
    var r = rankOf(n, t, k), v = val(n, t, k), tot = val(n, t, "total"), p = VIEW.pts[t];
    var col = isKB(n) ? BC[n].fg : "#fff";
    return '<b style="color:' + col + '">' + esc(n) + '</b> <span class="sub">' + where + " · " + p.date + (p.source === "capture" ? " (캡처)" : "") + "</span><br>" +
      (r ? r + "위 · " : "") + "진입 " + (v == null ? "-" : v) + "개" + (k === "total" ? "" : " · 6개국 합 " + (tot == null ? "-" : tot) + "개");
  }
  function inTab(e) { return e.target.closest && e.target.closest("#tab-brands"); }
  document.addEventListener("mouseover", function (e) {
    if (!inTab(e)) return;
    var el = e.target.closest("[data-b]"); if (!el) return;
    var n = el.getAttribute("data-b");
    if (!locked) setHL(n);
    if (el.classList.contains("cell")) { tip.innerHTML = tipFor(n, +el.getAttribute("data-t"), el.getAttribute("data-k")); tip.style.display = "block"; }
  });
  document.addEventListener("mousemove", function (e) {
    if (tip.style.display !== "block") return;
    var x = e.clientX + 16, y = e.clientY + 16;
    if (x + 360 > innerWidth) x = e.clientX - 360;
    if (y + 100 > innerHeight) y = e.clientY - 100;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  });
  document.addEventListener("mouseout", function (e) {
    if (!inTab(e) || !e.target.closest("[data-b]")) return;
    tip.style.display = "none";
    if (!locked) setHL(null);
  });
  document.addEventListener("click", function (e) {
    if (!inTab(e)) return;
    var csv = e.target.closest("button[data-csv]");
    if (csv) { var k = csv.getAttribute("data-csv"); saveFile("아마존뷰티_" + (k === "total" ? "총합계" : k) + "_" + BR.points[BR.points.length - 1].date + ".csv", csvSection(k)); return; }
    var rb = e.target.closest("button[data-range]");
    if (rb) { range = +rb.getAttribute("data-range"); document.querySelectorAll("#br-range button").forEach(function (x) { x.setAttribute("aria-pressed", x === rb); }); render(); return; }
    var el = e.target.closest("[data-b]"); if (!el) return;
    lock(el.getAttribute("data-b"));
  });

  /* ---- CSV ---- */
  function saveFile(filename, text) {
    var blob = new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 600);
  }
  function qq(s) { return '"' + String(s).replace(/"/g, '""') + '"'; }
  function csvAll() {
    var cn = BR.countries.map(function (c) { return c.name; });
    var rows = ["시점,출처,브랜드," + cn.join(",") + ",총합계,총합계순위"];
    BR.points.forEach(function (p, t) {
      Object.keys(BR.series).forEach(function (b) {
        var s = BR.series[b], tot = s.values.total[t];
        if (tot == null) return;
        rows.push([p.date, p.source === "capture" ? "캡처" : "자동", qq(b)].concat(BR.countries.map(function (c) { var v = s.values[c.cc][t]; return v == null ? "" : v; }))
          .concat([tot, s.ranks.total[t] || ""]).join(","));
      });
    });
    return rows.join("\n");
  }
  function csvSection(k) {
    var rows = ["브랜드," + VIEW.pts.map(function (p) { return p.date; }).join(",")];
    namesFor(k).forEach(function (n) {
      rows.push([qq(n)].concat(VIEW.pts.map(function (_, t) { var v = val(n, t, k); return v == null ? "" : v; })).join(","));
    });
    return rows.join("\n");
  }

  /* ---- 시작 ---- */
  function init(data) {
    BR = data;
    BR.kbeauty.forEach(function (k) { BC[k.brand] = { fg: k.fg, bg: k.bg }; });
    KB = BR.kbeauty.map(function (k) { return k.brand; }).filter(function (n) { return BR.series[n]; });
    var first = BR.points[0], last = BR.points[BR.points.length - 1];
    var nCap = BR.points.filter(function (p) { return p.source === "capture"; }).length;
    $("#br-meta").textContent = BR.points.length + "개 시점 · " + first.date + " ~ " + last.date.slice(5) +
      " · 숫자 = 각 나라 베스트셀러 Top 100 진입 개수 · 칸에 마우스를 올리면 같은 브랜드가 전부 표시되고, 누르면 고정된다";
    $("#br-nav").innerHTML = secs().map(function (s) { return '<a class="' + (s.k === "total" ? "tot" : "") + '" href="#' + s.id + '">' + esc(s.short) + "</a>"; }).join("");
    $("#br-legend").innerHTML = KB.map(function (n) {
      return '<button type="button" data-b="' + esc(n) + '" style="background:' + BC[n].bg + ";color:" + BC[n].fg + ";border-color:" + BC[n].fg + '">' + esc(n) + "</button>";
    }).join("") + ["CeraVe", "L'Oréal Paris", "NIVEA", "Garnier"].filter(function (n) { return BR.series[n]; }).map(function (n) {
      return '<button type="button" class="off" data-b="' + esc(n) + '">' + esc(n) + "</button>";
    }).join("");
    var unres = (BR.unresolved[BR.unresolved.length - 1] || {}).by_country || {};
    var nUn = Object.keys(unres).reduce(function (s, k) { return s + unres[k]; }, 0);
    $("#br-foot").innerHTML =
      "<p>· " + first.date + " ~ " + (BR.points[nCap - 1] || first).date + " " + nCap + "개 시점은 사용자 제공 캡처 집계표(상위 25~35개 브랜드)를 그대로 옮긴 값이다. 표에 없던 브랜드는 빈칸(·).</p>" +
      "<p>· 그 뒤는 매일 09:07 KST 자동 수집(각 나라 Beauty Top 100 전체). 브랜드는 제품 상세 페이지의 공식 브랜드 표기로 정하고, 표기가 다른 이름은 한 브랜드로 묶었다.</p>" +
      (nUn ? "<p>· 최근 시점에 아직 브랜드를 확인하지 못한 제품 " + nUn + "개는 집계에서 빠져 있다 (다음 수집 때 채워진다).</p>" : "") +
      "<p>· 순위는 각 시점 값 기준으로 매긴 자체 계산치. 동점은 이름순.</p>";
    $("#br-dl-all").onclick = function () { saveFile("아마존뷰티6개국_" + last.date + "_전체.csv", csvAll()); };
    $("#br-clear").onclick = function () { locked = null; setHL(null); showSel(null); drawCharts(null); };
    render();
  }
  fetch("data/brands.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).then(init)
    .catch(function (e) { $("#br-sections").textContent = "브랜드 데이터를 불러오지 못했습니다."; console.error(e); });
})();
