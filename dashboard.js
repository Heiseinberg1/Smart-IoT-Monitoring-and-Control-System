(function () {
  "use strict";

  const POLL_MS = 2000;
  const ledPins = window.__LED_PINS__ || {};
  const canvas = document.getElementById("chart");
  const ctx = canvas.getContext("2d");
  const logEl = document.getElementById("event-log");

  const SERIES = [
    { key: "temperature", color: "#00ffa3", label: "Temp (\u00b0C)" },
    { key: "humidity", color: "#3ec1d3", label: "Humidity (%)" },
    { key: "light", color: "#ffb020", label: "Light (lux)" },
  ];

  // ---------------- utility ----------------

  function logEvent(text) {
    const row = document.createElement("div");
    const ts = new Date().toLocaleTimeString();
    row.innerHTML = `<span class="ts">[${ts}]</span><span class="entry">${text}</span>`;
    logEl.prepend(row);
    while (logEl.children.length > 40) logEl.removeChild(logEl.lastChild);
  }

  function fmtUptime(seconds) {
    const s = Math.floor(seconds % 60);
    const m = Math.floor((seconds / 60) % 60);
    const h = Math.floor(seconds / 3600);
    return `${h}h ${m}m ${s}s`;
  }

  async function api(path, options) {
    const res = await fetch(path, options);
    if (!res.ok) throw new Error(`${path} -> ${res.status}`);
    return res.json();
  }

  // ---------------- LED panel ----------------

  function buildLedPanel() {
    const container = document.getElementById("led-list");
    container.innerHTML = "";
    Object.entries(ledPins).forEach(([pin, name]) => {
      const item = document.createElement("div");
      item.className = "led-item";
      item.innerHTML = `
        <div class="led-info">
          <span class="led-glow" id="glow-${pin}"></span>
          <div>
            <div class="led-name">${name}</div>
            <div class="led-pin">GPIO ${pin}</div>
          </div>
        </div>
        <div class="switch" id="switch-${pin}" data-pin="${pin}">
          <div class="switch-knob"></div>
        </div>
      `;
      container.appendChild(item);
      item.querySelector(".switch").addEventListener("click", () => toggleLed(pin));
    });
  }

  async function toggleLed(pin) {
    try {
      const result = await api(`/api/leds/${pin}/toggle`, { method: "POST" });
      applyLedState(pin, result.state);
      logEvent(`GPIO ${pin} (${result.label}) &rarr; ${result.state ? "ON" : "OFF"}`);
    } catch (err) {
      logEvent(`<span style="color:#ff5c5c">Failed to toggle GPIO ${pin}: ${err.message}</span>`);
    }
  }

  function applyLedState(pin, state) {
    const glow = document.getElementById(`glow-${pin}`);
    const sw = document.getElementById(`switch-${pin}`);
    if (glow) glow.classList.toggle("on", !!state);
    if (sw) sw.classList.toggle("on", !!state);
  }

  async function refreshLeds() {
    try {
      const all = await api("/api/leds");
      Object.entries(all).forEach(([pin, info]) => applyLedState(pin, info.state));
    } catch (err) {
      // non-fatal; leave last known UI state
    }
  }

  // ---------------- sensor readouts ----------------

  function refreshLatest() {
    api("/api/sensors/latest").then((data) => {
      if (data.temperature == null) return;
      document.getElementById("val-temp").textContent = data.temperature;
      document.getElementById("val-humidity").textContent = data.humidity;
      document.getElementById("val-light").textContent = data.light;
      document.getElementById("last-sample").textContent = data.timestamp;
    }).catch(() => {});
  }

  // ---------------- chart ----------------

  function resizeCanvas() {
    const wrap = canvas.parentElement;
    canvas.width = wrap.clientWidth - 20;
    canvas.height = 220;
  }

  function drawChart(history) {
    resizeCanvas();
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    if (!history.length) return;

    const padding = { left: 8, right: 8, top: 12, bottom: 12 };
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    // gridlines
    ctx.strokeStyle = "#1a2029";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (plotH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(w - padding.right, y);
      ctx.stroke();
    }

    SERIES.forEach((series) => {
      const values = history.map((pt) => pt[series.key]).filter((v) => v != null);
      if (!values.length) return;
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = max - min || 1;

      ctx.beginPath();
      ctx.strokeStyle = series.color;
      ctx.lineWidth = 2;
      history.forEach((pt, i) => {
        const v = pt[series.key];
        if (v == null) return;
        const x = padding.left + (plotW * i) / Math.max(1, history.length - 1);
        const norm = (v - min) / range;
        const y = padding.top + plotH - norm * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
  }

  function buildLegend() {
    const footer = document.querySelector(".readout-footer");
    const legend = document.createElement("div");
    legend.style.marginTop = "8px";
    legend.style.display = "flex";
    legend.style.gap = "14px";
    SERIES.forEach((s) => {
      const item = document.createElement("span");
      item.style.color = s.color;
      item.style.fontFamily = "var(--font-mono)";
      item.style.fontSize = "11px";
      item.textContent = `\u2014 ${s.label}`;
      legend.appendChild(item);
    });
    footer.after(legend);
  }

  function refreshHistory() {
    api("/api/sensors/history?limit=60").then(drawChart).catch(() => {});
  }

  // ---------------- system status ----------------

  function refreshStatus() {
    api("/api/system/status").then((data) => {
      document.getElementById("stat-uptime").textContent = fmtUptime(data.uptime_seconds);
      document.getElementById("stat-requests").textContent = data.requests_served;
      document.getElementById("stat-ip").textContent = data.client_ip;
      document.getElementById("stat-time").textContent = data.server_time;
      document.getElementById("stat-gpio-mode").textContent = data.gpio_mode;
      document.getElementById("stat-sensor-mode").textContent = data.sensor_mode;
      document.getElementById("pill-gpio").textContent = `GPIO: ${data.gpio_mode.toUpperCase()}`;
      document.getElementById("pill-sensor").textContent = `SENSORS: ${data.sensor_mode.toUpperCase()}`;
    }).catch(() => {});
  }

  // ---------------- init ----------------

  function tick() {
    refreshLatest();
    refreshHistory();
    refreshStatus();
  }

  buildLedPanel();
  buildLegend();
  refreshLeds();
  tick();
  logEvent("Dashboard connected to Flask API");
  window.addEventListener("resize", () => refreshHistory());
  setInterval(tick, POLL_MS);
  setInterval(refreshLeds, POLL_MS * 2);
})();
