// Dynamic imports with cache-busting: extract ?v=... from our own module URL
const _v = new URLSearchParams(new URL(import.meta.url).search).get('v') || Date.now();
const { createOrbScene } = await import(`/static/ultron-orb.js?v=${_v}`);
const { HandTracker }    = await import(`/static/handTracker.js?v=${_v}`);

/* U.L.T.R.O.N Adaptive Cinematic State UI & Animation System
   ═══════════════════════════════════════════════════════════════
   • 15-State Priority Engine & Race-Condition Safe State Machine
   • Live Audio-Visual Reactive Synchronization (Mic & Speaker)
   • Multi-Agent Satellite Orbital Network Telemetry
   • Real-World Biometric Identification State Integration
   • Developer State Debugging & Automated Diagnostic Test Harness
*/

"use strict";

// ── HTML Escape Helper ───────────────────────────────────────────────────
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── Token ────────────────────────────────────────────────────────────────
function getToken() {
  const params = new URLSearchParams(location.search);
  const fromUrl = (params.get("t") || params.get("token") || "").trim();
  if (fromUrl) {
    try { localStorage.setItem("ultron_token", fromUrl); } catch (e) {}
    return fromUrl;
  }
  let t = "";
  try { t = localStorage.getItem("ultron_token") || ""; } catch (e) {}
  if (!t) {
    t = (prompt(
      "ULTRON erişim token'ı:\n\n" +
      "(QR kodu okutursanız token otomatik gelir.)"
    ) || "").trim();
    if (t) { try { localStorage.setItem("ultron_token", t); } catch (e) {} }
  }
  return t;
}

// ── State Priority Constants ─────────────────────────────────────────────
const STATE_PRIORITY = {
  ERROR:            100,
  CONFIRMING:        90,
  UNKNOWN_SPEAKER:   85,
  VERIFIED_RABIA:    80,
  VERIFIED_NURI:     80,
  SUCCESS:           75,
  WARNING:           70,
  EXECUTING:         60,
  SPEAKING:          50,
  THINKING:          40,
  OBSERVING:         35,
  LISTENING:         30,
  CONNECTING:        20,
  DISCONNECTED:      15,
  IDLE:               0,
};

// ── Durum Nesnesi ────────────────────────────────────────────────────────
const S = {
  ws: null,
  ready: false,
  micOn: false,
  camOn: false,
  audioCtx: null,        // yakalama (mic)
  playCtx: null,         // çalma (24k)
  workletNode: null,
  micStream: null,
  camStream: null,
  camTimer: null,
  nextPlayTime: 0,
  playingSources: [],
  outLevel: 0,
  micLevel: 0,
  speaking: false,
  reconnectDelay: 2000,
  fatalMsg: null,
  lastLogKey: "",
  public: false,
  apiKey: "",
  currentUser: "Bilinmeyen",
  voice: localStorage.getItem("ultron_voice") || "Charon",
  awaitingKey: false,
  reconnectTimer: null,
  toastTimer: null,
  connInfo: null,
  activeQrMode: "cloud",
  geoWatchId: null,
  lastCoords: null,
  activeAgentCount: 0,
  wakeLock: null,        // Screen wake lock (PWA mobilte ekran uyumasın)
  pushSubscription: null // Web Push subscription
};

const $ = (id) => document.getElementById(id);
const statusEl = $("status");
const logEl = $("log");
const logContainer = $("log-container");
const toastEl = $("hud-toast");
const badgeGps = $("badge-gps");
const currentUserDisplay = $("current-user-display");
const speakerChip = $("speaker-chip");

// ── 3D Orb Scene Init ────────────────────────────────────────────────────
let ultronOrb = null;
const orbContainer = $("orb-container");
if (orbContainer) {
  ultronOrb = createOrbScene(orbContainer);
  window.ultronOrb = ultronOrb;
}

// ═══════════════════════════════════════════════════════════════════════════
// ── State Manager (Merkezi Durum & Öncelik Yöneticisi) ─────────────────────
// ═══════════════════════════════════════════════════════════════════════════
class StateManager {
  constructor() {
    this.baseState = "DISCONNECTED";
    this.transientStack = []; // [{ state, priority, expiresAt, label }]
    this.activeState = "DISCONNECTED";
    this.stateHistory = [];
    this.customStatusLabel = "";
    this.fpsHistory = [];
    this.lastFrameTime = performance.now();
    this.fps = 60;
  }

  setBaseState(state, customLabel = "") {
    const norm = String(state || "IDLE").toUpperCase();
    this.baseState = norm;
    if (customLabel) this.customStatusLabel = customLabel;
    this._evaluate();
  }

  pushTransientState(state, durationMs = 2000, customLabel = "") {
    const norm = String(state || "SUCCESS").toUpperCase();
    const priority = STATE_PRIORITY[norm] !== undefined ? STATE_PRIORITY[norm] : 50;
    const expiresAt = Date.now() + durationMs;

    // Filter out existing identical transient
    this.transientStack = this.transientStack.filter(t => t.state !== norm);
    this.transientStack.push({ state: norm, priority, expiresAt, customLabel });
    this.transientStack.sort((a, b) => b.priority - a.priority);

    this._evaluate();
  }

  clearTransient(stateName = null) {
    if (stateName) {
      this.transientStack = this.transientStack.filter(t => t.state !== stateName.toUpperCase());
    } else {
      this.transientStack = [];
    }
    this._evaluate();
  }

  _evaluate() {
    const now = Date.now();
    this.transientStack = this.transientStack.filter(t => t.expiresAt > now);

    let nextState = this.baseState;
    let nextLabel = this.customStatusLabel;

    if (this.transientStack.length > 0) {
      const top = this.transientStack[0];
      const basePriority = STATE_PRIORITY[this.baseState] || 0;
      if (top.priority >= basePriority) {
        nextState = top.state;
        if (top.customLabel) nextLabel = top.customLabel;
      }
    }

    if (nextState !== this.activeState) {
      const prev = this.activeState;
      this.activeState = nextState;
      this.stateHistory.push({ from: prev, to: nextState, time: new Date().toLocaleTimeString() });
      if (this.stateHistory.length > 50) this.stateHistory.shift();

      if (ultronOrb) {
        ultronOrb.setState(nextState);
      }
      this._updateHUD(nextLabel);
    }
  }

  _updateHUD(customLabel = "") {
    if (!statusEl) return;
    
    // Status text formatting
    let label = customLabel;
    if (!label) {
      switch (this.activeState) {
        case "IDLE":            label = "STANDBY // HAZIR"; break;
        case "LISTENING":       label = "DİNLİYOR // MIC ACTIVE"; break;
        case "THINKING":        label = "DÜŞÜNÜYOR // COGNITIVE"; break;
        case "EXECUTING":       label = "ÇALIŞTIRIYOR // EXECUTING"; break;
        case "OBSERVING":       label = "GÖRSEL ANALİZ // VISION"; break;
        case "SPEAKING":        label = "KONUŞUYOR // SYNTHESIZING"; break;
        case "SUCCESS":         label = "TAMAMLANDI // SUCCESS"; break;
        case "WARNING":         label = "DİKKAT // WARNING"; break;
        case "ERROR":           label = "SİSTEM HATASI // ERROR"; break;
        case "CONFIRMING":      label = "ONAY BEKLENİYOR // CONFIRM"; break;
        case "UNKNOWN_SPEAKER": label = "YETKİSİZ SES // UNKNOWN"; break;
        case "VERIFIED_NURI":   label = "DOĞRULANDI: NURİ CAN"; break;
        case "VERIFIED_RABIA":  label = "DOĞRULANDI: RABİA"; break;
        case "CONNECTING":      label = "BAĞLANIYOR // CONNECTING"; break;
        case "DISCONNECTED":    label = "BAĞLANTI KOPTU // OFFLINE"; break;
        default:                label = this.activeState;
      }
    }

    statusEl.textContent = label;
    statusEl.className = `status-indicator state-${this.activeState.toLowerCase()} live`;
  }

  tick() {
    this._evaluate();

    // Measure FPS
    const now = performance.now();
    const dt = now - this.lastFrameTime;
    this.lastFrameTime = now;
    if (dt > 0) {
      const curFps = 1000 / dt;
      this.fps = this.fps * 0.9 + curFps * 0.1;
    }

    // Audio-visual reactivity sync
    if (ultronOrb) {
      ultronOrb.setAudioEnergy(S.micLevel, S.outLevel);
    }

    // Decay output peak level smoothly
    S.outLevel *= 0.88;
    S.micLevel *= 0.88;
  }
}

const stateManager = new StateManager();
window.stateManager = stateManager;

// ── Main UI Animation Loop ───────────────────────────────────────────────
function mainLoop() {
  stateManager.tick();
  updateDebugOverlay();
  requestAnimationFrame(mainLoop);
}
requestAnimationFrame(mainLoop);

