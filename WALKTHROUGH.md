# ULTRON Mimari Dönüşüm & Proaktif Sistem Walkthrough

Bu belge, **ULTRON** kişisel yapay zekâ asistanının monolitik yapıdan **olay güdümlü (event-driven), proaktif ve otonom mimariye** dönüştürülmesine ilişkin tüm aşamaları, eklenen bileşenleri, doğrulama testlerini ve operasyonel kullanım kılavuzunu içerir.

---

## 🏗️ 1. Mimari Dönüşüm Özeti

| Faz | Bileşen | Dosya(lar) | Durum | Testler |
| :--- | :--- | :--- | :---: | :---: |
| **Phase 1** | Event Bus & Events | `sistem/core/events.py`<br>`sistem/core/event_bus.py` | ✅ Tamamlandı | 14/14 PASSED |
| **Phase 2** | Notification Engine | `sistem/core/notification_engine.py` | ✅ Tamamlandı | 8/8 PASSED |
| **Phase 3** | Webhook Gateway | `sistem/jarvis_web/server.py` | ✅ Tamamlandı | 7/7 PASSED |
| **Phase 4** | Presence State Machine | `sistem/core/presence_engine.py` | ✅ Tamamlandı | 12/12 PASSED |
| **Phase 5** | Location & Geofence & HA | `sistem/core/geofence_engine.py`<br>`sistem/core/ha_bridge.py` | ✅ Tamamlandı | 8/8 PASSED |
| **Phase 6** | Email Proactivity | `sistem/core/email_scorer.py`<br>`sistem/channels/email_manager.py` | ✅ Tamamlandı | 8/8 PASSED |
| **Phase 7** | Memory Consolidation | `sistem/core/unified_memory.py` | ✅ Tamamlandı | Entegre |
| **Phase 8** | Local RAG Engine | `sistem/core/local_rag_engine.py` | ✅ Tamamlandı | 9/9 PASSED |
| **Phase 9** | CLI & System Doctor | `sistem/cli/doctor.py`<br>`sistem/cli/ultron_cli.py` | ✅ Tamamlandı | 21/21 Kontrol |
| **Phase 10** | Legacy Cleanup | `sistem/requirements.txt` | ✅ Tamamlandı | Temizlendi |
| **Phase 11** | Master Regression Suite | `sistem/tests/run_all_tests.py` | ✅ Tamamlandı | 66/66 PASSED |

---

## 🧩 2. Hayata Geçirilen Temel Sistemler

### A. Event-Driven Omurga (`event_bus.py`)
- **Tipli veri modelleri**: `UltronEvent`, `EventPriority` (10-100), `EventSource`
- **Asenkron ve senkron subscriber desteği**: (`subscribe`, `subscribe_async`)
- **Wildcard eşleme**: `*` (tüm eventler), `camera.*` (kategori prefix)
- **Deduplication**: Aynı payload'ı kısa sürede tekrar yaymama
- **Cooldown kontrolü ve hata izolasyonu**: Bir listener çökse dahi diğer dinleyiciler kesintisiz çalışır
- **Geriye dönük %100 uyumluluk**: Eski string tabanlı `publish(name, dict)` çağrıları aynen korunur

### B. Çok Kanallı Bildirim Motoru (`notification_engine.py`)
- **Önceliğe göre dinamik kanal yönlendirme**:
  - `LOW`: Sessiz log
  - `NORMAL`: `web_ui`
  - `HIGH`: `web_ui` + `gemini`
  - `CRITICAL`: `web_ui` + `gemini` + `tts` + `ha`
- Gece sessiz saatler (`quiet_hours`) ve acil durum bypass mekanizması
- Ring-buffer bildirim geçmişi takibi (`get_history()`)

### C. Webhook Gateway (`server.py`)
- `/api/webhook/v1/event`: iOS Shortcuts, IFTTT ve harici betikler için evrensel event alıcısı
- `/api/webhook/homeassistant`: Home Assistant otomasyonlarından gelen durum değişikliklerini `ha.*` eventlerine dönüştürür
- `/api/webhook/location`: GPS Tracker uygulamalarından canlı koordinat alır, `user.location.changed` yayınlar
- IP bazlı dakikalık rate limiting ve token doğrulaması

### D. Varlık Durum Makinesi (`presence_engine.py`)
- **Durum akışı**: `UNKNOWN` → `PERSON_DETECTED` → `USER_PRESENT` → `USER_AWAY` → `USER_LEFT`
- Eski `server.py` içindeki 30 saniyede bir tekrarlanan spam karşılama kaldırıldı
- 30 dakikalık greeting cooldown ve debounce ile yalnızca kullanıcı gerçekten geri döndüğünde `presence.greeting_due` fırlatılır

