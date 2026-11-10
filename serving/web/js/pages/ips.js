/**
 * IP directory: every address, with counts and a link to its profile.
 */
(function () {
  "use strict";

  var PAGE_SIZE = 15;
  var page = 1;
  var sortKey = "times";
  var sortDir = "desc";
  var rows = [];

  STRIX.mount({
    active: "ips",
    title: "IP directory",
    subtitle: "How many times each IP appears, split by invalid user, failed password and success.",
    html:
      '<article class="panel panel--wide"><div class="panel__head panel__head--row"><div>' +
      '<h2 class="panel__title">All stored IPs</h2>' +
      '<p class="panel__hint">Malicious IPs keep their geolocation. Others stay in the auth log even without a map point.</p></div>' +
      '<div class="table-pager"><button type="button" class="btn btn--ghost" id="table-prev">Prev</button>' +
      '<span class="table-pager__meta mono" id="table-page-meta">1 / 1</span>' +
      '<button type="button" class="btn btn--ghost" id="table-next">Next</button></div></div>' +
      '<div class="table-wrap"><table class="data-table" id="ip-table"><thead><tr>' +
      th("ip", "IP") + th("times", "Times") + th("invalid_users", "Invalid user") +
      th("failed_passwords", "Failed password") + th("success_passwords", "Success") +
      th("country", "Country") + th("city", "City") + '<th>Flag</th><th></th>' +
      '</tr></thead><tbody id="ip-body"></tbody></table></div></article>',
    start: function () {
      document.getElementById("table-prev").addEventListener("click", function () {
        if (page > 1) { page -= 1; paint(); }
      });
      document.getElementById("table-next").addEventListener("click", function () {
        page += 1;
        paint();
      });
      document.querySelectorAll("#ip-table th[data-sort]").forEach(function (header) {
        header.addEventListener("click", function () {
          var key = header.getAttribute("data-sort");
          if (sortKey === key) sortDir = sortDir === "asc" ? "desc" : "asc";
          else {
            sortKey = key;
            sortDir = key === "ip" || key === "country" || key === "city" ? "asc" : "desc";
          }
          page = 1;
          paint();
        });
      });
      refresh();
    },
    onChange: function () {
      page = 1;
      refresh();
    }
  });

  function th(key, label) {
    return '<th data-sort="' + key + '">' + label + "</th>";
  }

  function refresh() {
    STRIX.api("/api/ips", { scope: "all", limit: 2000 })
      .then(function (data) {
        rows = data || [];
        paint();
      })
      .catch(function (err) {
        STRIX.toast("IP directory failed", String(err.message || err));
      });
  }

  function paint() {
    var search = (STRIX.filters().search || "").toLowerCase();
    var visible = rows.filter(function (row) {
      if (!search) return true;
      var blob = [row.ip, row.country, row.city, row.org, row.country_code].join(" ").toLowerCase();
      return blob.indexOf(search) !== -1;
    });
    var dir = sortDir === "asc" ? 1 : -1;
    visible.sort(function (a, b) {
      var av = a[sortKey];
      var bv = b[sortKey];
      if (av == null) av = "";
      if (bv == null) bv = "";
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
    var pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
    if (page > pages) page = pages;
    var slice = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
    document.getElementById("table-page-meta").textContent = page + " / " + pages + " · " + visible.length;
    document.getElementById("table-prev").disabled = page <= 1;
    document.getElementById("table-next").disabled = page >= pages;
    document.getElementById("ip-body").innerHTML = slice.map(function (row) {
      var flag = row.is_malicious || row.is_bot
        ? '<span class="badge badge--bot">MALICIOUS</span>'
        : '<span class="badge badge--clean">logged</span>';
      return (
        "<tr><td class=\"mono\"><a href=\"" + STRIX.ipHref(row.ip) + "\">" + STRIX.escapeHtml(row.ip) + "</a></td>" +
        "<td class=\"mono\">" + STRIX.formatNumber(row.times) + "</td>" +
        "<td class=\"mono\">" + STRIX.formatNumber(row.invalid_users) + "</td>" +
        "<td class=\"mono\">" + STRIX.formatNumber(row.failed_passwords) + "</td>" +
        "<td class=\"mono\">" + STRIX.formatNumber(row.success_passwords) + "</td>" +
        "<td>" + STRIX.escapeHtml(row.country || "—") + "</td>" +
        "<td>" + STRIX.escapeHtml(row.city || "—") + "</td>" +
        "<td>" + flag + "</td>" +
        "<td><a href=\"" + STRIX.ipHref(row.ip) + "\">Profile</a></td></tr>"
      );
    }).join("");
  }
})();