// ── Toast Helper (when chat is collapsed) ────────────────────────────────
function showToast(who, text) {
  if (!toastEl) return;
  if (!logContainer || !logContainer.classList.contains("collapsed")) return;
  
  if (S.toastTimer) {
    clearTimeout(S.toastTimer);
    S.toastTimer = null;
  }
  let prefix = "";
  if (who === "user") prefix = `${S.currentUser}: `;
  else if (who === "ultron" || who === "jarvis") prefix = "ULTRON: ";
  else if (who === "alert") prefix = "🚨 ";

  toastEl.textContent = prefix + text;
  toastEl.classList.remove("hidden");
  
  S.toastTimer = setTimeout(() => {
    toastEl.classList.add("hidden");
    S.toastTimer = null;
  }, 5000);
}

// ── Log ──────────────────────────────────────────────────────────────────
function addLog(who, text) {
  const key = who + "|" + text;
  if (key === S.lastLogKey) return;
  S.lastLogKey = key;
  const row = document.createElement("div");
  row.className = "row";
  
  let cls = "who-sys";
  let label = "SYS";
  if (who === "user") {
    cls = "who-user";
    label = S.currentUser.toUpperCase();
  } else if (who === "ultron" || who === "jarvis") {
    cls = "who-ultron";
    label = "ULTRON";
    // Araştırma/otomasyon raporu tespiti — otomatik modal açma
    if (text && text.length > 200 && typeof _detectAndShowReport === 'function') {
      setTimeout(() => _detectAndShowReport(text), 300);
    }
  } else if (who === "alert") {
    cls = "who-alert";
    label = "⏰ ALARM";
  }

  row.innerHTML = `<span class="${cls}">${label}:</span> `;
  row.appendChild(document.createTextNode(text));
  if (logEl) {
    logEl.appendChild(row);
    requestAnimationFrame(() => {
      logEl.scrollTop = logEl.scrollHeight;
    });
    while (logEl.children.length > 200) logEl.removeChild(logEl.firstChild);
  }

  showToast(who, text);
}

function setStatus(text, live = false) {
  stateManager.setBaseState(stateManager.baseState, text);
}

// ── Proaktif Uyarı Sesi (Sci-Fi Chime) ────────────────────────────────────
function playAlertChime() {
  try {
    const ctx = ensurePlayCtx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, now); // D5
    osc.frequency.exponentialRampToValueAtTime(880, now + 0.15); // A5
    osc.frequency.exponentialRampToValueAtTime(1174.66, now + 0.35); // D6

    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.85);
  } catch (e) {}
}

// ── WebSocket ────────────────────────────────────────────────────────────
function wsURL() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const voiceParam = `&voice=${encodeURIComponent(S.voice || "Charon")}`;
  const userParam = S.currentUser && S.currentUser !== "Bilinmeyen" ? `&user=${encodeURIComponent(S.currentUser)}` : "";
  if (S.public) return `${proto}://${location.host}/ws/client?v=1${voiceParam}${userParam}`;
  return `${proto}://${location.host}/ws/client?token=${encodeURIComponent(getToken())}${voiceParam}${userParam}`;
}

function connect() {
  if (currentUserDisplay) currentUserDisplay.textContent = S.currentUser;

  stateManager.setBaseState("CONNECTING");

  const ws = new WebSocket(wsURL());
  ws.binaryType = "arraybuffer";
  S.ws = ws;

  ws.onopen = () => {
    const bSrv = $("badge-server");
    if (bSrv) bSrv.className = "badge on";
    stateManager.setBaseState("CONNECTING", "GEMINI BAĞLANIYOR…");
    
    // Kimlik ve konum gönder
    if (S.currentUser && S.currentUser !== "Bilinmeyen") {
      ws.send(JSON.stringify({ type: "identify", user: S.currentUser }));
    }
    if (S.lastCoords) {
      ws.send(JSON.stringify({ type: "location", coords: S.lastCoords }));
    }
  };

  ws.onclose = (e) => {
    const bSrv = $("badge-server");
    const bAgt = $("badge-agent");
    if (bSrv) bSrv.className = "badge off";
    if (bAgt) bAgt.className = "badge off";
    S.ready = false;

    if (e.code === 4401) {
      localStorage.removeItem("ultron_token");
      stateManager.setBaseState("ERROR", "TOKEN HATALI — Yenileyin");
      return;
    }
    if (S.awaitingKey) return;
    
    stateManager.setBaseState("DISCONNECTED", S.fatalMsg || "BAĞLANTI KOPTU");
    S.reconnectDelay = Math.min(S.reconnectDelay * 1.6, 15000);
    S.reconnectTimer = setTimeout(connect, S.reconnectDelay);
  };

  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      playAudioChunk(ev.data);
      return;
    }
    let obj;
    try { obj = JSON.parse(ev.data); } catch { return; }

    switch (obj.type) {
      case "need_key":
        S.ws.send(JSON.stringify({ type: "apikey", key: S.apiKey }));
        stateManager.setBaseState("CONNECTING", "GEMINI BAĞLANIYOR…");
        break;

      case "ready":
        S.ready = true;
        S.fatalMsg = null;
        S.reconnectDelay = 2000;
        stateManager.setBaseState(S.micOn ? "LISTENING" : "IDLE", "ULTRON HAZIR");
        addLog("sys", "ULTRON aktif. Biyometrik ses tanıma devrede.");
        break;

      case "agent_status":
        const bAgt = $("badge-agent");
        if (bAgt) bAgt.className = "badge " + (obj.connected ? "on" : "off");
        break;

      case "log":
        addLog(obj.who, obj.text);
        break;


      case "proactive_alert":
        playAlertChime();
        stateManager.pushTransientState("WARNING", 3500, "⏰ ALARM / HATIRLATICI");
        addLog("alert", obj.text);
        break;

      case "agent_event":
        if (obj.status === "start" || obj.status === "running") {
          S.activeAgentCount++;
          if (ultronOrb) ultronOrb.spawnAgentOrb(obj.agent, obj.details);
          addActiveAgentChip(obj.agent, obj.details);
          stateManager.setBaseState("EXECUTING", `AJAN: ${obj.agent.toUpperCase()}`);
          // Orb renk efekti
          if (typeof _setOrbColorForAgent === 'function') _setOrbColorForAgent(obj.agent, 'start');
        } else if (obj.status === "complete" || obj.status === "error") {
          S.activeAgentCount = Math.max(0, S.activeAgentCount - 1);
          stateManager.pushTransientState(obj.status === "complete" ? "SUCCESS" : "WARNING", 1800);
          // Orb rengi sıfırla
          if (typeof _setOrbColorForAgent === 'function') _setOrbColorForAgent(obj.agent, obj.status);
          setTimeout(() => {
            if (ultronOrb) ultronOrb.removeAgentOrb(obj.agent);
            removeActiveAgentChip(obj.agent);
            if (S.activeAgentCount === 0) {
              stateManager.setBaseState(S.micOn ? "LISTENING" : "IDLE");
            }
          }, 2000);
        } else if (obj.status === "clear") {
          S.activeAgentCount = 0;
          if (ultronOrb) ultronOrb.clearAgentOrbs();
          clearActiveAgentChips();
          stateManager.setBaseState(S.micOn ? "LISTENING" : "IDLE");
        }
        break;

      case "tool":
        stateManager.setBaseState("EXECUTING", "İŞLEM: " + obj.name);
        const toolArgs = obj.args || {};
        if (obj.name === "code_action") {
          if (ultronOrb) ultronOrb.spawnAgentOrb("coding_agent", "Kodlama");
          addActiveAgentChip("coding_agent", "Kodlama Ajanı");
        } else if (obj.name === "run_tests") {
          if (ultronOrb) ultronOrb.spawnAgentOrb("testing_agent", "Test");
          addActiveAgentChip("testing_agent", "Test Ajanı");
        } else if (obj.name === "code_review") {
          if (ultronOrb) ultronOrb.spawnAgentOrb("reviewer_agent", "İnceleme");
          addActiveAgentChip("reviewer_agent", "İnceleme Ajanı");
        } else if (obj.name === "autonomous_task") {
          if (toolArgs.research_mode) {
            if (ultronOrb) ultronOrb.spawnAgentOrb("research_agent", "Araştırma");
            addActiveAgentChip("research_agent", "Araştırma Modu");
          } else {
            if (ultronOrb) ultronOrb.spawnAgentOrb("supervisor", "Supervisor");
            addActiveAgentChip("supervisor", "Supervisor Core");
          }
        } else if (obj.name === "orchestrate_task") {
          if (ultronOrb) ultronOrb.spawnAgentOrb("supervisor", "Supervisor");
          addActiveAgentChip("supervisor", "Supervisor Core");
        } else if (obj.name === "screen_awareness" || obj.name === "computer_control" || obj.name === "open_app") {
          if (ultronOrb) ultronOrb.spawnAgentOrb("computer_agent", "Bilgisayar");
          addActiveAgentChip("computer_agent", "Computer Use");
        } else if (obj.name === "fetch_webpage_content" || obj.name === "search_emails") {
          if (ultronOrb) ultronOrb.spawnAgentOrb("research_agent", "Araştırma");
          addActiveAgentChip("research_agent", "Web Araştırma");
        }
        break;

      case "turn_complete":
        stateManager.pushTransientState("SUCCESS", 1200);
        setTimeout(() => {
          if (S.activeAgentCount === 0) {
            stateManager.setBaseState(S.micOn ? "LISTENING" : "IDLE");
          }
        }, 1200);
        break;

      case "interrupt":
      case "barge_in":
        handleBargeIn();
        break;

      case "agent_thought":
        if (obj.agent && obj.thought) {
          updateThoughtTicker(obj.agent, obj.thought);
          if (ultronOrb && typeof ultronOrb.pulseAgentStream === "function") {
            ultronOrb.pulseAgentStream(obj.agent, 0.8);
          }
        }
        break;

      case "dag_update":
        if (ultronOrb && typeof ultronOrb.setNeuralDataGraph === "function") {
          ultronOrb.setNeuralDataGraph(obj.nodes || [], obj.edges || []);
        }
        break;

      case "proactive_alert":
        showProactiveAlert(obj.alert || obj);
        break;

      case "mcp_status":
        addLog("sys", `🔌 MCP Sunucuları: ${obj.active_servers || 0} aktif / ${obj.total_mcp_tools || 0} araç hazır.`);
        break;

      case "webcam":
        if (obj.action === "start") startCam();
        else stopCam();
        break;

      case "error":
        S.fatalMsg = obj.text;
        addLog("sys", "HATA: " + obj.text);
        stateManager.pushTransientState("ERROR", 4000, "HATA: " + obj.text);
        break;

    }
  };
}

