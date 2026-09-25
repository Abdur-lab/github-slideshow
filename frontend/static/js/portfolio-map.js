(function () {
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var container = document.getElementById("portfolio-map");
    if (!container) return;
    var properties = JSON.parse(document.getElementById("portfolio-map-data").textContent);

    var map = L.map(container);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    if (properties.length === 0) {
      map.setView([20, 0], 2);
      return;
    }

    var bounds = [];
    properties.forEach(function (p) {
      var marker = L.marker([p.lat, p.lng]).addTo(map);
      marker.bindPopup(
        '<div class="map-popup"><h4>' + escapeHtml(p.name) + "</h4>" +
        "<div>" + escapeHtml(p.code) + " &middot; " + p.occupancy + "% occupied</div>" +
        '<a href="' + p.url + '">View property</a></div>'
      );
      bounds.push([p.lat, p.lng]);
    });

    if (bounds.length === 1) {
      map.setView(bounds[0], 14);
    } else {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  });
})();
