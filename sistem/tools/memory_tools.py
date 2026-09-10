"""
ULTRON Hafıza ve Yerel RAG Araç Tanımları
"""

MEMORY_TOOLS = [   {   'description': 'Kullanıcı hakkında önemli bilgiyi kalıcı belleğe kaydeder. İsim, '
                       "tercihler, projeler, notlar vb. duyunca sessizce çağır. 'content' ile uzun "
                       'metin veya bağlam da kaydedilebilir.',
        'name': 'save_memory',
        'parameters': {   'properties': {   'category': {   'description': 'identity | preferences '
                                                                           '| projects | notes | '
                                                                           'episodic',
                                                            'type': 'STRING'},
                                            'content': {   'description': 'Uzun metin, not veya '
                                                                          'bağlam (opsiyonel — '
                                                                          'vector hafızaya '
                                                                          'kaydedilir)',
                                                           'type': 'STRING'},
                                            'key': {   'description': "Kısa anahtar (örn. 'name', "
                                                                      "'python_version')",
                                                       'type': 'STRING'},
                                            'value': {   'description': 'Kısa değer (İngilizce '
                                                                        'önerilir)',
                                                         'type': 'STRING'}},
                          'required': ['category', 'key'],
                          'type': 'OBJECT'}},
    {   'description': 'Kalıcı hafızada semantik (anlamsal) arama yapar. Tam kelimeyi bilmeden, '
                       "yakın anlamlı sorgularla da ilgili kayıtları bulur. Kullanıcı 'bunu "
                       "biliyor muydun?', 'ne kaydetmiştin?', 'bunu hatırlıyor musun?' dediğinde "
                       'veya geçmiş bilgiye ihtiyaç olduğunda kullan.',
        'name': 'search_memory',
        'parameters': {   'properties': {   'limit': {   'description': 'Döndürülecek maksimum '
                                                                        'sonuç sayısı (varsayılan: '
                                                                        '5)',
                                                         'type': 'NUMBER'},
                                            'query': {   'description': 'Aranacak konu veya soru '
                                                                        "(doğal dil). Örn: 'Python "
                                                                        "projeleri', 'aile "
                                                                        "üyeleri', 'tercihler'",
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': "Kalici hafizadaki bir kaydi siler. Kullanici 'bunu hafizandan kaldir', "
                       "'unut', 'sil' gibi bir sey derse kullan. Mumkunse category ve key ile sil; "
                       'emin degilsen match_text ile ilgili kaydi bulup kaldir.',
        'name': 'delete_memory',
        'parameters': {   'properties': {   'category': {   'description': 'Kaydin kategorisi. '
                                                                           'Ornek: notes | '
                                                                           'identity | preferences '
                                                                           '| projects',
                                                            'type': 'STRING'},
                                            'key': {   'description': 'Silinecek anahtar. Ornek: '
                                                                      'claude_limit_refresh',
                                                       'type': 'STRING'},
                                            'match_text': {   'description': 'Kaydi bulmak icin '
                                                                             'kullanilacak dogal '
                                                                             'dil parcasi. Ornek: '
                                                                             "'claude ai limit "
                                                                             "yenilenmesi'",
                                                              'type': 'STRING'}},
                          'type': 'OBJECT'}},
    {   'description': 'Yerel RAG bilgi tabanında (ChromaDB + BM25 hibrit arama) semantik arama '
                       'yapar. İndekslenmiş dokümanlar, teknik notlar, sistem mimarisi, kodlar ve '
                       'proje belgelerinde arama yapmak için doğrudan kullanılır.',
        'name': 'rag_search',
        'parameters': {   'properties': {   'limit': {   'description': 'Döndürülecek maksimum '
                                                                        'sonuç parçası sayısı '
                                                                        '(varsayılan: 3).',
                                                         'type': 'INTEGER'},
                                            'query': {   'description': 'Bilgi tabanında aranacak '
                                                                        'soru, kavram veya anahtar '
                                                                        'kelime.',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Yerel RAG bilgi tabanına yeni bir doküman, teknik not, makale veya kılavuz '
                       'indeksler. Bilginin kalıcı ve hızlı semantik olarak aranabilmesini sağlar.',
        'name': 'rag_index',
        'parameters': {   'properties': {   'category': {   'description': 'Opsiyonel kategori '
                                                                           'veya etiket (örn: '
                                                                           "'teknik', 'proje', "
                                                                           "'kisisel').",
                                                            'type': 'STRING'},
                                            'content': {   'description': 'İndekslenecek tam '
                                                                          'doküman veya not metni.',
                                                           'type': 'STRING'},
                                            'title': {   'description': 'Dokümanın başlığı veya '
                                                                        'benzersiz tanımlayıcısı '
                                                                        "(örn: 'Event Bus "
                                                                        "Dokümanı', 'API "
                                                                        "Kılavuzu').",
                                                         'type': 'STRING'}},
                          'required': ['title', 'content'],
                          'type': 'OBJECT'}}]