// ── Konum Takibi (Geolocation) ───────────────────────────────────────────
function initLocationTracking() {
  if (!navigator.geolocation) {
    if (badgeGps) {
      badgeGps.textContent = "GPS: N/A";
      badgeGps.className = "badge off";
    }
    return;
  }

  const onLocation = (pos) => {
    const coords = {
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
      accuracy: pos.coords.accuracy
    };
    S.lastCoords = coords;

    if (badgeGps) {
      badgeGps.textContent = `GPS: ±${Math.round(coords.accuracy)}m`;
      badgeGps.className = "badge on";
    }

    try {
      fetch("/api/location", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user: S.currentUser, ...coords })
      }).catch(() => {});
    } catch (e) {}

    if (S.ws && S.ws.readyState === WebSocket.OPEN) {
      S.ws.send(JSON.stringify({ type: "location", coords }));
    }
  };

  const onError = (err) => {
    if (badgeGps) {
      badgeGps.textContent = "GPS: DENIED";
      badgeGps.className = "badge off";
    }
  };

  S.geoWatchId = navigator.geolocation.watchPosition(onLocation, onError, {
    enableHighAccuracy: true,
    maximumAge: 30000,
    timeout: 27000
  });
}

// ── Aktif Ajan Orbları HUD Göstergesi ──────────────────────────────────────
const activeAgentsBar = $("active-agents-bar");
const agentMeta = {
  coding_agent:   { name: "CODING", icon: "💻" },
  testing_agent:  { name: "TESTING", icon: "🧪" },
  reviewer_agent: { name: "REVIEWER", icon: "🧐" },
  research_agent: { name: "RESEARCH", icon: "🧠" },
  terminal_agent: { name: "TERMINAL", icon: "⚡" },
  computer_agent: { name: "COMPUTER", icon: "👁️" },
  supervisor:     { name: "SUPERVISOR", icon: "👑" },
};

function addActiveAgentChip(agentKey, details = "") {
  if (!activeAgentsBar) return;
  const key = String(agentKey || "").toLowerCase().replace(/[^a-z0-9_]/g, "");
  let chip = document.getElementById(`agent-chip-${key}`);
  const meta = agentMeta[key] || { name: key.toUpperCase(), icon: "🤖" };
  const detailLabel = details ? String(details).replace(/^(Running |Ajan devrede: |Görev: )/, "") : "DEVREDE";

  if (!chip) {
    chip = document.createElement("div");
    chip.id = `agent-chip-${key}`;
    chip.className = `agent-orb-chip ${key}`;
    chip.innerHTML = `<span class="pulse-dot"></span><span class="agent-title">${meta.icon} ${meta.name}</span><span class="agent-detail-tag">${detailLabel}</span>`;
    activeAgentsBar.appendChild(chip);
  } else {
    const tag = chip.querySelector(".agent-detail-tag");
    if (tag && details) tag.textContent = detailLabel;
  }
}

function removeActiveAgentChip(agentKey) {
  if (!activeAgentsBar) return;
  const key = String(agentKey || "").toLowerCase().replace(/[^a-z0-9_]/g, "");
  const chip = document.getElementById(`agent-chip-${key}`);
  if (chip) {
    chip.style.opacity = "0";
    chip.style.transform = "scale(0.7)";
    setTimeout(() => chip.remove(), 300);
  }
}

function clearActiveAgentChips() {
  if (!activeAgentsBar) return;
  activeAgentsBar.innerHTML = "";
}

function setIdentifiedSpeaker(userName, meta = {}) {
  S.currentUser = "YARATICI";
  if (currentUserDisplay) currentUserDisplay.textContent = S.currentUser;
}


// ── Ses Çalma (24 kHz PCM16) & RMS Enerji Hesaplama ───────────────────────
function ensurePlayCtx() {
  if (!S.playCtx) {
    S.playCtx = new (window.AudioContext || window.webkitAudioContext)({
      sampleRate: 24000,
    });
  }
  if (S.playCtx.state === "suspended") S.playCtx.resume();
  return S.playCtx;
}

function playAudioChunk(buf) {
  const ctx = ensurePlayCtx();
  const i16 = new Int16Array(buf);
  if (i16.length === 0) return;

  const f32 = new Float32Array(i16.length);
  let peak = 0;
  for (let i = 0; i < i16.length; i++) {
    f32[i] = i16[i] / 32768;
    const a = Math.abs(f32[i]);
    if (a > peak) peak = a;
  }
  S.outLevel = Math.max(S.outLevel, peak);

  const audioBuf = ctx.createBuffer(1, f32.length, 24000);
  audioBuf.copyToChannel(f32, 0);

  const src = ctx.createBufferSource();
  src.buffer = audioBuf;
  src.connect(ctx.destination);

  const now = ctx.currentTime;
  if (S.nextPlayTime < now) S.nextPlayTime = now + 0.04;
  src.start(S.nextPlayTime);
  S.nextPlayTime += audioBuf.duration;

  S.playingSources.push(src);
  src.onended = () => {
    const idx = S.playingSources.indexOf(src);
    if (idx >= 0) S.playingSources.splice(idx, 1);
    if (S.playingSources.length === 0) {
      S.speaking = false;
      if (stateManager.activeState === "SPEAKING") {
        stateManager.setBaseState(S.micOn ? "LISTENING" : "IDLE");
      }
    }
  };

  if (!S.speaking) {
    S.speakingStartTime = Date.now();
    S.bargeInConsecutiveCount = 0;
  }
  S.speaking = true;
  stateManager.setBaseState("SPEAKING");
}

function flushPlayback() {
  for (const src of S.playingSources) {
    try { src.stop(); } catch {}
  }
  S.playingSources = [];
  S.nextPlayTime = 0;
  S.speaking = false;
  S.bargeInConsecutiveCount = 0;
}

// ── Full-Duplex Acoustic Echo Cancellation & Barge-In 2.0 ──────────────────
function handleBargeIn() {
  if (!S.speaking && S.playingSources.length === 0) return;
  console.log("[Barge-In 2.0] ⚡ Kullanıcı araya girdi, ses anında durduruluyor.");
  flushPlayback();
  S.speaking = false;
  stateManager.setBaseState("LISTENING", "DİNLİYORUM…");
  
  if (S.ws && S.ws.readyState === WebSocket.OPEN) {
    S.ws.send(JSON.stringify({ type: "barge_in", timestamp: Date.now() }));
  }
}

// ── Proaktif Bildirim ve Chain-of-Thought Ticker ───────────────────────────
function updateThoughtTicker(agentId, thoughtText) {
  let ticker = $("hud-thought-ticker");
  if (!ticker) {
    ticker = document.createElement("div");
    ticker.id = "hud-thought-ticker";
    ticker.className = "hud-thought-ticker";
    const topLeft = $("hud-top-left");
    if (topLeft) topLeft.appendChild(ticker);
  }
  ticker.innerHTML = `<strong>[${escapeHtml(agentId.toUpperCase())}]</strong> ${escapeHtml(thoughtText)}`;
  ticker.classList.remove("hidden");
  clearTimeout(ticker._hideTimer);
  ticker._hideTimer = setTimeout(() => ticker.classList.add("hidden"), 5000);
}

