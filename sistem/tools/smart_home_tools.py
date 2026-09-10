"""
ULTRON Akıllı Ev (Home Assistant) Araç Tanımları
"""

SMART_HOME_TOOLS = [   {   'description': 'Akıllı ev cihazlarını (Home Assistant / Işıklar / Prizler / Termostat / '
                       "Sahneler) kontrol eder. Kullanıcı 'ışıkları kapat', 'salonu aç', 'klimayı "
                       "22 derece yap', 'film modunu aç' dediğinde kullan.",
        'name': 'control_home_device',
        'parameters': {   'properties': {   'action': {   'description': 'turn_on | turn_off | '
                                                                         'toggle | set_temperature '
                                                                         '| activate_scene',
                                                          'type': 'STRING'},
                                            'brightness': {   'description': 'Işık parlaklık '
                                                                             'yüzdesi (%0 - 100)',
                                                              'type': 'NUMBER'},
                                            'device_name': {   'description': 'Cihaz veya oda adı. '
                                                                              "Örn: 'salon ışığı', "
                                                                              "'çalışma masası', "
                                                                              "'klima', 'yatak "
                                                                              "odası prizi'",
                                                               'type': 'STRING'},
                                            'temperature': {   'description': 'Klima/Termostat '
                                                                              'hedef sıcaklık '
                                                                              'derecesi (örn. '
                                                                              '22.5)',
                                                               'type': 'NUMBER'}},
                          'required': ['device_name'],
                          'type': 'OBJECT'}},
    {   'description': 'Akıllı ev durumunu ve odalardaki açık ışıkları, cihazları sorgular. '
                       "Kullanıcı 'evde açık ışık var mı', 'akıllı ev durumu nasıl' gibi sorular "
                       'sorduğunda kullan.',
        'name': 'get_home_status',
        'parameters': {   'properties': {   'query': {   'description': "Sorgu tipi. Örn: 'all' "
                                                                        "veya 'lights'",
                                                         'type': 'STRING'}},
                          'type': 'OBJECT'}}]
