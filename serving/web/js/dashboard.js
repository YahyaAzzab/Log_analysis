/**
 * STRIX Failed logins dashboard: filters, API sync, ECharts views.
 */
(function () {
  "use strict";

  var PAGE_SIZE = 10;
  var DEBOUNCE_MS = 280;
  var DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

  var state = {
    filters: {
      date_from: "",
      date_to: "",
      country: "",
      ip: "",
      username: "",
      bots_only: false,
      search: "",
    },
    table: {
      page: 1,
      sortKey: "failed_count",
      sortDir: "desc",
      rows: [],
    },
    charts: {},
    worldReady: false,
    loading: false,
  };

  var els = {};

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    cacheElements();
    if (!els.dashboard || typeof echarts === "undefined") {
      return;
    }

    bindFilters();
    bindTable();
    initCharts();
    loadWorldMap()
      .catch(function () {
        state.worldReady = false;
      })
      .finally(function () {
        checkHealth();
        refreshAll();
      });

    window.addEventListener("resize", debounce(resizeCharts, 150));
  }

  function cacheElements() {
    els.dashboard = document.getElementById("dashboard");
    els.dateFrom = document.getElementById("filter-date-from");
    els.dateTo = document.getElementById("filter-date-to");
    els.country = document.getElementById("filter-country");
    els.ip = document.getElementById("filter-ip");
    els.username = document.getElementById("filter-username");
    els.botsOnly = document.getElementById("filter-bots-only");
    els.search = document.getElementById("filter-search");
    els.reset = document.getElementById("filter-reset");
    els.tableBody = document.getElementById("table-bots-body");
    els.table = document.getElementById("table-bots");
    els.tablePrev = document.getElementById("table-prev");
    els.tableNext = document.getElementById("table-next");
    els.tableMeta = document.getElementById("table-page-meta");
    els.pipelineText = document.getElementById("pipeline-status-text");
    els.pipelineMeta = document.getElementById("pipeline-status-meta");
    els.kpi = {
      total_failures: document.querySelector('[data-kpi="total_failures"]'),
      unique_ips: document.querySelector('[data-kpi="unique_ips"]'),
      bots_detected: document.querySelector('[data-kpi="bots_detected"]'),
      countries: document.querySelector('[data-kpi="countries"]'),
    };
  }

  function bindFilters() {
    var inputs = [
      els.dateFrom,
      els.dateTo,
      els.country,
      els.ip,
      els.username,
      els.search,
    ];
    inputs.forEach(function (input) {
      if (!input) return;
      input.addEventListener("input", debounce(onFilterChange, DEBOUNCE_MS));
      input.addEventListener("change", onFilterChange);
    });
    if (els.botsOnly) {
      els.botsOnly.addEventListener("change", onFilterChange);
    }
    if (els.reset) {
      els.reset.addEventListener("click", function () {
        els.dateFrom.value = "";
        els.dateTo.value = "";
        els.country.value = "";
        els.ip.value = "";
        els.username.value = "";
        els.search.value = "";
        els.botsOnly.checked = false;
        state.table.page = 1;
        onFilterChange();
      });
    }
  }

  function bindTable() {
    if (els.table) {
      els.table.querySelectorAll("th[data-sort]").forEach(function (th) {
        th.addEventListener("click", function () {
          var key = th.getAttribute("data-sort");
          if (state.table.sortKey === key) {
            state.table.sortDir = state.table.sortDir === "asc" ? "desc" : "asc";
          } else {
            state.table.sortKey = key;
            state.table.sortDir = key === "ip" || key === "country" || key === "city" || key === "org"
              ? "asc"
              : "desc";
          }
          state.table.page = 1;
          renderTable();
        });
      });
    }
    if (els.tablePrev) {
      els.tablePrev.addEventListener("click", function () {
        if (state.table.page > 1) {
          state.table.page -= 1;
          renderTable();
        }
      });
    }
    if (els.tableNext) {
      els.tableNext.addEventListener("click", function () {
        var pages = Math.max(1, Math.ceil(state.table.rows.length / PAGE_SIZE));
        if (state.table.page < pages) {
          state.table.page += 1;
          renderTable();
        }
      });
    }
  }

  function onFilterChange() {
    readFiltersFromDom();
    state.table.page = 1;
    refreshAll();
  }

  function readFiltersFromDom() {
    state.filters.date_from = (els.dateFrom && els.dateFrom.value) || "";
    state.filters.date_to = (els.dateTo && els.dateTo.value) || "";
    state.filters.country = (els.country && els.country.value.trim()) || "";
    state.filters.ip = (els.ip && els.ip.value.trim()) || "";
    state.filters.username = (els.username && els.username.value.trim()) || "";
    state.filters.bots_only = !!(els.botsOnly && els.botsOnly.checked);
    state.filters.search = (els.search && els.search.value.trim()) || "";

    applySearchHeuristic();
  }

  function applySearchHeuristic() {
    var q = state.filters.search;
    if (!q) return;
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(q)) {
      state.filters.ip = q;
      if (els.ip) els.ip.value = q;
      return;
    }
    if (q.length <= 3) {
      state.filters.country = q;
      if (els.country) els.country.value = q;
      return;
    }
    state.filters.username = q;
    if (els.username) els.username.value = q;
  }

  function queryParams() {
    var params = new URLSearchParams();
    if (state.filters.date_from) {
      params.set("date_from", state.filters.date_from + "T00:00:00");
    }
    if (state.filters.date_to) {
      params.set("date_to", state.filters.date_to + "T23:59:59");
    }
    if (state.filters.country) params.set("country", state.filters.country);
    if (state.filters.ip) params.set("ip", state.filters.ip);
    if (state.filters.username) params.set("username", state.filters.username);
    if (state.filters.bots_only) params.set("bots_only", "true");
    return params;
  }

  function apiUrl(path, extra) {
    var params = queryParams();
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        params.set(key, String(extra[key]));
      });
    }
    var qs = params.toString();
    return path + (qs ? "?" + qs : "");
  }

  function token(name, fallback) {
    var value = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    return value || fallback;
  }

  function chartTheme() {
    return {
      bg: token("--strix-bg", "#0B0F1A"),
      surface: token("--strix-surface", "#121826"),
      text: token("--strix-text", "#E5E7EB"),
      muted: token("--strix-text-muted", "#9CA3AF"),
      accent: token("--strix-accent", "#22D3EE"),
      danger: token("--strix-danger", "#F43F5E"),
      warning: token("--strix-warning", "#F59E0B"),
      border: token("--strix-border", "rgba(148,163,184,0.16)"),
      mono: token("--strix-font-mono", "JetBrains Mono, monospace"),
      sans: token("--strix-font-sans", "Inter, sans-serif"),
    };
  }

  function initCharts() {
    state.charts.timeline = echarts.init(document.getElementById("chart-timeline"));
    state.charts.map = echarts.init(document.getElementById("chart-map"));
    state.charts.topIps = echarts.init(document.getElementById("chart-top-ips"));
    state.charts.topUsers = echarts.init(document.getElementById("chart-top-users"));
    state.charts.countries = echarts.init(document.getElementById("chart-countries"));
    state.charts.heatmap = echarts.init(document.getElementById("chart-heatmap"));
  }

  function resizeCharts() {
    Object.keys(state.charts).forEach(function (key) {
      if (state.charts[key]) state.charts[key].resize();
    });
  }

  function loadWorldMap() {
    return fetch("https://cdn.jsdelivr.net/npm/echarts@4.9.0/map/json/world.json")
      .then(function (res) {
        if (!res.ok) throw new Error("world map fetch failed");
        return res.json();
      })
      .then(function (geo) {
        echarts.registerMap("world", geo);
        state.worldReady = true;
      });
  }

  function setLoading(isLoading) {
    state.loading = isLoading;
    Object.keys(els.kpi).forEach(function (key) {
      if (els.kpi[key]) {
        els.kpi[key].classList.toggle("skeleton", isLoading);
      }
    });
    [
      "chart-timeline",
      "chart-map",
      "chart-top-ips",
      "chart-top-users",
      "chart-countries",
      "chart-heatmap",
    ].forEach(function (id) {
      var node = document.getElementById(id);
      if (node) node.classList.toggle("skeleton-block", isLoading);
    });
  }

  function setEmpty(id, isEmpty) {
    var node = document.getElementById(id);
    if (node) node.hidden = !isEmpty;
  }

  function checkHealth() {
    fetch("/api/health")
      .then(function (res) {
        return res.ok ? res.json() : Promise.reject();
      })
      .then(function () {
        els.pipelineText.textContent = "Online";
        els.pipelineText.className = "sidebar__status-value is-ok";
        els.pipelineMeta.textContent = "load OK · /api/health";
      })
      .catch(function () {
        els.pipelineText.textContent = "Unavailable";
        els.pipelineText.className = "sidebar__status-value is-bad";
        els.pipelineMeta.textContent = "API / DB unreachable";
      });
  }

  function refreshAll() {
    setLoading(true);
    var params = queryParams();

    Promise.all([
      fetchJson(apiUrl("/api/kpis")),
      fetchJson(apiUrl("/api/timeline", { granularity: "hour" })),
      fetchJson(apiUrl("/api/map")),
      fetchJson(apiUrl("/api/top-ips", { limit: 10 })),
      fetchJson(apiUrl("/api/top-users", { limit: 10 })),
      fetchJson(apiUrl("/api/countries", { limit: 12 })),
      fetchJson(apiUrl("/api/bots", { limit: 500, bots_only: "true" })),
    ])
      .then(function (results) {
        renderKpis(results[0] || {});
        renderTimeline(results[1] || []);
        renderMap(results[2] || []);
        renderTopIps(results[3] || []);
        renderTopUsers(results[4] || []);
        renderCountries(results[5] || []);
        renderHeatmap(results[1] || []);
        state.table.rows = results[6] || [];
        renderTable();
      })
      .catch(function (err) {
        console.error("dashboard refresh failed", err);
        renderKpis({});
        setEmpty("empty-timeline", true);
        setEmpty("empty-map", true);
        setEmpty("empty-top-ips", true);
        setEmpty("empty-top-users", true);
        setEmpty("empty-countries", true);
        setEmpty("empty-heatmap", true);
        state.table.rows = [];
        renderTable();
      })
      .finally(function () {
        setLoading(false);
        resizeCharts();
      });

    return params;
  }

  function fetchJson(url) {
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error(url + " -> " + res.status);
      return res.json();
    });
  }

  function renderKpis(data) {
    setKpi("total_failures", data.total_failures);
    setKpi("unique_ips", data.unique_ips);
    setKpi("bots_detected", data.bots_detected);
    setKpi("countries", data.countries);
  }

  function setKpi(key, value) {
    var node = els.kpi[key];
    if (!node) return;
    node.classList.remove("skeleton");
    node.textContent = formatNumber(value == null ? 0 : value);
  }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString("en-US");
  }

  function renderTimeline(rows) {
    var theme = chartTheme();
    var empty = !rows.length;
    setEmpty("empty-timeline", empty);
    if (empty) {
      state.charts.timeline.clear();
      return;
    }

    var times = rows.map(function (row) {
      return row.bucket;
    });
    var values = rows.map(function (row) {
      return row.failures;
    });

    state.charts.timeline.setOption({
      backgroundColor: "transparent",
      textStyle: { fontFamily: theme.sans, color: theme.muted },
      tooltip: { trigger: "axis" },
      grid: { left: 48, right: 24, top: 24, bottom: 72 },
      xAxis: {
        type: "category",
        data: times,
        axisLine: { lineStyle: { color: theme.border } },
        axisLabel: {
          color: theme.muted,
          formatter: function (value) {
            return String(value).slice(5, 16);
          },
        },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: theme.muted, fontFamily: theme.mono },
        splitLine: { lineStyle: { color: theme.border } },
      },
      dataZoom: [
        { type: "inside", start: 0, end: 100 },
        {
          type: "slider",
          height: 18,
          bottom: 12,
          borderColor: theme.border,
          fillerColor: "rgba(34,211,238,0.18)",
          handleStyle: { color: theme.accent },
          textStyle: { color: theme.muted },
        },
      ],
      series: [
        {
          type: "line",
          smooth: true,
          showSymbol: false,
          data: values,
          lineStyle: { color: theme.accent, width: 2 },
          areaStyle: { color: "rgba(34,211,238,0.12)" },
        },
      ],
    }, true);
  }

  function renderMap(rows) {
    var theme = chartTheme();
    var points = rows
      .filter(function (row) {
        return row.lat != null && row.lon != null;
      })
      .map(function (row) {
        return {
          name: row.ip,
          value: [Number(row.lon), Number(row.lat), Number(row.failures || 0)],
          ip: row.ip,
          country: row.country,
          city: row.city,
          failures: row.failures,
          is_bot: row.is_bot,
        };
      });

    var empty = !points.length || !state.worldReady;
    setEmpty("empty-map", empty);
    if (empty) {
      state.charts.map.clear();
      return;
    }

    var maxVal = points.reduce(function (max, item) {
      return Math.max(max, item.value[2]);
    }, 1);

    state.charts.map.setOption({
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        formatter: function (params) {
          var d = params.data || {};
          return (
            (d.ip || params.name) +
            "<br/>" +
            (d.city || "Unknown") +
            ", " +
            (d.country || "?") +
            "<br/>Attempts: " +
            formatNumber(d.failures || 0)
          );
        },
      },
      geo: {
        map: "world",
        roam: true,
        itemStyle: {
          areaColor: theme.surface,
          borderColor: theme.border,
        },
        emphasis: {
          itemStyle: { areaColor: "#1e293b" },
        },
      },
      series: [
        {
          type: "scatter",
          coordinateSystem: "geo",
          data: points,
          symbolSize: function (val) {
            return 6 + (Math.sqrt(val[2]) / Math.sqrt(maxVal)) * 22;
          },
          itemStyle: {
            color: theme.danger,
            shadowBlur: 12,
            shadowColor: "rgba(244,63,94,0.45)",
          },
        },
      ],
    }, true);

    state.charts.map.off("click");
    state.charts.map.on("click", function (params) {
      if (!params.data || !params.data.ip) return;
      applyIpFilter(params.data.ip);
    });
  }

  function renderTopIps(rows) {
    var theme = chartTheme();
    var empty = !rows.length;
    setEmpty("empty-top-ips", empty);
    if (empty) {
      state.charts.topIps.clear();
      return;
    }
    var labels = rows.map(function (row) { return row.ip; }).reverse();
    var values = rows.map(function (row) { return row.failures; }).reverse();

    state.charts.topIps.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      grid: { left: 110, right: 24, top: 16, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { color: theme.muted, fontFamily: theme.mono },
        splitLine: { lineStyle: { color: theme.border } },
      },
      yAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: theme.muted, fontFamily: theme.mono, fontSize: 10 },
      },
      series: [
        {
          type: "bar",
          data: values,
          itemStyle: { color: theme.accent, borderRadius: [0, 4, 4, 0] },
        },
      ],
    }, true);

    state.charts.topIps.off("click");
    state.charts.topIps.on("click", function (params) {
      if (params.name) applyIpFilter(params.name);
    });
  }

  function renderTopUsers(rows) {
    var theme = chartTheme();
    var empty = !rows.length;
    setEmpty("empty-top-users", empty);
    if (empty) {
      state.charts.topUsers.clear();
      return;
    }
    var labels = rows.map(function (row) { return row.username; }).reverse();
    var values = rows.map(function (row) { return row.failures; }).reverse();

    state.charts.topUsers.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      grid: { left: 80, right: 24, top: 16, bottom: 24 },
      xAxis: {
        type: "value",
        axisLabel: { color: theme.muted, fontFamily: theme.mono },
        splitLine: { lineStyle: { color: theme.border } },
      },
      yAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: theme.muted, fontFamily: theme.mono },
      },
      series: [
        {
          type: "bar",
          data: values,
          itemStyle: { color: theme.warning, borderRadius: [0, 4, 4, 0] },
        },
      ],
    }, true);
  }

  function renderCountries(rows) {
    var theme = chartTheme();
    var empty = !rows.length;
    setEmpty("empty-countries", empty);
    if (empty) {
      state.charts.countries.clear();
      return;
    }

    state.charts.countries.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "item" },
      legend: {
        type: "scroll",
        orient: "vertical",
        right: 0,
        top: 16,
        bottom: 16,
        textStyle: { color: theme.muted, fontSize: 11 },
      },
      series: [
        {
          type: "pie",
          radius: ["48%", "72%"],
          center: ["38%", "50%"],
          data: rows.map(function (row) {
            return {
              name: row.country_code || row.country || "??",
              value: row.failures,
            };
          }),
          label: { color: theme.muted },
          itemStyle: {
            borderColor: theme.bg,
            borderWidth: 2,
          },
          color: [
            theme.accent,
            theme.danger,
            theme.warning,
            "#38bdf8",
            "#2dd4bf",
            "#34d399",
            "#fb7185",
            "#fbbf24",
          ],
        },
      ],
    }, true);
  }

  function renderHeatmap(timelineRows) {
    var theme = chartTheme();
    var matrix = {};
    var max = 0;

    timelineRows.forEach(function (row) {
      if (!row.bucket) return;
      var dt = new Date(row.bucket);
      if (isNaN(dt.getTime())) return;
      var day = dt.getUTCDay();
      var hour = dt.getUTCHours();
      var key = day + "-" + hour;
      matrix[key] = (matrix[key] || 0) + Number(row.failures || 0);
      max = Math.max(max, matrix[key]);
    });

    var data = [];
    for (var day = 0; day < 7; day += 1) {
      for (var hour = 0; hour < 24; hour += 1) {
        data.push([hour, day, matrix[day + "-" + hour] || 0]);
      }
    }

    var empty = max === 0;
    setEmpty("empty-heatmap", empty);
    if (empty) {
      state.charts.heatmap.clear();
      return;
    }

    state.charts.heatmap.setOption({
      backgroundColor: "transparent",
      tooltip: {
        formatter: function (p) {
          return (
            DAY_NAMES[p.value[1]] +
            " " +
            String(p.value[0]).padStart(2, "0") +
            ":00 — " +
            formatNumber(p.value[2])
          );
        },
      },
      grid: { left: 48, right: 24, top: 16, bottom: 28 },
      xAxis: {
        type: "category",
        data: Array.from({ length: 24 }, function (_, i) {
          return String(i).padStart(2, "0");
        }),
        axisLabel: { color: theme.muted, fontFamily: theme.mono, fontSize: 10 },
      },
      yAxis: {
        type: "category",
        data: DAY_NAMES,
        axisLabel: { color: theme.muted },
      },
      visualMap: {
        min: 0,
        max: max,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        inRange: { color: ["#121826", "#164e63", theme.accent, theme.danger] },
        textStyle: { color: theme.muted },
      },
      series: [
        {
          type: "heatmap",
          data: data,
          emphasis: {
            itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.4)" },
          },
        },
      ],
    }, true);
  }

  function renderTable() {
    var rows = state.table.rows.slice();
    var key = state.table.sortKey;
    var dir = state.table.sortDir === "asc" ? 1 : -1;

    rows.sort(function (a, b) {
      var av = a[key];
      var bv = b[key];
      if (key === "burst") {
        av = a.failed_count;
        bv = b.failed_count;
      }
      if (typeof av === "boolean") {
        av = av ? 1 : 0;
        bv = bv ? 1 : 0;
      }
      if (av == null) av = "";
      if (bv == null) bv = "";
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });

    var pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    if (state.table.page > pages) state.table.page = pages;
    var start = (state.table.page - 1) * PAGE_SIZE;
    var pageRows = rows.slice(start, start + PAGE_SIZE);

    setEmpty("empty-table", rows.length === 0);
    if (els.tableMeta) {
      els.tableMeta.textContent = state.table.page + " / " + pages;
    }
    if (els.tablePrev) els.tablePrev.disabled = state.table.page <= 1;
    if (els.tableNext) els.tableNext.disabled = state.table.page >= pages;

    if (els.table) {
      els.table.querySelectorAll("th[data-sort]").forEach(function (th) {
        th.classList.toggle(
          "is-sorted",
          th.getAttribute("data-sort") === state.table.sortKey
        );
      });
    }

    if (!els.tableBody) return;
    if (!pageRows.length) {
      els.tableBody.innerHTML = "";
      return;
    }

    els.tableBody.innerHTML = pageRows
      .map(function (row) {
        var active = state.filters.ip === row.ip ? " is-active" : "";
        var botBadge = row.is_bot
          ? '<span class="badge badge--bot">BOT</span>'
          : '<span class="badge badge--clean">—</span>';
        return (
          "<tr class=\"" +
          active.trim() +
          "\" data-ip=\"" +
          escapeHtml(row.ip || "") +
          "\">" +
          "<td class=\"mono\">" +
          escapeHtml(row.ip || "") +
          "</td>" +
          "<td>" +
          escapeHtml(row.country || row.country_code || "—") +
          "</td>" +
          "<td>" +
          escapeHtml(row.city || "—") +
          "</td>" +
          "<td>" +
          escapeHtml(row.org || "—") +
          "</td>" +
          "<td class=\"mono\">" +
          formatNumber(row.failed_count || row.failures_in_range || 0) +
          "</td>" +
          "<td class=\"mono\">—</td>" +
          "<td>" +
          botBadge +
          "</td>" +
          "</tr>"
        );
      })
      .join("");

    els.tableBody.querySelectorAll("tr[data-ip]").forEach(function (tr) {
      tr.addEventListener("click", function () {
        applyIpFilter(tr.getAttribute("data-ip"));
      });
    });
  }

  function applyIpFilter(ip) {
    if (!ip) return;
    if (els.ip) els.ip.value = ip;
    if (els.search) els.search.value = ip;
    state.filters.ip = ip;
    state.filters.search = ip;
    state.table.page = 1;
    refreshAll();
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function debounce(fn, wait) {
    var timer = null;
    return function () {
      var args = arguments;
      var ctx = this;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(ctx, args);
      }, wait);
    };
  }
})();