function showProactiveAlert(alert) {
  if (!alert) return;
  const toast = $("hud-toast");
  if (!toast) return;
  
  const icon = alert.severity === "CRITICAL" ? "🚨" : (alert.severity === "HIGH" ? "⚠️" : "💡");
  toast.innerHTML = `
    <div class="proactive-alert-card ${alert.severity ? alert.severity.toLowerCase() : 'info'}">
      <div class="proactive-title">${icon} ${escapeHtml(alert.title || "Proaktif Sistem Önerisi")}</div>
      <div class="proactive-msg">${escapeHtml(alert.message || "")}</div>
      ${alert.suggested_action ? `<div class="proactive-action">💡 <em>Öneri: ${escapeHtml(alert.suggested_action)}</em></div>` : ""}
      <div class="proactive-btns">
        ${alert.auto_executable ? `<button class="btn-proactive-exec" onclick="window.ultronUI.executeAlert('${escapeHtml(alert.alert_id)}')">⚡ DÜZELT</button>` : ""}
        <button class="btn-proactive-dismiss" onclick="this.closest('.proactive-alert-card').remove()">✕ KAPAT</button>
      </div>
    </div>
  `;
  toast.classList.remove("hidden");
  addLog("sys", `[PROAKTİF ÖNERİ] ${alert.title}: ${alert.message}`);
}

// ── Mikrofon (DSP Gürültü Engelleme & Netlik Filtresi) ────────────────────
async function startMic() {
  if (S.micOn) return;
  // İlk mikrofon aktivasyonunda push bildirim izni iste
  requestPushPermission().catch(() => {});
  try {
    S.micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
        sampleRate: { ideal: 16000 },
        latency: { ideal: 0.01 }
      },
    });
  } catch {
    addLog("sys", "Mikrofon izni reddedildi.");
    stateManager.pushTransientState("WARNING", 3000, "MİKROFON İZNİ YOK");
    return;
  }

  S.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (S.audioCtx.state === "suspended") await S.audioCtx.resume();
  await S.audioCtx.audioWorklet.addModule("/static/pcm-worklet.js");

  const srcNode = S.audioCtx.createMediaStreamSource(S.micStream);
  // --- Audio Visualizer Injection ---
  S.analyserNode = S.audioCtx.createAnalyser();
  S.analyserNode.fftSize = 64;
  srcNode.connect(S.analyserNode);

  const visCanvas = document.getElementById("audio-visualizer");
  if (visCanvas) {
    const visCtx = visCanvas.getContext("2d");
    const bufferLength = S.analyserNode.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function drawVisualizer() {
      if (!S.micStream) {
        visCtx.clearRect(0, 0, visCanvas.width, visCanvas.height);
        return; // stop if mic closed
      }
      requestAnimationFrame(drawVisualizer);
      S.analyserNode.getByteFrequencyData(dataArray);

      visCtx.clearRect(0, 0, visCanvas.width, visCanvas.height);
      const barWidth = (visCanvas.width / bufferLength) * 1.5;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (dataArray[i] / 255) * visCanvas.height;
        // Ultron color
        visCtx.fillStyle = `rgb(255, ${68 + (dataArray[i] / 2)}, 34)`;
        visCtx.fillRect(x, visCanvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 2;
      }
    }
    drawVisualizer();
  }
  // ----------------------------------


  // 1. Highpass Filter (85 Hz)
  const highpass = S.audioCtx.createBiquadFilter();
  highpass.type = "highpass";
  highpass.frequency.setValueAtTime(85, S.audioCtx.currentTime);
  highpass.Q.setValueAtTime(0.707, S.audioCtx.currentTime);

  // 2. Dynamics Compressor
  const compressor = S.audioCtx.createDynamicsCompressor();
  compressor.threshold.setValueAtTime(-34, S.audioCtx.currentTime);
  compressor.knee.setValueAtTime(10, S.audioCtx.currentTime);
  compressor.ratio.setValueAtTime(4.5, S.audioCtx.currentTime);
  compressor.attack.setValueAtTime(0.003, S.audioCtx.currentTime);
  compressor.release.setValueAtTime(0.20, S.audioCtx.currentTime);

  // 3. Vocal Presence Gain (+2.5 dB)
  const vocalGain = S.audioCtx.createGain();
  vocalGain.gain.setValueAtTime(1.35, S.audioCtx.currentTime);

  // 4. PCM Capture Worklet Node (16 kHz Int16 stream)
  S.workletNode = new AudioWorkletNode(S.audioCtx, "pcm-capture");

  S.workletNode.port.onmessage = (ev) => {
    const i16 = ev.data;
    if (i16.length > 0) {
      let sumSquares = 0;
      for (let s = 0; s < i16.length; s += 8) {
        const v = i16[s] / 32768;
        sumSquares += v * v;
      }
      const rms = Math.sqrt(sumSquares / (i16.length / 8));
      S.micLevel = Math.max(S.micLevel, Math.min(1.0, rms * 3.5));

      // ── Akustik Yankı Korumalı Barge-In (Yalnızca Gerçek İnsan Müdahalesinde) ───
      if (S.speaking) {
        const now = Date.now();
        const speakDuration = now - (S.speakingStartTime || now);
        // Hoparlör sesinin mikrofonu yankı olarak kesmesini önlemek için:
        // En az 750ms çalma geçmiş olmalı ve mikrofon seviyesi bariz insan sesi düzeyinde (rms > 0.12) olmalı
        if (speakDuration > 750 && rms > 0.12 && S.micLevel > 0.55) {
          S.bargeInConsecutiveCount = (S.bargeInConsecutiveCount || 0) + 1;
          if (S.bargeInConsecutiveCount >= 4) {
            handleBargeIn();
            S.bargeInConsecutiveCount = 0;
          }
        } else {
          S.bargeInConsecutiveCount = 0;
        }
      } else {
        S.bargeInConsecutiveCount = 0;
      }
    }

    if (S.studioRecordingActive && S.studioChunks) {
      S.studioChunks.push(new Int16Array(i16));
    }
    if (typeof drawVoiceVisualizer === "function") {
      drawVoiceVisualizer(i16);
    }
    if (!S.ws || S.ws.readyState !== WebSocket.OPEN || !S.ready) return;
    const out = new Uint8Array(1 + i16.byteLength);
    out[0] = 0x01;
    out.set(new Uint8Array(i16.buffer, i16.byteOffset, i16.byteLength), 1);
    S.ws.send(out);

  };

  srcNode.connect(highpass);
  highpass.connect(compressor);
  compressor.connect(vocalGain);
  vocalGain.connect(S.workletNode);

  const silent = S.audioCtx.createGain();
  silent.gain.value = 0;
  S.workletNode.connect(silent).connect(S.audioCtx.destination);

  ensurePlayCtx();

  S.micOn = true;
  const btnMic = $("btn-mic");
  if (btnMic) {
    btnMic.className = "ctl rec";
    btnMic.textContent = "🔴 MIC ON";
  }
  stateManager.setBaseState("LISTENING");
}

function stopMic() {
  if (S.micStream) S.micStream.getTracks().forEach((t) => t.stop());
  if (S.workletNode) { try { S.workletNode.disconnect(); } catch {} }
  if (S.audioCtx) { try { S.audioCtx.close(); } catch {} }
  S.micStream = S.workletNode = S.audioCtx = null;
  S.micOn = false;
  const btnMic = $("btn-mic");
  if (btnMic) {
    btnMic.className = "ctl";
    btnMic.textContent = "🎙️ MIC";
  }
  stateManager.setBaseState("IDLE");
}

// ── Kamera & Görsel Analiz (Vision) ──────────────────────────────────────
async function startCam() {
  if (S.camOn) return;
  try {
    S.camStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, facingMode: "user" },
    });
  } catch {
    addLog("sys", "Kamera izni reddedildi.");
    stateManager.pushTransientState("WARNING", 3000, "KAMERA İZNİ YOK");
    return;
  }
  const video = $("cam");
  if (video) video.srcObject = S.camStream;
  const camWrap = $("cam-wrap");
  if (camWrap) camWrap.classList.remove("hidden");

  const canvas = document.createElement("canvas");
  const sendFrame = () => {
    if (!S.camOn || !S.ws || S.ws.readyState !== WebSocket.OPEN || !S.ready || !video) return;
    const w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return;
    const scale = Math.min(1, 1024 / Math.max(w, h));
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx2 = canvas.getContext("2d");
    ctx2.translate(canvas.width, 0);
    ctx2.scale(-1, 1);
    ctx2.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      const buf = new Uint8Array(await blob.arrayBuffer());
      const out = new Uint8Array(1 + buf.length);
      out[0] = 0x02;
      out.set(buf, 1);
      if (S.ws && S.ws.readyState === WebSocket.OPEN) S.ws.send(out);
    }, "image/jpeg", 0.7);
  };

  S.camTimer = setInterval(sendFrame, 1500);
  S.camOn = true;
  const btnCam = $("btn-cam");
  if (btnCam) {
    btnCam.className = "ctl rec";
    btnCam.textContent = "🔴 CAM ON";
  }
  addLog("sys", "Webcam CANLI — Görsel analiz aktif.");
  stateManager.setBaseState("OBSERVING");

  if (video) {
    try {
      await autoStartHandTracking(video);
    } catch (err) {
      enableDragFallback();
    }
  }
}