### E. Coğrafi Sınır & Akıllı Ev (`geofence_engine.py` & `ha_bridge.py`)
- Haversine formülü ile milimetrik GPS mesafe hesaplaması
- Ev ve ofis sınırları için `geofence.enter`, `geofence.exit`, `user.arrived_home`, `user.left_home` eventleri
- Çoklu kullanıcı (`YARATICI`, `AILE_UYESI`) bağımsız bölge takibi
- Çift yönlü Home Assistant köprüsü (HA sensörlerinden varlık tetikleme, eve varışta karşılama senaryosu)

### F. Akıllı E-Posta Skorlama (`email_scorer.py`)
- Kural tabanlı hızlı skorlama (0-100 puan):
  - **Doğrulama / OTP kodları**: 95 puan (`CRITICAL`)
  - **Finans / Fatura / Banka**: 80 puan (`HIGH`)
  - **Acil / Onay / Deadline**: 85 puan (`HIGH`)
  - **Toplantı / Mülakat**: 70 puan (`NORMAL`)
  - **Bülten / Reklam / Unsubscribe**: 15 puan (`LOW`, sessiz)
- Event Bus ile `email.important` ve `email.received` yayınları

### G. Konsolide Bellek & Yerel RAG (`unified_memory.py` & `local_rag_engine.py`)
- `memory.json`, `memory_v2.json` ve vektör hafızayı tek arayüz altında toplayan `unified_memory`
- Katmanlı hafıza: `USER_PROFILE`, `SEMANTIC`, `EPISODIC`, `WORKING`
- `LocalRagEngine`: Sliding window metin parçalama, ChromaDB vektör deposu, çevrimdışı BM25 anahtar kelime fallback'i ve LLM bağlam oluşturucu

### H. Sistem Teşhisi ve CLI (`doctor.py` & `ultron_cli.py`)
- **doctor**: Python sürümü, paketler, API anahtarı, portlar ve 9 çekirdek modülü tek adımda doğrular
- **ultron_cli**: Durum raporlama, bildirim gönderme, event yayınlama, hafıza ve RAG yönetimi

### I. Gelişmiş Araç Tanımları & Canlı Entegrasyon (`tool_defs.py` & `agent.py`)
- **Modern Başlık ve Mimari**: Eski "JARVIS" kalıntıları temizlenerek `ULTRON — Gemini Live Araç (Tool) Tanımları Mimarisi` standardına getirildi (Toplam 61 araç).
- **Yeni 6 Çekirdek Araç**:
  - `rag_search`: Yerel RAG bilgi tabanında (ChromaDB + BM25) semantik arama
  - `rag_index`: RAG bilgi tabanına doküman ve not indeksleme
  - `get_presence_status`: Anlık varlık durumu (Presence State) ve karşılama raporu
  - `manage_geofence`: Coğrafi sınır (Geofence) listeleme, ekleme ve silme
  - `send_system_notification`: Çok kanallı öncelikli sistem bildirimi
  - `run_system_diagnostics`: Canlı ULTRON System Doctor teşhis motoru
- **Anti-Fake-Confirmation Kuralları**: `shell_run`, `computer_control`, `file_operations` araçlarına doğrudan ve otonom yürütme direktifleri yerleştirildi.

---

## 🧪 3. Doğrulama ve Test Sonuçları

### 1. Sistem Teşhis Raporu (`python -X utf8 sistem/cli/doctor.py`)

