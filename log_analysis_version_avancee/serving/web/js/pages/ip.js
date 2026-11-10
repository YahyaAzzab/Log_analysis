/**
 * One IP: counts, geolocation, map, users and the lines that mention it.
 */
(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var ip = params.get("ip") || "";
  var mapChart = null;

  STRIX.mount({
    active: "ips",
    title: ip || "IP profile",
    subtitle: "Everything stored for this address.",
    html:
      '<p class="panel__hint" id="ip-missing"></p>' +
      '<section class="kpi-row">' +
      stat("Times", "stat-times") + stat("Invalid user", "stat-invalid") +
      stat("Failed password", "stat-failed") + stat("Success", "stat-success") +
      "</section>" +
      '<section class="grid-dashboard">' +
      '<article class="panel"><div class="panel__head"><h2 class="panel__title">Identity</h2></div><div id="ip-identity"></div></article>' +
      '<article class="panel"><div class="panel__head"><h2 class="panel__title">Map</h2>' +
      '<p class="panel__hint">Shown when this IP was geolocated.</p></div><div id="ip-map" class="chart"></div></article>' +
      '<article class="panel"><div class="panel__head"><h2 class="panel__title">Users tried</h2></div><div id="ip-users"></div></article>' +
      '<article class="panel panel--wide"><div class="panel__head"><h2 class="panel__title">Lines</h2></div>' +
      '<div class="table-wrap"><table class="data-table"><thead><tr><th>Date</th><th>Time</th><th>User</th><th>Outcome</th><th>Port</th></tr></thead>' +
      '<tbody id="ip-events"></tbody></table></div></article></section>',
    start: function () {
      if (!ip) {
        document.getElementById("ip-missing").textContent = "No IP in the address. Open one from the directory.";
        return;
      }
      mapChart = STRIX.mountChart("ip-map");
      STRIX.loadMap().catch(function () { mapChart = null; }).finally(load);
    }
  });

  function stat(label, id) {
    return '<article class="kpi-card"><p class="kpi-card__label">' + label + '</p><p class="kpi-card__value mono" id="' + id + '">--</p></article>';
  }

  function load() {
    Promise.all([
      fetch("/api/ip/" + encodeURIComponent(ip)).then(function (res) {
        if (!res.ok) throw new Error("profile " + res.status);
        return res.json();
      }),
      fetch("/api/ips?scope=all&limit=1&ip=" + encodeURIComponent(ip)).then(function (res) {
        if (!res.ok) throw new Error("counts " + res.status);
        return res.json();
      })
    ])
      .then(function (rows) {
        render(rows[0], (rows[1] && rows[1][0]) || {});
      })
      .catch(function (err) {
        STRIX.toast("Profile failed", String(err.message || err));
      });
  }

  function render(data, counts) {
    var geo = data.geo || {};
    var events = data.events || [];
    document.getElementById("stat-times").textContent = STRIX.formatNumber(counts.times || data.failures);
    document.getElementById("stat-invalid").textContent = STRIX.formatNumber(counts.invalid_users || 0);
    document.getElementById("stat-failed").textContent = STRIX.formatNumber(counts.failed_passwords || 0);
    document.getElementById("stat-success").textContent = STRIX.formatNumber(counts.success_passwords || 0);
    var flag = geo.is_malicious || geo.is_bot ? "Malicious" : "Not flagged";
    document.getElementById("ip-identity").innerHTML =
      "<ul class=\"drawer__list\">" +
      line("IP", data.ip) +
      line("Country", geo.country || "—") +
      line("City", geo.city || "—") +
      line("Region", geo.region || "—") +
      line("Org", geo.org || "—") +
      line("Flag", flag) +
      line("Burst / 30s", STRIX.formatNumber(data.max_burst)) +
      line("First seen", String(data.first_seen || "—").replace("T", " ").slice(0, 19)) +
      line("Last seen", String(data.last_seen || "—").replace("T", " ").slice(0, 19)) +
      "</ul>";
    document.getElementById("ip-users").innerHTML =
      "<ul class=\"drawer__list\">" +
      (data.users || []).map(function (row) {
        return "<li><span class=\"mono\">" + STRIX.escapeHtml(row.username) + "</span><span class=\"mono\">" + STRIX.formatNumber(row.failures) + "</span></li>";
      }).join("") +
      "</ul>";
    document.getElementById("ip-events").innerHTML = events.map(function (row) {
      var stamp = String(row.ts || "");
      return (
        "<tr><td class=\"mono\">" + STRIX.escapeHtml(stamp.slice(0, 10)) + "</td>" +
        "<td class=\"mono\">" + STRIX.escapeHtml(stamp.slice(11, 19)) + "</td>" +
        "<td class=\"mono\">" + STRIX.escapeHtml(row.username || "—") + "</td>" +
        "<td>" + STRIX.escapeHtml(STRIX.outcome(row.event_type)) + "</td>" +
        "<td class=\"mono\">" + STRIX.escapeHtml(row.port == null ? "—" : row.port) + "</td></tr>"
      );
    }).join("");
    if (mapChart && geo.lat != null && geo.lon != null) {
      var theme = STRIX.chartTheme();
      mapChart.setOption({
        geo: {
          map: "world",
          roam: true,
          center: [Number(geo.lon), Number(geo.lat)],
          zoom: 5,
          itemStyle: { areaColor: theme.surface, borderColor: theme.border }
        },
        series: [{
          type: "effectScatter",
          coordinateSystem: "geo",
          data: [{ value: [Number(geo.lon), Number(geo.lat), 1] }],
          symbolSize: 14,
          itemStyle: { color: theme.accent },
          rippleEffect: { scale: 3, period: 3 }
        }]
      });
      STRIX.resizeCharts();
    }
  }

  function line(label, value) {
    return "<li><span>" + STRIX.escapeHtml(label) + "</span><span class=\"mono\">" + STRIX.escapeHtml(value) + "</span></li>";
  }
})();
