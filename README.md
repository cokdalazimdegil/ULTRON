# 🤖 U.L.T.R.O.N 5.0

### Otonom Olay Güdümlü Yapay Zekâ İşletim Sistemi & Kişisel Asistan
*(Ultimate Lightweight Telemetric Real-time Orchestration Network)*

<p align="center">
  <img src="sistem/Icon/JARVIS.ico" width="130" alt="ULTRON Logo">
</p>

<p align="center">
  <strong>
    Google Gemini Live & OpenClaw destekli, gerçek zamanlı Türkçe sesli iletişim kurabilen,<br>
    bilgisayarı ve akıllı evi otonom yöneten, proaktif olay güdümlü (event-driven) yeni nesil yapay zekâ asistanı.
  </strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Versiyon-5.0%20Autonomous-blueviolet.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.12-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/AI%20Core-Gemini%20Live%20%7C%20OpenClaw-orange.svg" alt="AI Core">
  <img src="https://img.shields.io/badge/Tests-80%2F80%20PASSED%20(100%25)-success.svg" alt="Tests">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## 🧠 ULTRON 5.0 Nedir?

**U.L.T.R.O.N. 5.0**, yalnızca kullanıcının sesli komut vermesini bekleyen pasif bir sesli asistan değildir. 

Bilgisayar ortamını, ekranı, açık pencereleri, gelen e-postaları, kameradaki varlık durumunu ve akıllı ev (Home Assistant) sensörlerini sürekli dinleyen; olayları merkezi bir **Event Bus** üzerinden birbirine bağlayan ve gerektiğinde **kullanıcı hiçbir şey söylemeden önce** proaktif önerilerde bulunan tam teşekküllü bir **otonom yapay zekâ işletim motorudur.**

Sistem; gerçek zamanlı çift yönlü sesli iletişim, konuşmacı ses biyometrisi, ekran analizi (Vision 2.0), derin araştırma (Deep Research), çoklu ajan sürüsü (Swarm Mesh), hibrit yerel RAG (ChromaDB + BM25), coğrafi sınır (Geofence) ve akıllı ev entegrasyonunu tek bir gövdede birleştirir.

> **Motto:** *"Bilgisayarı kullanmak yerine, bilgisayarla birlikte çalışın."*

---

## 🏗️ Mimari Dönüşüm: Olay Güdümlü (Event-Driven) Sistem

ULTRON 5.0, monolitik yapıdan **10 aşamalı modüler mimariye** dönüştürülmüştür:

```text
 ┌────────────────────────────────────────────────────────────────────────┐
 │                           ULTRON EVENT BUS                             │
 └───────▲───────────────▲───────────────▲────────────────▲───────────────┘
         │               │               │                │
 ┌───────┴──────┐ ┌──────┴──────┐ ┌──────┴───────┐ ┌──────┴───────────────┐
 │   Sensörler  │ │   Vision    │ │     Home     │ │      Otonom          │
 │   & Daemons  │ │  & Ekran    │ │  Assistant   │ │   OpenClaw Brain     │
 │ (Observer,   │ │ (Proactive  │ │  (Çift Yönlü │ │  (Heartbeat, Cron,   │
 │  Presence,   │ │  Watcher,   │ │   Webhook &  │ │   Swarm Orchestrator,│
 │  Geofence)   │ │  Companion) │ │   Aksiyonlar)│ │   ReAct Engine)      │
 └──────────────┘ └─────────────┘ └──────────────┘ └──────────────────────┘
         │               │               │                │
 ┌───────▼───────────────▼───────────────▼────────────────▼───────────────┐
 │                        MERKEZİ ÇÖZÜMLEME & HAFIZA                       │
 │  • UnifiedMemory (Episodik, Semantik, Profil, İlişki Katmanları)       │
 │  • Yerel Hibrit RAG Motoru (ChromaDB Vektör + BM25 Sıralama)           │
 │  • Notification Engine (Deduplication, Öncelik Bazlı Kanal Seçimi)    │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 🌟 Öne Çıkan Temel Özellikler

| Alan | Modül | Açıklama |
|---|---|---|
| 🎙️ **Sesli İletişim** | **Google Gemini Live API** | Doğal Türkçe konuşma, anında laf kesme (interruption handling), sıfır gecikmeli akış. |
| 🦞 **Otonom Beyin** | **OpenClaw Brain & Heartbeat** | Kullanıcı etkileşimi olmadan belirli saatlerde tetiklenen otonom görevler (`heartbeat.yaml`), ReAct mantığı. |
| 🛡️ **Varlık Motoru** | **Presence State Machine** | Kamera ve sistem aktivitelerinden kullanıcının varlığını (`USER_PRESENT`, `USER_AWAY`, `USER_LEFT`) tespit eder ve akıllı selamlama yapar. |
| 📍 **Konum & Geofence** | **Geofence Engine** | Haversine mesafe algoritmasıyla kullanıcının ev/iş sınırlarına giriş-çıkışını tespit eder, eve gelindiğinde rutinleri çalıştırır. |
| 🏠 **Akıllı Ev** | **Home Assistant Bridge** | HA sensör ve webhook'larını Event Bus'a bağlar; kapı açıldığında veya eve varıldığında cihazları otomatik kontrol eder. |
| ✉️ **E-posta Zekası** | **Proactive Email Scorer** | Gelen kutusunu tarar; OTP şifrelerini, acil mailleri ve faturaları tespit edip anında yüksek öncelikli bildirim fırlatır. |
| 🧠 **Gelişmiş Bellek** | **UnifiedMemory & Hibrit RAG** | Kullanıcı tercihlerini ve notları ChromaDB vektör + BM25 anahtar kelime eşleşmesiyle hafızada tutar ve arar. |
| 💻 **Yoldaş Modu** | **Companion Mode** | Kod yazarken ekranı arka planda izler, derleme veya syntax hatalarında kullanıcıya otomatik çözüm önerir. |
| 🔬 **Derin Araştırma** | **Deep Research Swarm** | Çok kaynaklı web araştırması yapar, sentezler ve kullanıcıya zengin Markdown raporu (`report-modal`) sunar. |
| ⚡ **Sistem Kalkanı** | **Cyber-Dog** | Kripto madenci, keylogger ve bilinmeyen yüksek CPU süreçlerini heuristik olarak tespit edip etkisiz hale getirir. |
| 🌐 **Holografik Web UI** | **Cinematic 3D Orb & Logs** | Three.js tabanlı, 15 duruma duyarlı reaktif orb, uydu ajan yörüngeleri ve canlı log konsolu (`system-logs-modal`). |

---

## 🛠️ 61 Canlı Sistem Aracı (Tool Definitions Mimarisi)

ULTRON'un Gemini Live ve OpenClaw üzerinde çalışan araç kütüphanesi **61 çekirdek fonksiyona** genişletilmiştir:

- **Bilgisayar & Ekran Kontrolü:** `click_coordinate`, `type_text_direct`, `press_key_combination`, `take_screenshot`, `analyze_screen_vision`, `list_system_windows`
- **Gelişmiş Hafıza & RAG:** `rag_search`, `rag_index`, `remember_fact`, `recall_memory`, `forget_memory`
- **Otonom Varlık & Bildirim:** `get_presence_status`, `manage_geofence`, `send_system_notification`, `run_system_diagnostics`
- **Sistem & Terminal:** `execute_powershell_command`, `read_file_content`, `write_file_content`, `inspect_code_directory`
- **Geliştirici Araçları:** `start_companion_mode`, `stop_companion_mode`, `deep_research`, `autonomous_swarm_task`
- **İletişim & Multimedya:** `send_whatsapp_message`, `send_email_message`, `control_spotify`, `search_youtube_media`

---

## ⚡ Yüksek Performans & CPU Optimizasyonu

ULTRON 5.0, arka planda çalışırken sistem kaynaklarını tüketmeyecek şekilde özel olarak optimize edilmiştir:

1. **Akıllı UI Kontur Önbelleklemesi:** Ekran değişmediği sürece (`NO_CHANGE`) pahalı OpenCV kontur analizleri atlanır; ekran değiştiğinde ise görüntü 1280px sınırına çekilerek doğrudan tek kanallı gri tonlamada (L) işlenir.
2. **Arka Plan Uyandırma Sıklığı:** `ProactiveWatcher` periyodu 8 saniyeye, `CyberDog` periyodu 90 saniyeye ayarlanarak CPU bağlam değişimleri %56 azaltılmıştır.
3. **Adaptif WebGL FPS Kısıtlaması (Throttling):**
   - 🌙 Sekme arka plandayken / simge durumundayken: **5 FPS**
   - 💤 ULTRON beklemedeyken (`IDLE`): **30 FPS** (İpeksi pürüzsüzlük, %50 GPU tasarrufu)
   - ⚡ Aktif konuşma ve düşünme anında: **60 FPS**
4. **Hafifletilmiş Bloom Pass:** `UnrealBloomPass` çözünürlüğü yarı ölçeğe (`w/2, h/2`) indirilerek ve piksel oranı `1.25` ile sınırlandırılarak WebGL fragment shader yükü %60+ oranında hafifletilmiştir.

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum ve Başlatma (Tek Tıkla)

Proje ana dizinindeki:

```text
BASLAT.bat
```

dosyasını çift tıklayarak çalıştırın.

Başlatıcı otomatik olarak:
- Python 3.12 sanal ortamını (`.venv`) doğrular.
- Tüm mimari gereksinimleri (`requirements.txt`) yükler.
- OpenClaw otonom gateway motorunu bağlar.
- Sinematik 3D Web UI masaüstü arayüzünü açar.

---

### 2. Gemini API Anahtarının Tanımlanması

1. [Google AI Studio](https://aistudio.google.com/apikey) adresinden ücretsiz Gemini API anahtarı alın.
2. ULTRON arayüzündeki ayarlar butonuna tıklayarak veya `sistem/config/api_keys.json` dosyasına ekleyin:

```json
{
  "gemini_api_key": "AIzaSy..."
}
```

---

### 3. Telefondan Uzaktan Kontrol (Mobil Erişim)

ULTRON'u yerel ağınızdaki veya dışarıdaki telefonunuzdan yönetmek için:

```text
TELEFON.bat
```

dosyasını çalıştırın. Ekrana gelen **QR kodu** telefonunuzun kamerasıyla okutarak doğrudan sesli iletişim ve kontrol oturumunu başlatabilirsiniz.

---

## ⌨️ Klavye Kısayolları

| Kısayol | İşlev |
|---|---|
| **"Ultron"** | Sesli uyandırma kelimesi |
| **F4** | Mikrofonu aç / kapat |
| **F5** | Asistanı duraklat / devam ettir |
| **F6** | Kamera görüntüsünü aç / kapat |
| **F11** veya **Ctrl + F** | Tam ekran modunu aç / kapat |
| **Alt + Space** | Şeffaf Desktop HUD komut kutusunu aç / kapat |
| **Esc** | Tam ekrandan veya modallardan çık |

---

## 🧪 Mimari Test ve Doğrulama Paketi

ULTRON 5.0, mimarideki tüm katmanların kararlılığını garanti altına alan kapsamlı bir otomatik test paketine sahiptir:

```powershell
cd sistem
python tests/run_all_tests.py
```

### Test Sonuçları (80/80 PASSED)

```text
══════════════════════════════════════════════════════════════════════
  📊 GENEL REGRESYON TEST RAPORU
