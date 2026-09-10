"""
ULTRON Takvim ve Hatırlatıcı Araç Tanımları
"""

CALENDAR_TOOLS = [   {   'description': 'Google Takvim üzerinden bugünkü veya gelecek günlerdeki '
                       'toplantıları/etkinlikleri getirir.',
        'name': 'workspace_get_upcoming_events',
        'parameters': {   'properties': {   'days_ahead': {   'description': 'Kaç gün sonrasına '
                                                                             'kadar getirilsin? '
                                                                             '(Varsayılan: 1)',
                                                              'type': 'INTEGER'}},
                          'type': 'OBJECT'}},
    {   'description': 'Google Takvime yeni etkinlik ekler.',
        'name': 'workspace_create_event',
        'parameters': {   'properties': {   'description': {   'description': 'Etkinlik detayı',
                                                               'type': 'STRING'},
                                            'end_time': {   'description': 'Bitiş zamanı (ISO '
                                                                           '8601, örn: '
                                                                           '2026-08-28T11:00:00)',
                                                            'type': 'STRING'},
                                            'start_time': {   'description': 'Başlangıç zamanı '
                                                                             '(ISO 8601, örn: '
                                                                             '2026-08-28T10:00:00)',
                                                              'type': 'STRING'},
                                            'title': {   'description': 'Etkinlik başlığı',
                                                         'type': 'STRING'}},
                          'required': ['title', 'start_time', 'end_time'],
                          'type': 'OBJECT'}},
    {   'description': 'Apple Animsaticilar listesini okur. Bugunku, yaklasan, geciken veya tum '
                       'acik animsaticilari ozetler. Kullanici hatirlatma, animsatici, reminder '
                       'veya yapilacaklar listesini sordugunda kullan.',
        'name': 'get_reminders',
        'parameters': {   'properties': {   'limit': {   'description': 'Maksimum animsatici '
                                                                        'sayisi',
                                                         'type': 'NUMBER'},
                                            'list_name': {   'description': 'Istenirse belirli bir '
                                                                            'animsatici listesi '
                                                                            'adi',
                                                             'type': 'STRING'},
                                            'query': {   'description': 'today | upcoming | '
                                                                        'overdue | all | next',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Apple Animsaticilar uygulamasina yeni bir animsatici ekler. Kullanici '
                       "'hatirlat', 'animsatici ekle', 'reminder kur' dediginde kullan. Goreli "
                       'zaman ifadelerini bugunku tarih baglamina gore due_iso alanina ISO '
                       'formatinda cevir.',
        'name': 'add_reminder',
        'parameters': {   'properties': {   'all_day': {   'description': 'Tum gun animsatici ise '
                                                                          'true',
                                                           'type': 'BOOLEAN'},
                                            'due_iso': {   'description': 'Opsiyonel tarih/saat. '
                                                                          'Ornek: 2026-04-13T09:00 '
                                                                          'veya tum gun icin '
                                                                          '2026-04-13',
                                                           'type': 'STRING'},
                                            'list_name': {   'description': 'Opsiyonel animsatici '
                                                                            'listesi',
                                                             'type': 'STRING'},
                                            'notes': {   'description': 'Opsiyonel not',
                                                         'type': 'STRING'},
                                            'priority': {   'description': 'low | medium | high',
                                                            'type': 'STRING'},
                                            'title': {   'description': 'Animsatici basligi',
                                                         'type': 'STRING'}},
                          'required': ['title'],
                          'type': 'OBJECT'}},
    {   'description': "Proaktif geri sayım sayacı, alarm veya hatırlatıcı kurar. Kullanıcı '1 "
                       "dakika sonra bana hatırlat', '15 dk sonra fırını haber ver', 'yarın sabah "
                       "9'da alarm kur' dediğinde KESİNLİKLE bu aracı kullan. Süresi bittiğinde "
                       'sistem otomatik olarak kullanıcıya sesli ve ekrandan seslenecektir.',
        'name': 'set_proactive_timer',
        'parameters': {   'properties': {   'due_iso': {   'description': 'Belirli bir hedef '
                                                                          'saat/tarih varsa ISO '
                                                                          'formatında (örn: '
                                                                          "'14:30' veya "
                                                                          "'2026-08-17T14:30').",
                                                           'type': 'STRING'},
                                            'is_task': {   'description': 'True ise; süre '
                                                                          'dolduğunda sadece '
                                                                          'bildirim vermek yerine '
                                                                          "'title' alanındaki "
                                                                          'içeriği otonom bir Ajan '
                                                                          'Görevi (Deep Research, '
                                                                          'Mail Gönderme vb.) '
                                                                          'olarak arka planda '
                                                                          'çalıştırır.',
                                                           'type': 'BOOLEAN'},
                                            'minutes': {   'description': 'Kaç dakika sonra '
                                                                          'hatırlatılacağı (örn: '
                                                                          '1, 5, 15, 60).',
                                                           'type': 'NUMBER'},
                                            'seconds': {   'description': 'Ek saniye (örn: 30).',
                                                           'type': 'NUMBER'},
                                            'title': {   'description': 'Hatırlatılacak konu veya '
                                                                        'alarm adı. Örn: '
                                                                        "'Makarnayı ocaktan al', "
                                                                        "'Toplantıya katıl'",
                                                         'type': 'STRING'},
                                            'user': {   'description': 'Hatırlatıcının kurulduğu '
                                                                       "kişi: 'YARATICI' veya "
                                                                       "'AILE_UYESI'.",
                                                        'type': 'STRING'}},
                          'required': ['title'],
                          'type': 'OBJECT'}},
    {   'description': 'Şu anda bekleyen aktif geri sayım sayaçlarını, alarmları ve '
                       'hatırlatıcıları listeler.',
        'name': 'get_active_timers',
        'parameters': {'properties': {}, 'type': 'OBJECT'}},
    {   'description': 'Belirtilen veya tüm aktif hatırlatıcı ve sayaçları iptal eder.',
        'name': 'cancel_timer',
        'parameters': {   'properties': {   'query': {   'description': 'İptal edilecek '
                                                                        "hatırlatıcı adı, ID'si "
                                                                        "veya 'all' / 'hepsi'",
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}}]
