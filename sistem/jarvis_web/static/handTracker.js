import {
  FilesetResolver,
  HandLandmarker
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/vision_bundle.mjs";

const WASM_CDN = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm";
const MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

const WRIST = 0;
const THUMB_TIP = 4;
const INDEX_TIP = 8;
const MIDDLE_MCP = 9;

const PINCH_ON = 0.32;
const PINCH_OFF = 0.45;
const ROTATE_SPEED = 5.0;
const SMOOTHING = 0.4;

export class HandTracker {
  constructor(video, overlay, callbacks) {
    this.video = video;
    this.overlay = overlay;
    this.callbacks = callbacks || {};
    this.landmarker = null;
    this.stream = null;
    this.rafId = 0;
    this.running = false;
    this.lastVideoTime = -1;
    this.handStates = new Map();
    this.prevMode = "idle";
    this.prevSpinGrab = null;
    this.prevZoomDist = null;
    this.lastStatus = { hands: 0, mode: "idle" };
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 640, height: 480, facingMode: "user" },
      audio: false,
    });
    this.video.srcObject = this.stream;
    await this.video.play();

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
      this.landmarker = await HandLandmarker.createFromOptions(fileset, options);
    } catch {
      this.landmarker = await HandLandmarker.createFromOptions(fileset, {
        ...options,
        baseOptions: { ...options.baseOptions, delegate: "CPU" },
      });
    }

    this.running = true;
    this.loop();
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.rafId);
    if (this.landmarker) {
      try { this.landmarker.close(); } catch {}
      this.landmarker = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.video) this.video.srcObject = null;
    this.handStates.clear();
    this.prevMode = "idle";
    this.prevSpinGrab = null;
    this.prevZoomDist = null;
    if (this.overlay) {
      const ctx = this.overlay.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);
    }
    this.emitStatus({ hands: 0, mode: "idle" });
  }

  loop = () => {
    if (!this.running) return;
    this.rafId = requestAnimationFrame(this.loop);

    if (!this.landmarker || this.video.readyState < 2) return;
    if (this.video.currentTime === this.lastVideoTime) return;
    this.lastVideoTime = this.video.currentTime;

    const result = this.landmarker.detectForVideo(this.video, performance.now());
    this.processHands(result.landmarks || [], (result.handedness || []).map((h) => h[0]?.categoryName ?? "?"));
    this.drawOverlay(result.landmarks || []);
  };

  processHands(landmarks, labels) {
    const pinchedGrabs = [];
    const seen = new Set();

    landmarks.forEach((lm, i) => {
      const label = labels[i] || `Hand_${i}`;
      seen.add(label);

      const handScale = dist2d(lm[WRIST], lm[MIDDLE_MCP]);
      if (handScale < 1e-6) return;
      const pinchRatio = dist2d(lm[THUMB_TIP], lm[INDEX_TIP]) / handScale;

      const raw = {
        x: 1 - (lm[THUMB_TIP].x + lm[INDEX_TIP].x) / 2,
        y: (lm[THUMB_TIP].y + lm[INDEX_TIP].y) / 2,
      };

      let state = this.handStates.get(label);
      if (!state) {
        state = { pinching: false, grab: raw };
        this.handStates.set(label, state);
      }

      if (state.pinching && pinchRatio > PINCH_OFF) state.pinching = false;
      else if (!state.pinching && pinchRatio < PINCH_ON) state.pinching = true;

      state.grab = {
        x: state.grab.x + (raw.x - state.grab.x) * SMOOTHING,
        y: state.grab.y + (raw.y - state.grab.y) * SMOOTHING,
      };

      if (state.pinching) pinchedGrabs.push(state.grab);
    });

    for (const key of this.handStates.keys()) {
      if (!seen.has(key)) this.handStates.delete(key);
    }

    const mode = pinchedGrabs.length >= 2 ? "zoom" : pinchedGrabs.length === 1 ? "spin" : "idle";

    if (mode !== this.prevMode) {
      this.prevSpinGrab = null;
      this.prevZoomDist = null;
      this.prevMode = mode;
    }

    if (mode === "spin") {
      const grab = pinchedGrabs[0];
      if (this.prevSpinGrab) {
        const dx = grab.x - this.prevSpinGrab.x;
        const dy = grab.y - this.prevSpinGrab.y;
        if (this.callbacks.onRotate) {
          this.callbacks.onRotate(dx * ROTATE_SPEED, dy * ROTATE_SPEED);
        }
      }
      this.prevSpinGrab = grab;
    } else if (mode === "zoom") {
      const d = dist2d(pinchedGrabs[0], pinchedGrabs[1]);
      if (this.prevZoomDist !== null) {
        const delta = d - this.prevZoomDist;
        if (this.callbacks.onZoom) {
          this.callbacks.onZoom(delta * 2.0);
        }
      }
      this.prevZoomDist = d;
    }

    this.emitStatus({ hands: landmarks.length, mode });
  }

  emitStatus(status) {
    if (status.hands !== this.lastStatus.hands || status.mode !== this.lastStatus.mode) {
      this.lastStatus = status;
      if (this.callbacks.onStatus) this.callbacks.onStatus(status);
    }
  }

  drawOverlay(landmarks) {
    if (!this.overlay) return;
    const ctx = this.overlay.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, this.overlay.width, this.overlay.height);

    const w = this.overlay.width;
    const h = this.overlay.height;

    landmarks.forEach((lm) => {
      ctx.fillStyle = "rgba(255, 68, 34, 0.6)";
      lm.forEach((p) => {
        ctx.beginPath();
        ctx.arc((1 - p.x) * w, p.y * h, 3, 0, Math.PI * 2);
        ctx.fill();
      });

      ctx.fillStyle = "#ffaa00";
      [THUMB_TIP, INDEX_TIP].forEach((idx) => {
        const p = lm[idx];
        ctx.beginPath();
        ctx.arc((1 - p.x) * w, p.y * h, 6, 0, Math.PI * 2);
        ctx.fill();
      });
    });
  }
}

function dist2d(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.sqrt(dx * dx + dy * dy);
}