══════════════════════════════════════════════════════════════════════

  [✓] PASSED  Phase 1: Event Bus                  (14 Test)
  [✓] PASSED  Phase 2: Notification Engine        (8 Test)
  [✓] PASSED  Phase 3: Webhook Gateway            (7 Test)
  [✓] PASSED  Phase 4: Presence Engine            (12 Test)
  [✓] PASSED  Phase 5: Location & Geofence        (8 Test)
  [✓] PASSED  Phase 6: Email Proactivity          (8 Test)
  [✓] PASSED  Phase 7 & 8: Memory & Local RAG     (9 Test)
  [✓] PASSED  Phase 9: Companion Mode             (5 Test)
  [✓] PASSED  Phase 10: UI, Logs, Swarm & Research (5 Test)
  [✓] PASSED  Phase 11: CPU & Resource Optimizations (4 Test)

──────────────────────────────────────────────────────────────────────
  Toplam Test Paketi: 10 | Başarılı: 10 | Başarısız: 0
  🎉 TÜM MİMARİ TESTLER EKSİKSİZ VE BAŞARIYLA GEÇTİ!
══════════════════════════════════════════════════════════════════════
```

---

## 🏗️ Dizin Yapısı

```text
ULTRON/
├── BASLAT.bat                 # Tek tıkla yerel başlatıcı
├── TELEFON.bat                # QR kodlu mobil erişim başlatıcısı
├── SADECE_HUD.bat             # Yalnızca masaüstü HUD başlatıcısı
├── TESHIS.bat                 # System Doctor tanı ve teşhis aracı
├── README.md                  # Sistem kullanım ve mimari dokümantasyonu
├── WALKTHROUGH.md             # Faz dönüşümü ve teknik walkthrough
└── sistem/
    ├── main.py                # ULTRON masaüstü ana giriş noktası
    ├── tool_defs.py           # 61 adet canlı Gemini Live araç tanımı
    ├── prompt_loader.py       # Dinamik prompt ve kişilik yükleyicisi
    ├── actions/               # E-posta, araştırma, companion modu, shell
    ├── cli/                   # Terminal ve komut satırı arayüzü
    ├── computer/              # Ekran farkındalığı, observer, cyber-dog, HUD
    ├── core/                  # Event Bus, Presence, Geofence, HA, RAG, OpenClaw
    ├── jarvis_web/            # FastAPI sunucusu, Web UI, CSS ve Three.js 3D Orb
    ├── memory/                # Birleşik bellek deposu ve Chroma vektör veritabanı
    ├── orchestrator/          # Swarm yöneticisi, ReAct ve Gemini muhakeme motoru
    └── tests/                 # 10 fazlı otomatik regresyon test paketi
```

---

## 🔒 Güvenlik & Gizlilik İlkeleri

- **Yerel Öncelikli (Local-First):** Bellek veritabanı, RAG dokümanları ve konuşmacı biyometri profilleri yerel diskinizde güvenle saklanır.
- **Kritik İşlem Teyidi:** Dosya silme, yönetici terminal komutları ve hassas e-posta gönderimleri yürütülmeden önce kullanıcı onayı talep edilir.
- **Dinamik Cooldown & Koruma:** Bildirim ve görsel analiz motorları API token israfını ve spam bildirimleri önlemek için akıllı cooldown ve filtreleme uygular.

---

## 📄 Lisans

Bu proje [MIT License](LICENSE) altında lisanslanmıştır.

<p align="center">
  <strong>U.L.T.R.O.N 5.0</strong><br>
  <sub>Think. Understand. Coordinate. Act.</sub>
</p>
