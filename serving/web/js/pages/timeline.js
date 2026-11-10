/**
 * Timeline page: failed-attempt curve, hour x day heatmap, targeted users.
 */
(function () {
  "use strict";

  var DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  var timelineChart = null;
  var heatChart = null;
  var usersChart = null;

  STRIX.mount({
    active: "timeline",
    title: "Timeline",
    subtitle: "When the attacks happen, and which accounts they try.",
    html:
      '<section class="grid-dashboard">' +
      wide("Failures over time", "Zoom and brush. This chart counts failed attempts only.", '<div id="chart-timeline" class="chart"></div>') +
      card("Heatmap hour x day", '<div id="chart-heatmap" class="chart"></div>') +
      card("Targeted users", '<div id="chart-users" class="chart"></div>') +
      "</section>",
    start: function () {
      timelineChart = STRIX.mountChart("chart-timeline");
      heatChart = STRIX.mountChart("chart-heatmap");
      usersChart = STRIX.mountChart("chart-users");
      refresh();
    },
    onChange: refresh
  });

  function wide(title, hint, body) {
    return (
      '<article class="panel panel--wide"><div class="panel__head"><h2 class="panel__title">' +
      title +
      '</h2><p class="panel__hint">' +
      hint +
      "</p></div>" +
      body +
      "</article>"
    );
  }

  function card(title, body) {
    return (
      '<article class="panel"><div class="panel__head"><h2 class="panel__title">' +
      title +
      "</h2></div>" +
      body +
      "</article>"
    );
  }

  function refresh() {
    Promise.all([
      STRIX.api("/api/timeline", { granularity: "hour" }),
      STRIX.api("/api/top-users", { limit: 12 })
    ])
      .then(function (rows) {
        renderTimeline(rows[0] || []);
        renderHeat(rows[0] || []);
        renderUsers(rows[1] || []);
        STRIX.resizeCharts();
      })
      .catch(function (err) {
        STRIX.toast("Timeline failed", String(err.message || err));
      });
  }

  function renderTimeline(rows) {
    var theme = STRIX.chartTheme();
    timelineChart.setOption(
      Object.assign({}, STRIX.anim(), {
        tooltip: { trigger: "axis" },
        grid: { left: 48, right: 16, top: 16, bottom: 64 },
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
          axisLabel: { color: theme.muted },
          splitLine: { lineStyle: { color: theme.border } }
        },
        dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8 }],
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

  function renderHeat(rows) {
    var theme = STRIX.chartTheme();
    var matrix = {};
    var max = 0;
    rows.forEach(function (row) {
      var dt = new Date(row.bucket);
      if (isNaN(dt.getTime())) return;
      var key = dt.getUTCDay() + "-" + dt.getUTCHours();
      matrix[key] = (matrix[key] || 0) + Number(row.failures || 0);
      max = Math.max(max, matrix[key]);
    });
    var data = [];
    for (var day = 0; day < 7; day += 1) {
      for (var hour = 0; hour < 24; hour += 1) {
        data.push([hour, day, matrix[day + "-" + hour] || 0]);
      }
    }
    heatChart.setOption(
      Object.assign({}, STRIX.anim(), {
        tooltip: {
          formatter: function (p) {
            return DAY_NAMES[p.value[1]] + " " + String(p.value[0]).padStart(2, "0") + ":00 — " + STRIX.formatNumber(p.value[2]);
          }
        },
        grid: { left: 48, right: 16, top: 12, bottom: 28 },
        xAxis: {
          type: "category",
          data: Array.from({ length: 24 }, function (_, i) { return String(i).padStart(2, "0"); }),
          axisLabel: { color: theme.muted, fontSize: 10 }
        },
        yAxis: { type: "category", data: DAY_NAMES, axisLabel: { color: theme.muted } },
        visualMap: {
          min: 0,
          max: Math.max(max, 1),
          orient: "horizontal",
          left: "center",
          bottom: 0,
          textStyle: { color: theme.muted },
          inRange: { color: [theme.surface, "#164e63", theme.accent, theme.danger] }
        },
        series: [{ type: "heatmap", data: data }]
      }),
      true
    );
  }

  function renderUsers(rows) {
    var theme = STRIX.chartTheme();
    var labels = rows.map(function (row) { return row.username; }).reverse();
    var values = rows.map(function (row) { return row.failures; }).reverse();
    usersChart.setOption(
      Object.assign({}, STRIX.anim(), {
        tooltip: { trigger: "axis" },
        grid: { left: 88, right: 16, top: 12, bottom: 24 },
        xAxis: { type: "value", axisLabel: { color: theme.muted }, splitLine: { lineStyle: { color: theme.border } } },
        yAxis: { type: "category", data: labels, axisLabel: { color: theme.muted, fontFamily: theme.mono } },
        series: [{ type: "bar", data: values, itemStyle: { color: theme.warning, borderRadius: [0, 4, 4, 0] } }]
      }),
      true
    );
  }
})();
