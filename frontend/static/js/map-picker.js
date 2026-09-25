(function () {
  function initPicker(container) {
    var latInput = document.getElementById(container.dataset.latInput);
    var lngInput = document.getElementById(container.dataset.lngInput);
    var defaultLat = parseFloat(container.dataset.defaultLat);
    var defaultLng = parseFloat(container.dataset.defaultLng);
    var defaultZoom = parseInt(container.dataset.defaultZoom || "11", 10);

    var hasInitial = latInput.value !== "" && lngInput.value !== "";
    var startLat = hasInitial ? parseFloat(latInput.value) : defaultLat;
    var startLng = hasInitial ? parseFloat(lngInput.value) : defaultLng;

    var map = L.map(container).setView([startLat, startLng], hasInitial ? 15 : defaultZoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    var marker = hasInitial ? L.marker([startLat, startLng]).addTo(map) : null;

    function setPoint(lat, lng, recenter) {
      latInput.value = lat.toFixed(6);
      lngInput.value = lng.toFixed(6);
      if (marker) {
        marker.setLatLng([lat, lng]);
      } else {
        marker = L.marker([lat, lng]).addTo(map);
      }
      if (recenter) {
        map.setView([lat, lng], Math.max(map.getZoom(), 14));
      }
    }

    map.on("click", function (e) {
      setPoint(e.latlng.lat, e.latlng.lng, false);
    });

    [latInput, lngInput].forEach(function (input) {
      input.addEventListener("change", function () {
        var lat = parseFloat(latInput.value);
        var lng = parseFloat(lngInput.value);
        if (!isNaN(lat) && !isNaN(lng)) {
          setPoint(lat, lng, true);
        }
      });
    });

    var clearBtn = document.getElementById(container.dataset.clearButton);
    if (clearBtn) {
      clearBtn.addEventListener("click", function (e) {
        e.preventDefault();
        latInput.value = "";
        lngInput.value = "";
        if (marker) {
          map.removeLayer(marker);
          marker = null;
        }
      });
    }
  }

  function initStatic(container) {
    var lat = parseFloat(container.dataset.lat);
    var lng = parseFloat(container.dataset.lng);
    var map = L.map(container, { scrollWheelZoom: false }).setView([lat, lng], 15);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    L.marker([lat, lng]).addTo(map);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-map-picker]").forEach(initPicker);
    document.querySelectorAll("[data-map-static]").forEach(initStatic);
  });
})();