```text
═════════════════════════════════════════════════════════════════
  🏥 ULTRON MİMARİ SAĞLIK VE TEŞHİS RAPORU (DOCTOR)
═════════════════════════════════════════════════════════════════

┌─ [ Ortam ] ─────────────────────────────────────────────
  [✓] PASS  Python Sürümü: Python 3.12.10 (Uyumlu)
  [✓] PASS  İşletim Sistemi: win32 (nt)

┌─ [ Bağımlılıklar ] ─────────────────────────────────────
  [✓] PASS  Paket: fastapi: v0.141.1 (Web sunucusu ve REST API)
  [✓] PASS  Paket: uvicorn: v0.52.2 (ASGI sunucusu)
  [✓] PASS  Paket: google.genai: v2.18.0 (Gemini 2.5 Live ve Reasoning SDK)
  [✓] PASS  Paket: chromadb: v1.5.9 (Vektör veritabanı ve semantik arama)
  [✓] PASS  Paket: cv2: v5.0.0 (Kamera ve yüz algılama (OpenCV))
  [✓] PASS  Paket: requests: v2.34.2 (Dış servis ve webhook istemcisi)
  [✓] PASS  Paket: numpy: v2.5.2 (Sayısal hesaplama altyapısı)

┌─ [ Kimlik & Yapılandırma ] ─────────────────────────────
  [✓] PASS  Gemini API Anahtarı: Tanımlı (AQ.Ab8...Qg8A)

┌─ [ Ağ ] ────────────────────────────────────────────────
  [✓] PASS  Port 8765 (ULTRON Web Sunucusu): Port boş, dinlemeye hazır.
  [✓] PASS  Port 8766 (HTTPS / Telefon Tüneli): Port boş, dinlemeye hazır.

┌─ [ Mimari Bileşenler ] ─────────────────────────────────
  [✓] PASS  Çekirdek: core.events: Başarıyla yüklendi (Event Veri Yapıları)
  [✓] PASS  Çekirdek: core.event_bus: Başarıyla yüklendi (Asenkron Event Bus)
  [✓] PASS  Çekirdek: core.notification_engine: Başarıyla yüklendi (Çok Kanallı Bildirim Motoru)
  [✓] PASS  Çekirdek: core.presence_engine: Başarıyla yüklendi (Varlık Durum Makinesi)
  [✓] PASS  Çekirdek: core.geofence_engine: Başarıyla yüklendi (Coğrafi Sınır Motoru)
  [✓] PASS  Çekirdek: core.ha_bridge: Başarıyla yüklendi (Home Assistant Köprüsü)
  [✓] PASS  Çekirdek: core.email_scorer: Başarıyla yüklendi (E-Posta Önem Skorlayıcı)
  [✓] PASS  Çekirdek: core.unified_memory: Başarıyla yüklendi (Konsolide Bellek Motoru)
  [✓] PASS  Çekirdek: core.local_rag_engine: Başarıyla yüklendi (Yerel RAG Arama Motoru)

═════════════════════════════════════════════════════════════════
  ÖZET: 21 Başarılı | 0 Uyarı | 0 Hata
  🎉 ULTRON sistemi kusursuz durumda, tüm bileşenler hazır!
═════════════════════════════════════════════════════════════════
```

### 2. Tam Regresyon Test Paketi (`python -X utf8 sistem/tests/run_all_tests.py`)

```text
══════════════════════════════════════════════════════════════════════
  📊 GENEL REGRESYON TEST RAPORU
══════════════════════════════════════════════════════════════════════

  [✓] PASSED  Phase 1: Event Bus                  (0.30s) — 14 test
  [✓] PASSED  Phase 2: Notification Engine        (0.62s) — 8 test
  [✓] PASSED  Phase 3: Webhook Gateway            (1.97s) — 7 test
  [✓] PASSED  Phase 4: Presence Engine            (0.64s) — 12 test
  [✓] PASSED  Phase 5: Location & Geofence        (0.02s) — 8 test
  [✓] PASSED  Phase 6: Email Proactivity          (0.07s) — 8 test
  [✓] PASSED  Phase 7 & 8: Memory & Local RAG     (6.16s) — 9 test

──────────────────────────────────────────────────────────────────────
  Toplam Test Paketi: 7 | Başarılı: 7 | Başarısız: 0
  Toplam Bireysel Test: 66/66 PASSED (%100 Başarı)
  Toplam Süre:        9.78 saniye
  🎉 TÜM MİMARİ TESTLER EKSİKSİZ VE BAŞARIYLA GEÇTİ!
══════════════════════════════════════════════════════════════════════
```

---

## 💻 4. CLI Hızlı Kullanım Rehberi

```bash
# 1. Sistem durumunu ve bileşenleri denetle
python -X utf8 sistem/cli/doctor.py

# 2. Anlık varlık, bölge ve hafıza durumunu gör
python -X utf8 sistem/cli/ultron_cli.py status

# 3. Çok kanallı bildirim gönder
python -X utf8 sistem/cli/ultron_cli.py notify "Sistem" "Yedekleme tamamlandı" --priority high

# 4. Event Bus'a manuel event yayınla
python -X utf8 sistem/cli/ultron_cli.py event "home.motion" '{"room":"salon"}'

# 5. Hafızaya bilgi kaydet ve ara
python -X utf8 sistem/cli/ultron_cli.py memory set preferences theme dark
python -X utf8 sistem/cli/ultron_cli.py memory search "tema tercihi"

# 6. Yerel RAG bilgi tabanında arama yap veya doküman indeksle
python -X utf8 sistem/cli/ultron_cli.py rag search "Event Bus nasıl çalışır?"
python -X utf8 sistem/cli/ultron_cli.py rag index "Proje Dokümanı" "Doküman metni..."
```
