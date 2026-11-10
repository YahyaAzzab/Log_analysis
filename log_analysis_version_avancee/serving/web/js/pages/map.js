/**
 * Map page: geolocated attackers and country share.
 */
(function () {
  "use strict";

  var mapChart = null;
  var countryChart = null;

  STRIX.mount({
    active: "map",
    title: "Map",
    subtitle: "Where the IPs come from. Click a point to open its profile.",
    html:
      '<section class="grid-dashboard">' +
      '<article class="panel panel--wide"><div class="panel__head"><h2 class="panel__title">Attacker map</h2>' +
      '<p class="panel__hint">Bubble size is the number of attempts. Only geolocated IPs are plotted. Malicious IPs were enriched with IPinfo.</p></div>' +
      '<div id="chart-map" class="chart chart--tall"></div></article>' +
      '<article class="panel"><div class="panel__head"><h2 class="panel__title">Countries</h2></div>' +
      '<div id="chart-countries" class="chart"></div></article>' +
      "</section>",
    start: function () {
      mapChart = STRIX.mountChart("chart-map");
      countryChart = STRIX.mountChart("chart-countries");
      STRIX.loadMap()
        .then(refresh)
        .catch(function () {
          STRIX.toast("Map unavailable", "world.json could not be loaded.");
        });
    },
    onChange: refresh
  });

  function refresh() {
    Promise.all([STRIX.api("/api/map"), STRIX.api("/api/countries", { limit: 12 })])
      .then(function (rows) {
        renderMap(rows[0] || []);
        renderCountries(rows[1] || []);
        STRIX.resizeCharts();
      })
      .catch(function (err) {
        STRIX.toast("Map refresh failed", String(err.message || err));
      });
  }

  function renderMap(rows) {
    var theme = STRIX.chartTheme();
    var points = rows
      .filter(function (row) { return row.lat != null && row.lon != null; })
      .map(function (row) {
        return {
          name: row.ip,
          ip: row.ip,
          value: [Number(row.lon), Number(row.lat), Number(row.failures || 0)],
          country: row.country,
          city: row.city,
          failures: row.failures
        };
      });
    var maxVal = points.reduce(function (max, item) { return Math.max(max, item.value[2]); }, 1);
    var hot = points.slice().sort(function (a, b) { return b.value[2] - a.value[2]; }).slice(0, 8);
    mapChart.setOption(
      Object.assign({}, STRIX.anim(), {
        tooltip: {
          formatter: function (params) {
            var data = params.data || {};
            return (data.ip || "") + "<br/>" + (data.city || "Unknown") + " · " + STRIX.formatNumber(data.failures || 0);
          }
        },
        geo: {
          map: "world",
          roam: true,
          itemStyle: { areaColor: theme.surface, borderColor: theme.border },
          emphasis: { itemStyle: { areaColor: theme.bg } }
        },
        series: [
          {
            type: "scatter",
            coordinateSystem: "geo",
            data: points,
            symbolSize: function (val) { return 6 + (Math.sqrt(val[2]) / Math.sqrt(maxVal)) * 22; },
            itemStyle: { color: theme.danger }
          },
          {
            type: "effectScatter",
            coordinateSystem: "geo",
            data: hot,
            symbolSize: 12,
            rippleEffect: { scale: 3, period: 3.2 },
            itemStyle: { color: theme.accent }
          }
        ]
      }),
      true
    );
    mapChart.off("click");
    mapChart.on("click", function (params) {
      if (params.data && params.data.ip) globalThis.location.href = STRIX.ipHref(params.data.ip);
    });
  }

  function renderCountries(rows) {
    var theme = STRIX.chartTheme();
    countryChart.setOption(
      Object.assign({}, STRIX.anim(), {
        tooltip: { trigger: "item" },
        series: [{
          type: "pie",
          radius: ["46%", "72%"],
          data: rows.map(function (row) {
            return { name: row.country || row.country_code || "Unknown", value: row.failures };
          }),
          label: { color: theme.muted },
          itemStyle: { borderColor: theme.bg, borderWidth: 2 }
        }]
      }),
      true
    );
  }
})();