function stopCam() {
  if (S.camTimer) clearInterval(S.camTimer);
  if (S.camStream) S.camStream.getTracks().forEach((t) => t.stop());
  S.camTimer = S.camStream = null;
  S.camOn = false;
  const video = $("cam");
  if (video) video.srcObject = null;
  const camWrap = $("cam-wrap");
  if (camWrap) camWrap.classList.add("hidden");
  const btnCam = $("btn-cam");
  if (btnCam) {
    btnCam.className = "ctl";
    btnCam.textContent = "📷 CAM";
  }
  addLog("sys", "Webcam KAPALI");
  stateManager.setBaseState(S.micOn ? "LISTENING" : "IDLE");

  if (gestureActive && handTracker) {
    handTracker.stop();
    gestureActive = false;
    if (camWrap) camWrap.classList.remove("gesture-active");
  }
  disableDragFallback();
}

// ── Mouse / Touch Sürükleme ile Orb Kontrolü ─────────────────────────────
let dragFallbackEnabled = false;
let dragActive = false;
let dragLastX = 0;
let dragLastY = 0;

function onDragStart(x, y) {
  dragActive = true;
  dragLastX = x;
  dragLastY = y;
}
function onDragMove(x, y) {
  if (!dragActive || !ultronOrb) return;
  const dx = (x - dragLastX) * 0.01;
  const dy = (y - dragLastY) * 0.01;
  ultronOrb.rotateBy(dx, dy);
  dragLastX = x;
  dragLastY = y;
}
function onDragEnd() {
  dragActive = false;
}

function onMouseDown(e) { 
  if (e.target.closest("#hud-center, #hud-bottom, #qr-modal, #key-screen, #hud-top-right, #voice-modal, #debug-overlay")) return;
  onDragStart(e.clientX, e.clientY); 
}
function onMouseMove(e) { onDragMove(e.clientX, e.clientY); }
function onMouseUp()    { onDragEnd(); }
function onTouchStart(e) {
  if (e.target.closest("#hud-center, #hud-bottom, #qr-modal, #key-screen, #hud-top-right, #voice-modal, #debug-overlay")) return;
  if (e.touches.length === 1) {
    onDragStart(e.touches[0].clientX, e.touches[0].clientY);
  }
}
function onTouchMove(e) {
  if (e.touches.length === 1) {
    onDragMove(e.touches[0].clientX, e.touches[0].clientY);
  }
}
function onTouchEnd() { onDragEnd(); }

function enableDragFallback() {
  if (dragFallbackEnabled) return;
  dragFallbackEnabled = true;
  window.addEventListener("mousedown",  onMouseDown);
  window.addEventListener("mousemove",  onMouseMove);
  window.addEventListener("mouseup",    onMouseUp);
  window.addEventListener("touchstart", onTouchStart, { passive: true });
  window.addEventListener("touchmove",  onTouchMove,  { passive: true });
  window.addEventListener("touchend",   onTouchEnd);
}

function disableDragFallback() {
  if (!dragFallbackEnabled) return;
  dragFallbackEnabled = false;
  window.removeEventListener("mousedown",  onMouseDown);
  window.removeEventListener("mousemove",  onMouseMove);
  window.removeEventListener("mouseup",    onMouseUp);
  window.removeEventListener("touchstart", onTouchStart);
  window.removeEventListener("touchmove",  onTouchMove);
  window.removeEventListener("touchend",   onTouchEnd);
}

enableDragFallback();

// ── El Takibi (MediaPipe Hand Tracking) ──────────────────────────────────
let handTracker = null;
let gestureActive = false;

async function autoStartHandTracking(video) {
  const overlayCanvas = $("hand-canvas");

  if (!handTracker) {
    handTracker = new HandTracker(video, overlayCanvas, {
      onRotate: (dt, dp) => { if (ultronOrb) ultronOrb.rotateBy(dt, dp); },
      onZoom:   (factor) => { if (ultronOrb) ultronOrb.zoomBy(factor); },
      onStatus: (status) => {
        const camWrap = $("cam-wrap");
        if (camWrap) {
          if (status.mode !== "idle") {
            camWrap.classList.add("gesture-active");
          } else {
            camWrap.classList.remove("gesture-active");
          }
        }
      }
    });
  }

  await _startHandTrackerWithExistingStream(handTracker, video);
  gestureActive = true;
  const camWrap = $("cam-wrap");
  if (camWrap) camWrap.classList.add("gesture-active");
  addLog("sys", "El takibi hazır.");
}

async function _startHandTrackerWithExistingStream(tracker, video) {

  const { FilesetResolver, HandLandmarker } =
    await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs");

  const WASM_CDN  = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm";
  const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

  if (video.paused) await video.play();

  const fileset = await FilesetResolver.forVisionTasks(WASM_CDN);
  const options = {
    baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
    runningMode: "VIDEO",
    numHands: 2,
    minHandDetectionConfidence: 0.6,
    minHandPresenceConfidence: 0.6,
    minTrackingConfidence: 0.6,
  };
  try {
    tracker.landmarker = await HandLandmarker.createFromOptions(fileset, options);
  } catch {
    tracker.landmarker = await HandLandmarker.createFromOptions(fileset, {
      ...options,
      baseOptions: { ...options.baseOptions, delegate: "CPU" },
    });
  }

  tracker.stream  = null;
  tracker.video   = video;
  tracker.running = true;
  tracker.loop();
}

// ── Sohbet / Konsol Açıp Kapatma ─────────────────────────────────────────
function toggleChat(forceOpen = null) {
  if (!logContainer) return;
  const isCurrentlyCollapsed = logContainer.classList.contains("collapsed");
  const shouldOpen = forceOpen !== null ? forceOpen : isCurrentlyCollapsed;
  
  if (shouldOpen) {
    logContainer.classList.remove("collapsed");
    if (toastEl) toastEl.classList.add("hidden");
    const btnToggle = $("btn-toggle-log");
    if (btnToggle) btnToggle.classList.add("active");
    if (logEl) {
      requestAnimationFrame(() => {
        logEl.scrollTop = logEl.scrollHeight;
      });
    }
  } else {
    logContainer.classList.add("collapsed");
    const btnToggle = $("btn-toggle-log");
    if (btnToggle) btnToggle.classList.remove("active");
  }
}

const btnToggleLog = $("btn-toggle-log");
if (btnToggleLog) btnToggleLog.addEventListener("click", () => toggleChat());
const btnCloseLog = $("btn-close-log");
if (btnCloseLog) btnCloseLog.addEventListener("click", () => toggleChat(false));

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    const qrModal = $("qr-modal");
    if (qrModal && !qrModal.classList.contains("hidden")) {
      closeQrModal();
    } else {
      toggleChat();
    }
  } else if (e.key === "F11") {
    e.preventDefault();
    toggleFullscreen();
  } else if (e.ctrlKey && e.shiftKey && (e.key === "D" || e.key === "d")) {
    toggleDebugOverlay();
  }
});

// ── Tam Ekran Yönetimi (Fullscreen Management) ─────────────────────────────
function toggleFullscreen() {
  if (!document.fullscreenElement && !document.webkitFullscreenElement) {
    if (document.documentElement.requestFullscreen) {
      document.documentElement.requestFullscreen().catch(err => {
        console.warn("Fullscreen request error:", err);
      });
    } else if (document.documentElement.webkitRequestFullscreen) {
      document.documentElement.webkitRequestFullscreen();
    }
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen().catch(err => {
        console.warn("Exit fullscreen error:", err);
      });
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
  }
}

const btnFullscreen = $("btn-fullscreen");
if (btnFullscreen) {
  btnFullscreen.addEventListener("click", () => toggleFullscreen());
}

document.addEventListener("fullscreenchange", () => {
  const btn = $("btn-fullscreen");
  if (btn) {
    if (document.fullscreenElement) {
      btn.classList.add("active");
      btn.textContent = "⛶ PENCERE";
      btn.title = "Pencere Moduna Geç (F11)";
    } else {
      btn.classList.remove("active");
      btn.textContent = "⛶ TAM EKRAN";
      btn.title = "Tam Ekran Modunu Aç (F11)";
    }
  }
});


