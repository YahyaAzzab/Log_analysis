/**
 * Dashboard: the short operational picture, with links to each full page.
 */
(function () {
  "use strict";

  var timelineChart = null;

  STRIX.mount({
    active: "dashboard",
    intro: true,
    title: "Dashboard",
    subtitle: "What needs attention now. Open a page for the full record.",
    html:
      '<section class="kpi-row" aria-label="KPIs">' +
      kpi("Invalid user", "kpi-invalid") +
      kpi("Failed password", "kpi-failed") +
      kpi("Success password", "kpi-success") +
      kpi("Unique IPs", "kpi-ips") +
      "</section>" +
      '<section class="grid-dashboard">' +
      panel("Attack pressure", "Failed attempts. Full view on Timeline.", '<div id="chart-timeline" class="chart"></div>', "panel--wide") +
      panel("Most active IPs", '<a href="/ips.html">Open the directory</a>', '<div id="home-ips"></div>') +
      panel("Latest auth lines", '<a href="/events.html">Open the log</a>', '<div id="home-events"></div>') +
      "</section>",
    start: function () {
      timelineChart = STRIX.mountChart("chart-timeline");
      refresh();
    },
    onChange: refresh
  });

  function kpi(label, id) {
    return (
      '<article class="kpi-card"><p class="kpi-card__label">' +
      label +
      '</p><p class="kpi-card__value mono" id="' +
      id +
      '">--</p></article>'
    );
  }

  function panel(title, hint, body, extra) {
    return (
      '<article class="panel ' +
      (extra || "") +
      '"><div class="panel__head"><h2 class="panel__title">' +
      title +
      '</h2><p class="panel__hint">' +
      hint +
      "</p></div>" +
      body +
      "</article>"
    );
  }

  function refresh() {
    Promise.all([
      STRIX.api("/api/kpis", { scope: "all" }),
      STRIX.api("/api/timeline", { granularity: "hour" }),
      STRIX.api("/api/ips", { scope: "all", limit: 5 }),
      STRIX.api("/api/events", { scope: "all", page_size: 6 })
    ])
      .then(function (rows) {
        var data = rows[0] || {};
        STRIX.animateNumber(document.getElementById("kpi-invalid"), data.invalid_users);
        STRIX.animateNumber(document.getElementById("kpi-failed"), data.failed_passwords);
        STRIX.animateNumber(document.getElementById("kpi-success"), data.success_passwords);
        STRIX.animateNumber(document.getElementById("kpi-ips"), data.unique_ips);
        renderTimeline(rows[1] || []);
        renderIps(rows[2] || []);
        renderEvents((rows[3] && rows[3].items) || []);
        STRIX.resizeCharts();
      })
      .catch(function (err) {
        STRIX.toast("Dashboard refresh failed", String(err.message || err));
      });
  }

  function renderTimeline(rows) {
    if (!timelineChart) return;
    var theme = STRIX.chartTheme();
    timelineChart.setOption(
      Object.assign({}, STRIX.anim(), {
        backgroundColor: "transparent",
        tooltip: { trigger: "axis" },
        grid: { left: 48, right: 16, top: 16, bottom: 56 },
        xAxis: {
          type: "category",
          data: rows.map(function (row) { return row.bucket; }),
          axisLabel: {
            color: theme.muted,
            formatter: function (value) { return String(value).slice(5, 16); }
          }
        },
        yAxis: {
          type: "value",
          axisLabel: { color: theme.muted, fontFamily: theme.mono },
          splitLine: { lineStyle: { color: theme.border } }
        },
        dataZoom: [{ type: "inside" }, { type: "slider", height: 16, bottom: 8 }],
        series: [{
          type: "line",
          smooth: true,
          showSymbol: false,
          data: rows.map(function (row) { return row.failures; }),
          lineStyle: { color: theme.accent, width: 2 },
          areaStyle: { color: "rgba(34,211,238,0.12)" }
        }]
      }),
      true
    );
  }

  function renderIps(rows) {
    var node = document.getElementById("home-ips");
    if (!node) return;
    if (!rows.length) {
      node.innerHTML = '<p class="panel__hint">No IP in this range.</p>';
      return;
    }
    node.innerHTML =
      '<ul class="drawer__list">' +
      rows
        .map(function (row) {
          return (
            '<li><a class="mono" href="' +
            STRIX.ipHref(row.ip) +
            '">' +
            STRIX.escapeHtml(row.ip) +
            "</a><span class=\"mono\">" +
            STRIX.formatNumber(row.times || row.failures || 0) +
            "</span></li>"
          );
        })
        .join("") +
      "</ul>";
  }

  function renderEvents(rows) {
    var node = document.getElementById("home-events");
    if (!node) return;
    if (!rows.length) {
      node.innerHTML = '<p class="panel__hint">No auth line in this range.</p>';
      return;
    }
    node.innerHTML =
      '<ul class="drawer__list">' +
      rows
        .map(function (row) {
          var stamp = String(row.ts || "");
          return (
            "<li><span>" +
            STRIX.escapeHtml(stamp.slice(0, 10) + " " + stamp.slice(11, 19)) +
            " · " +
            STRIX.escapeHtml(STRIX.outcome(row.event_type)) +
            '</span><a class="mono" href="' +
            STRIX.ipHref(row.ip) +
            '">' +
            STRIX.escapeHtml(row.ip) +
            "</a></li>"
          );
        })
        .join("") +
      "</ul>";
  }
})();
