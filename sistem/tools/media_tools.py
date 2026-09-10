"""
ULTRON Medya, Ses ve Ekran Araç Tanımları
"""

MEDIA_TOOLS = [   {   'description': 'Gerçek zamanlı webcam akışını başlatır veya durdurur. Akış aktifken model '
                       "sürekli kamera görüntüsü alır — 'bak', 'gör', 'göster', 'kameraya bak', "
                       "'önümdekileri anlat', 'ne görüyorsun' gibi komutlarda 'start' kullan. "
                       "'kamerayı kapat', 'artık bakma' gibi durumlarda 'stop' kullan.",
        'name': 'toggle_webcam',
        'parameters': {   'properties': {   'action': {   'description': 'start — akışı başlat  |  '
                                                                         'stop — akışı durdur',
                                                          'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'YouTube, Spotify veya Apple Music/Music uygulamasında şarkı, müzik veya '
                       'video açar. Kullanıcı belirli bir platform söylerse onu kullan. '
                       "Belirtmezse uygun olanı dene. Kullanıcı 'çal', 'oynat', 'aç' diyorsa "
                       'autoplay=true kullan.',
        'name': 'play_media',
        'parameters': {   'properties': {   'autoplay': {   'description': 'true ise mümkünse '
                                                                           'doğrudan oynatır',
                                                            'type': 'BOOLEAN'},
                                            'provider': {   'description': 'auto | youtube | '
                                                                           'spotify | apple_music',
                                                            'type': 'STRING'},
                                            'query': {   'description': 'Şarkı, sanatçı, albüm '
                                                                        'veya video arama ifadesi',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Halihazirda calan medyayi kontrol eder: durdurur, devam ettirir, '
                       'sonraki/onceki parcaya gecer. Spotify, YouTube veya hangi oynatici '
                       "caliyorsa ona gider. Kullanici 'durdur', 'duraklat', 'sustur', 'muzigi "
                       "kapat', 'devam et', 'sonraki sarki', 'gec', 'onceki' gibi bir sey "
                       'soyledigINDE bunu kullan. Yeni bir sarki BASLATMAK icin bu araci degil '
                       "play_media'yi kullan.",
        'name': 'control_media',
        'parameters': {   'properties': {   'action': {   'description': 'pause (durdur/duraklat) '
                                                                         '| resume (devam et) | '
                                                                         'stop (tamamen durdur) | '
                                                                         'next (sonraki parca) | '
                                                                         'previous (onceki parca)',
                                                          'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'YouTube kanalinin public istatistiklerini ve son videolarin performansini '
                       'raporlar. Kullanici kanal istatistiklerini, abone sayisini, son '
                       'videolarini, buyume hizini veya YouTube analizini sordugunda kullan. Bu '
                       'arac Studio yerine public YouTube Data API verisini kullanir.',
        'name': 'get_youtube_channel_report',
        'parameters': {   'properties': {   'handle': {   'description': 'Opsiyonel kanal '
                                                                         "handle'i, kanal linki "
                                                                         "veya kanal ID'si. Bos "
                                                                         'birakilirsa ayarlardaki '
                                                                         'youtube_channel_handle '
                                                                         'kullanilir.',
                                                          'type': 'STRING'},
                                            'query': {   'description': 'Dogal dilde analiz '
                                                                        "istegi. Ornek: 'YouTube "
                                                                        "istatistiklerim nasil', "
                                                                        "'son videolarimi analiz "
                                                                        "et', 'kanal buyumemi "
                                                                        "ozetle'",
                                                         'type': 'STRING'},
                                            'video_limit': {   'description': 'Analize dahil '
                                                                              'edilecek son video '
                                                                              'sayisi. Varsayilan '
                                                                              '6.',
                                                               'type': 'NUMBER'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Aktif pencerenin ekran goruntusunu alip Gemini vision ile analiz eder. '
                       'Kullanici ekranda ne oldugunu, bir hatayi, gorunen metni, butonlari veya '
                       'pencere icerigini sordugunda kullan. Bu surum yalnizca aktif pencereyi '
                       'destekler.',
        'name': 'analyze_screen',
        'parameters': {   'properties': {   'query': {   'description': 'Kullanicinin ekranla '
                                                                        "ilgili sorusu. Ornek: 'Bu "
                                                                        "hatayi oku', 'Ekranda ne "
                                                                        "var?'",
                                                         'type': 'STRING'},
                                            'target': {   'description': 'Su an sadece '
                                                                         'active_window '
                                                                         'desteklenir.',
                                                          'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Bilgisayar ekranında ne olduğunu yerel ve görsel modellerle analiz eder. '
                       "Kullanıcı 'ekranda ne var?', 'aktif pencere ne?', 'ekranı gör/oku' "
                       'dediğinde kullan.',
        'name': 'screen_awareness',
        'parameters': {   'properties': {   'force_vision': {   'description': 'Derin görsel '
                                                                               'vision analizini '
                                                                               'zorunlu kıl',
                                                                'type': 'BOOLEAN'},
                                            'question': {   'description': 'Ekranla ilgili '
                                                                           'spesifik soru veya '
                                                                           'inceleme talebi',
                                                            'type': 'STRING'}},
                          'type': 'OBJECT'}}]