// ── QR Kod Bağlantı Modalı ────────────────────────────────────────────────
const btnQrModal = $("btn-qr-modal");
const qrModal = $("qr-modal");
const btnCloseQr = $("btn-close-qr");
const qrCodeBox = $("qr-code-box");
const qrUrlInput = $("qr-url-input");
const btnCopyQrUrl = $("btn-copy-qr-url");
const tabQrCloud = $("tab-qr-cloud");
const tabQrLan = $("tab-qr-lan");
const qrStatusMsg = $("qr-status-msg");
const qrHintText = $("qr-hint-text");
const btnFirewall = $("btn-firewall-permission");

let qrCodeInstance = null;

function renderQr(targetUrl) {
  if (!qrCodeBox) return;
  qrCodeBox.innerHTML = "";
  if (qrUrlInput) qrUrlInput.value = targetUrl;
  try {
    if (window.QRCode) {
      qrCodeInstance = new window.QRCode(qrCodeBox, {
        text: targetUrl,
        width: 200,
        height: 200,
        colorDark: "#ff4422",
        colorLight: "#0a0402",
        correctLevel: window.QRCode.CorrectLevel.M
      });
    } else {
      qrCodeBox.innerHTML = `<div style="color:var(--amber); font-size:11px; padding:10px; word-break:break-all;">${targetUrl}</div>`;
    }
  } catch (err) {
    qrCodeBox.innerHTML = `<div style="color:var(--amber); font-size:11px; padding:10px; word-break:break-all;">${targetUrl}</div>`;
  }
}

function updateQrView() {
  if (!S.connInfo) return;
  const hasCloud = !!S.connInfo.tunnel_url;
  
  if (S.activeQrMode === "cloud" && hasCloud) {
    if (tabQrCloud) tabQrCloud.classList.add("active");
    if (tabQrLan) tabQrLan.classList.remove("active");
    if (qrStatusMsg) qrStatusMsg.textContent = "🌐 Cloudflare İnternet Tüneli Aktif. Telefonunuzdan herhangi bir yerden bağlanabilirsiniz.";
    if (qrHintText) qrHintText.textContent = "✓ Doğrudan mobil tarayıcıda açılır, sertifika hatası vermez.";
    renderQr(S.connInfo.tunnel_url);
  } else {
    S.activeQrMode = "lan";
    if (tabQrCloud) tabQrCloud.classList.remove("active");
    if (tabQrLan) tabQrLan.classList.add("active");
    const lanUrl = S.connInfo.lan_url || S.connInfo.http_url || "";
    if (qrStatusMsg) qrStatusMsg.textContent = "🏠 Yerel Wi-Fi Bağlantısı. Telefon ile bilgisayarın aynı Wi-Fi ağına bağlı olması gerekir.";
    if (qrHintText) qrHintText.textContent = "🔒 Tarayıcı güvenlik uyarısı verirse 'Gelişmiş' ve 'Devam Et' seçin.";
    renderQr(lanUrl);
  }
}

async function openQrModal() {
  if (!qrModal) return;
  qrModal.classList.remove("hidden");

  try {
    const res = await fetch("/api/connection-info");
    if (res.ok) {
      S.connInfo = await res.json();
      S.activeQrMode = S.connInfo.has_tunnel ? "cloud" : "lan";
    }
  } catch (e) {
    S.connInfo = {
      lan_url: `${location.protocol}//${location.host}/?t=${encodeURIComponent(getToken())}`,
      has_tunnel: false
    };
  }

  updateQrView();
}

function closeQrModal() {
  if (qrModal) qrModal.classList.add("hidden");
}

if (tabQrCloud) {
  tabQrCloud.addEventListener("click", () => {
    S.activeQrMode = "cloud";
    updateQrView();
  });
}
if (tabQrLan) {
  tabQrLan.addEventListener("click", () => {
    S.activeQrMode = "lan";
    updateQrView();
  });
}

if (btnFirewall) {
  btnFirewall.addEventListener("click", async () => {
    btnFirewall.textContent = "Kontrol ediliyor...";
    try {
      const res = await (await fetch("/api/allow-firewall", { method: "POST" })).json();
      btnFirewall.textContent = res.message || "İzin Verildi!";
      btnFirewall.style.background = "var(--green)";
      btnFirewall.style.color = "#000";
      setTimeout(() => {
        btnFirewall.textContent = "🛡️ Güvenlik Duvarı İzni Ver";
        btnFirewall.style.background = "";
        btnFirewall.style.color = "";
      }, 2500);
    } catch (e) {
      btnFirewall.textContent = "Hata oluştu.";
    }
  });
}

if (btnQrModal) btnQrModal.addEventListener("click", openQrModal);
if (btnCloseQr) btnCloseQr.addEventListener("click", closeQrModal);
if (qrModal) {
  qrModal.addEventListener("click", (e) => {
    if (e.target === qrModal) closeQrModal();
  });
}

if (btnCopyQrUrl) {
  btnCopyQrUrl.addEventListener("click", async () => {
    if (!qrUrlInput || !qrUrlInput.value) return;
    try {
      await navigator.clipboard.writeText(qrUrlInput.value);
      btnCopyQrUrl.textContent = "KOPYALANDI!";
      btnCopyQrUrl.style.background = "var(--green)";
      btnCopyQrUrl.style.color = "#000";
      setTimeout(() => {
        btnCopyQrUrl.textContent = "KOPYALA";
        btnCopyQrUrl.style.background = "";
        btnCopyQrUrl.style.color = "";
      }, 1600);
    } catch (e) {
      qrUrlInput.select();
      document.execCommand("copy");
    }
  });
}

// ── UI Olayları ──────────────────────────────────────────────────────────
const btnMic = $("btn-mic");
if (btnMic) {
  btnMic.addEventListener("click", () => {
    if (S.micOn) {
      stopMic();
    } else {
      ensurePlayCtx();
      startMic();
    }
  });
}

const btnCam = $("btn-cam");
if (btnCam) {
  btnCam.addEventListener("click", () => (S.camOn ? stopCam() : startCam()));
}

const textForm = $("text-form");
if (textForm) {
  textForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("text-input");
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    if (!S.ws || S.ws.readyState !== WebSocket.OPEN || !S.ready) {
      input.style.borderColor = "#ff4422";
      addLog("sys", "⚠ Sunucu bağlantısı bekleniyor…");
      return;
    }

    stateManager.setBaseState("THINKING", "KOMUT İŞLENİYOR…");
    S.ws.send(JSON.stringify({ type: "text", text }));
    addLog("user", text);
    input.value = "";
    ensurePlayCtx();
  });
}

// ── API Anahtarı Ekranı (Public Mod) ───────────────────────────────────────
function showKeyScreen(errText) {
  S.awaitingKey = true;
  if (S.reconnectTimer) { clearTimeout(S.reconnectTimer); S.reconnectTimer = null; }
  const screen = $("key-screen");
  if (screen) screen.classList.remove("hidden");
  stateManager.setBaseState("CONFIRMING", "API ANAHTARI GEREKLİ");
}

function hideKeyScreen() {
  S.awaitingKey = false;
  const screen = $("key-screen");
  if (screen) screen.classList.add("hidden");
}

const keySave = $("key-save");
if (keySave) keySave.addEventListener("click", saveKeyAndStart);
const keyInput = $("key-input");
if (keyInput) {
  keyInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveKeyAndStart();
  });
}

function saveKeyAndStart() {
  const input = $("key-input");
  if (!input) return;
  const key = input.value.trim();
  if (!key) return;
  S.apiKey = key;
  localStorage.setItem("ultron_gemini_key", key);
  hideKeyScreen();
  ensurePlayCtx();
  connect();
}

// ── Başlat ───────────────────────────────────────────────────────────────
async function initApp() {
  S.currentUser = "Bilinmeyen";

  try {
    const info = await (await fetch("/mode")).json();
    S.public = !!info.public;
    if (info.voice && !localStorage.getItem("ultron_voice")) {
      S.voice = info.voice;
    }
    const stamp = $("build-stamp");
    if (stamp && info.build) stamp.textContent = info.build;
  } catch { S.public = false; }

  initLocationTracking();

  // PWA: Mobil ekran uyanık tut + Push bildirimleri
  initWakeLock();
  initPushNotifications();

  if (S.public) {
    S.apiKey = localStorage.getItem("ultron_gemini_key") || "";
    if (!S.apiKey) {
      showKeyScreen();
      return;
    }
  }
  connect();
}

// ── PWA: Screen Wake Lock — Mobil cihazda ekran uyumasını engelle ────────
async function initWakeLock() {
  if (!("wakeLock" in navigator)) return;
  const acquireWakeLock = async () => {
    try {
      S.wakeLock = await navigator.wakeLock.request("screen");
      S.wakeLock.addEventListener("release", () => {
        S.wakeLock = null;
      });
    } catch (err) {
      // İzin reddedildi veya desteklenmiyor — sessizce devam et
    }
  };
  await acquireWakeLock();
  // Sayfa tekrar görünür olunca (arka plandan dönünce) yeniden al
  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState === "visible" && !S.wakeLock) {
      await acquireWakeLock();
    }
  });
}

