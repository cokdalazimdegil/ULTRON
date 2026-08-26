```markdown
# 🤖 U.L.T.R.O.N — Kişisel Yapay Zeka Asistanı & Otonom Bilgisayar Kontrolü

<p align="center">
  <img src="sistem/Icon/JARVIS.ico" width="120" alt="ULTRON Logo" />
</p>

<p align="center">
  <strong>Google Gemini Live API destekli, gerçek zamanlı Türkçe sesli sohbet edebilen, bilgisayarınızı yönetebilen ve telefondan uzaktan kontrol edilebilen yeni nesil yapay zeka asistanı.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey.svg" alt="Platform" />
  <img src="https://img.shields.io/badge/AI%20Core-Google%20Gemini%20Live-orange.svg" alt="AI Core" />
  <img src="https://img.shields.io/badge/Lisans-MIT-green.svg" alt="License" />
</p>

---

## 🌟 Öne Çıkan Özellikler

| Kategori | Özellik | Açıklama |
|---|---|---|
| 🎙️ **Sesli İletişim** | **Gemini Live API** | Gecikmesiz, doğal Türkçe sesli sohbet. Asistan konuşurken sözünü kesebilirsiniz (Barge-in desteği). |
| 🗣️ **Biyometri** | **Konuşmacı Tanıma** | ONNX modelleri (WeSpeaker & CAM++) ile sesinizi tanır, yalnızca yetkili kullanıcıların komutlarını dinler. |
| 👁️ **Görsel Zeka** | **Ekran & Kamera Analizi** | Aktif pencereyi/ekranı okur, kod hatalarını analiz eder, web kamerasından canlı görüntü alır. |
| 💻 **Bilgisayar Kontrolü** | **Otonom İşlem** | Fare/klavye kontrolü, pencere yönetimi, güvenli PowerShell/Bash komut yürütme. |
| 📱 **Mobil Erişim** | **Telefondan Kontrol** | QR kod ile anında bağlanın; Cloudflare tüneli sayesinde nerede olursanız olun telefonunuzdan bilgisayarınızı sesle yönetin. |
| 🌐 **Holografik Web UI** | **3D Orb & El Takibi** | Three.js destekli fütüristik 3D Orb ve MediaPipe el hareketleriyle (webcam) kontrol. |
| 📅 **Ajanda & Görevler** | **Takvim & Hatırlatıcı** | Outlook COM veya dahili `.ics` takvim yönetimi, süreli anımsatıcılar. |
| 💬 **Mesajlaşma** | **WhatsApp & E-posta** | WhatsApp Web/Desktop üzerinden sesli komutla mesaj gönderme, e-posta okuma/yazma. |
| 🎵 **Medya** | **Müzik & Video** | Spotify veya YouTube üzerinden sesli parça/video arama ve oynatma. |
| 🧠 **Hafıza & RAG** | **Kalıcı Bellek** | Kişisel tercihleri, notları, rehberi ve ilişkileri öğrenir ve unutmaz. |
| 🤖 **Çoklu Ajan Mimarisi** | **Autonomous Orchestrator**| Karmaşık görevler için Araştırmacı (Research), Kodlayıcı (Coding), Test ve İnceleme (Reviewer) ajanlarını otonom koordine eder. |

---

## 🚀 Hızlı Başlangıç (Windows)

ULTRON, sıfır teknik bilgi ile tek tıkla kurulup çalıştırılacak şekilde tasarlanmıştır.

### 1. Çalıştırma
Klasör içindeki **`BASLAT.bat`** dosyasına çift tıklayın:
- Gerekli Python sürümünü (Python 3.12) ve sanal ortamı (`venv`) **otomatik kurar**.
- Gerekli bağımlılıkları yükler ve **Masaüstü Kısayolu** oluşturur.
- Sonraki açılışlarda doğrudan uygulamayı başlatır.

### 2. Gemini API Anahtarını Girme
İlk açılışta ücretsiz Gemini API anahtarı istenir:
1. [Google AI Studio](https://aistudio.google.com/apikey) adresine gidin.
2. Google hesabınızla giriş yapıp **"Create API key"** butonuna tıklayın.
3. Aldığınız anahtarı ULTRON arayüzündeki kutuya yapıştırıp **Kaydet** deyin.

---

## 📱 Telefondan Uzaktan Kontrol

Bilgisayarınızı cep telefonunuzun tarayıcısından (aynı Wi-Fi'da olmasanız dahi) yönetmek için:

1. Klasördeki **`TELEFON.bat`** dosyasına çift tıklayın.
2. Konsolda çıkan **QR Kodu** telefonunuzun kamerasıyla okutun veya verilen bağlantıyı açın.
3. Telefondan konuşun, bilgisayarınız yanıt versin ve komutları uygulasın!

> 🔒 *Güvenlik Notu:* Mobil bağlantı adresi ve token'ı her oturumda rastgele üretilir ve şifrelenir. Bağlantınızı yabancılarla paylaşmayın.

---

## ⌨️ Klavye Kısayolları

| Tuş | İşlev |
|---|---|
| **"Ultron"** | Uyandırma kelimesi (Wake-word) |
| **F4** | Mikrofonu Aç / Sustur (Mute) |
| **F5** | Asistanı Duraklat / Devam Ettir |
| **F6** | Canlı Kamera Görüntüsünü Aç / Kapat |
| **F11 / Ctrl+F** | Tam Ekran Modu |
| **Esc** | Tam Ekrandan Çık |

---

## 🛠️ Proje Mimarisi

```text
├── BASLAT.bat               # Windows tek tıkla kurulum ve başlatıcı
├── BASLAT.ps1               # Otomatik ortam hazırlama PowerShell betiği
├── TELEFON.bat              # Telefon web sunucusu ve Cloudflare tünel başlatıcı
├── OKU_BENI.txt             # Türkçe kullanım kılavuzu
└── sistem/
    ├── main.py              # Canlı ses döngüsü, Gemini bağlantısı & olay dağıtıcı
    ├── ui.py                # Tkinter arayüzü ve görsel animasyonlar
    ├── tool_defs.py         # Gemini Function Calling (Araç) tanımları
    ├── actions/             # Asistan yetenekleri (Takvim, WhatsApp, Spotify, Shell, vb.)
    ├── computer/            # Otonom fare, klavye, pencere ve ekran denetleyicisi
    ├── core/                # Yapay zeka sağlayıcısı, güvenlik yöneticisi & yetkilendirme
    ├── jarvis_web/          # Telefon için Flask/WebSocket sunucusu & Web UI
    ├── models/              # ONNX ses ve biyometri modelleri
    ├── orchestrator/        # Çoklu ajan (Multi-agent) koordinasyon motoru
    └── memory/              # Kalıcı hafıza ve kullanıcı profilleri
```

---

## 🔒 Gizlilik ve Güvenlik

- Ses ve görsel verileriniz yalnızca **kendi Gemini API anahtarınız** aracılığıyla doğrudan Google servislerine iletilir.
- API anahtarlarınız, takvim kayıtlarınız, notlarınız ve kişi listeniz **kesinlikle 3. şahıslarla paylaşılmaz; yerel bilgisayarınızda saklanır.**
- Sistem kritik kabuk komutları öncesinde güvenlik filtreleri ve teyit mekanizmaları çalıştırır.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında lisanslanmıştır.
```
