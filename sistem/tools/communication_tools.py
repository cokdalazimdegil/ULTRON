"""
ULTRON İletişim Araç Tanımları (Telefon, WhatsApp, E-Posta)
"""

COMMUNICATION_TOOLS = [   {   'description': 'Kullanıcıyı doğrudan cebindeki numaradan (Twilio GSM) arar ve ilettiğin '
                       'mesajı sesli olarak okur.',
        'name': 'trigger_phone_call',
        'parameters': {   'properties': {   'message': {   'description': 'Kullanıcı telefonu '
                                                                          'açtığında sesli olarak '
                                                                          'okunacak mesaj.',
                                                           'type': 'STRING'}},
                          'required': ['message'],
                          'type': 'OBJECT'}},
    {   'description': 'Google Workspace üzerinden e-postaları arar (Gmail query syntax '
                       "destekler). Örn: 'is:unread', 'from:patron@sirket.com'.",
        'name': 'workspace_search_emails',
        'parameters': {   'properties': {   'max_results': {   'description': 'Maksimum e-posta '
                                                                              'sayısı',
                                                               'type': 'INTEGER'},
                                            'query': {   'description': 'Gmail arama sorgusu',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Belirli bir e-postanın gövdesini (snippet veya detay) okur.',
        'name': 'workspace_read_email',
        'parameters': {   'properties': {   'message_id': {   'description': 'Okunacak e-postanın '
                                                                             "message ID'si",
                                                              'type': 'STRING'}},
                          'required': ['message_id'],
                          'type': 'OBJECT'}},
    {   'description': 'Gmail üzerinden e-posta taslağı oluşturur veya gönderir.',
        'name': 'workspace_draft_email',
        'parameters': {   'properties': {   'body': {   'description': 'E-posta içeriği',
                                                        'type': 'STRING'},
                                            'is_draft': {   'description': 'Taslak olarak kalsın '
                                                                           'mı? (Varsayılan: True)',
                                                            'type': 'BOOLEAN'},
                                            'subject': {'description': 'Konu', 'type': 'STRING'},
                                            'to': {   'description': 'Alıcı e-posta adresi',
                                                      'type': 'STRING'}},
                          'required': ['to', 'subject', 'body'],
                          'type': 'OBJECT'}},
    {   'description': 'WhatsApp Desktop veya WhatsApp Web üzerinden mesaj taslağı açar veya '
                       'mesajı gönderir. Kişi adı veya telefon numarasıyla çalışabilir. Telefon '
                       'numarası verilmemişse kişi adını önce kayıtlı WhatsApp kişileri ve içe '
                       "aktarılan telefon rehberinde ara. Kullanıcı 'gönder', 'yolla', 'ile', "
                       "'hemen gönder' gibi açık bir gönderme niyeti söylüyorsa ekstra onay "
                       "istemeden send_now=true kullan. Yalnızca 'hazırla', 'taslak aç', 'yaz ama "
                       "gönderme' diyorsa send_now=false kullan.",
        'name': 'send_whatsapp_message',
        'parameters': {   'properties': {   'app_target': {   'description': 'desktop | web | '
                                                                             'auto. Varsayılan '
                                                                             'auto, tercihen '
                                                                             'desktop.',
                                                              'type': 'STRING'},
                                            'message': {   'description': 'Gönderilecek mesaj '
                                                                          'içeriği',
                                                           'type': 'STRING'},
                                            'phone_number': {   'description': 'Uluslararası '
                                                                               'telefon numarası. '
                                                                               'Örn: +905551112233',
                                                                'type': 'STRING'},
                                            'recipient_name': {   'description': 'Kişi adı. Örn: '
                                                                                 "'Anne', 'Ahmet', "
                                                                                 "'Ece'",
                                                                  'type': 'STRING'},
                                            'send_now': {   'description': 'true ise sohbet '
                                                                           'açıldıktan sonra '
                                                                           'mesajı otomatik '
                                                                           'gönderir',
                                                            'type': 'BOOLEAN'}},
                          'required': ['message'],
                          'type': 'OBJECT'}},
    {   'description': 'Sık kullanılan bir WhatsApp kişisini adı ve telefon numarasıyla kalıcı '
                       "belleğe kaydeder. Kullanıcı bir kişiyi 'annem', 'Ahmet', 'iş ortağım' gibi "
                       'tekrar kullanılacak şekilde tanımladığında kullan.',
        'name': 'save_whatsapp_contact',
        'parameters': {   'properties': {   'aliases': {   'description': 'Virgülle ayrılmış '
                                                                          'alternatif hitaplar. '
                                                                          "Örn: 'anne, annem, mom'",
                                                           'type': 'STRING'},
                                            'display_name': {   'description': 'Kaydedilecek kişi '
                                                                               "adı. Örn: 'Annem', "
                                                                               "'Ahmet'",
                                                                'type': 'STRING'},
                                            'phone_number': {   'description': 'Uluslararası '
                                                                               'telefon numarası. '
                                                                               'Örn: +905551112233',
                                                                'type': 'STRING'}},
                          'required': ['display_name', 'phone_number'],
                          'type': 'OBJECT'}},
    {   'description': 'Belirtilen alıcıya e-posta gönderir.',
        'name': 'send_email',
        'parameters': {   'properties': {   'body': {   'description': 'E-postanın metin içeriği.',
                                                        'type': 'STRING'},
                                            'subject': {   'description': 'E-postanın konusu.',
                                                           'type': 'STRING'},
                                            'to_address': {   'description': 'Alıcının e-posta '
                                                                             'adresi.',
                                                              'type': 'STRING'}},
                          'required': ['to_address', 'subject', 'body'],
                          'type': 'OBJECT'}},
    {   'description': 'Kullanıcının yazım tarzını taklit ederek gelen bir mesaja yanıt TASLAĞI '
                       'üretir. Asla otomatik göndermez — kullanıcı onayı gerektirir. WhatsApp, '
                       'e-posta veya Discord mesajlarına klon yanıt taslağı hazırlar.',
        'name': 'draft_reply',
        'parameters': {   'properties': {   'original_message': {   'description': 'Yanıt '
                                                                                   'verilecek '
                                                                                   'orijinal mesaj',
                                                                    'type': 'STRING'},
                                            'platform': {   'description': 'Mesajın geldiği '
                                                                           'platform (whatsapp, '
                                                                           'email, discord, genel)',
                                                            'type': 'STRING'},
                                            'sender_name': {   'description': 'Mesajı gönderen '
                                                                              'kişinin adı',
                                                               'type': 'STRING'}},
                          'required': ['original_message'],
                          'type': 'OBJECT'}}]
