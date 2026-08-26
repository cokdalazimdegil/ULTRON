"""
JARVIS — Gemini Live araç (tool) tanımları
Masaüstü (main.py) ve web sunucusu (jarvis_web/server.py) ortak kullanır.
"""

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "macOS'ta herhangi bir uygulamayı açar. Spotify, Safari, Terminal, Finder, VS Code vb.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Uygulama adı (örn. 'Spotify', 'Safari', 'Terminal')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "sys_info",
        "description": "Sistem bilgisi alır: pil durumu, CPU, RAM, disk, saat, tarih, ağ bağlantısı.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "battery | cpu | ram | disk | time | date | network | all"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_weather",
        "description": (
            "Anlik hava durumunu ozetler. Konum verilmezse kullanicinin "
            "BULUNDUGU sehir otomatik tespit edilir. "
            "Kullanici hava durumunu, sicakligi veya yagmur durumunu sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "location": {
                    "type": "STRING",
                    "description": "Sehir veya konum. Bos birakilirsa Istanbul kullanilir."
                }
            }
        }
    },
    {
        "name": "get_calendar_events",
        "description": (
            "Apple Calendar takvimini okur. "
            "Bugun, yarin, siradaki etkinlik veya yaklasan ajandayi ozetler. "
            "Kullanici toplanti, takvim, ajanda, etkinlik veya gunluk programini sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "today | tomorrow | next | agenda | week veya dogal dilde "
                        "'onumuzdeki 30 gun', '2 hafta', 'bu ay', 'gelecek ay'"
                    )
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum etkinlik sayisi"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_calendar_event",
        "description": (
            "Apple Calendar takvimine yeni etkinlik ekler. "
            "Kullanici toplanti, randevu, takvime ekleme veya etkinlik olusturma isterse kullan. "
            "Baslangic tarihini gercek tarih/saat olarak ver; bitis verilmezse varsayilan sure kullanilir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Etkinlik basligi. Ornek: 'Disci Randevusu'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Baslangic tarih/saat. ISO veya yyyy-MM-dd HH:mm formatinda."
                },
                "end_iso": {
                    "type": "STRING",
                    "description": "Bitis tarih/saat. Opsiyonel."
                },
                "location": {
                    "type": "STRING",
                    "description": "Etkinlik konumu. Opsiyonel."
                },
                "notes": {
                    "type": "STRING",
                    "description": "Etkinlik notlari. Opsiyonel."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Eklenecek takvim adi. Opsiyonel."
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "true ise tum gun etkinligi olusturur."
                }
            },
            "required": ["title", "start_iso"]
        }
    },
    {
        "name": "delete_calendar_event",
        "description": (
            "Apple Calendar takviminden etkinlik siler. "
            "Kullanici bir toplantiyi, randevuyu veya takvim kaydini silmek istediginde kullan. "
            "Ayni ada birden fazla etkinlik varsa dogru kaydi bulmak icin baslangic tarihini gercek tarih/saat olarak ver."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Silinecek etkinlik basligi. Ornek: 'Disci Randevusu'"
                },
                "start_iso": {
                    "type": "STRING",
                    "description": "Opsiyonel tarih/saat. Ayni isimli birden fazla etkinligi ayirt etmek icin kullan."
                },
                "calendar_name": {
                    "type": "STRING",
                    "description": "Opsiyonel takvim adi"
                },
                "delete_all_matches": {
                    "type": "BOOLEAN",
                    "description": "true ise eslesen tum etkinlikleri siler"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_reminders",
        "description": (
            "Apple Animsaticilar listesini okur. "
            "Bugunku, yaklasan, geciken veya tum acik animsaticilari ozetler. "
            "Kullanici hatirlatma, animsatici, reminder veya yapilacaklar listesini sordugunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "today | upcoming | overdue | all | next"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Maksimum animsatici sayisi"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Istenirse belirli bir animsatici listesi adi"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "add_reminder",
        "description": (
            "Apple Animsaticilar uygulamasina yeni bir animsatici ekler. "
            "Kullanici 'hatirlat', 'animsatici ekle', 'reminder kur' dediginde kullan. "
            "Goreli zaman ifadelerini bugunku tarih baglamina gore due_iso alanina ISO formatinda cevir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Animsatici basligi"
                },
                "due_iso": {
                    "type": "STRING",
                    "description": "Opsiyonel tarih/saat. Ornek: 2026-04-13T09:00 veya tum gun icin 2026-04-13"
                },
                "notes": {
                    "type": "STRING",
                    "description": "Opsiyonel not"
                },
                "list_name": {
                    "type": "STRING",
                    "description": "Opsiyonel animsatici listesi"
                },
                "priority": {
                    "type": "STRING",
                    "description": "low | medium | high"
                },
                "all_day": {
                    "type": "BOOLEAN",
                    "description": "Tum gun animsatici ise true"
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "browser_control",
        "description": "Tarayıcıda URL açar, Google'da arama yapar veya YouTube'da ilk sonucu doğrudan oynatır.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "open_url | search | play_youtube"},
                "url":    {"type": "STRING", "description": "Açılacak URL (open_url için)"},
                "query":  {"type": "STRING", "description": "Arama sorgusu (search veya play_youtube için)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shell_run",
        "description": (
            "Bilgisayar terminalinde PowerShell, Cmd veya bash komutları çalıştırır. "
            "Dosya yönetimi, git işlemleri, python/node betikleri, ağ ve sistem durumunu sorgulama, "
            "paket yükleme veya herhangi bir komut çalıştırmak istediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "Çalıştırılacak terminal / PowerShell komutu. Örn: 'dir', 'git status', 'python --version', 'ipconfig'"
                },
                "cwd": {
                    "type": "STRING",
                    "description": "Komutun çalıştırılacağı dizin yolu (opsiyonel)."
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "toggle_webcam",
        "description": (
            "Gerçek zamanlı webcam akışını başlatır veya durdurur. "
            "Akış aktifken model sürekli kamera görüntüsü alır — 'bak', 'gör', 'göster', "
            "'kameraya bak', 'önümdekileri anlat', 'ne görüyorsun' gibi komutlarda 'start' kullan. "
            "'kamerayı kapat', 'artık bakma' gibi durumlarda 'stop' kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "start — akışı başlat  |  stop — akışı durdur"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "play_media",
        "description": (
            "YouTube, Spotify veya Apple Music/Music uygulamasında şarkı, müzik veya video açar. "
            "Kullanıcı belirli bir platform söylerse onu kullan. "
            "Belirtmezse uygun olanı dene. "
            "Kullanıcı 'çal', 'oynat', 'aç' diyorsa autoplay=true kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Şarkı, sanatçı, albüm veya video arama ifadesi"
                },
                "provider": {
                    "type": "STRING",
                    "description": "auto | youtube | spotify | apple_music"
                },
                "autoplay": {
                    "type": "BOOLEAN",
                    "description": "true ise mümkünse doğrudan oynatır"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "control_media",
        "description": (
            "Halihazirda calan medyayi kontrol eder: durdurur, devam ettirir, "
            "sonraki/onceki parcaya gecer. Spotify, YouTube veya hangi oynatici "
            "caliyorsa ona gider. "
            "Kullanici 'durdur', 'duraklat', 'sustur', 'muzigi kapat', 'devam et', "
            "'sonraki sarki', 'gec', 'onceki' gibi bir sey soyledigINDE bunu kullan. "
            "Yeni bir sarki BASLATMAK icin bu araci degil play_media'yi kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": (
                        "pause (durdur/duraklat) | resume (devam et) | stop (tamamen durdur) | "
                        "next (sonraki parca) | previous (onceki parca)"
                    )
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "get_youtube_channel_report",
        "description": (
            "YouTube kanalinin public istatistiklerini ve son videolarin performansini raporlar. "
            "Kullanici kanal istatistiklerini, abone sayisini, son videolarini, buyume hizini "
            "veya YouTube analizini sordugunda kullan. Bu arac Studio yerine public YouTube Data API verisini kullanir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Dogal dilde analiz istegi. Ornek: "
                        "'YouTube istatistiklerim nasil', 'son videolarimi analiz et', "
                        "'kanal buyumemi ozetle'"
                    )
                },
                "handle": {
                    "type": "STRING",
                    "description": (
                        "Opsiyonel kanal handle'i, kanal linki veya kanal ID'si. "
                        "Bos birakilirsa ayarlardaki youtube_channel_handle kullanilir."
                    )
                },
                "video_limit": {
                    "type": "NUMBER",
                    "description": "Analize dahil edilecek son video sayisi. Varsayilan 6."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "analyze_screen",
        "description": (
            "Aktif pencerenin ekran goruntusunu alip Gemini vision ile analiz eder. "
            "Kullanici ekranda ne oldugunu, bir hatayi, gorunen metni, butonlari veya pencere icerigini sordugunda kullan. "
            "Bu surum yalnizca aktif pencereyi destekler."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Kullanicinin ekranla ilgili sorusu. Ornek: 'Bu hatayi oku', 'Ekranda ne var?'"
                },
                "target": {
                    "type": "STRING",
                    "description": "Su an sadece active_window desteklenir."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_memory",
        "description": "Kullanıcı hakkında önemli bilgiyi kalıcı belleğe kaydeder. İsim, tercihler, projeler, notlar vb. duyunca sessizce çağır. 'content' ile uzun metin veya bağlam da kaydedilebilir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "identity | preferences | projects | notes | episodic"
                },
                "key":     {"type": "STRING", "description": "Kısa anahtar (örn. 'name', 'python_version')"},
                "value":   {"type": "STRING", "description": "Kısa değer (İngilizce önerilir)"},
                "content": {"type": "STRING", "description": "Uzun metin, not veya bağlam (opsiyonel — vector hafızaya kaydedilir)"}
            },
            "required": ["category", "key"]
        }
    },
    {
        "name": "search_memory",
        "description": "Kalıcı hafızada semantik (anlamsal) arama yapar. Tam kelimeyi bilmeden, yakın anlamlı sorgularla da ilgili kayıtları bulur. Kullanıcı 'bunu biliyor muydun?', 'ne kaydetmiştin?', 'bunu hatırlıyor musun?' dediğinde veya geçmiş bilgiye ihtiyaç olduğunda kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Aranacak konu veya soru (doğal dil). Örn: 'Python projeleri', 'aile üyeleri', 'tercihler'"
                },
                "limit": {
                    "type": "NUMBER",
                    "description": "Döndürülecek maksimum sonuç sayısı (varsayılan: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "delete_memory",
        "description": (
            "Kalici hafizadaki bir kaydi siler. "
            "Kullanici 'bunu hafizandan kaldir', 'unut', 'sil' gibi bir sey derse kullan. "
            "Mumkunse category ve key ile sil; emin degilsen match_text ile ilgili kaydi bulup kaldir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": "Kaydin kategorisi. Ornek: notes | identity | preferences | projects"
                },
                "key": {
                    "type": "STRING",
                    "description": "Silinecek anahtar. Ornek: claude_limit_refresh"
                },
                "match_text": {
                    "type": "STRING",
                    "description": "Kaydi bulmak icin kullanilacak dogal dil parcasi. Ornek: 'claude ai limit yenilenmesi'"
                }
            }
        }
    },
    {
        "name": "send_whatsapp_message",
        "description": (
            "WhatsApp Desktop veya WhatsApp Web üzerinden mesaj taslağı açar veya mesajı gönderir. "
            "Kişi adı veya telefon numarasıyla çalışabilir. "
            "Telefon numarası verilmemişse kişi adını önce kayıtlı WhatsApp kişileri ve içe aktarılan telefon rehberinde ara. "
            "Kullanıcı 'gönder', 'yolla', 'ile', 'hemen gönder' gibi açık bir gönderme niyeti söylüyorsa "
            "ekstra onay istemeden send_now=true kullan. "
            "Yalnızca 'hazırla', 'taslak aç', 'yaz ama gönderme' diyorsa send_now=false kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "recipient_name": {
                    "type": "STRING",
                    "description": "Kişi adı. Örn: 'Anne', 'Ahmet', 'Ece'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "Uluslararası telefon numarası. Örn: +905551112233"
                },
                "message": {
                    "type": "STRING",
                    "description": "Gönderilecek mesaj içeriği"
                },
                "app_target": {
                    "type": "STRING",
                    "description": "desktop | web | auto. Varsayılan auto, tercihen desktop."
                },
                "send_now": {
                    "type": "BOOLEAN",
                    "description": "true ise sohbet açıldıktan sonra mesajı otomatik gönderir"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "save_whatsapp_contact",
        "description": (
            "Sık kullanılan bir WhatsApp kişisini adı ve telefon numarasıyla kalıcı belleğe kaydeder. "
            "Kullanıcı bir kişiyi 'annem', 'Ahmet', 'iş ortağım' gibi tekrar kullanılacak şekilde tanımladığında kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "display_name": {
                    "type": "STRING",
                    "description": "Kaydedilecek kişi adı. Örn: 'Annem', 'Ahmet'"
                },
                "phone_number": {
                    "type": "STRING",
                    "description": "Uluslararası telefon numarası. Örn: +905551112233"
                },
                "aliases": {
                    "type": "STRING",
                    "description": "Virgülle ayrılmış alternatif hitaplar. Örn: 'anne, annem, mom'"
                }
            },
            "required": ["display_name", "phone_number"]
        }
    },
    {
        "name": "control_system",
        "description": (
            "Windows/macOS sistem donanım ayarlarını kontrol eder: ses seviyesi ayarlama, sesi artırma/azaltma, "
            "sessize alma (mute), ekran parlaklığı ayarlama, ekranı kilitleme ve uyku moduna alma. "
            "Kullanıcı 'sesi kıs', 'sesi %70 yap', 'sustur', 'parlaklığı düşür', 'bilgisayarı kilitle' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "volume_set | volume_up | volume_down | mute | brightness_set | lock_screen | sleep"
                },
                "value": {
                    "type": "STRING",
                    "description": "İşlem değeri. Örneğin volume_set veya brightness_set için 0-100 arası sayı."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "control_home_device",
        "description": (
            "Akıllı ev cihazlarını (Home Assistant / Işıklar / Prizler / Termostat / Sahneler) kontrol eder. "
            "Kullanıcı 'ışıkları kapat', 'salonu aç', 'klimayı 22 derece yap', 'film modunu aç' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "device_name": {
                    "type": "STRING",
                    "description": "Cihaz veya oda adı. Örn: 'salon ışığı', 'çalışma masası', 'klima', 'yatak odası prizi'"
                },
                "action": {
                    "type": "STRING",
                    "description": "turn_on | turn_off | toggle | set_temperature | activate_scene"
                },
                "brightness": {
                    "type": "NUMBER",
                    "description": "Işık parlaklık yüzdesi (%0 - 100)"
                },
                "temperature": {
                    "type": "NUMBER",
                    "description": "Klima/Termostat hedef sıcaklık derecesi (örn. 22.5)"
                }
            },
            "required": ["device_name"]
        }
    },
    {
        "name": "get_home_status",
        "description": (
            "Akıllı ev durumunu ve odalardaki açık ışıkları, cihazları sorgular. "
            "Kullanıcı 'evde açık ışık var mı', 'akıllı ev durumu nasıl' gibi sorular sorduğunda kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Sorgu tipi. Örn: 'all' veya 'lights'"
                }
            }
        }
    },
    {
        "name": "file_operations",
        "description": (
            "Dosya ve dizin yönetimi yapar: dosya içeriğini okur (read), dosya oluşturur veya üzerine yazar (write), "
            "dosyaya metin ekler (append), klasör içeriğini listeler (list) veya dosya arar (search). "
            "Kullanıcı 'şu dosyayı oku', 'kod yaz ve dosyaya kaydet', 'klasördekileri listele' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "read | write | append | list | search"
                },
                "path": {
                    "type": "STRING",
                    "description": "Hedef dosya veya klasör yolu. Örn: 'C:/Users/.../test.py' veya 'proje/main.js'"
                },
                "content": {
                    "type": "STRING",
                    "description": "Dosyaya yazılacak veya eklenecek metin/kod (write ve append için)."
                },
                "search_query": {
                    "type": "STRING",
                    "description": "Dosya arama ifadesi (search için)."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "clipboard_control",
        "description": (
            "Sistem panosunu (clipboard) okur veya panoya metin/kod kopyalar. "
            "Kullanıcı 'panomda ne var', 'bunu panoma kopyala', 'panoyu oku' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "get (panodaki metni oku) | set (panoya kopyala)"
                },
                "text": {
                    "type": "STRING",
                    "description": "Panoya kopyalanacak metin (set için)."
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "fetch_webpage_content",
        "description": (
            "Belirtilen URL adresindeki web sayfasının veya makalenin metnini okur ve özetler. "
            "Kullanıcı bir web linki verip 'bu sayfayı oku', 'bu makaleyi özetle', 'bu linkte ne yazıyor' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {
                    "type": "STRING",
                    "description": "Okunacak web adresi (https://...)"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "set_proactive_timer",
        "description": (
            "Proaktif geri sayım sayacı, alarm veya hatırlatıcı kurar. "
            "Kullanıcı '1 dakika sonra bana hatırlat', '15 dk sonra fırını haber ver', 'yarın sabah 9'da alarm kur' "
            "dediğinde KESİNLİKLE bu aracı kullan. Süresi bittiğinde sistem otomatik olarak kullanıcıya sesli ve ekrandan seslenecektir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "title": {
                    "type": "STRING",
                    "description": "Hatırlatılacak konu veya alarm adı. Örn: 'Makarnayı ocaktan al', 'Toplantıya katıl'"
                },
                "minutes": {
                    "type": "NUMBER",
                    "description": "Kaç dakika sonra hatırlatılacağı (örn: 1, 5, 15, 60)."
                },
                "seconds": {
                    "type": "NUMBER",
                    "description": "Ek saniye (örn: 30)."
                },
                "due_iso": {
                    "type": "STRING",
                    "description": "Belirli bir hedef saat/tarih varsa ISO formatında (örn: '14:30' veya '2026-08-17T14:30')."
                },
                "user": {
                    "type": "STRING",
                    "description": "Hatırlatıcının kurulduğu kişi: 'Nuri Can' veya 'Rabia'."
                },
                "is_task": {
                    "type": "BOOLEAN",
                    "description": "True ise; süre dolduğunda sadece bildirim vermek yerine 'title' alanındaki içeriği otonom bir Ajan Görevi (Deep Research, Mail Gönderme vb.) olarak arka planda çalıştırır."
                }
            },
            "required": ["title"]
        }
    },
    {
        "name": "get_active_timers",
        "description": "Şu anda bekleyen aktif geri sayım sayaçlarını, alarmları ve hatırlatıcıları listeler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "cancel_timer",
        "description": "Belirtilen veya tüm aktif hatırlatıcı ve sayaçları iptal eder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "İptal edilecek hatırlatıcı adı, ID'si veya 'all' / 'hepsi'"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_user_location",
        "description": (
            "Nuri Can ve Rabia'nın anlık canlı GPS konumlarını, adreslerini ve aralarındaki mesafeyi sorgular. "
            "Kullanıcı 'ben neredeyim', 'Rabia nerede', 'Rabia'nın konumu ne', 'aramızda ne kadar mesafe var' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "user_name": {
                    "type": "STRING",
                    "description": "'all' (ikisi birden ve mesafe) | 'Nuri Can' | 'Rabia'"
                }
            }
        }
    },
    {
        "name": "get_unread_emails",
        "description": (
            "Gelen kutusundaki okunmamış e-postaları kontrol eder ve listeler. "
            "Kullanıcı 'maillerime bak', 'yeni mail var mı', 'önemli bir e-posta geldi mi' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "limit": {
                    "type": "INTEGER",
                    "description": "Listelenecek maksimum e-posta sayısı (varsayılan: 5)."
                },
                "only_important": {
                    "type": "BOOLEAN",
                    "description": "Sadece acil/önemli (doğrulama kodları, faturalar, banka, toplantılar) e-postaları filtrele."
                }
            }
        }
    },
    {
        "name": "read_email_detail",
        "description": (
            "Belirli bir e-postanın tam metnini ve içeriğini okur. "
            "Kullanıcı '1. maili oku', 'şu kişiden gelen maili aç', 'mailin içeriğinde ne yazıyor' dediğinde kullan."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "index_or_query": {
                    "type": "STRING",
                    "description": "E-posta sıra numarası (örn: '1') veya konu/gönderen adı."
                }
            },
            "required": ["index_or_query"]
        }
    },
    {
        "name": "send_email",
        "description": "Belirtilen alıcıya e-posta gönderir.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "to_address": {
                    "type": "STRING",
                    "description": "Alıcının e-posta adresi."
                },
                "subject": {
                    "type": "STRING",
                    "description": "E-postanın konusu."
                },
                "body": {
                    "type": "STRING",
                    "description": "E-postanın metin içeriği."
                }
            },
            "required": ["to_address", "subject", "body"]
        }
    },
    {
        "name": "search_emails",
        "description": "E-postalar arasında konu, gönderen veya anahtar kelimeye göre arama yapar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Aranacak kelime, kişi adı veya konu (örn: 'Garanti', 'fatura', 'Trendyol', 'mülakat')."
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maksimum sonuç sayısı (varsayılan: 5)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "screen_awareness",
        "description": "Bilgisayar ekranında ne olduğunu yerel ve görsel modellerle analiz eder. Kullanıcı 'ekranda ne var?', 'aktif pencere ne?', 'ekranı gör/oku' dediğinde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "question": {
                    "type": "STRING",
                    "description": "Ekranla ilgili spesifik soru veya inceleme talebi"
                },
                "force_vision": {
                    "type": "BOOLEAN",
                    "description": "Derin görsel vision analizini zorunlu kıl"
                }
            }
        }
    },
    {
        "name": "computer_control",
        "description": "Masaüstünde fare, klavye, pencere ve uygulama kontrollerini gerçekleştirir. grounding_mode=true ile Gemini Vision ekrandaki hedef elemanı piksel düzeyinde otomatik bulur ve tıklar — koordinat bilmene gerek kalmaz.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "move_mouse | click | double_click | right_click | scroll | drag | type_text | press_key | hotkey | paste_text | focus_window | minimize_window | maximize_window | close_window"
                },
                "x": {"type": "NUMBER", "description": "Fare X koordinatı (grounding_mode=true ise opsiyonel)"},
                "y": {"type": "NUMBER", "description": "Fare Y koordinatı (grounding_mode=true ise opsiyonel)"},
                "text": {"type": "STRING", "description": "Yazılacak veya yapıştırılacak metin"},
                "key": {"type": "STRING", "description": "Basılacak tuş veya kısayol (örn: 'enter', 'ctrl+c', 'alt+tab', 'win+r')"},
                "target": {"type": "STRING", "description": "Hedef pencere adı veya UI elemanı açıklaması (örn: 'Tamam butonu', 'arama kutusu')"},
                "grounding_mode": {"type": "BOOLEAN", "description": "true ise Gemini Vision ile ekranda hedef eleman otomatik bulunur ve tıklanır — koordinat gerekmez"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "browser_action",
        "description": "Web tarayıcısını yönetir: URL açma, arama yapma, sayfa içeriğini okuma, yeni sekme veya geri gitme.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "open | search | read_page | new_tab | back"
                },
                "url": {"type": "STRING", "description": "Açılacak veya okunacak web adresi"},
                "query": {"type": "STRING", "description": "Arama motorunda aranacak sorgu"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "autonomous_task",
        "description": "Kullanıcının 'şunu hallet', 'araştırma moduna geç', 'şu dosyaları düzenle', 'görevi yap' gibi çok adımlı isteklerini planlar, otonom yürütür, doğrular ve tamamlandığında kullanıcıya sonuç raporu döner.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_description": {
                    "type": "STRING",
                    "description": "Görevin tam açıklaması veya araştırılacak konu"
                },
                "research_mode": {
                    "type": "BOOLEAN",
                    "description": "Çok kaynaklı araştırma modu aktif edilsin mi?"
                }
            },
            "required": ["task_description"]
        }
    },
    {
        "name": "emergency_stop",
        "description": "Devam eden tüm otonom görevleri, araştırmaları ve masaüstü otomasyonlarını derhal durdurur ve iptal eder. Kullanıcı 'Ultron dur', 'iptal et', 'stop' dediğinde kullan.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "orchestrate_task",
        "description": "Kullanıcının 'bu projeye özellik ekle', 'bu hatayı düzelt', 'bu işi başka ajana ver' gibi karmaşık yazılım mühendisliği ve çoklu ajan görevlerini orkestre eder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "task_description": {
                    "type": "STRING",
                    "description": "Görevin tam açıklaması veya yapılacak yazılım değişikliği"
                }
            },
            "required": ["task_description"]
        }
    },
    {
        "name": "code_action",
        "description": "Yazılım geliştirme, dosya yazma, syntax kontrolü ve otonom hata düzeltme (Self-Correction Loop) işlemlerini yürütür.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "write_file | execute_and_fix | validate_syntax"
                },
                "file_path": {"type": "STRING", "description": "Dosya yolu"},
                "code_content": {"type": "STRING", "description": "Yazılacak kod içeriği"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "run_tests",
        "description": "Belirtilen test dosyasını veya test paketini bağımsız Testing Agent ile çalıştırır ve detaylı rapor döner.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "test_script_path": {
                    "type": "STRING",
                    "description": "Çalıştırılacak test dosyasının yolu"
                }
            },
            "required": ["test_script_path"]
        }
    },
    {
        "name": "code_review",
        "description": "Kodu veya git diff farklarını güvenlik, mantık hataları ve regresyon açısından bağımsız Reviewer Agent ile denetler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "code_or_diff": {"type": "STRING", "description": "İncelenecek kod veya diff metni"},
                "is_diff": {"type": "BOOLEAN", "description": "İncelenen metin git diff mi?"}
            }
        }
    },
    {
        "name": "git_snapshot_rollback",
        "description": "Kod değişiklikleri öncesi anlık snapshot alır veya regresyon durumunda dosyaları geri yükler (Rollback).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create_snapshot | rollback | status | diff"
                },
                "snapshot_id": {"type": "STRING", "description": "Geri yüklenecek snapshot ID"},
                "label": {"type": "STRING", "description": "Snapshot etiketi"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "web_search",
        "description": (
            "Hızlı web araması yapar ve ilk birkaç sonucun içeriğini okur. "
            "Güncel haberler, fiyatlar, bilgiler veya belirli bir URL'nin içeriğini okumak için kullan. "
            "Örnek: 'yapay zeka haberleri', 'Python 3.12 yenilikleri', 'https://example.com'"
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Arama sorgusu veya okunacak URL adresi"
                },
                "max_chars": {
                    "type": "NUMBER",
                    "description": "Döndürülecek maksimum karakter sayısı (varsayılan: 4000)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "deep_research",
        "description": (
            "Kapsamlı çok kaynaklı araştırma yapar ve yapılandırılmış Markdown raporu üretir. "
            "Kullanıcı 'araştır', 'rapor hazırla', 'detaylı incele', 'analiz et' dediğinde kullan. "
            "Rapor otomatik olarak memory/research_reports/ dizinine kaydedilir."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Araştırılacak konu veya soru"
                },
                "topic": {
                    "type": "STRING",
                    "description": "Araştırma konusu (query ile aynı, alternatif parametre)"
                },
                "num_sources": {
                    "type": "NUMBER",
                    "description": "Okunacak kaynak sayısı (varsayılan: 5, maksimum: 10)"
                },
                "save_report": {
                    "type": "BOOLEAN",
                    "description": "Raporu dosyaya kaydet (varsayılan: true)"
                }
            },
            "required": ["query"]
        }
    }
]