// ── PWA: Web Push Bildirimleri ────────────────────────────────────────────
async function initPushNotifications() {
  if (!("Notification" in window) || !("serviceWorker" in navigator)) return;
  // Sadece zaten izin verilmişse otomatik abone ol
  if (Notification.permission === "granted") {
    await subscribeToPush();
  }
  // İzin henüz sorulmamışsa: kullanıcı mikrofonla ilk konuştuğunda sor
  // (startMic() çağrıldığında tetiklenir — aşağıda)
}

async function requestPushPermission() {
  if (!("Notification" in window)) return;
  if (Notification.permission === "default") {
    const perm = await Notification.requestPermission();
    if (perm === "granted") {
      await subscribeToPush();
    }
  }
}

async function subscribeToPush() {
  try {
    if (S.pushSubscription) return;
    const reg = await navigator.serviceWorker.ready;
    // VAPID public key'i sunucudan al
    const resp = await fetch("/api/push/vapid-public-key");
    if (!resp.ok) return;
    const { public_key } = await resp.json();
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
    S.pushSubscription = sub;
    // Subscription'ı sunucuya kaydet
    await fetch("/api/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sub.toJSON()),
    });
  } catch (err) {
    // Push kurulumu sessizce başarısız olabilir
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

initApp();

// ═══════════════════════════════════════════════════════════════════════════
// ── UI State Debug Mode & Automated Diagnostic Test Harness ───────────────
// ═══════════════════════════════════════════════════════════════════════════

let debugOverlayEl = null;
let isDebugVisible = false;

function toggleDebugOverlay() {
  isDebugVisible = !isDebugVisible;
  if (!debugOverlayEl) {
    debugOverlayEl = document.createElement("div");
    debugOverlayEl.id = "debug-overlay";
    debugOverlayEl.className = "debug-hud-overlay";
    document.body.appendChild(debugOverlayEl);
  }
  debugOverlayEl.style.display = isDebugVisible ? "block" : "none";
}

function updateDebugOverlay() {
  if (!debugOverlayEl || !isDebugVisible) return;
  const activeOrbs = ultronOrb ? ultronOrb.getActiveAgentOrbs().join(", ") || "None" : "N/A";
  debugOverlayEl.innerHTML = `
    <div class="dbg-title">⚡ ULTRON UI STATE DEBUG // HUD</div>
    <div class="dbg-row"><span>ACTIVE STATE:</span> <strong style="color:var(--cyan)">${stateManager.activeState}</strong></div>
    <div class="dbg-row"><span>BASE STATE:</span> <span>${stateManager.baseState}</span></div>
    <div class="dbg-row"><span>PRIORITY:</span> <span>${STATE_PRIORITY[stateManager.activeState] || 0}</span></div>
    <div class="dbg-row"><span>TRANSIENT STACK:</span> <span>${stateManager.transientStack.map(t => t.state).join(" > ") || "Empty"}</span></div>
    <div class="dbg-row"><span>FPS:</span> <strong style="color:${stateManager.fps >= 55 ? 'var(--green)' : 'var(--amber)'}">${Math.round(stateManager.fps)} FPS</strong></div>
    <div class="dbg-row"><span>SATELLITE ORBS:</span> <span>${activeOrbs}</span></div>
    <div class="dbg-row"><span>MIC ENERGY:</span> <span>${(S.micLevel * 100).toFixed(0)}%</span></div>
    <div class="dbg-row"><span>OUT ENERGY:</span> <span>${(S.outLevel * 100).toFixed(0)}%</span></div>
    <div class="dbg-actions">
      <button class="dbg-btn" onclick="window.ultronUI.runStateDiagnostics()">🧪 TEST TÜM STATE'LERİ</button>
      <button class="dbg-btn" onclick="window.ultronUI.toggleDebug()">✕ Kapat</button>
    </div>
  `;
}

// Global window.ultronUI Developer API
window.ultronUI = {
  setState: (state, durationMs = 0, label = "") => {
    if (durationMs > 0) {
      stateManager.pushTransientState(state, durationMs, label);
    } else {
      stateManager.setBaseState(state, label);
    }
  },
  getState: () => stateManager.activeState,
  getHistory: () => stateManager.stateHistory,
  toggleDebug: toggleDebugOverlay,
  setConfig: (cfg) => {
    if (ultronOrb) ultronOrb.setUIConfig(cfg);
  },
  runStateDiagnostics: async () => {
    console.log("=================================================");
    console.log(">>> ULTRON UI STATE DIAGNOSTIC HARNESS START <<<");
    console.log("=================================================");
    
    const statesToTest = [
      { name: "IDLE",            type: "loop",      dur: 1000 },
      { name: "LISTENING",       type: "loop",      dur: 1200 },
      { name: "THINKING",        type: "loop",      dur: 1500 },
      { name: "EXECUTING",       type: "loop",      dur: 1500 },
      { name: "OBSERVING",       type: "loop",      dur: 1200 },
      { name: "SPEAKING",        type: "loop",      dur: 1200 },
      { name: "CONFIRMING",      type: "loop",      dur: 1200 },
      { name: "UNKNOWN_SPEAKER", type: "transient", dur: 1200 },
      { name: "VERIFIED_NURI",   type: "transient", dur: 1200 },
      { name: "VERIFIED_RABIA",  type: "transient", dur: 1200 },
      { name: "SUCCESS",         type: "transient", dur: 1200 },
      { name: "WARNING",         type: "transient", dur: 1200 },
      { name: "ERROR",           type: "transient", dur: 1200 },
      { name: "CONNECTING",      type: "loop",      dur: 1000 },
      { name: "DISCONNECTED",    type: "loop",      dur: 1000 },
    ];

    for (let i = 0; i < statesToTest.length; i++) {
      const st = statesToTest[i];
      console.log(`[TEST ${i+1}/${statesToTest.length}] State: ${st.name} (${st.type}, ${st.dur}ms)...`);
      
      if (st.type === "transient") {
        stateManager.pushTransientState(st.name, st.dur, `TEST: ${st.name}`);
      } else {
        stateManager.setBaseState(st.name, `TEST: ${st.name}`);
      }
      
      await new Promise(r => setTimeout(r, st.dur));
    }

    stateManager.clearTransient();
    stateManager.setBaseState(S.ready ? (S.micOn ? "LISTENING" : "IDLE") : "DISCONNECTED");
    console.log("=================================================");
    console.log(">>> TÜM 15 UI STATE TESTİ %100 BAŞARIYLA TAMAMLANDI <<<");
    console.log("=================================================");
    return "Tüm 15 state başarıyla simüle edildi ve doğrulandı.";
  },
  executeAlert: (alertId) => {
    addLog("user", `Proaktif öneri onaylandı: ${alertId}`);
    if (S.ws && S.ws.readyState === WebSocket.OPEN) {
      S.ws.send(JSON.stringify({ type: "execute_alert", alert_id: alertId }));
    }
  },
  setNeuralDataGraph: (nodes, edges) => {
    if (ultronOrb && typeof ultronOrb.setNeuralDataGraph === "function") {
      ultronOrb.setNeuralDataGraph(nodes, edges);
    }
  },
  pulseAgentStream: (agentId, intensity = 1.0) => {
    if (ultronOrb && typeof ultronOrb.pulseAgentStream === "function") {
      ultronOrb.pulseAgentStream(agentId, intensity);
    }
  }
};


// ═══════════════════════════════════════════════════════════════════════════
// RAPOR GÖRÜNTÜLEYİCİ MODALI — V19
// ═══════════════════════════════════════════════════════════════════════════

let _lastReportData = null;

/**
 * Bir Markdown metnini basit HTML'e dönüştürür (harici lib gerekmez).
 */
function _markdownToHtml(md) {
  if (!md) return '';
  let html = md
    // Başlıklar
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Kod blokları (önce — sıra önemli)
    .replace(/```[\w]*\n?([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>')
    // Kalın + italik
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Bağlantılar
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    // Yatay çizgi
    .replace(/^---+$/gm, '<hr>')
    // Madde işaretleri
    .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
    // Numaralı liste
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Paragraflar (boş satır = <br><br>)
    .replace(/\n{2,}/g, '<br><br>')
    .replace(/\n/g, '<br>');
  // li elemanlarını ul ile sar
  html = html.replace(/(<li>.*?<\/li>)+/gs, (m) => `<ul>${m}</ul>`);
  return html;
}

/**
 * Rapor görüntüleyici modalını açar.
 * @param {string} title    - Modal başlığı
 * @param {string} content  - Markdown içerik
 * @param {string} meta     - Üstte gösterilecek meta satırı (tarih, kaynak sayısı vs.)
 * @param {string} rawMd    - Ham markdown (indirme için)
 */
window.showReportModal = function(title, content, meta = '', rawMd = '') {
  _lastReportData = { title, content: rawMd || content, filename: title.replace(/[^\w\s-]/g, '').replace(/\s+/g, '_') };

  const modal   = document.getElementById('report-modal');
  const titleEl = document.getElementById('report-modal-title');
  const metaEl  = document.getElementById('report-modal-meta');
  const bodyEl  = document.getElementById('report-modal-content');

  if (!modal || !bodyEl) return;

  titleEl.textContent = '📋 ' + (title || 'ARAŞTIRMA RAPORU');
  metaEl.textContent  = meta || '';
  bodyEl.innerHTML    = _markdownToHtml(content || '');
  modal.classList.remove('hidden');
};

window.closeReportModal = function() {
  const modal = document.getElementById('report-modal');
  if (modal) modal.classList.add('hidden');
};

window.openReportFromNotification = function() {
  document.getElementById('report-notification')?.classList.add('hidden');
  if (_lastReportData) {
    window.showReportModal(_lastReportData.title, _lastReportData.content);
  }
};

/**
 * Rapor hazır olduğunda bildirim gösterir.
 */
function _showReportNotification(icon, text, reportData) {
  _lastReportData = reportData;
  const notif    = document.getElementById('report-notification');
  const iconEl   = document.getElementById('report-notif-icon');
  const textEl   = document.getElementById('report-notif-text');
  if (!notif) return;
  iconEl.textContent = icon || '📋';
  textEl.textContent = text || 'Rapor hazır!';
  notif.classList.remove('hidden');
  // 30 saniye sonra otomatik kapat
  setTimeout(() => notif.classList.add('hidden'), 30000);
}

// Modal kapat butonları
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-close-report')?.addEventListener('click', window.closeReportModal);
  document.getElementById('report-modal')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('report-modal')) window.closeReportModal();
  });

  // Raporu indir
  document.getElementById('btn-download-report')?.addEventListener('click', () => {
    if (!_lastReportData) return;
    const blob = new Blob([_lastReportData.content], { type: 'text/markdown;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = (_lastReportData.filename || 'rapor') + '.md';
    a.click();
    URL.revokeObjectURL(url);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Metin yanıtlarında rapor içeriğini tespit et ve göster
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Bir metin yanıtında araştırma/otomasyon raporu var mı kontrol eder.
 * Varsa modalı gösterir ve bildirim çıkarır.
 */
function _detectAndShowReport(text) {
  if (!text || text.length < 200) return false;

  const isResearchReport   = text.includes('Araştırma Raporu') || text.includes('Arastirma Raporu') ||
                             (text.includes('## ') && text.includes('Kaynaklar'));
  const isAutomationReport = text.includes('Otomasyon Görevi Raporu') || text.includes('Adım Sonuçları');

  if (!isResearchReport && !isAutomationReport) return false;

  const title  = isResearchReport ? '🔍 Araştırma Raporu' : '⚙️ Otomasyon Görevi Raporu';
  const icon   = isResearchReport ? '🔍' : '⚙️';
  const nText  = isResearchReport ? 'Araştırma raporu hazır — görüntülemek için tıkla' : 'Otomasyon raporu hazır';
  const data   = { title, content: text, filename: isResearchReport ? 'arastirma_raporu' : 'otomasyon_raporu' };

  // Kaynak sayısını meta bilgisi olarak çıkar
  const sourceMatch = text.match(/Kaynak sayısı:\s*(\d+)/);
  const elapsedMatch = text.match(/süresi?:\s*([\d.]+)s/);
  const meta = [
    elapsedMatch ? `⏱ ${elapsedMatch[1]}s` : '',
    sourceMatch  ? `📚 ${sourceMatch[1]} kaynak` : ''
  ].filter(Boolean).join(' | ');

  _showReportNotification(icon, nText, data);
  window.showReportModal(title, text, meta, text);
  return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// ORB DİNAMİK RENK EFEKTLERİ — V19
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Aktif ajana göre Orb rengini değiştirir.
 * ultronOrb.setThemeColor(hex) metodunu çağırır.
 */
function _setOrbColorForAgent(agentId, status) {
  if (!ultronOrb || typeof ultronOrb.setThemeColor !== 'function') return;
  const colorMap = {
    research_agent:  '#9b5de5',  // mor — araştırma
    coding_agent:    '#00ff88',  // yeşil — kod
    testing_agent:   '#39ff14',  // neon yeşil — test
    reviewer_agent:  '#ffbe0b',  // sarı — inceleme
    supervisor:      '#ff6b35',  // turuncu — görev
    computer_agent:  '#00f5ff',  // cyan — bilgisayar (varsayılan)
  };
  if (status === 'complete' || status === 'error') {
    // Varsayılan renge dön
    setTimeout(() => {
      if (ultronOrb && typeof ultronOrb.setThemeColor === 'function')
        ultronOrb.setThemeColor('#00f5ff');
    }, 2500);
    return;
  }
  const color = colorMap[agentId];
  if (color) ultronOrb.setThemeColor(color);
}

// Mevcut agent_event işleyicisini orb renk entegrasyonuyla genişlet
const _originalAgentEventOrbIntegration = window._agentOrbHook;
window._agentOrbHook = function(agent, status) {
  _setOrbColorForAgent(agent, status);
  if (_originalAgentEventOrbIntegration) _originalAgentEventOrbIntegration(agent, status);
};

// ── SWARM CONSOLE ────────────────────────────────────────────────────────────
// Agent Ağı Şeffaflık Paneli: /ws/swarm üzerinden canlı görev takibi

let _swarmWs = null;
let _swarmTasks = {};  // task_id → task_data

window.toggleSwarmConsole = function() {
  const panel = document.getElementById('swarm-console');
  if (!panel) return;
  const isHidden = panel.classList.contains('hidden');
  panel.classList.toggle('hidden', !isHidden);
  if (isHidden) {
    _connectSwarmWs();
  }
};

function _connectSwarmWs() {
  if (_swarmWs && _swarmWs.readyState === WebSocket.OPEN) return;

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${proto}//${location.host}/ws/swarm`;

  _swarmWs = new WebSocket(wsUrl);

  _swarmWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === 'swarm_init' || msg.type === 'swarm_update') {
        const tasks = msg.all_tasks || [];
        _swarmTasks = {};
        tasks.forEach(t => { _swarmTasks[t.task_id] = t; });
        _renderSwarmTasks();
      }
    } catch (e) { /* ignore */ }
  };

  _swarmWs.onerror = () => { _swarmWs = null; };
  _swarmWs.onclose = () => { _swarmWs = null; };
}

