# 🤖 U.L.T.R.O.N

### Kişisel Yapay Zeka Asistanı & Otonom Bilgisayar Kontrol Sistemi

<p align="center">
  <img src="sistem/Icon/JARVIS.ico" width="120" alt="ULTRON Logo">
</p>

<p align="center">
  <strong>
    Google Gemini Live API destekli, gerçek zamanlı Türkçe sesli iletişim kurabilen,
    bilgisayarı otonom şekilde kontrol edebilen ve mobil cihazlardan uzaktan yönetilebilen
    yeni nesil kişisel yapay zeka asistanı.
  </strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/AI-Google%20Gemini%20Live-orange.svg" alt="AI Core">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## 🧠 ULTRON Nedir?

**U.L.T.R.O.N.**, bilgisayarınızı yalnızca sesli komutlarla kontrol etmenizi sağlayan klasik bir sesli asistanın ötesinde, bilgisayar ortamını algılayabilen, karar verebilen ve karmaşık görevleri farklı ajanlara dağıtarak gerçekleştirebilen **otonom bir yapay zeka asistanıdır.**

Sistem; sesli iletişim, konuşmacı biyometrisi, ekran analizi, bilgisayar kontrolü, kalıcı hafıza, mobil erişim ve çoklu ajan mimarisini tek bir platform altında birleştirir.

> **Amaç:** Bilgisayarı kullanmak yerine bilgisayarla konuşabilmek.

---

## 🌟 Öne Çıkan Özellikler

| Kategori                   | Özellik                     | Açıklama                                                                                           |
| -------------------------- | --------------------------- | -------------------------------------------------------------------------------------------------- |
| 🎙️ **Sesli İletişim**     | **Gemini Live API**         | Gerçek zamanlı ve doğal Türkçe sesli iletişim. Konuşma sırasında kullanıcı tarafından kesilebilir. |
| 🗣️ **Biyometri**          | **Konuşmacı Tanıma**        | WeSpeaker ve CAM++ tabanlı ONNX modelleriyle konuşmacıyı tanır ve yetkilendirme uygular.           |
| 👁️ **Görsel Zeka**        | **Ekran & Kamera Analizi**  | Ekran görüntülerini, aktif pencereleri ve kamera görüntülerini analiz edebilir.                    |
| 💻 **Bilgisayar Kontrolü** | **Otonom İşlem**            | Fare, klavye, pencereler ve terminal üzerinden bilgisayar üzerinde işlem gerçekleştirebilir.       |
| 📱 **Mobil Erişim**        | **Uzaktan Kontrol**         | Telefon üzerinden bilgisayara bağlanabilir ve sesli komut gönderebilirsiniz.                       |
| 🌐 **Holografik Web UI**   | **3D Orb & Hand Tracking**  | Three.js tabanlı 3D arayüz ve MediaPipe el takibi desteği.                                         |
| 📅 **Ajanda & Görevler**   | **Takvim & Hatırlatıcı**    | Outlook COM ve `.ics` tabanlı takvim yönetimi ve zamanlanmış hatırlatıcılar.                       |
| 💬 **Mesajlaşma**          | **WhatsApp & E-posta**      | Sesli komutlarla mesaj ve e-posta okuma/gönderme.                                                  |
| 🎵 **Medya**               | **Spotify & YouTube**       | Müzik ve video arama, seçme ve oynatma.                                                            |
| 🧠 **Hafıza & RAG**        | **Kalıcı Bellek**           | Kullanıcı tercihlerini, notları, kişileri ve ilişkileri hatırlayabilir.                            |
| 🤖 **Multi-Agent**         | **Autonomous Orchestrator** | Araştırma, kodlama, test ve inceleme ajanlarını karmaşık görevlerde koordine eder.                 |

---

## 🚀 Hızlı Başlangıç

ULTRON, Windows üzerinde mümkün olduğunca az manuel kurulum gerektirecek şekilde tasarlanmıştır.

### 1. Kurulum ve Başlatma

Proje klasöründeki:

```text
BASLAT.bat
```

dosyasına çift tıklayın.

Başlatıcı:

* Gerekli Python ortamını kontrol eder.
* Python 3.12 için sanal ortam (`venv`) oluşturur.
* Gerekli bağımlılıkları yükler.
* Sistem yapılandırmasını hazırlar.
* Masaüstü kısayolu oluşturur.
* Sonraki çalıştırmalarda uygulamayı doğrudan başlatır.

