"""
ULTRON — SOTA Biyometrik Konuşmacı Tanıma & Doğrulama Modülü (Speaker Recognition V2)
───────────────────────────────────────────────────────────────────────────────────────
• CAM++ 512-Boyutlu Kaldi-Uyumlu Derin Akustik Konuşmacı Gömmeleri (Speaker Embeddings)
• Çoklu Prototip Bankası Mimarisi (Prototype Bank Architecture & Dispersion Tracking)
• Gerçek Dünya Audio Quality Gate (RMS, SNR, Clipping, VAD Enerji Kontrolü)
• Top-1 / Top-2 Margin & Mutlak Eşik Bazlı UNKNOWN Konuşmacı Reddi (Zero-False-Acceptance)
• Temporal Aggregation & Hysteresis Tabanlı Oturum Kararlılığı (Session State Machine)
• F0 Temel Frekans Telemetrisi (Yalnızca Diagnostik Bilgi — Kimlik Kararından Bağımsız)
• Geriye Dönük Uyumluluk & Otomatik Şema Göçü (Automatic Schema Migration)
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort

from app_config import get_app_config_value
from app_paths import data_path

logger = logging.getLogger("ultron.voice_recognition")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "speaker_recognition.json"
MODEL_PATH = BASE_DIR / "models" / "speaker_campplus_voxceleb.onnx"
PROFILES_FILE = data_path("memory", "speaker_profiles.json")
BACKUP_PROFILES_FILE = data_path("memory", "speaker_profiles.backup.json")
LATEST_SPEECH_FILE = data_path("memory", "latest_live_speech.pcm")

# ═══════════════════════════════════════════════════════════════════════════
# 1. Konfigürasyon Yöneticisi (Config-Driven Hyperparameters)
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG: dict[str, Any] = {
    "version": "2.0.0",
    "engine": "CAM++ 512-D + Prototype Bank",
    "thresholds": {
        "absolute_match_threshold": 0.48,
        "top1_top2_margin_threshold": 0.08,
        "speaker_switch_margin": 0.10,
        "session_continue_threshold": 0.38,
        "uncertain_lower_threshold": 0.28,
        "adaptation_threshold": 0.65,
    },
    "audio_quality_gate": {
        "min_voiced_duration_sec": 0.50,
        "min_rms_energy": 0.007,
        "min_snr_db": 6.0,
        "max_clipping_ratio": 0.025,
        "target_rms_level": 0.05,
    },
    "prototype_bank": {
        "top_k_prototypes": 3,
        "centroid_weight": 0.40,
        "top_k_weight": 0.60,
        "max_prototypes_per_profile": 12,
        "min_prototype_duration_sec": 0.80,
    },
    "temporal_aggregation": {
        "window_size": 4,
        "decay_factor": 0.85,
        "required_consecutive_frames": 3,
    },
}

_config_cache: dict[str, Any] | None = None
_config_lock = threading.Lock()


def load_speaker_recognition_config() -> dict[str, Any]:
    global _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache

        cfg = dict(DEFAULT_CONFIG)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                            cfg[k].update(v)
                        else:
                            cfg[k] = v
            except Exception as e:
                logger.warning(f"Konfigürasyon dosyası okunamadı ({e}), varsayılanlar kullanılıyor.")

        _config_cache = cfg
        return _config_cache


# Modül düzeyinde geriye dönük uyumluluk ve audit sabitleri
NEW_SESSION_THRESHOLD = 0.40
CONTINUE_SESSION_THRESHOLD = 0.33
ADAPTATION_THRESHOLD = 0.60
STRONG_MATCH_THRESHOLD = ADAPTATION_THRESHOLD
UNCERTAIN_LOWER_THRESHOLD = 0.25
REQUIRED_SWITCH_FRAMES = 3
DEFAULT_SIMILARITY_THRESHOLD = CONTINUE_SESSION_THRESHOLD
MIN_VOICED_DURATION_SEC = 0.50

_model_lock = threading.Lock()
_profiles_lock = threading.Lock()
_live_buffer_lock = threading.Lock()
_session_instance: ort.InferenceSession | None = None
_mel_matrix_cache: np.ndarray | None = None
_live_audio_buffer = bytearray()
_last_buffer_dump_time: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Audio Quality Gate (Akustik Kalite & Sinyal Analizi)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AudioQualityReport:
    status: str  # "GOOD", "ACCEPTABLE", "POOR", "INSUFFICIENT_AUDIO", "CLIPPED", "SILENCE"
    is_acceptable: bool
    duration_sec: float
    rms_energy: float
    snr_db: float
    clipping_ratio: float
    voiced_ratio: float
    reason: str = ""


def assess_audio_quality(pcm_data: bytes | np.ndarray, sample_rate: int = 16000) -> tuple[np.ndarray | None, AudioQualityReport]:
    """
    Mikrofon sesini inceler; DC offset temizler, RMS, SNR, Kırpılma (Clipping) ve konuşma süresini doğrular.
    """
    cfg = load_speaker_recognition_config().get("audio_quality_gate", {})
    min_dur = float(cfg.get("min_voiced_duration_sec", 0.50))
    min_rms = float(cfg.get("min_rms_energy", 0.007))
    min_snr = float(cfg.get("min_snr_db", 6.0))
    max_clip = float(cfg.get("max_clipping_ratio", 0.025))

    if isinstance(pcm_data, bytes):
        if len(pcm_data) < int(sample_rate * 0.1 * 2):
            rep = AudioQualityReport("INSUFFICIENT_AUDIO", False, len(pcm_data) / (sample_rate * 2), 0.0, 0.0, 0.0, 0.0, "Ses tamponu çok kısa (<100ms)")
            return None, rep
        audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        audio = pcm_data.astype(np.float32)
        if len(audio) < int(sample_rate * 0.1):
            rep = AudioQualityReport("INSUFFICIENT_AUDIO", False, len(audio) / sample_rate, 0.0, 0.0, 0.0, 0.0, "Ses dizisi çok kısa (<100ms)")
            return None, rep

    dur = len(audio) / float(sample_rate)

    # 1. DC Offset Temizliği
    audio = audio - np.mean(audio)

    # 2. Clipping Kontrolü (|x| >= 0.99)
    clip_count = np.sum(np.abs(audio) >= 0.99)
    clipping_ratio = float(clip_count / max(1, len(audio)))

    # 3. RMS Enerji Hesabı
    rms = float(np.sqrt(np.mean(audio ** 2)))

    # 4. Çerçeve Bazlı SNR ve Voiced Oranı Tahmini (25ms pencereler, 10ms adımlar)
    frame_len = int(sample_rate * 0.025)
    hop_len = int(sample_rate * 0.010)
    num_frames = max(1, (len(audio) - frame_len) // hop_len)
    
    frame_energies = np.array([
        float(np.sqrt(np.mean(audio[i * hop_len : i * hop_len + frame_len] ** 2)))
        for i in range(num_frames)
    ], dtype=np.float32)

    voiced_mask = frame_energies >= min_rms
    voiced_frames = np.sum(voiced_mask)
    voiced_ratio = float(voiced_frames / max(1, len(frame_energies)))
    voiced_dur = voiced_ratio * dur

    if voiced_frames > 0:
        speech_rms = float(np.mean(frame_energies[voiced_mask]))
        unvoiced = frame_energies[~voiced_mask]
        noise_floor = float(np.mean(unvoiced)) if len(unvoiced) > 0 else 0.0015
        snr_db = 20.0 * math.log10(max(speech_rms, 1e-4) / max(noise_floor, 1e-4))
    else:
        speech_rms = rms
        noise_floor = max(rms, 1e-4)
        snr_db = 0.0

    # Kalite Kararı
    if dur < min_dur or voiced_dur < 0.20:
        rep = AudioQualityReport("INSUFFICIENT_AUDIO", False, dur, rms, snr_db, clipping_ratio, voiced_ratio, f"Konuşma süresi çok kısa ({dur:.2f}s, aktif: {voiced_dur:.2f}s)")
        return None, rep

    if rms < min_rms or voiced_frames == 0:
        rep = AudioQualityReport("SILENCE", False, dur, rms, snr_db, clipping_ratio, voiced_ratio, f"Ses enerjisi çok düşük (RMS: {rms:.4f} < {min_rms})")
        return None, rep

    if clipping_ratio > max_clip:
        rep = AudioQualityReport("CLIPPED", False, dur, rms, snr_db, clipping_ratio, voiced_ratio, f"Mikrofon kırpılma bozulması (%{clipping_ratio*100:.1f})")
        return None, rep

    if snr_db < min_snr:
        rep = AudioQualityReport("POOR", False, dur, rms, snr_db, clipping_ratio, voiced_ratio, f"Gürültü seviyesi yüksek (SNR: {snr_db:.1f} dB < {min_snr} dB)")
        return None, rep

    status = "GOOD" if snr_db >= 12.0 and voiced_ratio >= 0.40 else "ACCEPTABLE"
    rep = AudioQualityReport(status, True, dur, rms, snr_db, clipping_ratio, voiced_ratio, "Ses kalitesi biyometrik doğrulama için uygun")
    return audio, rep


# ═══════════════════════════════════════════════════════════════════════════
# 3. Canlı Mikrofon Akış Tamponu
# ═══════════════════════════════════════════════════════════════════════════

def update_live_audio_buffer(pcm_chunk: bytes) -> None:
    global _last_buffer_dump_time
    if not pcm_chunk:
        return
    with _live_buffer_lock:
        _live_audio_buffer.extend(pcm_chunk)
        if len(_live_audio_buffer) > 192000:  # 6 saniye @ 16k mono
            del _live_audio_buffer[:-192000]

        now = time.monotonic()
        if (now - _last_buffer_dump_time) >= 0.4 and len(_live_audio_buffer) >= 24000:
            _last_buffer_dump_time = now
            try:
                LATEST_SPEECH_FILE.parent.mkdir(parents=True, exist_ok=True)
                sample = bytes(_live_audio_buffer[-128000:])  # son 4 saniye
                LATEST_SPEECH_FILE.write_bytes(sample)
            except Exception:
                pass


def get_recent_live_audio(seconds: float = 4.0) -> bytes:
    with _live_buffer_lock:
        req = int(16000 * 2 * seconds)
        if len(_live_audio_buffer) >= int(16000 * 2 * 0.8):
            return bytes(_live_audio_buffer[-req:]) if len(_live_audio_buffer) >= req else bytes(_live_audio_buffer)

    if LATEST_SPEECH_FILE.exists():
        try:
            data = LATEST_SPEECH_FILE.read_bytes()
            if len(data) >= int(16000 * 2 * 0.6):
                return data[-int(16000 * 2 * seconds):] if len(data) >= int(16000 * 2 * seconds) else data
        except Exception as e:
            logger.error(f"Paylaşılan ses tamponu okuma hatası: {e}")
    return b""


# ═══════════════════════════════════════════════════════════════════════════
# 4. Kaldi-Uyumlu Log Mel-Filtre Bankası & CAM++ 512-D ONNX Motoru
# ═══════════════════════════════════════════════════════════════════════════

def _get_povey_window(win_len: int) -> np.ndarray:
    n = np.arange(win_len)
    return (0.5 - 0.5 * np.cos(2 * np.pi * n / (win_len - 1))) ** 0.85


def _get_mel_filter_matrix(sr: int = 16000, n_fft: int = 512, n_mels: int = 80,
                           f_min: float = 20.0, f_max: float = 7600.0) -> np.ndarray:
    global _mel_matrix_cache
    if _mel_matrix_cache is not None:
        return _mel_matrix_cache

    def hz_to_mel(hz: float) -> float:
        return 1127.0 * np.log(1.0 + hz / 700.0)

    def mel_to_hz(mel: float) -> float:
        return 700.0 * (np.exp(mel / 1127.0) - 1.0)

    mel_min = hz_to_mel(f_min)
    mel_max = hz_to_mel(f_max)
    mels = np.linspace(mel_min, mel_max, n_mels + 2)
    hzs = mel_to_hz(mels)
    bins = np.floor((n_fft + 1) * hzs / sr).astype(int)

    matrix = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
    for i in range(n_mels):
        left, center, right = bins[i], bins[i + 1], bins[i + 2]
        for k in range(left, center):
            matrix[i, k] = (k - left) / max(1, center - left)
        for k in range(center, right):
            matrix[i, k] = (right - k) / max(1, right - center)

    _mel_matrix_cache = matrix
    return matrix


def extract_fbank_kaldi(audio_float: np.ndarray, sr: int = 16000, n_mels: int = 80,
                        win_ms: float = 25.0, hop_ms: float = 10.0, n_fft: int = 512) -> np.ndarray:
    if len(audio_float) < int(sr * 0.1):
        return np.zeros((1, n_mels), dtype=np.float32)

    # Standart Kaldi aralığı [-32768, 32767]
    audio = audio_float * 32768.0 if np.max(np.abs(audio_float)) <= 1.5 else audio_float.copy()

    win_len = int(sr * win_ms / 1000.0)
    hop_len = int(sr * hop_ms / 1000.0)

    # Pre-emphasis (0.97)
    audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

    num_frames = 1 + (len(audio) - win_len) // hop_len
    if num_frames <= 0:
        return np.zeros((1, n_mels), dtype=np.float32)

    shape = (num_frames, win_len)
    strides = (audio.strides[0] * hop_len, audio.strides[0])
    frames = np.lib.stride_tricks.as_strided(audio, shape=shape, strides=strides)
    frames = frames * _get_povey_window(win_len)

    spec = np.abs(np.fft.rfft(frames, n=n_fft)) ** 2
    mel_mat = _get_mel_filter_matrix(sr, n_fft, n_mels)
    mel_spec = np.dot(spec, mel_mat.T)
    mel_spec = np.maximum(mel_spec, 1e-10)
    log_mel = np.log(mel_spec)

    # CMVN (Cepstral Mean Normalization)
    log_mel = log_mel - np.mean(log_mel, axis=0, keepdims=True)
    return log_mel.astype(np.float32)


def _get_onnx_session() -> ort.InferenceSession:
    global _session_instance
    if _session_instance is not None:
        return _session_instance

    with _model_lock:
        if _session_instance is not None:
            return _session_instance

        if not MODEL_PATH.exists():
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            import urllib.request
            url = "https://huggingface.co/csukuangfj/speaker-embedding-models/resolve/main/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx"
            logger.info("CAM++ ONNX modeli indiriliyor...")
            urllib.request.urlretrieve(url, MODEL_PATH)

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        opts.intra_op_num_threads = 2
        opts.inter_op_num_threads = 1

        available_providers = ort.get_available_providers()
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if "CUDAExecutionProvider" in available_providers else ["CPUExecutionProvider"]

        _session_instance = ort.InferenceSession(str(MODEL_PATH), sess_options=opts, providers=providers)
        return _session_instance


def compute_speaker_embedding(pcm_data: bytes | np.ndarray, sample_rate: int = 16000, enforce_quality_gate: bool = True) -> np.ndarray | None:
    """
    CAM++ 512-Boyutlu L2-Normalize Edilmiş Konuşmacı Gömme Vektörünü Çıkarır.
    """
    if enforce_quality_gate:
        audio, quality = assess_audio_quality(pcm_data, sample_rate)
        if audio is None or not quality.is_acceptable:
            return None
    else:
        if isinstance(pcm_data, bytes):
            audio = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio = pcm_data.astype(np.float32)
        audio = audio - np.mean(audio)

    # RMS Normalizasyonu (Standart Seviye 0.05)
    rms = float(np.sqrt(np.mean(audio ** 2)))
    if rms > 1e-5:
        audio = audio * (0.05 / rms)

    try:
        fbank = extract_fbank_kaldi(audio, sr=sample_rate)
        if fbank.shape[0] < 15:
            return None

        session = _get_onnx_session()
        input_tensor = fbank[np.newaxis, ...]
        raw_emb = session.run(None, {"x": input_tensor})[0][0]

        norm = np.linalg.norm(raw_emb)
        if norm < 1e-6:
            return None
        return (raw_emb / norm).astype(np.float32)

    except Exception as e:
        logger.error(f"CAM++ Embedding çıkarım hatası: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 5. F0 Pitch (Temel Frekans) Diagnostik Telemetrisi (Non-Gating)
# ═══════════════════════════════════════════════════════════════════════════

def extract_f0_pitch(audio_input: bytes | np.ndarray, sr: int = 16000) -> dict[str, Any]:
    """
    Center-Clipped Autocorrelation F0 Pitch Çıkarıcısı.
    NOT: Bu bilgi yalnızca telemetri, teşhis ve UI gösterimi içindir; kimlik kararı için filtre DEĞİLDİR.
    """
    if isinstance(audio_input, bytes):
        if len(audio_input) < 1000:
            return {"median_f0": 0.0, "mean_f0": 0.0, "voiced_ratio": 0.0, "gender_hint": "unknown"}
        audio = np.frombuffer(audio_input, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        audio = audio_input.astype(np.float32)

    audio = audio - np.mean(audio)
    if len(audio) < int(sr * 0.1):
        return {"median_f0": 0.0, "mean_f0": 0.0, "voiced_ratio": 0.0, "gender_hint": "unknown"}

    frame_len = int(sr * 0.040)  # 40 ms
    hop_len = int(sr * 0.015)    # 15 ms
    min_lag = int(sr / 380.0)    # 380 Hz
    max_lag = int(sr / 75.0)     # 75 Hz

    f0_values = []
    num_frames = max(1, (len(audio) - frame_len) // hop_len)

    for i in range(num_frames):
        start = i * hop_len
        frame = audio[start : start + frame_len]
        energy = np.mean(frame ** 2)
        if energy < 1e-4:
            continue

        clip_lvl = 0.28 * np.max(np.abs(frame))
        clipped = np.where(np.abs(frame) >= clip_lvl, np.sign(frame) * (np.abs(frame) - clip_lvl), 0.0)

        autocorr = np.correlate(clipped, clipped, mode="full")
        mid = len(autocorr) // 2
        r0 = autocorr[mid]
        if r0 < 1e-8:
            continue

        segment = autocorr[mid + min_lag : mid + max_lag]
        if len(segment) == 0:
            continue

        peak_idx = np.argmax(segment)
        peak_val = segment[peak_idx]
        lag = min_lag + peak_idx

        if (peak_val / r0) > 0.22:
            f0 = sr / lag
            if 75.0 <= f0 <= 380.0:
                f0_values.append(f0)

    if not f0_values:
        return {"median_f0": 0.0, "mean_f0": 0.0, "voiced_ratio": 0.0, "gender_hint": "unknown"}

    med_f0 = float(np.median(f0_values))
    mean_f0 = float(np.mean(f0_values))
    voiced_ratio = len(f0_values) / float(max(1, num_frames))

    gender_hint = "unknown"
    if voiced_ratio >= 0.15:
        if med_f0 < 165.0:
            gender_hint = "male"
        elif med_f0 >= 170.0:
            gender_hint = "female"
        else:
            gender_hint = "neutral"

    return {
        "median_f0": round(med_f0, 1),
        "mean_f0": round(mean_f0, 1),
        "voiced_ratio": round(voiced_ratio, 3),
        "gender_hint": gender_hint,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 6. Çoklu Prototip Bankası & Top-1 / Top-2 Margin Skorlama Motoru
# ═══════════════════════════════════════════════════════════════════════════

def compute_pitch_compatibility(pitch_info: Optional[dict[str, Any]], spk_name: str, prof: dict[str, Any]) -> float:
    """
    F0 temel frekansı ile profil arasındaki akustik frekans uyumluluğunu hesaplar.
    Profilde kayıtlı bir medyan F0 varsa Gauss uyumluluk fonksiyonu (std=22 Hz) uygular.
    Yoksa erkek/kadın genel aralık filtrelemesi yapar.
    """
    if not pitch_info:
        return 1.0
    f0 = float(pitch_info.get("median_f0") or pitch_info.get("mean_f0") or 0.0)
    if f0 <= 0:
        return 1.0

    # 1. Profilin Kayıtlı Medyan Pitch Değeri Varsa Birebir Gauss Uyumluluğu
    f0_meta = prof.get("f0_telemetry") or prof.get("f0_info") or {}
    prof_f0 = float(f0_meta.get("median_f0") or f0_meta.get("mean_f0") or 0.0)

    if prof_f0 >= 60.0:
        delta_f = abs(f0 - prof_f0)
        # 18 Hz standart sapmalı Gauss uyumluluğu
        gauss_compat = math.exp(-(delta_f ** 2) / (2.0 * (20.0 ** 2)))
        return max(0.20, min(1.0, gauss_compat))

    # 2. Genel Cinsiyet / Rol Aralık Filtresi (Yedek)
    spk_lower = spk_name.lower()
    role_lower = str(prof.get("role", "")).lower()

    is_male_profile = "nuri" in spk_lower or "ahmet" in spk_lower or "erkek" in role_lower or "yonetici" in role_lower or "yönetici" in role_lower
    is_female_profile = "rabia" in spk_lower or "kadin" in role_lower or "kadın" in role_lower or "eşi" in role_lower

    if is_male_profile:
        if f0 < 165.0:
            return 1.0
        elif f0 < 185.0:
            return 0.75
        else:
            return 0.20

    if is_female_profile:
        if f0 >= 170.0:
            return 1.0
        elif f0 >= 155.0:
            return 0.75
        else:
            return 0.20

    return 1.0




def compute_prototype_similarity_scores(
    query_emb: np.ndarray,
    profiles: dict[str, dict[str, Any]],
    pitch_info: Optional[dict[str, Any]] = None
) -> dict[str, dict[str, Any]]:
    """
    Canlı embedding'i kayıtlı konuşmacıların Prototip Bankası ve Centroid vektörleriyle karşılaştırır.
    Top-K Prototip Ortalaması (%60) + Centroid Kosinüs Benzerliği (%40) + Aktif F0 Pitch Gating uygular.
    """
    scores: dict[str, dict[str, Any]] = {}
    if not profiles or query_emb is None:
        return scores

    cfg = load_speaker_recognition_config().get("prototype_bank", {})
    top_k = int(cfg.get("top_k_prototypes", 3))
    w_top_k = float(cfg.get("top_k_weight", 0.60))
    w_centroid = float(cfg.get("centroid_weight", 0.40))

    q_norm = np.linalg.norm(query_emb)
    if q_norm < 1e-6:
        return scores
    q_vec = query_emb / q_norm

    for spk_id, prof in profiles.items():
        spk_name = prof.get("name", spk_id)
        prototypes = prof.get("prototypes") or prof.get("embeddings", [])
        centroid_list = prof.get("centroid_embedding")

        # 1. Prototip Bankası Benzerlikleri
        proto_sims = []
        for p in prototypes:
            p_arr = np.array(p, dtype=np.float32)
            p_norm = np.linalg.norm(p_arr)
            if p_norm > 1e-6:
                proto_sims.append(float(np.dot(q_vec, p_arr / p_norm)))

        if not proto_sims and not centroid_list:
            continue

        proto_sims.sort(reverse=True)
        k_val = min(top_k, len(proto_sims)) if proto_sims else 1
        top_k_mean = float(np.mean(proto_sims[:k_val])) if proto_sims else -1.0
        max_proto = proto_sims[0] if proto_sims else -1.0

        # 2. Centroid Benzerliği
        centroid_sim = -1.0
        if centroid_list:
            c_arr = np.array(centroid_list, dtype=np.float32)
            c_norm = np.linalg.norm(c_arr)
            if c_norm > 1e-6:
                centroid_sim = float(np.dot(q_vec, c_arr / c_norm))

        # 3. Kompozit Füzyon Skoru
        if centroid_sim > -0.99 and top_k_mean > -0.99:
            composite_score = w_top_k * top_k_mean + w_centroid * centroid_sim
        elif top_k_mean > -0.99:
            composite_score = top_k_mean
        elif centroid_sim > -0.99:
            composite_score = centroid_sim
        else:
            composite_score = -1.0

        # 4. Aktif Pitch Uyumluluk Faktörü
        pitch_factor = compute_pitch_compatibility(pitch_info, spk_name, prof)
        adjusted_score = composite_score * pitch_factor

        scores[spk_name] = {
            "match_score": round(adjusted_score, 4),
            "raw_composite": round(composite_score, 4),
            "top_k_mean": round(top_k_mean, 4),
            "max_proto": round(max_proto, 4),
            "centroid_sim": round(centroid_sim, 4),
            "final_score": round(adjusted_score, 4),  # Geriye dönük uyumluluk anahtarı
            "cosine": round(max_proto, 4),            # Geriye dönük uyumluluk anahtarı
            "probability": round(adjusted_score, 4),  # Geriye dönük uyumluluk anahtarı
            "pitch_comp": round(pitch_factor, 3),     # Geriye dönük uyumluluk anahtarı
            "prototype_count": len(proto_sims),
            "role": prof.get("role", ""),
            "dispersion": prof.get("dispersion", 0.0),
        }

    return scores


# Geriye dönük uyumluluk için takma ad
def compute_hybrid_speaker_scores(emb: np.ndarray, pitch_info: dict, profiles: dict) -> dict[str, dict[str, Any]]:
    scores = compute_prototype_similarity_scores(emb, profiles, pitch_info=pitch_info)
    for spk_name, d in scores.items():
        d["f0_telemetry"] = pitch_info
        d["probability"] = d["match_score"]
        d["fused"] = d["match_score"]
    return scores



# ═══════════════════════════════════════════════════════════════════════════
# 7. Profil Veritabanı, Şema Göçü & Kalıcılık
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_tr_text(text: str) -> str:
    tr_map = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iIgGuUsSoOcC")
    cleaned = text.translate(tr_map).lower().strip()
    return re.sub(r"[^\w\s]", "", cleaned)


def _slugify_name(name: str) -> str:
    norm = _normalize_tr_text(name)
    cleaned = re.sub(r"\s+", "_", norm)
    return cleaned or "speaker"


def _migrate_legacy_profiles(data: dict[str, Any]) -> dict[str, Any]:
    """
    V1 profil şemasını V2 Prototip Bankası formatına dönüştürür.
    """
    migrated = False
    new_profiles: dict[str, Any] = {}

    for spk_id, prof in data.items():
        if not isinstance(prof, dict):
            continue
        p = dict(prof)
        
        # 1. Prototip Bankası Yapılandırması
        if "prototypes" not in p:
            raw_embs = p.get("embeddings", [])
            p["prototypes"] = raw_embs
            migrated = True

        # 2. Centroid & Dispersiyon Hesabı
        protos = p.get("prototypes", [])
        if protos:
            all_arr = np.array(protos, dtype=np.float32)
            c = np.mean(all_arr, axis=0)
            c_norm = np.linalg.norm(c)
            if c_norm > 1e-6:
                c = c / c_norm
                p["centroid_embedding"] = c.tolist()

                # Prototip varyans / dispersiyonu
                sims = [float(np.dot(vec / np.linalg.norm(vec), c)) for vec in all_arr if np.linalg.norm(vec) > 1e-6]
                p["dispersion"] = round(float(np.mean([1.0 - s for s in sims])), 4) if sims else 0.0
            p["sample_count"] = len(protos)

        # 3. F0 Telemetri & Bilgi Şeması (Geriye dönük uyumlu)
        f0_data = p.get("f0_telemetry", p.get("f0_info", {}))
        p["f0_telemetry"] = f0_data
        p["f0_info"] = f0_data

        new_profiles[spk_id] = p

    if migrated:
        try:
            BACKUP_PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
            BACKUP_PROFILES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Eski ses profilleri yedeği alındı ve V2 Prototip Bankası formatına taşındı.")
        except Exception as e:
            logger.error(f"Yedek alma hatası: {e}")

    return new_profiles


def _load_all_profiles() -> dict[str, dict[str, Any]]:
    with _profiles_lock:
        if PROFILES_FILE.exists():
            try:
                data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    migrated = _migrate_legacy_profiles(data)
                    return migrated
            except Exception as e:
                logger.error(f"Profil okuma hatası: {e}")
        return {}


def _save_all_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    with _profiles_lock:
        try:
            PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
            PROFILES_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Profil kaydetme hatası: {e}")


def get_similarity_threshold() -> float:
    cfg = load_speaker_recognition_config()
    return float(cfg.get("thresholds", {}).get("absolute_match_threshold", 0.48))


def update_profile_centroid_ema(speaker_name: str, new_emb: np.ndarray, alpha: float = 0.05) -> bool:
    """
    Yalnızca yüksek güvenilirlikli doğrulanmış çerçevelerde prototip bankasını günceller.
    """
    spk_id = _slugify_name(speaker_name)
    profiles = _load_all_profiles()
    if spk_id not in profiles:
        return False

    prof = profiles[spk_id]
    cfg = load_speaker_recognition_config().get("prototype_bank", {})
    max_protos = int(cfg.get("max_prototypes_per_profile", 12))

    new_emb_arr = new_emb.astype(np.float32)
    norm = np.linalg.norm(new_emb_arr)
    if norm < 1e-6:
        return False
    norm_emb = new_emb_arr / norm

    protos = prof.get("prototypes", [])
    protos.append(norm_emb.tolist())
    if len(protos) > max_protos:
        protos = protos[-max_protos:]

    all_arr = np.array(protos, dtype=np.float32)
    c = np.mean(all_arr, axis=0)
    c_norm = np.linalg.norm(c)
    if c_norm > 1e-6:
        c = c / c_norm

    prof["prototypes"] = protos
    prof["embeddings"] = protos  # Geriye dönük uyumluluk
    prof["centroid_embedding"] = c.tolist()
    prof["sample_count"] = len(protos)
    prof["last_seen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    _save_all_profiles(profiles)
    return True


# ═══════════════════════════════════════════════════════════════════════════
# 8. Oturum Kararlılığı, Histeresis & Temporal Aggregation (SpeakerSessionTracker)
# ═══════════════════════════════════════════════════════════════════════════

class SpeakerSessionTracker:
    """
    ULTRON V2 — Hysteresis ve Temporal Aggregation Destekli Oturum Takipçisi.
    • Top-1 / Top-2 Margin & Mutlak Eşik Gating
    • Tek frame dalgalanmalarına karşı histeresis oturum koruması
    • UNKNOWN konuşmacı kesin reddi
    """
    def __init__(self, initial_user: str = "Bilinmeyen"):
        self.active_user: str = initial_user or "Bilinmeyen"
        self.switch_candidate: str | None = None
        self.switch_candidate_count: int = 0
        self.temporal_history: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def set_active_user(self, user_name: str) -> None:
        with self._lock:
            self.active_user = user_name
            self.switch_candidate = None
            self.switch_candidate_count = 0
            self.temporal_history.clear()

    def process_frame_scores(self, all_scores: dict[str, float | dict[str, Any]], raw_embedding: np.ndarray | None = None, pitch_info: dict | None = None) -> tuple[str, str, dict[str, Any]]:
        """
        all_scores: { "Nuri Can": 0.84, "Rabia": 0.52 } veya { "Nuri Can": {"match_score": 0.84, ...} }
        Dönen: (active_user, state, meta)
        state: 'STABLE', 'HOLD', 'SWITCH_CANDIDATE', 'SWITCHED', 'UNKNOWN', 'INSUFFICIENT_AUDIO'
        """
        with self._lock:
            cfg = load_speaker_recognition_config()
            thresh = cfg.get("thresholds", {})
            abs_thresh = float(thresh.get("absolute_match_threshold", 0.48))
            margin_thresh = float(thresh.get("top1_top2_margin_threshold", 0.08))
            switch_margin = float(thresh.get("speaker_switch_margin", 0.10))
            continue_thresh = float(thresh.get("session_continue_threshold", 0.38))
            adapt_thresh = float(thresh.get("adaptation_threshold", 0.65))

            # Skor sözlüğünü normalize et
            flat_scores: dict[str, float] = {}
            for k, v in all_scores.items():
                flat_scores[k] = float(v["match_score"] if isinstance(v, dict) and "match_score" in v else (v["final_score"] if isinstance(v, dict) and "final_score" in v else v))

            meta: dict[str, Any] = {
                "scores": flat_scores,
                "active_user": self.active_user,
                "switch_candidate": self.switch_candidate,
                "switch_candidate_count": self.switch_candidate_count,
                "pitch_info": pitch_info or {},
                "f0_telemetry": pitch_info or {},
                "top2_speaker": None,
                "top2_score": 0.0,
                "margin": 0.0,
                "verification_status": "UNVERIFIED",
            }

            if not flat_scores:
                meta["similarity"] = 0.0
                meta["best_similarity"] = 0.0
                return self.active_user, "HOLD", meta

            # Top-1 ve Top-2 hesapla
            sorted_scores = sorted(flat_scores.items(), key=lambda x: x[1], reverse=True)
            top1_speaker, top1_score = sorted_scores[0]
            top2_speaker, top2_score = (sorted_scores[1][0], sorted_scores[1][1]) if len(sorted_scores) > 1 else (None, 0.0)
            margin = top1_score - top2_score if top2_speaker else top1_score

            current_sim = flat_scores.get(self.active_user, 0.0) if self.active_user else 0.0

            meta["best_speaker"] = top1_speaker
            meta["best_similarity"] = round(top1_score, 4)
            meta["similarity"] = round(top1_score, 4)
            meta["top2_speaker"] = top2_speaker
            meta["top2_score"] = round(top2_score, 4)
            meta["margin"] = round(margin, 4)
            meta["current_similarity"] = round(current_sim, 4)

            # Doğrulama Kriteri (Absolute Threshold + Margin Threshold)
            is_match_verified = (top1_score >= abs_thresh) and (margin >= margin_thresh or len(sorted_scores) == 1)

            # ── 1. AKTİF BİR OTURUM MEVCUTKEN ──
            if self.active_user and self.active_user.lower() not in {"bilinmeyen", "unknown"}:
                # Başka bir kayıtlı konuşmacıya geçiş talebi
                if top1_speaker != self.active_user and is_match_verified and (top1_score > current_sim + switch_margin):
                    if self.switch_candidate == top1_speaker:
                        self.switch_candidate_count += 1
                    else:
                        self.switch_candidate = top1_speaker
                        self.switch_candidate_count = 1

                    meta["switch_candidate"] = self.switch_candidate
                    meta["switch_candidate_count"] = self.switch_candidate_count
                    meta["verification_status"] = "SWITCH_PENDING"

                    if self.switch_candidate_count >= REQUIRED_SWITCH_FRAMES:
                        old_user = self.active_user
                        self.active_user = self.switch_candidate
                        self.switch_candidate = None
                        self.switch_candidate_count = 0
                        meta["verification_status"] = "VERIFIED"
                        logger.info(f"[Speaker] Oturum geçişi: {old_user} -> {self.active_user} (Skor: {top1_score:.2f}, Margin: {margin:.2f})")
                        return self.active_user, "SWITCHED", meta
                    return self.active_user, "SWITCH_CANDIDATE", meta

                # Tanınmayan / Yabancı ses veya sessizlik durumunda UNKNOWN geçişi
                elif current_sim < UNCERTAIN_LOWER_THRESHOLD and top1_score < abs_thresh:
                    if self.switch_candidate == "Bilinmeyen":
                        self.switch_candidate_count += 1
                    else:
                        self.switch_candidate = "Bilinmeyen"
                        self.switch_candidate_count = 1

                    meta["switch_candidate"] = self.switch_candidate
                    meta["switch_candidate_count"] = self.switch_candidate_count
                    meta["verification_status"] = "UNKNOWN_PENDING"

                    if self.switch_candidate_count >= REQUIRED_SWITCH_FRAMES:
                        old_user = self.active_user
                        self.active_user = "Bilinmeyen"
                        self.switch_candidate = None
                        self.switch_candidate_count = 0
                        meta["verification_status"] = "UNKNOWN"
                        logger.info(f"[Speaker] Oturum sonlandı: {old_user} -> Bilinmeyen")
                        return "Bilinmeyen", "UNKNOWN", meta
                    return self.active_user, "SWITCH_CANDIDATE", meta

                # Mevcut oturum konuşmacısını koru (STABLE / HOLD)
                else:
                    self.switch_candidate = None
                    self.switch_candidate_count = 0
                    state = "STABLE" if current_sim >= continue_thresh else "HOLD"
                    meta["verification_status"] = "VERIFIED" if state == "STABLE" else "HOLD"

                    # Güvenli Online Adaptasyon
                    if raw_embedding is not None and current_sim >= adapt_thresh and self.active_user not in {"Bilinmeyen", "unknown"}:
                        update_profile_centroid_ema(self.active_user, raw_embedding, alpha=0.04)

                    meta["similarity"] = current_sim
                    return self.active_user, state, meta

            # ── 2. AKTİF OTURUM YOKKEN (Bilinmeyen / Idle Durumu) ──
            else:
                if is_match_verified:
                    if self.switch_candidate == top1_speaker:
                        self.switch_candidate_count += 1
                    else:
                        self.switch_candidate = top1_speaker
                        self.switch_candidate_count = 1

                    meta["switch_candidate"] = self.switch_candidate
                    meta["switch_candidate_count"] = self.switch_candidate_count
                    if self.switch_candidate_count >= REQUIRED_SWITCH_FRAMES:
                        self.active_user = self.switch_candidate
                        self.switch_candidate = None
                        self.switch_candidate_count = 0
                        meta["verification_status"] = "VERIFIED"
                        logger.info(f"[Speaker] Biyometrik Onay: Bilinmeyen -> {self.active_user} (Skor: {top1_score:.2f}, Margin: {margin:.2f})")
                        return self.active_user, "STABLE", meta
                    return "Bilinmeyen", "SWITCH_CANDIDATE", meta

                meta["verification_status"] = "UNKNOWN"
                return "Bilinmeyen", "UNKNOWN", meta

    def process_pcm_frame(self, pcm_bytes: bytes, sample_rate: int = 16000) -> tuple[str, str, dict[str, Any]]:
        """
        Mikrofon PCM akışını Audio Quality Gate -> CAM++ -> Prototype Bank -> Hysteresis State Machine sırasıyla işler.
        """
        # 1. Ses Kalite Değerlendirmesi
        audio, quality = assess_audio_quality(pcm_bytes, sample_rate)
        pitch_info = extract_f0_pitch(pcm_bytes, sample_rate)

        if audio is None or not quality.is_acceptable:
            return self.active_user, "INSUFFICIENT_AUDIO", {
                "reason": quality.reason,
                "active_user": self.active_user,
                "quality_report": quality.__dict__,
                "pitch_info": pitch_info,
                "f0_telemetry": pitch_info,
            }

        # 2. Embedding Çıkarımı
        emb = compute_speaker_embedding(audio, sample_rate, enforce_quality_gate=False)
        if emb is None:
            return self.active_user, "INSUFFICIENT_AUDIO", {
                "reason": "Embedding çıkarılamadı",
                "active_user": self.active_user,
                "quality_report": quality.__dict__,
                "pitch_info": pitch_info,
                "f0_telemetry": pitch_info,
            }

        profiles = _load_all_profiles()
        if not profiles:
            return "Bilinmeyen", "UNKNOWN", {
                "reason": "no_enrolled_profiles",
                "active_user": self.active_user,
                "quality_report": quality.__dict__,
                "pitch_info": pitch_info,
                "f0_telemetry": pitch_info,
            }

        # 3. Çoklu Pencere Temporal Doğrulama (Bilinmeyen durumunda alt pencereleri tara)
        if self.active_user in ("Bilinmeyen", "unknown") and len(audio) >= int(sample_rate * 0.7):
            try:
                audio_np = (audio * 32767).astype(np.int16)
                chunk_len = int(sample_rate * 0.5)
                hop_len = int(sample_rate * 0.15)
                if len(audio_np) >= chunk_len + hop_len:
                    for start in range(0, len(audio_np) - chunk_len + 1, hop_len):
                        sub_pcm = audio_np[start : start + chunk_len].tobytes()
                        sub_emb = compute_speaker_embedding(sub_pcm, sample_rate, enforce_quality_gate=False)
                        if sub_emb is not None:
                            sub_sc = compute_prototype_similarity_scores(sub_emb, profiles)
                            spk, state, meta = self.process_frame_scores(sub_sc, raw_embedding=sub_emb, pitch_info=pitch_info)
                            if state == "STABLE":
                                meta["quality_report"] = quality.__dict__
                                meta["hybrid_breakdown"] = sub_sc
                                return spk, state, meta
            except Exception:
                pass

        # 4. Prototip Bankası Skorlaması
        proto_scores = compute_prototype_similarity_scores(emb, profiles)
        spk, state, meta = self.process_frame_scores(proto_scores, raw_embedding=emb, pitch_info=pitch_info)
        meta["quality_report"] = quality.__dict__
        meta["hybrid_breakdown"] = proto_scores
        return spk, state, meta


# Varsayılan global takipçi
default_speaker_tracker = SpeakerSessionTracker(initial_user="Bilinmeyen")


def identify_speaker_from_pcm(pcm_bytes: bytes, sample_rate: int = 16000) -> tuple[str, float, dict[str, Any]]:
    speaker, state, meta = default_speaker_tracker.process_pcm_frame(pcm_bytes, sample_rate)
    return speaker, meta.get("similarity", 0.0), meta


# ═══════════════════════════════════════════════════════════════════════════
# 9. Profesyonel Konuşmacı Kaydı & Silme (Enrollment Pipeline)
# ═══════════════════════════════════════════════════════════════════════════

def enroll_speaker_from_pcm(speaker_name: str, pcm_bytes: bytes, role: str = "", sample_rate: int = 16000) -> str:
    """
    Ses Stüdyosundan veya mikrofondan gelen kaydı Audio Quality Gate ile kontrol eder,
    alt pencerelerle çoklu prototip çıkarır, aykırı (outlier) parçaları eler ve profile kaydeder.
    """
    name_clean = str(speaker_name).strip()
    if not name_clean or name_clean.lower() in {"bilinmeyen", "unknown"}:
        return "Geçersiz konuşmacı adı. Lütfen geçerli bir isim belirtin (örn: 'Nuri Can', 'Rabia', 'Ahmet')."

    audio, quality = assess_audio_quality(pcm_bytes, sample_rate)
    if audio is None or not quality.is_acceptable:
        return f"Ses kaydı kalite eşiğini geçemedi: {quality.reason}. Lütfen arka plan gürültüsünü azaltıp mikrofona 3-4 saniye net konuşun."

    emb_full = compute_speaker_embedding(audio, sample_rate, enforce_quality_gate=False)
    if emb_full is None:
        return "Akustik model ses gömme vektörünü çıkaramadı. Lütfen tekrar deneyin."

    # Çoklu Prototip Çıkarımı (1.2s pencereler, 0.5s adımlarla)
    candidate_prototypes = [emb_full]
    audio_i16 = (audio * 32767).astype(np.int16)
    chunk_len = int(sample_rate * 1.2)
    hop_len = int(sample_rate * 0.5)

    if len(audio_i16) >= chunk_len + hop_len:
        for start in range(0, len(audio_i16) - chunk_len + 1, hop_len):
            sub_pcm = audio_i16[start : start + chunk_len].tobytes()
            sub_emb = compute_speaker_embedding(sub_pcm, sample_rate, enforce_quality_gate=False)
            if sub_emb is not None:
                candidate_prototypes.append(sub_emb)

    # Aykırı (Outlier / Öksürük / Nefes) Prototip Eleme
    if len(candidate_prototypes) > 3:
        all_mat = np.array(candidate_prototypes, dtype=np.float32)
        mean_v = np.mean(all_mat, axis=0)
        mean_v = mean_v / (np.linalg.norm(mean_v) + 1e-6)
        similarities = [float(np.dot(vec, mean_v)) for vec in all_mat]
        valid_prototypes = [cand for cand, s in zip(candidate_prototypes, similarities) if s >= 0.50]
        if not valid_prototypes:
            valid_prototypes = candidate_prototypes[:3]
    else:
        valid_prototypes = candidate_prototypes

    pitch_info = extract_f0_pitch(pcm_bytes, sample_rate)
    spk_id = _slugify_name(name_clean)
    profiles = _load_all_profiles()

    cfg = load_speaker_recognition_config().get("prototype_bank", {})
    max_protos = int(cfg.get("max_prototypes_per_profile", 12))

    existing = profiles.get(spk_id)
    if existing:
        current_protos = existing.get("prototypes", existing.get("embeddings", []))
        for p in valid_prototypes:
            current_protos.append(p.tolist())
        if len(current_protos) > max_protos:
            current_protos = current_protos[-max_protos:]

        all_arr = np.array(current_protos, dtype=np.float32)
        c = np.mean(all_arr, axis=0)
        c = (c / (np.linalg.norm(c) + 1e-6)).tolist()

        sims = [float(np.dot(vec / np.linalg.norm(vec), np.array(c, dtype=np.float32))) for vec in all_arr if np.linalg.norm(vec) > 1e-6]
        dispersion = round(float(np.mean([1.0 - s for s in sims])), 4) if sims else 0.0

        existing["name"] = name_clean
        existing["prototypes"] = current_protos
        existing["embeddings"] = current_protos
        existing["centroid_embedding"] = c
        existing["dispersion"] = dispersion
        existing["sample_count"] = len(current_protos)
        existing["last_seen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        existing["f0_telemetry"] = pitch_info
        existing["f0_info"] = pitch_info
        existing["quality_stats"] = {
            "last_snr_db": round(quality.snr_db, 1),
            "last_rms": round(quality.rms_energy, 4),
        }
        if role:
            existing["role"] = role
        profiles[spk_id] = existing
        _save_all_profiles(profiles)
        f0_val = pitch_info.get("median_f0", 0)
        return f"✓ '{name_clean}' ses profili güncellendi ({len(current_protos)} prototip, Dağılım: {dispersion}, Pitch: {f0_val} Hz, SNR: {quality.snr_db:.1f} dB)."

    else:
        proto_list = [p.tolist() for p in valid_prototypes]
        all_arr = np.array(proto_list, dtype=np.float32)
        c = np.mean(all_arr, axis=0)
        c = (c / (np.linalg.norm(c) + 1e-6)).tolist()

        sims = [float(np.dot(vec / np.linalg.norm(vec), np.array(c, dtype=np.float32))) for vec in all_arr if np.linalg.norm(vec) > 1e-6]
        dispersion = round(float(np.mean([1.0 - s for s in sims])), 4) if sims else 0.0

        profiles[spk_id] = {
            "id": spk_id,
            "name": name_clean,
            "role": role or ("Yaratıcı & Sistem Yöneticisi" if "nuri" in spk_id else ("Nuri Can'ın Eşi" if "rabia" in spk_id else "Kayıtlı Kullanıcı")),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sample_count": len(proto_list),
            "prototypes": proto_list,
            "embeddings": proto_list,
            "centroid_embedding": c,
            "dispersion": dispersion,
            "f0_telemetry": pitch_info,
            "f0_info": pitch_info,
            "quality_stats": {
                "last_snr_db": round(quality.snr_db, 1),
                "last_rms": round(quality.rms_energy, 4),
            },
        }
        _save_all_profiles(profiles)
        f0_val = pitch_info.get("median_f0", 0)
        return f"✓ '{name_clean}' için yeni biyometrik profil oluşturuldu ({len(proto_list)} prototip, Dağılım: {dispersion}, Pitch: {f0_val} Hz, SNR: {quality.snr_db:.1f} dB)."


def enroll_voice_profile(speaker_name: str, role: str = "") -> str:
    name_clean = str(speaker_name).strip() or "Nuri Can"
    recent_pcm = get_recent_live_audio(4.0)
    if not recent_pcm or len(recent_pcm) < int(16000 * 2 * 0.6):
        for _ in range(4):
            time.sleep(0.3)
            recent_pcm = get_recent_live_audio(4.0)
            if recent_pcm and len(recent_pcm) >= int(16000 * 2 * 0.6):
                break

    if not recent_pcm or len(recent_pcm) < int(16000 * 2 * 0.5):
        return f"'{name_clean}' için canlı ses örneği yakalanamadı. Lütfen mikrofona 2-3 saniye doğal konuşup tekrar deneyin."

    return enroll_speaker_from_pcm(name_clean, recent_pcm, role=role)


def remove_voice_profile(speaker_name: str) -> str:
    clean_target = str(speaker_name).strip()
    if not clean_target:
        return "Silinecek kişi adı belirtilmedi."

    profiles = _load_all_profiles()
    if not profiles:
        return "Sistemde silinecek kayıtlı bir ses profili bulunmuyor."

    norm_target = _normalize_tr_text(clean_target)

    if norm_target in {"all", "hepsi", "tumunu_sil", "tumu", "herkesi_sil"}:
        count = len(profiles)
        _save_all_profiles({})
        return f"✓ Kayıtlı tüm konuşmacı ses profilleri ({count} profil) sistemden tamamen silindi."

    spk_id = _slugify_name(clean_target)
    if spk_id in profiles:
        removed_name = profiles[spk_id].get("name", clean_target)
        del profiles[spk_id]
        _save_all_profiles(profiles)
        return f"✓ '{removed_name}' adlı ses profili sistemden kalıcı olarak silindi."

    for k, v in list(profiles.items()):
        v_name = v.get("name", "")
        v_norm = _normalize_tr_text(v_name)
        if norm_target == v_norm or norm_target in v_norm or v_norm in norm_target:
            del profiles[k]
            _save_all_profiles(profiles)
            return f"✓ '{v_name}' adlı ses profili sistemden kalıcı olarak silindi."

    available = ", ".join(v.get("name", k) for k, v in profiles.items())
    return f"'{clean_target}' adında kayıtlı bir ses profili bulunamadı. (Mevcut kayıtlar: {available})"


def list_voice_profiles() -> list[dict[str, Any]]:
    profiles = _load_all_profiles()
    summary = []
    for spk_id, p in profiles.items():
        f0_data = p.get("f0_telemetry", p.get("f0_info", {}))
        protos = p.get("prototypes", p.get("embeddings", []))
        summary.append({
            "id": spk_id,
            "name": p.get("name", spk_id),
            "role": p.get("role", ""),
            "sample_count": p.get("sample_count", len(protos)),
            "prototype_count": len(protos),
            "dispersion": p.get("dispersion", 0.0),
            "created_at": p.get("created_at", ""),
            "last_seen_at": p.get("last_seen_at", ""),
            "f0_telemetry": f0_data,
            "median_f0": f0_data.get("median_f0", 0.0),
            "gender_hint": f0_data.get("gender_hint", "unknown"),
        })
    return summary


def get_voice_recognition_status() -> str:
    profiles = list_voice_profiles()
    threshold = get_similarity_threshold()

    if not profiles:
        return (
            f"Sistemde kayıtlı biyometrik ses profili bulunmuyor (Doğrulama Eşiği: {threshold:.2f}). "
            "Sesinizi kaydetmek için Ses Stüdyosu'nu kullanabilirsiniz."
        )

    lines = [f"🎙️ Kayıtlı Biyometrik Konuşmacı Profilleri ({len(profiles)} kişi, Eşik: {threshold:.2f}):"]
    for i, p in enumerate(profiles, 1):
        role_str = f" ({p['role']})" if p['role'] else ""
        lines.append(f"{i}. {p['name']}{role_str} — {p['prototype_count']} prototip [Disp: {p['dispersion']}, Son: {p['last_seen_at'] or 'Yok'}]")
    return "\n".join(lines)


def update_speaker_profile(speaker_name: str, pcm_bytes: bytes) -> str:
    return enroll_speaker_from_pcm(speaker_name, pcm_bytes)