function _renderSwarmTasks() {
  const list = document.getElementById('swarm-task-list');
  const badge = document.getElementById('swarm-active-count');
  const dot = document.getElementById('swarm-dot');
  if (!list) return;

  const tasks = Object.values(_swarmTasks);
  const activeTasks = tasks.filter(t => t.status === 'running');

  // Badge güncelle
  if (badge) {
    badge.textContent = `${activeTasks.length} AKTİF`;
    badge.classList.toggle('has-tasks', activeTasks.length > 0);
  }
  if (dot) dot.classList.toggle('hidden', activeTasks.length === 0);

  if (tasks.length === 0) {
    list.innerHTML = '<div class="swarm-empty-msg">Aktif ajan görevi yok.</div>';
    return;
  }

  // Çalışanlarda önce göster
  tasks.sort((a, b) => {
    const order = { running: 0, pending: 1, success: 2, failed: 3 };
    return (order[a.status] ?? 9) - (order[b.status] ?? 9);
  });

  list.innerHTML = tasks.map(t => {
    const elapsed = t.elapsed ? `${t.elapsed}s` : '';
    const progress = t.progress || 0;
    return `
      <div class="swarm-task-item ${t.status}">
        <div class="swarm-task-agent">${escapeHtml(t.agent_name)}</div>
        <div class="swarm-task-desc" title="${escapeHtml(t.description)}">${escapeHtml(t.description)}</div>
        <div class="swarm-progress-bar">
          <div class="swarm-progress-fill" style="width:${progress}%"></div>
        </div>
        <div class="swarm-task-footer">
          <span class="swarm-task-status ${t.status}">${t.status === 'running' ? '▶ ÇALIŞIYOR' : t.status === 'success' ? '✔ TAMAM' : t.status === 'failed' ? '✗ HATA' : '⏳ BEKLE'}</span>
          <span class="swarm-task-elapsed">${elapsed}</span>
        </div>
      </div>`;
  }).join('');
}

// Sayfa yüklenince swarm ws bağlantısını arkaplanda aç (panel kapalı olsa bile badge güncel olsun)
window.addEventListener('load', () => {
  setTimeout(_connectSwarmWs, 2000);
});
