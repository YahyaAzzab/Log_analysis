/**
 * Shared STRIX shell: navigation, filters, theme, API helpers.
 */
(function (global) {
  "use strict";

  var FILTER_KEY = "strix-filters";
  var THEME_KEY = "strix-theme";
  var listeners = [];
  var charts = [];

  var NAV = [
    { id: "dashboard", href: "/", label: "Dashboard" },
    { id: "timeline", href: "/timeline.html", label: "Timeline" },
    { id: "map", href: "/map.html", label: "Map" },
    { id: "ips", href: "/ips.html", label: "IP directory" },
    { id: "events", href: "/events.html", label: "Auth log" }
  ];

  function prefersReduced() {
    return (
      global.matchMedia &&
      global.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function readFilters() {
    var empty = {
      date_from: "",
      date_to: "",
      country: "",
      ip: "",
      username: "",
      bots_only: false,
      search: ""
    };
    try {
      var raw = sessionStorage.getItem(FILTER_KEY);
      if (!raw) return empty;
      var saved = JSON.parse(raw);
      return {
        date_from: saved.date_from || "",
        date_to: saved.date_to || "",
        country: saved.country || "",
        ip: saved.ip || "",
        username: saved.username || "",
        bots_only: !!saved.bots_only,
        search: saved.search || ""
      };
    } catch (err) {
      return empty;
    }
  }

  function writeFilters(filters) {
    try {
      sessionStorage.setItem(FILTER_KEY, JSON.stringify(filters));
    } catch (err) {
      /* private mode */
    }
  }

  function filtersFromDom() {
    return {
      date_from: value("filter-date-from"),
      date_to: value("filter-date-to"),
      country: value("filter-country").trim(),
      ip: value("filter-ip").trim(),
      username: value("filter-username").trim(),
      bots_only: !!(document.getElementById("filter-bots-only") || {}).checked,
      search: value("filter-search").trim()
    };
  }

  function value(id) {
    var node = document.getElementById(id);
    return node ? node.value || "" : "";
  }

  function applyFiltersToDom(filters) {
    setValue("filter-date-from", filters.date_from);
    setValue("filter-date-to", filters.date_to);
    setValue("filter-country", filters.country);
    setValue("filter-ip", filters.ip);
    setValue("filter-username", filters.username);
    setValue("filter-search", filters.search);
    var bots = document.getElementById("filter-bots-only");
    if (bots) bots.checked = !!filters.bots_only;
  }

  function setValue(id, next) {
    var node = document.getElementById(id);
    if (node) node.value = next || "";
  }

  function query(extra) {
    var filters = readFilters();
    var params = new URLSearchParams();
    if (filters.date_from) params.set("date_from", filters.date_from + "T00:00:00");
    if (filters.date_to) params.set("date_to", filters.date_to + "T23:59:59");
    if (filters.country) params.set("country", filters.country);
    if (filters.ip) params.set("ip", filters.ip);
    if (filters.username) params.set("username", filters.username);
    if (filters.bots_only) params.set("bots_only", "true");
    if (extra) {
      Object.keys(extra).forEach(function (key) {
        if (extra[key] != null && extra[key] !== "") params.set(key, String(extra[key]));
      });
    }
    return params;
  }

  function api(path, extra) {
    var params = query(extra);
    var qs = params.toString();
    var url = path + (qs ? "?" + qs : "");
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error(path + " -> " + res.status);
      return res.json();
    });
  }

  function token(name, fallback) {
    var raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return raw || fallback;
  }

  function chartTheme() {
    return {
      text: token("--strix-text", "#E5E7EB"),
      muted: token("--strix-text-muted", "#9CA3AF"),
      accent: token("--strix-accent", "#22D3EE"),
      danger: token("--strix-danger", "#F43F5E"),
      warning: token("--strix-warning", "#F59E0B"),
      success: token("--strix-success", "#10B981"),
      border: token("--strix-border", "rgba(148,163,184,0.16)"),
      surface: token("--strix-surface", "#121826"),
      bg: token("--strix-bg", "#0B0F1A"),
      mono: token("--strix-font-mono", "JetBrains Mono, monospace"),
      sans: token("--strix-font-sans", "Inter, sans-serif")
    };
  }

  function anim() {
    if (prefersReduced()) {
      return { animation: false, animationDuration: 0, animationDurationUpdate: 0 };
    }
    return {
      animation: true,
      animationDuration: 450,
      animationDurationUpdate: 280,
      animationEasing: "cubicOut",
      animationEasingUpdate: "cubicInOut"
    };
  }

  function mountChart(id) {
    var node = document.getElementById(id);
    if (!node || !global.echarts) return null;
    var chart = global.echarts.init(node);
    charts.push(chart);
    return chart;
  }

  function resizeCharts() {
    charts.forEach(function (chart) {
      chart.resize();
    });
  }

  function loadMap() {
    if (global.__strixWorld) return Promise.resolve(true);
    return fetch("/assets/world.json")
      .then(function (res) {
        if (!res.ok) throw new Error("world map");
        return res.json();
      })
      .then(function (geo) {
        global.echarts.registerMap("world", geo);
        global.__strixWorld = true;
        return true;
      });
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatNumber(value) {
    return Number(value || 0).toLocaleString("en-US");
  }

  function outcome(eventType) {
    if (eventType === "invalid_user") return "Invalid user";
    if (eventType === "failed_password") return "Failed password";
    if (eventType === "accepted") return "Success password";
    if (eventType === "auth_failure") return "Auth failure";
    return eventType || "—";
  }

  function ipHref(ip) {
    return "/ip.html?ip=" + encodeURIComponent(ip || "");
  }

  function toast(title, body) {
    var stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      stack.setAttribute("aria-live", "polite");
      document.body.appendChild(stack);
    }
    var node = document.createElement("div");
    node.className = "toast toast--error";
    node.innerHTML = '<p class="toast__title"></p><p class="toast__body"></p>';
    node.querySelector(".toast__title").textContent = title;
    node.querySelector(".toast__body").textContent = body || "";
    stack.appendChild(node);
    requestAnimationFrame(function () {
      node.classList.add("is-visible");
    });
    setTimeout(function () {
      node.classList.remove("is-visible");
      setTimeout(function () {
        if (node.parentNode) node.parentNode.removeChild(node);
      }, 220);
    }, 4200);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var button = document.getElementById("theme-toggle");
    if (button) button.textContent = theme === "light" ? "Dark mode" : "Light mode";
  }

  function savedTheme() {
    try {
      return localStorage.getItem(THEME_KEY) || "dark";
    } catch (err) {
      return "dark";
    }
  }

  function navHtml(active) {
    return NAV.map(function (item) {
      var cls = item.id === active ? "sidebar__link is-active" : "sidebar__link";
      return '<a class="' + cls + '" href="' + item.href + '">' + item.label + "</a>";
    }).join("");
  }

  function shellHtml(options) {
    return (
      '<aside class="sidebar" aria-label="Primary">' +
      '<header class="sidebar__brand">' +
      '<div id="header-logo-slot" class="sidebar__logo-slot">' +
      '<svg class="sidebar__logo" viewBox="0 0 64 64" width="28" height="28" aria-hidden="true">' +
      '<use href="/assets/logo.svg#strix-mark" width="64" height="64"></use>' +
      "</svg></div>" +
      '<div class="sidebar__brand-text"><span class="sidebar__title">STRIX</span>' +
      '<span class="sidebar__tag">Threat intelligence</span></div></header>' +
      '<nav class="sidebar__nav">' +
      navHtml(options.active) +
      "</nav>" +
      '<div class="sidebar__status"><p class="sidebar__status-label">Pipeline</p>' +
      '<p class="sidebar__status-value" id="pipeline-status-text">Checking…</p>' +
      '<p class="sidebar__status-meta mono" id="pipeline-status-meta">/api/health</p></div>' +
      "</aside>" +
      '<div class="workspace"><header class="filters">' +
      '<div class="filters__title-block"><h1 class="filters__title">' +
      escapeHtml(options.title) +
      '</h1><p class="filters__subtitle">' +
      escapeHtml(options.subtitle || "") +
      "</p></div>" +
      '<button type="button" class="btn btn--ghost" id="theme-toggle">Light mode</button>' +
      '<div class="filters__controls">' +
      field("From", "filter-date-from", "date", "") +
      field("To", "filter-date-to", "date", "") +
      field("Country", "filter-country", "text", "US, France…") +
      field("IP", "filter-ip", "text", "1.2.3.4") +
      field("User", "filter-username", "text", "root, admin…") +
      '<label class="field field--switch"><span class="field__label">Bots only</span>' +
      '<input class="field__switch" type="checkbox" id="filter-bots-only" /></label>' +
      '<label class="field field--search"><span class="field__label">Search</span>' +
      '<input class="field__input" type="search" id="filter-search" placeholder="IP, user, country…" /></label>' +
      '<button type="button" class="btn btn--ghost" id="filter-reset">Reset</button>' +
      "</div></header><main class=\"main\" id=\"page\">" +
      (options.html || "") +
      "</main></div>"
    );
  }

  function field(label, id, type, placeholder) {
    var mono = type === "date" || id.indexOf("ip") >= 0 || id.indexOf("user") >= 0 ? " mono" : "";
    return (
      '<label class="field"><span class="field__label">' +
      label +
      '</span><input class="field__input' +
      mono +
      '" type="' +
      type +
      '" id="' +
      id +
      '" placeholder="' +
      placeholder +
      '" /></label>'
    );
  }

  function bindChrome(onChange) {
    applyTheme(savedTheme());
    applyFiltersToDom(readFilters());
    var themeButton = document.getElementById("theme-toggle");
    if (themeButton) {
      themeButton.addEventListener("click", function () {
        var next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
        applyTheme(next);
        try {
          localStorage.setItem(THEME_KEY, next);
        } catch (err) {
          /* ignore */
        }
        notify();
      });
    }
    ["filter-date-from", "filter-date-to", "filter-country", "filter-ip", "filter-username", "filter-search"].forEach(function (id) {
      var node = document.getElementById(id);
      if (!node) return;
      node.addEventListener("input", debounce(commitFilters, 280));
      node.addEventListener("change", commitFilters);
    });
    var bots = document.getElementById("filter-bots-only");
    if (bots) bots.addEventListener("change", commitFilters);
    var reset = document.getElementById("filter-reset");
    if (reset) {
      reset.addEventListener("click", function () {
        writeFilters({
          date_from: "",
          date_to: "",
          country: "",
          ip: "",
          username: "",
          bots_only: false,
          search: ""
        });
        applyFiltersToDom(readFilters());
        notify();
      });
    }
    if (onChange) listeners.push(onChange);
    checkHealth();
    global.addEventListener("resize", debounce(resizeCharts, 150));
    global.addEventListener("strix-dashboard-visible", resizeCharts);
  }

  function commitFilters() {
    writeFilters(filtersFromDom());
    notify();
  }

  function notify() {
    listeners.forEach(function (fn) {
      fn(readFilters());
    });
  }

  function checkHealth() {
    var label = document.getElementById("pipeline-status-text");
    var meta = document.getElementById("pipeline-status-meta");
    fetch("/api/health")
      .then(function (res) {
        if (!res.ok) throw new Error("health");
        return res.json();
      })
      .then(function () {
        if (label) {
          label.textContent = "Online";
          label.className = "sidebar__status-value is-ok";
        }
        if (meta) meta.textContent = "PostgreSQL connected";
      })
      .catch(function () {
        if (label) {
          label.textContent = "Unavailable";
          label.className = "sidebar__status-value is-bad";
        }
        if (meta) meta.textContent = "API or database down";
        toast("API unavailable", "Start the server with python main.py serve");
      });
  }

  function mount(options) {
    var root = document.getElementById("dashboard");
    if (!root) return;
    root.innerHTML = shellHtml(options);
    if (!options.intro) {
      root.classList.remove("is-hidden");
      root.classList.add("is-visible");
      root.setAttribute("aria-hidden", "false");
      var logo = root.querySelector(".sidebar__logo");
      if (logo) logo.style.opacity = "1";
    }
    bindChrome(options.onChange || null);
    if (options.start) options.start(document.getElementById("page"));
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

  function animateNumber(node, next) {
    if (!node) return;
    node.classList.remove("skeleton");
    var target = Number(next || 0);
    var from = Number(node.getAttribute("data-value") || 0);
    node.setAttribute("data-value", String(target));
    if (prefersReduced() || from === target) {
      node.textContent = formatNumber(target);
      return;
    }
    var start = null;
    function step(ts) {
      if (start == null) start = ts;
      var t = Math.min(1, (ts - start) / 450);
      var eased = 1 - Math.pow(1 - t, 3);
      node.textContent = formatNumber(Math.round(from + (target - from) * eased));
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  global.STRIX = {
    mount: mount,
    api: api,
    filters: readFilters,
    toast: toast,
    escapeHtml: escapeHtml,
    formatNumber: formatNumber,
    outcome: outcome,
    ipHref: ipHref,
    chartTheme: chartTheme,
    anim: anim,
    mountChart: mountChart,
    resizeCharts: resizeCharts,
    loadMap: loadMap,
    animateNumber: animateNumber
  };
})(window);
