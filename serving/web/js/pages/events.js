/**
 * Auth log: every stored line, with date, time, IP, user and outcome.
 */
(function () {
  "use strict";

  var page = 1;
  var pageSize = 40;

  STRIX.mount({
    active: "events",
    title: "Auth log",
    subtitle: "Date, time, IP, user, invalid user, failed password and success.",
    html:
      '<article class="panel panel--wide"><div class="panel__head panel__head--row"><div>' +
      '<h2 class="panel__title">Stored authentication lines</h2>' +
      '<p class="panel__hint">One row is one parsed sshd event. Click an IP for its full profile.</p></div>' +
      '<div class="table-pager"><button type="button" class="btn btn--ghost" id="ev-prev">Prev</button>' +
      '<span class="table-pager__meta mono" id="ev-meta">1</span>' +
      '<button type="button" class="btn btn--ghost" id="ev-next">Next</button></div></div>' +
      '<div class="table-wrap"><table class="data-table"><thead><tr>' +
      "<th>Date</th><th>Time</th><th>IP</th><th>User</th><th>Outcome</th><th>Port</th><th>Source</th>" +
      '</tr></thead><tbody id="ev-body"></tbody></table></div></article>',
    start: function () {
      document.getElementById("ev-prev").addEventListener("click", function () {
        if (page > 1) { page -= 1; refresh(); }
      });
      document.getElementById("ev-next").addEventListener("click", function () {
        page += 1;
        refresh();
      });
      refresh();
    },
    onChange: function () {
      page = 1;
      refresh();
    }
  });

  function refresh() {
    STRIX.api("/api/events", { scope: "all", page: page, page_size: pageSize })
      .then(function (data) {
        var items = data.items || [];
        var pages = Math.max(1, Math.ceil((data.total || 0) / pageSize));
        document.getElementById("ev-meta").textContent = page + " / " + pages + " · " + STRIX.formatNumber(data.total);
        document.getElementById("ev-prev").disabled = page <= 1;
        document.getElementById("ev-next").disabled = page >= pages;
        document.getElementById("ev-body").innerHTML = items.map(function (row) {
          var stamp = String(row.ts || "");
          return (
            "<tr><td class=\"mono\">" + STRIX.escapeHtml(stamp.slice(0, 10)) + "</td>" +
            "<td class=\"mono\">" + STRIX.escapeHtml(stamp.slice(11, 19)) + "</td>" +
            "<td class=\"mono\"><a href=\"" + STRIX.ipHref(row.ip) + "\">" + STRIX.escapeHtml(row.ip) + "</a></td>" +
            "<td class=\"mono\">" + STRIX.escapeHtml(row.username || "—") + "</td>" +
            "<td>" + STRIX.escapeHtml(STRIX.outcome(row.event_type)) + "</td>" +
            "<td class=\"mono\">" + STRIX.escapeHtml(row.port == null ? "—" : row.port) + "</td>" +
            "<td class=\"mono\">" + STRIX.escapeHtml(row.source_file || "—") + "</td></tr>"
          );
        }).join("");
      })
      .catch(function (err) {
        STRIX.toast("Auth log failed", String(err.message || err));
      });
  }
})();
