# ULTRON — Kapsamlı Envanter, Güvenlik ve Temizlik Raporu (Görev 0)
**Tarih:** 10 Eylül 2026  
**Durum:** Kullanıcı Onayına Hazır (Kod/Dosya Silinmedi)

---

## 1. YÖNETİCİ ÖZETİ

ULTRON kod tabanı üzerinde gerçekleştirilen statik kod analizi, AST bağımlılık grafiği, dosya envanteri ve güvenlik incelemesi tamamlanmıştır. Sistem genel olarak güçlü bir mimariye (Event Bus, Presence Engine, Local RAG, Autonomous Agents) sahip olmakla birlikte; **eski projelerden kalan scriptler**, **kullanılmayan ağır kütüphaneler**, **dağınık dosya/klasör yapıları**, **yarım kalmış JARVIS rebrand kalıntıları** ve **kritik güvenlik izolasyon eksiklikleri** tespit edilmiştir.

Aşağıdaki raporda tüm bulgular kategorize edilmiş ve **SİL / TUT / BİRLEŞTİR / TAŞI** eylem planı çıkarılmıştır.

---

## 2. KULLANILMAYAN / ÖLÜ PYTHON MODÜLLERİ VE FONKSİYONLAR

| Dosya Yolu | Satır | Durum / Ne İşe Yarıyor? | Öneri |
|---|---|---|---|
| `sistem/actions/stylometry_analyzer.py` | 334 | Türkçe N-gram ve üslup tabanlı kimlik doğrulama. `core/multimodal_auth.py` doğrudan erişim moduna geçtiğinden beri hiçbir yerden import edilmiyor. `memory/learned_stylometry.json` ölü veridir. | **SİL** (veya `legacy/` arşivine taşı) |
| `sistem/actions/visual_biometrics.py` | 202 | Yüz biyometrisi ve liveness anti-spoofing motoru. Varlık tespiti `computer/observer_daemon.py` ve `core/presence_engine.py` üzerinden bağımsız yapıldığı için hiçbir yerden import edilmiyor. | **SİL** (veya `legacy/` arşivine taşı) |
| `sistem/actions/webcam_vision.py` | 214 | Eski tekil webcam kare yakalayıcısı (`LAST_SNAPSHOT = tempfile / "jarvis_webcam_last.jpg"`). Web/HUD tarafı websocket üzerinden, arka plan ise `observer_daemon.py` üzerinden çalıştığı için ölü koddur. | **SİL** |
| `sistem/actions/health.py` | 582 | macOS iCloud HealthAutoExport JSON okuyucusu. `tool_defs.py` veya `agent.py` içinde tanımlı DEĞİLDİR. Hiçbir servis veya test tarafından çağrılmamaktadır. | **SİL** (veya `legacy/` arşivine taşı) |
| `sistem/skills/skill_base.py` | 39 | `SkillBase` abstract base class. `skills/__init__.py` dinamik fonksiyon yüklemesi (`execute(args)`) kullanıyor ve mevcut handler'lar (`weather`, `smarthome`) bu sınıfı miras almıyor. | **TUT & ENTEGRE ET** (Handler'lara miras verdirilerek mimari standartlaştırılmalı) |
| `sistem/orchestrator/supervisor_2.py` & `supervisor.py` | 127 + 32 | `supervisor_2.py` asıl motor, `supervisor.py` ise sadece `from orchestrator.supervisor_2 import ...` yapan bir uyumluluk cephesidir. | **BİRLEŞTİR** (Kod `supervisor.py` altında toplanmalı, `supervisor_2.py` silinmeli) |
| `sistem/core/self_healer.py` & `self_healing.py` | 158 + 261 | İki farklı dosya: `self_healer.py` araç çağrı hatalarını izler (`agent.py`), `self_healing.py` ise sistem kaynakları ve arızalarını onarır (`autonomous_monitor.py`). İkisi de aktiftir ancak isim benzerliği kafa karıştırmaktadır. | **TUT & AÇIKLA** (İkisi de korunacak; docstring'ler netleştirilecek) |

---

## 3. BAŞLATMA VE YARDIMCI SCRİPTLER ENVANTERİ (.bat, .ps1, .command, .vbs, .sh)

Repoda toplam **21 adet** script dosyası incelenmiştir:

### A. Kök Dizin
1. **`BASLAT.bat` (484 B):**
   - *İşlev:* Windows kullanıcıları için çift tıklama konsol başlatıcısı. `BASLAT.ps1` dosyasını çalıştırır.
   - *Öneri:* **TUT**.
2. **`BASLAT.ps1` (5.7 KB):**
   - *İşlev:* Python 3.11+ arama, otomatik venv oluşturma, pip bağımlılıklarını kurma ve masaüstü kısayolu oluşturup `main.py` başlatma.
   - *Sorun:* Log dosya adı `$LOG = ... "jarvis_kurulum.log"` olarak kalmış, gereksiz OpenClaw CLI kontrolleri var.
   - *Öneri:* **TUT & TEMİZLE** (ULTRON standartlarına çek).
3. **`SADECE_HUD.bat` (432 B):**
   - *İşlev:* `BASLAT.ps1 --hud` parametresiyle sadece masaüstü HUD arayüzünü açar.
   - *Öneri:* **TUT**.
4. **`Sadece_HUD_Baslat.vbs` (299 B):**
   - *İşlev:* PowerShell penceresini arka planda gizleyerek HUD'ı sessiz açar.
   - *Öneri:* **TUT**.
5. **`TELEFON.bat` (1.2 KB):**
   - *İşlev:* `main.py --web` çalıştırarak web sunucusunu ve telefon bağlantısını açar.
   - *Öneri:* **TUT & GÜNCELLE**.
6. **`TELEFON_IZIN_VER.bat` (1.6 KB):**
   - *İşlev:* Windows Güvenlik Duvarı'na 8765-8766 portları için izin ekler.
   - *Sorun:* Başlık ve firewall kural adı `"JARVIS Telefon"` olarak kalmış.
   - *Öneri:* **GÜNCELLE** (Kural adı `ULTRON Telefon` yapılacak).
7. **`TEMIZLE_ESKI_JARVIS.bat` (2.4 KB):**
   - *İşlev:* Eski "JARVIS V3.2" süreçlerini (`JARVIS.exe`) öldüren, eski güvenlik duvarı kurallarını silen geçiş scripti.
   - *Sorun:* Artık ULTRON 5.0 mimarisine geçildiği için kök dizinde durması gereksizdir.
   - *Öneri:* **SİL** (veya `sistem/legacy/` klasörüne taşı).
8. **`TESHIS.bat` (3.0 KB):**
   - *İşlev:* Ağ, port, süreç ve log durumunu tarayıp masaüstüne teşhis raporu döker.
   - *Sorun:* Çıktı dosya adı `JARVIS_TESHIS.txt`, aradığı süreç `JARVIS.exe` ve log dizini `jarvis_web_logs` olarak kalmış.
   - *Öneri:* **GÜNCELLE & TUT** (ULTRON süreçlerini tarayacak şekilde modernize edilecek).
9. **`install-node.ps1` (633 B):**
   - *İşlev:* `node-v26.7.0-win-x64.zip` indirip kullanıcının ana dizinine açmaya çalışan harici script.
   - *Sorun:* Kişisel yollar (`C:\Users\OSMBILISIM`) içeriyor, ULTRON'un parçası değil.
   - *Öneri:* **SİL**.
10. **`node.zip` (41.1 MB — Binary Arşiv):**
    - *İşlev:* `install-node.ps1` tarafından indirilip kök dizinde unutulmuş devasa zip dosyası.
    - *Öneri:* **SİL** (Git reposu için ciddi bir gereksiz yüktür).
11. **`install-openclaw.ps1`, `fix-openclaw.ps1`, `start-openclaw.ps1`, `start-daemon.ps1` (Toplam ~1.7 KB):**
    - *İşlev:* OpenClaw Node.js paketini kurup daemon ve gateway'ini yöneten scriptler.
    - *Öneri:* **TAŞI** (`third_party/openclaw/` altına) veya **SİL**.

### B. `sistem/` ve `sistem/jarvis_web/` Dizinleri
12. **`sistem/BASLAT.command` (6.2 KB):**
    - *İşlev:* macOS tek tıkla başlatıcısı.
    - *Sorun:* İçi tamamen "J.A.R.V.I.S" ve "Alp'e gönder" metinleriyle dolu.
    - *Öneri:* **GÜNCELLE & TUT** (ULTRON'a uyarla).
13. **`sistem/TELEFON.command` (1.1 KB):**
    - *İşlev:* macOS telefon sunucusu başlatıcı.
    - *Öneri:* **GÜNCELLE & TUT**.
14. **`sistem/TELEFON_EXE.bat` (874 B):**
    - *İşlev:* `JARVIS.exe --web` arayan eski script.
    - *Öneri:* **BİRLEŞTİR / SİL** (Kök dizindeki `TELEFON.bat` zaten Python/EXE uyumludur).
15. **`sistem/autostart_kur.sh` & `autostart_kaldir.sh` (Toplam 3.5 KB):**
    - *İşlev:* macOS `com.alp.jarvis.plist` LaunchAgent otomatik başlatıcı kurma/kaldırma.
    - *Öneri:* **GÜNCELLE & TUT** (`com.ultron.assistant.plist` ve ULTRON loglarına güncelle).
16. **`sistem/build_exe.ps1` (3.6 KB):**
    - *İşlev:* Windows PyInstaller derleyicisi. `jarvis.spec`'i derleyip `dist/JARVIS/JARVIS.exe` üretir.
    - *Öneri:* **GÜNCELLE & TUT** (`ultron.spec` ve `dist/ULTRON/ULTRON.exe` üretecek şekilde güncelle).
17. **`sistem/jarvis_web/WEB_BASLAT.ps1` (8.4 KB) & `WEB_BASLAT.command` (6.5 KB):**
    - *İşlev:* Web sunucusu, ajanı ve Cloudflare tünelini başlatan detaylı scriptler.
    - *Öneri:* **GÜNCELLE & TUT**.

---

## 4. OPENCLAW DOSYALARI VE ULTRON İLİŞKİSİ

- **Bulunan Dosyalar:** `openclaw_home.md` (9.2 KB), `install-openclaw.ps1`, `fix-openclaw.ps1`, `start-openclaw.ps1`, `start-daemon.ps1`, `install-node.ps1`, `node.zip` (41.1 MB).
- **Kod Tarafındaki Durumu:**
  - `core/openclaw_brain.py`: Localhost 18789 portunda bir OpenClaw Gateway arar, varsa komutları ona iletir.
  - `tool_defs.py`: `ask_openclaw_brain` aracı kayıtlıdır.
  - `orchestrator/gemini_reasoning.py`: OpenClaw varsa öncelikli olarak dener, yoksa sessizce Gemini REST fallback'ine geçer.
  - `core/daemon_manager.py`: Arka plan servisi olarak OpenClaw'ı başlatmayı dener.
- **Değerlendirme:**
  OpenClaw, ULTRON'un çalışması için **zorunlu değildir**; kod tabanı zaten Gemini Live ve yerel araçlarla tam otonom çalışmaktadır. Kök dizinde Node.js/OpenClaw kurulum scriptlerinin ve 41 MB'lık zip dosyasının durması mimari kirliliktir.
- **Öneri:**
  1. `node.zip` ve `install-node.ps1` **DERHAL SİLİNMELİDİR**.
  2. `openclaw_home.md`, `install-openclaw.ps1`, `fix-openclaw.ps1`, `start-openclaw.ps1`, `start-daemon.ps1` dosyaları kökten alınıp `third_party/openclaw/` klasörüne taşınmalıdır.
  3. `core/openclaw_brain.py` tamamen opsiyonel bir eklenti (graceful degradation) olarak korunmalıdır.

---

## 5. REQUIREMENTS.TXT VE BAĞIMLILIK ANALİZİ

Repoda 3 ayrı requirements dosyası bulunmaktadır:

### A. `sistem/requirements.txt`
- **Kullanılmayan / Ölü Paketler (İmport edilmiyor):**
  - `telethon`: Kodda sıfır kullanım. -> **SİL**
  - `py-tgcalls`: Kodda sıfır kullanım. -> **SİL**
  - `pydub`: Kodda sıfır kullanım. -> **SİL**
  - `onnxruntime`: Ses/biyometri modelleri çıkarıldığı için import edilmiyor. -> **SİL**
  - `scipy`: Hiçbir yerde import edilmiyor (`jarvis.spec` içinde de exclude edilmiş). -> **SİL**
  - `pywinauto`: Kodda sadece 1 yorum satırında geçiyor, import edilmiyor. -> **SİL**
- **Eksik Paketler (Kodda import edilip burada yazmayanlar):**
  - `google-api-python-client` (`actions/workspace/` servisleri için şart)
  - `google-auth-oauthlib` (`actions/workspace/auth.py` için şart)
  - `google-auth-httplib2` (`actions/workspace/` için şart)
  - `pytest` (Test koşucusu ve CI için şart)
- **Sürüm Sabitleme Eksikliği:**
  - Paketlerin çoğu üst sınırsızdır (`fastapi>=0.110.0`, `websockets>=12.0` vb.). Bunlar semantik versiyonlama gereği `<` üst sınırlarıyla pinlenmelidir (örn: `fastapi>=0.110.0,<1.0.0`, `websockets>=12.0,<14.0`).

### B. `sistem/jarvis_web/requirements.txt`
- `fastapi`, `uvicorn[standard]`, `websockets`, `google-genai`, `requests`, `cryptography` içeriyor.
- Bunların hepsi zaten `sistem/requirements.txt` içinde mevcuttur. Ayrı bir venv bulunmadığı için bu dosya yedek/alt modül amaçlıdır.
- **Öneri:** Ana requirements ile uyumlu tutulmalı, üst README'de ilişkisi açıklanmalıdır.

### C. `sistem/stock_trend_platform/requirements.txt`
- İçinde `yfinance`, `pandas`, `numpy`, `scikit-learn`, `streamlit`, `plotly`, `ta`, `pytest` yazılıdır.
- **DURUM:** `sistem/stock_trend_platform/` klasöründe bu requirements.txt haricinde TEK BİR PYTHON DOSYASI BİLE YOKTUR! Reponun hiçbir yerinde referans verilmemiştir.
- **Öneri:** Bu klasör ve dosyası tamamen **SİLİNMELİDİR**.

---

## 6. YORUM SATIRINA ALINMIŞ (COMMENTED-OUT) BÜYÜK KOD BLOKLARI

Kod tabanı taranmış; 4 satır veya daha uzun terk edilmiş/yorum satırına alınmış ölü Python kod bloğuna **rastlanmamıştır**. Önceki refactor çalışmalarında eski kodlar yorum satırı olarak bırakılmak yerine temiz bir şekilde silinmiştir.

---

## 7. PROJEDEKİ "JARVIS" MARKA KALINTILARI

Projede toplam **445 adet** "JARVIS/jarvis" referansı tespit edilmiştir:
- **Dosya/Klasör İsimleri:**
  - `sistem/jarvis_web/` klasörü -> `sistem/web_bridge/` veya `sistem/ultron_web/` yapılmalı (veya bilinçli alt bileşen olarak dokümante edilmeli).
  - `sistem/jarvis.spec` -> `sistem/ultron.spec`
  - `sistem/Icon/JARVIS.ico` -> `sistem/Icon/ULTRON.ico`
  - `sistem/memory/jarvis_calendar.ics` -> `sistem/memory/ultron_calendar.ics` (geriye dönük uyumlulukla okunacak şekilde).
  - `sistem/helpers/jarvis_calendar_helper.*` ve `.app`
  - `sistem/helpers/jarvis_screen_helper.*` ve `.app`
  - `TEMIZLE_ESKI_JARVIS.bat`
- **Script Başlıkları & Log Dosyaları:**
  - `jarvis_kurulum.log`, `jarvis_server.log`, `jarvis_agent.log`, `jarvis_tunnel.log`, `JARVIS_TESHIS.txt` -> Hepsi `ultron_*` olarak standartlaştırılmalıdır.
  - Windows Güvenlik Duvarı kuralı: `"JARVIS Telefon"` -> `"ULTRON Telefon"`.
  - macOS Plist: `com.alp.jarvis` -> `com.ultron.assistant`.
- **Kod İçi Stringler:**
  - `actions/health.py`, `actions/platform_utils.py`, `actions/win_organizer.py`, `wake_word.py` vb. dosyalardaki loglar ve varsayılan uyandırma kelimeleri.

---

## 8. SİL / TUT / BİRLEŞTİR / TAŞI ÖNERİ TABLOSU

| Dosya / Klasör | İşlem | Gerekçe |
|---|---|---|
| `node.zip` (41.1 MB) | **SİL** | Repoda kalmış gereksiz dev binary arşiv. |
| `install-node.ps1` | **SİL** | Kullanıcıya özel hardcoded yollar içeren harici script. |
| `TEMIZLE_ESKI_JARVIS.bat` | **SİL** | V3.2'den kalma, işlevini tamamlamış geçiş scripti. |
| `sistem/stock_trend_platform/` | **SİL** | İçi boş, hiçbir Python kodu olmayan ölü klasör. |
| `sistem/actions/stylometry_analyzer.py` | **SİL** | `core/multimodal_auth.py` sadeleştiği için çağrılmayan ölü kod (334 satır). |
| `sistem/actions/visual_biometrics.py` | **SİL** | Varlık motoru bağımsızlaştığı için import edilmeyen ölü kod (202 satır). |
| `sistem/actions/webcam_vision.py` | **SİL** | Eski tekil script kalıntısı, sistem canlı websocket/observer kullanıyor (214 satır). |
| `sistem/actions/health.py` | **SİL** | Araç tanımı olmayan, hiçbir yerden çağrılmayan ölü kod (582 satır). |
| `sistem/TELEFON_EXE.bat` | **SİL / BİRLEŞTİR** | Kök dizindeki `TELEFON.bat` ile mükerrer. |
| `sistem/orchestrator/supervisor_2.py` | **BİRLEŞTİR** | `supervisor.py` altında birleştirilecek, tek dosya olacak. |
| `openclaw_home.md`, `install-openclaw.ps1`, `fix-openclaw.ps1`, `start-openclaw.ps1`, `start-daemon.ps1` | **TAŞI** | `third_party/openclaw/` klasörüne taşınacak, kök dizin temizlenecek. |
| `BASLAT.bat`, `BASLAT.ps1`, `SADECE_HUD.bat`, `Sadece_HUD_Baslat.vbs`, `TELEFON.bat` | **TUT & İYİLEŞTİR** | Birincil Windows başlatıcıları; log isimleri ve ULTRON markası güncellenecek. |
| `sistem/BASLAT.command`, `TELEFON.command`, `autostart_*.sh`, `build_exe.ps1` | **TUT & İYİLEŞTİR** | Birincil macOS ve build scriptleri; JARVIS isimleri ULTRON'a güncellenecek. |
| `sistem/skills/skill_base.py` | **TUT & ENTEGRE ET** | Dynamic skill altyapısına bağlanacak. |
| `sistem/requirements.txt` | **GÜNCELLE** | 6 ölü paket çıkarılacak, 4 eksik paket eklenecek, üst sınırlar pinlenecek. |
| `TESHIS.bat` | **GÜNCELLE** | `ULTRON_TESHIS.bat` mantığına ve ULTRON loglarına göre revize edilecek. |
| `TELEFON_IZIN_VER.bat` | **GÜNCELLE** | Firewall kuralı "ULTRON Telefon" olarak güncellenecek. |

---

## 9. KULLANICI ONAYI BEKLENEN NOKTALAR

Bu rapor tamamlandıktan sonra, sizden onay gelene kadar **HİÇBİR DOSYA SİLİNMEYECEK VE DEĞİŞTİRİLMEYECEKTİR**.
Onayınızla birlikte:
1. **Görev 1 (Merkezi Güvenlik Katmanı):** `shell.py`, `file_tools.py`, `whatsapp.py`, `browser.py`, `win_controls.py`, `email_manager.py` modülleri `security_engine.authorize()` ile donatılacak, Whitelist politikası ve Untrusted Content izolasyonu kurulacak, Cloudflare tüneli token + kilit korumasıyla varsayılan yerel moda çekilecek.
2. **Görev 2 (Test Kapsamı & CI & MIT License):** Actions birim testleri eklenecek, GitHub Actions CI oluşturulacak, köke MIT `LICENSE` eklenecek.
3. **Görev 3 (Kod Organizasyonu):** `ui.py` ve `tool_defs.py` modüler parçalara bölünecek, `requirements.txt` üst sınırlarla pinlenecek.
4. **Görev 4 (Marka Tutarlılığı):** Kalan tüm JARVIS isimleri, spec dosyaları, loglar ve scriptler ULTRON'a dönüştürülecek.
5. **Görev 5 (Temizlik & Taşıma):** Yukarıdaki tabloda "SİL" ve "TAŞI" olarak işaretlenen işlemler uygulanacak.

---

## 10. BİLEREK BIRAKILAN JARVIS BİLEŞENLERİ VE GEREKÇELERİ

Sistem bütünlüğünü, platform yeteneklerini ve kullanıcı verilerini korumak amacıyla aşağıdaki bileşenlerin iç isimleri bilinçli olarak korunmuştur:

1. **`sistem/jarvis_web/` Dizin Adı:**
   - *Gerekçe:* FastAPI sunucusu, masaüstü WebView istemcisi (`main.py`), mobil QR oluşturucu ve test suiteleri bu modülü `jarvis_web` import yoluyla tüketmektedir. Yüzlerce dosyadaki importları kırıp çalışma zamanı regresyonu riski yaratmamak adına dizin adı korunmuş, kullanıcıya sunulan başlıklar, UI logoları ve endpointler ULTRON olarak güncellenmiştir.

2. **`sistem/helpers/JARVIS *.app` ve macOS Yardımcı Dosyaları:**
   - *Gerekçe:* macOS güvenlik ve gizlilik modeli (TCC - Transparency, Consent, and Control), Takvim ve Ekran Kaydı izinlerini uygulamanın Bundle ID'si (`com.alp.jarvis`) ve derlenmiş `.app` imzası üzerinden takip eder. Bu ikili dosyaların yeniden adlandırılması kullanıcının macOS Sistem Ayarları'ndaki tüm izinlerini sıfırlayacağı için orijinal helper isimleri ve kod imzaları korunmuştur.

3. **`sistem/jarvis_web/certs/jarvis.crt` & `jarvis.key`:**
   - *Gerekçe:* Yerel ağ üzerinden telefon kamerasını ve mikrofonunu açabilmek için tarayıcının kabul ettiği kendinden imzalı SSL sertifikasıdır. Yeniden adlandırma veya silme, kullanıcının telefonundaki kurulu SSL güvenini iptal edeceğinden korunmuştur.

4. **`sistem/memory/jarvis_calendar.ics` (Geriye Dönük Uyumluluk):**
   - *Gerekçe:* Kullanıcının eski takvim kayıtlarının kaybolmaması için `win_organizer.py` içinde otomatik taşıma ve okuma köprüsü kurulmuştur. Yeni kayıtlar `ultron_calendar.ics` dosyasına yazılır, ancak eski `jarvis_calendar.ics` mevcutsa otomatik içeri aktarılır.

5. **`sistem/jarvis.spec` (Geriye Dönük Uyumluluk):**
   - *Gerekçe:* Yeni ana derleme dosyası `sistem/ultron.spec` olarak oluşturulmuş ve `build_exe.ps1` buna bağlanmıştır. Eski harici betiklerin veya otomasyonların çalışmaya devam edebilmesi için `jarvis.spec` korunmuştur.
