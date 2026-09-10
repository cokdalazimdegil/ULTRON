"""
ULTRON Sistem ve Otomasyon Araç Tanımları (Shell, Uygulamalar, Teşhis, Geofence)
"""

SYSTEM_TOOLS = [   {   'description': "macOS'ta herhangi bir uygulamayı açar. Spotify, Safari, Terminal, Finder, "
                       'VS Code vb.',
        'name': 'open_app',
        'parameters': {   'properties': {   'app_name': {   'description': 'Uygulama adı (örn. '
                                                                           "'Spotify', 'Safari', "
                                                                           "'Terminal')",
                                                            'type': 'STRING'}},
                          'required': ['app_name'],
                          'type': 'OBJECT'}},
    {   'description': 'Sistem bilgisi alır: pil durumu, CPU, RAM, disk, saat, tarih, ağ '
                       'bağlantısı.',
        'name': 'sys_info',
        'parameters': {   'properties': {   'query': {   'description': 'battery | cpu | ram | '
                                                                        'disk | time | date | '
                                                                        'network | all',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Anlik hava durumunu ozetler. Konum verilmezse kullanicinin BULUNDUGU sehir '
                       'otomatik tespit edilir. Kullanici hava durumunu, sicakligi veya yagmur '
                       'durumunu sordugunda kullan.',
        'name': 'get_weather',
        'parameters': {   'properties': {   'location': {   'description': 'Sehir veya konum. Bos '
                                                                           'birakilirsa Istanbul '
                                                                           'kullanilir.',
                                                            'type': 'STRING'}},
                          'type': 'OBJECT'}},
    {   'description': 'Bilgisayar terminalinde PowerShell, Cmd veya bash komutları çalıştırır. '
                       'Dosya yönetimi, git işlemleri, python/node betikleri, ağ ve sistem '
                       'durumunu sorgulama, paket yükleme veya komut çalıştırmak istediğinde '
                       "doğrudan kullan. ÖNEMLİ: Bu aracı çağırırken kullanıcıya 'onaylıyor "
                       "musunuz' veya 'çalıştırayım mı' diye sorma; aracı çağırdığın an komut "
                       'anında yürütülür. Standart komutları doğrudan çalıştır. Yalnızca kritik ve '
                       'sistemi çökertebilecek tehlikeli komutlarda bu aracı çağırmadan önce sözlü '
                       'onay iste.',
        'name': 'shell_run',
        'parameters': {   'properties': {   'command': {   'description': 'Çalıştırılacak terminal '
                                                                          '/ PowerShell komutu. '
                                                                          "Örn: 'dir', 'git "
                                                                          "status', 'python "
                                                                          "--version', 'ipconfig'",
                                                           'type': 'STRING'},
                                            'cwd': {   'description': 'Komutun çalıştırılacağı '
                                                                      'dizin yolu (opsiyonel).',
                                                       'type': 'STRING'}},
                          'required': ['command'],
                          'type': 'OBJECT'}},
    {   'description': 'Windows/macOS sistem donanım ayarlarını kontrol eder: ses seviyesi '
                       'ayarlama, sesi artırma/azaltma, sessize alma (mute), ekran parlaklığı '
                       "ayarlama, ekranı kilitleme ve uyku moduna alma. Kullanıcı 'sesi kıs', "
                       "'sesi %70 yap', 'sustur', 'parlaklığı düşür', 'bilgisayarı kilitle' "
                       'dediğinde kullan.',
        'name': 'control_system',
        'parameters': {   'properties': {   'action': {   'description': 'volume_set | volume_up | '
                                                                         'volume_down | mute | '
                                                                         'brightness_set | '
                                                                         'lock_screen | sleep',
                                                          'type': 'STRING'},
                                            'value': {   'description': 'İşlem değeri. Örneğin '
                                                                        'volume_set veya '
                                                                        'brightness_set için 0-100 '
                                                                        'arası sayı.',
                                                         'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Dosya ve dizin yönetimi yapar: dosya içeriğini okur (read), dosya '
                       'oluşturur veya üzerine yazar (write), dosyaya metin ekler (append), klasör '
                       "içeriğini listeler (list) veya dosya arar (search). Kullanıcı 'şu dosyayı "
                       "oku', 'kod yaz ve dosyaya kaydet', 'klasördekileri listele' dediğinde "
                       'doğrudan çalıştır; gereksiz teyit sorma.',
        'name': 'file_operations',
        'parameters': {   'properties': {   'action': {   'description': 'read | write | append | '
                                                                         'list | search',
                                                          'type': 'STRING'},
                                            'content': {   'description': 'Dosyaya yazılacak veya '
                                                                          'eklenecek metin/kod '
                                                                          '(write ve append için).',
                                                           'type': 'STRING'},
                                            'path': {   'description': 'Hedef dosya veya klasör '
                                                                       'yolu. Örn: '
                                                                       "'C:/Users/.../test.py' "
                                                                       "veya 'proje/main.js'",
                                                        'type': 'STRING'},
                                            'search_query': {   'description': 'Dosya arama '
                                                                               'ifadesi (search '
                                                                               'için).',
                                                                'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Sistem panosunu (clipboard) okur veya panoya metin/kod kopyalar. Kullanıcı '
                       "'panomda ne var', 'bunu panoma kopyala', 'panoyu oku' dediğinde kullan.",
        'name': 'clipboard_control',
        'parameters': {   'properties': {   'action': {   'description': 'get (panodaki metni oku) '
                                                                         '| set (panoya kopyala)',
                                                          'type': 'STRING'},
                                            'text': {   'description': 'Panoya kopyalanacak metin '
                                                                       '(set için).',
                                                        'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Google Drive üzerinde dosya arar.',
        'name': 'workspace_search_drive',
        'parameters': {   'properties': {   'mime_type': {   'description': 'Opsiyonel. Örn: '
                                                                            "'application/vnd.google-apps.document'",
                                                             'type': 'STRING'},
                                            'name_query': {   'description': 'Dosya adı sorgusu',
                                                              'type': 'STRING'}},
                          'required': ['name_query'],
                          'type': 'OBJECT'}},
    {   'description': "Google Drive'daki bir dosyanın veya dökümanın içeriğini okur.",
        'name': 'workspace_read_drive_file',
        'parameters': {   'properties': {   'file_id': {   'description': "Drive dosya ID'si",
                                                           'type': 'STRING'}},
                          'required': ['file_id'],
                          'type': 'OBJECT'}},
    {   'description': "Yerel bilgisayardaki bir dosyayı Google Drive'a yükler.",
        'name': 'workspace_upload_drive',
        'parameters': {   'properties': {   'file_path': {   'description': 'Yüklenecek yerel '
                                                                            'dosyanın tam yolu',
                                                             'type': 'STRING'}},
                          'required': ['file_path'],
                          'type': 'OBJECT'}},
    {   'description': 'Masaüstünde fare, klavye, pencere ve uygulama kontrollerini '
                       'gerçekleştirir. grounding_mode=true ile Gemini Vision ekrandaki hedef '
                       'elemanı piksel düzeyinde otomatik bulur ve tıklar — koordinat bilmene '
                       "gerek kalmaz. Bu aracı çağırırken kullanıcıya 'onaylıyor musunuz' diye "
                       'sorma, doğrudan yürüt.',
        'name': 'computer_control',
        'parameters': {   'properties': {   'action': {   'description': 'move_mouse | click | '
                                                                         'double_click | '
                                                                         'right_click | scroll | '
                                                                         'drag | type_text | '
                                                                         'press_key | hotkey | '
                                                                         'paste_text | '
                                                                         'focus_window | '
                                                                         'minimize_window | '
                                                                         'maximize_window | '
                                                                         'close_window',
                                                          'type': 'STRING'},
                                            'grounding_mode': {   'description': 'true ise Gemini '
                                                                                 'Vision ile '
                                                                                 'ekranda hedef '
                                                                                 'eleman otomatik '
                                                                                 'bulunur ve '
                                                                                 'tıklanır — '
                                                                                 'koordinat '
                                                                                 'gerekmez',
                                                                  'type': 'BOOLEAN'},
                                            'key': {   'description': 'Basılacak tuş veya kısayol '
                                                                      "(örn: 'enter', 'ctrl+c', "
                                                                      "'alt+tab', 'win+r')",
                                                       'type': 'STRING'},
                                            'target': {   'description': 'Hedef pencere adı veya '
                                                                         'UI elemanı açıklaması '
                                                                         "(örn: 'Tamam butonu', "
                                                                         "'arama kutusu')",
                                                          'type': 'STRING'},
                                            'text': {   'description': 'Yazılacak veya '
                                                                       'yapıştırılacak metin',
                                                        'type': 'STRING'},
                                            'x': {   'description': 'Fare X koordinatı '
                                                                    '(grounding_mode=true ise '
                                                                    'opsiyonel)',
                                                     'type': 'NUMBER'},
                                            'y': {   'description': 'Fare Y koordinatı '
                                                                    '(grounding_mode=true ise '
                                                                    'opsiyonel)',
                                                     'type': 'NUMBER'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Devam eden tüm otonom görevleri, araştırmaları ve masaüstü otomasyonlarını '
                       "derhal durdurur ve iptal eder. Kullanıcı 'Ultron dur', 'iptal et', 'stop' "
                       'dediğinde kullan.',
        'name': 'emergency_stop',
        'parameters': {'properties': {}, 'type': 'OBJECT'}},
    {   'description': 'ULTRON System Doctor teşhis motorunu çalıştırır. Python sürümü, paket '
                       'bağımlılıkları, portlar, API anahtarı ve 9 çekirdek modülün sağlık '
                       'durumunu denetleyip tam teşhis raporu döner.',
        'name': 'run_system_diagnostics',
        'parameters': {'properties': {}, 'type': 'OBJECT'}},
    {   'description': 'ULTRON çok kanallı bildirim motoru (web_ui, gemini, tts, ha) üzerinden '
                       'öncelikli sistem bildirimi gönderir.',
        'name': 'send_system_notification',
        'parameters': {   'properties': {   'message': {   'description': 'Bildirim mesaj içeriği.',
                                                           'type': 'STRING'},
                                            'priority': {   'description': 'low | normal | high | '
                                                                           'critical (varsayılan: '
                                                                           'normal)',
                                                            'type': 'STRING'},
                                            'title': {   'description': 'Bildirim başlığı.',
                                                         'type': 'STRING'}},
                          'required': ['title', 'message'],
                          'type': 'OBJECT'}},
    {   'description': "YARATICI ve AILE_UYESI'nın anlık canlı GPS konumlarını, adreslerini ve "
                       "aralarındaki mesafeyi sorgular. Kullanıcı 'ben neredeyim', 'AILE_UYESI "
                       "nerede', 'AILE_UYESI'nın konumu ne', 'aramızda ne kadar mesafe var' "
                       'dediğinde kullan.',
        'name': 'get_user_location',
        'parameters': {   'properties': {   'user_name': {   'description': "'all' (ikisi birden "
                                                                            've mesafe) | '
                                                                            "'YARATICI' | "
                                                                            "'AILE_UYESI'",
                                                             'type': 'STRING'}},
                          'type': 'OBJECT'}},
    {   'description': 'Kullanıcının coğrafi sınırlarını (ev, ofis vb. geofence alanları) '
                       'listeler, yeni bölge ekler veya mevcut bir bölgeyi siler.',
        'name': 'manage_geofence',
        'parameters': {   'properties': {   'action': {   'description': 'list (bölgeleri listele) '
                                                                         '| add (yeni bölge ekle) '
                                                                         '| remove (bölgeyi sil)',
                                                          'type': 'STRING'},
                                            'latitude': {   'description': 'Bölgenin GPS enlem '
                                                                           'değeri (add için).',
                                                            'type': 'NUMBER'},
                                            'longitude': {   'description': 'Bölgenin GPS boylam '
                                                                            'değeri (add için).',
                                                             'type': 'NUMBER'},
                                            'name': {   'description': "Bölge adı (örn: 'Ev', "
                                                                       "'Ofis', 'Garaj').",
                                                        'type': 'STRING'},
                                            'radius_meters': {   'description': 'Bölge yarıçapı '
                                                                                'metre cinsinden '
                                                                                '(varsayılan: '
                                                                                '150.0).',
                                                                 'type': 'NUMBER'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Kullanıcının anlık varlık durumunu (UNKNOWN, PERSON_DETECTED, '
                       'USER_PRESENT, USER_AWAY, USER_LEFT), son görülme zamanını ve sistem '
                       'karşılama durumunu raporlar.',
        'name': 'get_presence_status',
        'parameters': {'properties': {}, 'type': 'OBJECT'}}]