---

### 2. Gemini API Anahtarı

ULTRON'un sesli yapay zeka özelliklerini kullanabilmek için bir Gemini API anahtarı gerekir.

1. [Google AI Studio](https://aistudio.google.com/apikey) sayfasını açın.
2. Google hesabınızla giriş yapın.
3. **Create API key** seçeneğine tıklayın.
4. Oluşturulan API anahtarını ULTRON arayüzündeki ilgili alana girin.
5. **Kaydet** butonuna basın.

> ⚠️ API anahtarınızı GitHub'a, ekran görüntülerine veya herkese açık dosyalara yüklemeyin.

---

## 📱 Telefondan Uzaktan Kontrol

ULTRON, bilgisayarınızı telefonunuzun tarayıcısından uzaktan kontrol etmenize olanak sağlar.

### Başlatmak için:

```text
TELEFON.bat
```

dosyasını çalıştırın.

Terminalde oluşturulan **QR kodu** telefonunuzla okutun veya verilen bağlantıyı tarayıcıda açın.

Artık telefonunuz üzerinden ULTRON ile konuşabilir ve bilgisayarınızda işlemler gerçekleştirebilirsiniz.

### 🔐 Güvenlik

Mobil bağlantı için oluşturulan erişim bilgileri oturum bazlıdır.

**Bağlantı adresini veya erişim token'ını üçüncü kişilerle paylaşmayın.**

---

## ⌨️ Klavye Kısayolları

| Tuş          | İşlev                           |
| ------------ | ------------------------------- |
| **Ultron**   | Uyandırma kelimesi              |
| **F4**       | Mikrofonu aç / kapat            |
| **F5**       | Asistanı duraklat / devam ettir |
| **F6**       | Kamera görüntüsünü aç / kapat   |
| **F11**      | Tam ekran                       |
| **Ctrl + F** | Tam ekran                       |
| **Esc**      | Tam ekrandan çık                |

---

## 🏗️ Proje Mimarisi

```text
ULTRON/
│
├── BASLAT.bat
├── BASLAT.ps1
├── TELEFON.bat
├── OKU_BENI.txt
│
└── sistem/
    │
    ├── main.py
    │
    ├── ui.py
    │
    ├── tool_defs.py
    │
    ├── actions/
    │   ├── calendar/
    │   ├── whatsapp/
    │   ├── spotify/
    │   ├── shell/
    │   └── ...
    │
    ├── computer/
    │   ├── mouse/
    │   ├── keyboard/
    │   ├── screen/
    │   └── windows/
    │
    ├── core/
    │   ├── ai/
    │   ├── security/
    │   └── authorization/
    │
    ├── jarvis_web/
    │   ├── server/
    │   └── web_ui/
    │
    ├── models/
    │   └── ONNX/
    │
    ├── orchestrator/
    │   ├── research/
    │   ├── coding/
    │   ├── testing/
    │   └── reviewer/
    │
    └── memory/
        ├── profiles/
        ├── knowledge/
        └── storage/
```

> Proje yapısı geliştirme sürecine bağlı olarak değişebilir.

---

## 🤖 Multi-Agent Orchestrator

ULTRON yalnızca tek bir yapay zeka modelinden oluşmaz.

Karmaşık görevlerde farklı uzman ajanları kullanabilen bir **orchestrator** mimarisine sahiptir.

```text
                    ┌─────────────────────┐
                    │       ULTRON        │
                    │    Orchestrator     │
                    └──────────┬──────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
       ┌───────────┐     ┌───────────┐     ┌───────────┐
       │ Research  │     │  Coding   │     │  Testing  │
       │   Agent   │     │   Agent   │     │   Agent   │
       └───────────┘     └───────────┘     └───────────┘
                               │
                               ▼
                        ┌─────────────┐
                        │  Reviewer   │
                        │    Agent    │
                        └─────────────┘
```

Bu yapı sayesinde ULTRON;

* Araştırma yapabilir.
* Kod oluşturabilir.
* Kod üzerinde değişiklik yapabilir.
* Test çalıştırabilir.
* Sonuçları inceleyebilir.
* Hataları tespit edip yeniden deneyebilir.
* Birden fazla görevi sıraya koyabilir.

---

## 🧠 Hafıza Sistemi

ULTRON'un kalıcı hafıza sistemi kullanıcıyla gerçekleştirilen etkileşimlerden elde edilen bilgileri saklayabilir.

Örneğin:

* Kullanıcı tercihleri
* Notlar
* Kişiler
* İlişkiler
* Görevler
* Önceki konuşmalardan elde edilen bilgiler
* Kişisel bağlam

Bu bilgiler sonraki oturumlarda ULTRON tarafından kullanılabilir.

---

## 👁️ Bilgisayar Farkındalığı

ULTRON yalnızca komutları çalıştırmakla kalmaz; bilgisayarın mevcut durumunu analiz ederek karar verebilir.

Sistem;

* Aktif pencereyi algılayabilir.
* Ekran görüntüsünü analiz edebilir.
* Web sayfalarını inceleyebilir.
* Kod hatalarını analiz edebilir.
* Fare ve klavye girişlerini kontrol edebilir.
* Uygulamalar arasında geçiş yapabilir.
* Terminal komutlarını çalıştırabilir.

Bu sayede kullanıcı yalnızca:

> **"ULTRON, şu hatayı bul ve düzelt."**

gibi doğal bir komut verebilir.

---

## 🔒 Gizlilik ve Güvenlik

ULTRON mümkün olduğunca **local-first** çalışma prensibiyle tasarlanmıştır.

* Gemini API iletişimi kullanıcının kendi API anahtarı üzerinden gerçekleştirilir.
* Kullanıcı verileri varsayılan olarak yerel sistemde tutulur.
* API anahtarları ve kişisel veriler kaynak koduna dahil edilmemelidir.
* Kritik terminal işlemlerinde güvenlik kontrolleri uygulanır.
* Yetkilendirme ve konuşmacı tanıma mekanizmaları kullanılabilir.
* Uzaktan erişim bağlantıları oturum bazlı erişim bilgileri kullanır.

> ⚠️ ULTRON'a bilgisayar üzerinde güçlü yetkiler verilebildiğinden, projeyi çalıştırmadan önce güvenlik yapılandırmasını ve izinleri kontrol etmeniz önerilir.

---

## 🛠️ Teknolojiler

| Teknoloji                   | Kullanım Alanı            |
| --------------------------- | ------------------------- |
| **Python**                  | Ana uygulama              |
| **Google Gemini Live API**  | Gerçek zamanlı yapay zeka |
| **ONNX Runtime**            | Ses/biyometri modelleri   |
| **WeSpeaker**               | Konuşmacı tanıma          |
| **CAM++**                   | Speaker embedding         |
| **MediaPipe**               | El takibi                 |
| **Three.js**                | 3D Web UI                 |
| **Flask / WebSocket**       | Mobil erişim              |
| **PowerShell**              | Sistem otomasyonu         |
| **Outlook COM / iCalendar** | Takvim                    |
| **Cloudflare Tunnel**       | Uzaktan bağlantı          |

---

## 📋 Gereksinimler

### Önerilen

* Windows 10 / 11
* Python 3.12
* Mikrofon
* Webcam
* İnternet bağlantısı
* Google Gemini API anahtarı

### İsteğe Bağlı

* Telefon
* NVIDIA GPU
* Hoparlör / kulaklık
* Outlook

---

## ⚠️ Güvenlik Uyarısı

ULTRON bilgisayar üzerinde fare, klavye, terminal ve uygulama kontrolü gibi güçlü yeteneklere sahip olabilir.

Bu nedenle:

* API anahtarlarınızı paylaşmayın.
* `.env` ve gizli yapılandırma dosyalarını GitHub'a yüklemeyin.
* Uzaktan erişim bağlantılarını paylaşmayın.
* Tanımadığınız kişilere bilgisayar kontrolü vermeyin.
* Otonom komut yürütme özelliklerini kullanırken güvenlik politikalarınızı kontrol edin.

---

## 📄 Lisans

Bu proje [MIT License](LICENSE) altında lisanslanmıştır.

---

<p align="center">
  <strong>U.L.T.R.O.N</strong><br>
  <sub>Think. Understand. Act.</sub>
</p>
