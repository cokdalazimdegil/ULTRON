r"""
ULTRON — İleri Seviye Türkçe Morfolojik Stilometri & Kendi Kendine Öğrenme Motoru
═════════════════════════════════════════════════════════════════════════════════
• Türkçe Bitişken Morfoloji & Kök/Ek Ayrıştırıcı (Agglutinative Morphology Engine)
• Karakteristik N-Gram (Unigram, Bigram, Trigram) Üslup İmzaları
• Dinamik Kendi Kendine Öğrenen Sözlük Bankası (Self-Learning Vocabulary Profiling)
• Çok Modlu (Multimodal) Doğrulama için $S_{style} \in [0.0, 1.0]$ Güven Skoru Üretimi
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app_paths import data_path

logger = logging.getLogger("ultron.stylometry_analyzer")

LEARNED_STYLES_FILE = data_path("memory", "learned_stylometry.json")


def _clean_turkish_text(text: str) -> str:
    """Türkçe karakterleri ve noktalama işaretlerini standartlaştırır."""
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"[^\w\sğüşıöçĞÜŞİÖÇ]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# Türkçe Bitişken Ek Listeleri (Morfolojik Kök Tespiti için)
TURKISH_SUFFIXES = [
    # Birleşik / Çekim Ekleri
    "ebilirmisin", "abilirmisin", "ebilirmisiniz", "abilirmisiniz",
    "verirmisin", "verirmisiniz", "verir misin", "verir misiniz",
    "layalım", "leyelim", "layalim", "layın", "leyin", "layıver", "leyiver",
    "misin", "mısın", "musun", "müsün", "misiniz", "mısınız", "musunuz", "müsünüz",
    # İstek / Emir / Tezlik Ekleri
    "ıver", "iver", "uver", "üver", "sene", "sana", "senize", "sanıza",
    "alım", "elim", "ayım", "eyim", "sak", "sek",
    # Yapım / Çekim / Durum Ekleri
    "deki", "daki", "teki", "taki", "den", "dan", "ten", "tan",
    "de", "da", "te", "ta", "e", "a", "i", "ı", "u", "ü", "ye", "ya", "yi", "yı", "yu", "yü",
    "ler", "lar", "leri", "ları", "nin", "nın", "nun", "nün", "in", "ın", "un", "ün",
    "im", "ım", "um", "üm", "imiz", "ımız", "umuz", "ümüz",
    "le", "la", "yle", "yla", "lı", "li", "lu", "lü", "lık", "lik", "luk", "lük"
]


def extract_turkish_stems(words: list[str]) -> list[str]:
    """
    Türkçe kelimelerin bitişken eklerini 2 kademeli budayarak kök veya gövde adaylarını çıkarır.
    """
    stems = set()
    for raw_w in words:
        w = raw_w.lower().strip()
        if not w:
            continue
        stems.add(w)

        # 1. Aşama Budama
        cur = w
        for sfx in TURKISH_SUFFIXES:
            if len(cur) > len(sfx) + 2 and cur.endswith(sfx):
                cur = cur[:-len(sfx)]
                stems.add(cur)
                break

        # 2. Aşama Budama (İkincil ekler: örn. kodlayalım -> kodlay -> kod)
        for sfx in TURKISH_SUFFIXES:
            if len(cur) > len(sfx) + 2 and cur.endswith(sfx):
                stems.add(cur[:-len(sfx)])
                break

    return list(stems)



# Sabit Temel Üslup İmzaları
BASE_STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "nuri_can": {
        "display_name": "YARATICI",
        "role": "Yönetici & Yaratıcı (Root)",
        "roots": {
            "kod", "yazilim", "yazılım", "terminal", "commit", "git", "sunucu", "port",
            "docker", "api", "test", "hata", "duzelt", "düzelt", "ekle", "kaldir", "kaldır",
            "tam ekran", "calistir", "çalıştır", "bak", "dosya", "analiz", "prompt", "ultron",
            "jarvis", "proje", "python", "ac", "aç", "kapat", "yap", "ne diyorsun", "incele",
            "guncelle", "güncelle", "baglan", "bağlan", "restart", "log", "mimari", "kodla",
            "kontrol", "versiyon", "bilesen", "bileşen", "repo", "fonksiyon", "branch", "diff",
            "review", "supervisor", "harness", "audit", "derle", "build", "script"
        },
        "phrases": {
            "tam ekran yap", "kodu incele", "terminali aç", "testleri çalıştır", "hatayı düzelt",
            "ne diyorsun", "commit et", "sunucuyu başlat", "loglara bak", "nasıl yapabiliriz",
            "şunu yap", "kontrol et", "analiz yap"
        },
        "imperative_verbs": {
            "yap", "et", "ac", "aç", "kapat", "bak", "duzelt", "düzelt", "yaz", "calistir", "çalıştır",
            "incele", "goster", "göster", "getir", "sil", "tara", "durdur", "ekle", "kodla", "derle"
        },
        "politeness_weight": 0.10,
        "technical_weight": 0.90,
    },
    "rabia": {
        "display_name": "AILE_UYESI",
        "role": "YARATICI'ın Eşi (Yetkili Aile)",
        "roots": {
            "gunaydin", "günaydın", "merhaba", "nasilsin", "nasılsın", "iyi aksamlar", "iyi akşamlar",
            "tesekkur", "teşekkür", "rica", "bakar misin", "bakar mısın", "yardim", "yardım",
            "hava", "saat", "muzik", "müzik", "sarki", "şarkı", "animsatici", "anımsatıcı",
            "hatirlatici", "hatırlatıcı", "yemek", "ne haber", "lutfen", "lütfen", "canim", "canım",
            "tatlim", "tatlım", "iyi geceler", "selam", "ne yapsak", "film", "kahve", "nasil", "nasıl"
        },
        "phrases": {
            "bakar mısın", "bana yardım eder misin", "hava nasıl", "saat kaç", "müzik aç",
            "anımsatıcı kur", "teşekkür ederim", "rica ederim", "günaydın canım", "iyi akşamlar",
            "lütfen açar mısın", "nasılsın ultron"
        },
        "polite_suffixes": {
            "misin", "mısın", "musun", "müsün", "misiniz", "mısınız", "musunuz", "müsünüz",
            "lütfen", "lutfen", "eder misin", "yapar mısın", "rica", "teşekkür"
        },
        "politeness_weight": 0.90,
        "technical_weight": 0.10,
    }
}


@dataclass
class StylometryReport:
    text: str
    word_count: int
    scores: dict[str, float]
    best_match: str
    confidence: float
    detected_traits: dict[str, Any] = field(default_factory=dict)
    is_authoritative: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "word_count": self.word_count,
            "scores": {k: round(v, 4) for k, v in self.scores.items()},
            "best_match": self.best_match,
            "confidence": round(self.confidence, 4),
            "detected_traits": self.detected_traits,
            "is_authoritative": self.is_authoritative,
        }


class StylometryAnalyzer:
    """
    Türkçe morfolojik analiz, n-gram örüntüleri ve kendi kendine öğrenen kelime bankasını
    kullanan üstün yetenekli dilbilimsel üslup motoru.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._learned_vocabulary: dict[str, dict[str, int]] = {"nuri_can": {}, "rabia": {}}
        self._load_learned_vocabulary()

    def _load_learned_vocabulary(self) -> None:
        """Kalıcı olarak öğrenilen kullanıcı sözlüklerini yükler."""
        if LEARNED_STYLES_FILE.exists():
            try:
                data = json.loads(LEARNED_STYLES_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._learned_vocabulary = data
            except Exception as e:
                logger.debug(f"Öğrenilen sözlük okuma hatası: {e}")

    def _save_learned_vocabulary(self) -> None:
        """Öğrenilen sözlükleri diske kaydeder."""
        try:
            LEARNED_STYLES_FILE.parent.mkdir(parents=True, exist_ok=True)
            LEARNED_STYLES_FILE.write_text(
                json.dumps(self._learned_vocabulary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.debug(f"Öğrenilen sözlük kaydetme hatası: {e}")

    def learn_user_turn(self, user_name: str, text: str) -> None:
        """
        Kullanıcı yüksek güvenle doğrulandığında, kullandığı karakteristik kelimeleri öğrenir.
        """
        if not text or not user_name or user_name.lower() in ("bilinmeyen", "unknown"):
            return

        user_key = user_name.lower().replace(" ", "_")
        cleaned = _clean_turkish_text(text)
        words = cleaned.split()
        if len(words) < 2:
            return

        stems = extract_turkish_stems(words)
        with self._lock:
            if user_key not in self._learned_vocabulary:
                self._learned_vocabulary[user_key] = {}

            user_dict = self._learned_vocabulary[user_key]
            for st in stems:
                if len(st) >= 3:
                    user_dict[st] = user_dict.get(st, 0) + 1

            # En sık kullanılan 150 kelimeyi sınırla
            if len(user_dict) > 150:
                sorted_items = sorted(user_dict.items(), key=lambda x: x[1], reverse=True)[:150]
                self._learned_vocabulary[user_key] = dict(sorted_items)

            self._save_learned_vocabulary()

    def analyze_text(self, text: str) -> StylometryReport:
        """
        Metni morfolojik kökler, n-gram kalıpları ve öğrenilmiş sözlükle karşılaştırıp skorlar.
        """
        if not text or not text.strip():
            return StylometryReport(
                text="",
                word_count=0,
                scores={"nuri_can": 0.0, "rabia": 0.0},
                best_match="Bilinmeyen",
                confidence=0.0,
                detected_traits={},
                is_authoritative=False
            )

        cleaned = _clean_turkish_text(text)
        words = cleaned.split()
        word_count = len(words)
        if word_count == 0:
            return StylometryReport(text, 0, {"nuri_can": 0.0, "rabia": 0.0}, "Bilinmeyen", 0.0)

        # 1. Morfolojik Kökleri Çıkar
        stems = set(extract_turkish_stems(words))

        # 2. Nezaket / Soru Eki Tespiti (Politeness Index)
        polite_hits = 0
        for p_suffix in BASE_STYLE_PROFILES["rabia"]["polite_suffixes"]:
            if p_suffix in cleaned:
                polite_hits += 1.5
        politeness_index = min(1.0, polite_hits / max(1.0, math.sqrt(word_count) * 1.5))

        # 3. Teknik Kelime ve Doğrudan Emir Kipi Tespiti (Tech & Imperative Index)
        tech_hits = 0
        imperative_hits = 0
        for st in stems:
            if st in BASE_STYLE_PROFILES["nuri_can"]["roots"]:
                tech_hits += 1.0
            if st in BASE_STYLE_PROFILES["nuri_can"]["imperative_verbs"]:
                imperative_hits += 1.0

        tech_density = min(1.0, tech_hits / max(1.0, math.sqrt(word_count) * 1.4))
        imperative_index = min(1.0, imperative_hits / max(1.0, math.sqrt(word_count) * 1.2))

        scores: dict[str, float] = {}

        # 4. Profil Eşleştirme (Statik Kökler + N-Gram Kalıpları + Öğrenilmiş Sözlük)
        for user_id, prof in BASE_STYLE_PROFILES.items():
            roots = prof.get("roots", set())
            phrases = prof.get("phrases", set())

            # Kök örtüşmesi
            matched_roots = len(stems.intersection(roots))
            root_score = min(1.0, matched_roots / max(1.0, math.sqrt(word_count) * 1.3))

            # Kalıp (Bigram / Trigram) örtüşmesi
            phrase_hits = 0
            for phr in phrases:
                if phr in cleaned:
                    phrase_hits += 2.0
            phrase_score = min(1.0, phrase_hits / max(1.0, math.sqrt(word_count) * 1.2))

            # Öğrenilmiş sözlük örtüşmesi
            learned_dict = self._learned_vocabulary.get(user_id, {})
            learned_hits = sum(1.0 for st in stems if st in learned_dict)
            learned_score = min(1.0, learned_hits / max(1.0, math.sqrt(word_count) * 1.5))

            if user_id == "nuri_can":
                combined = (
                    0.35 * root_score +
                    0.25 * phrase_score +
                    0.20 * tech_density +
                    0.10 * imperative_index +
                    0.10 * learned_score -
                    0.30 * politeness_index
                )
            elif user_id == "rabia":
                combined = (
                    0.35 * root_score +
                    0.25 * phrase_score +
                    0.25 * politeness_index +
                    0.15 * learned_score -
                    0.25 * tech_density
                )
            else:
                combined = root_score

            scores[user_id] = max(0.0, min(1.0, combined))

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top1_user, top1_score = sorted_scores[0]
        top2_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0.0
        margin = top1_score - top2_score

        is_auth = (top1_score >= 0.28 and margin >= 0.06)
        best_match = BASE_STYLE_PROFILES.get(top1_user, {}).get("display_name", top1_user) if is_auth else "Bilinmeyen"

        return StylometryReport(
            text=text,
            word_count=word_count,
            scores=scores,
            best_match=best_match,
            confidence=top1_score,
            detected_traits={
                "politeness_index": round(politeness_index, 3),
                "tech_density": round(tech_density, 3),
                "imperative_index": round(imperative_index, 3),
                "stems_count": len(stems)
            },
            is_authoritative=is_auth
        )


# Canonical Global Singleton Instance
stylometry_analyzer = StylometryAnalyzer()
