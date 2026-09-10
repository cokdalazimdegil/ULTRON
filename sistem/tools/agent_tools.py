"""
ULTRON Otonom Ajan, Swarm ve Kod Geliştirme Araç Tanımları
"""

AGENT_TOOLS = [   {   'description': "Tarayıcıda URL açar, Google'da arama yapar veya YouTube'da ilk sonucu "
                       'doğrudan oynatır.',
        'name': 'browser_control',
        'parameters': {   'properties': {   'action': {   'description': 'open_url | search | '
                                                                         'play_youtube',
                                                          'type': 'STRING'},
                                            'query': {   'description': 'Arama sorgusu (search '
                                                                        'veya play_youtube için)',
                                                         'type': 'STRING'},
                                            'url': {   'description': 'Açılacak URL (open_url '
                                                                      'için)',
                                                       'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Web tarayıcısını yönetir: URL açma, arama yapma, sayfa içeriğini okuma, '
                       'yeni sekme veya geri gitme.',
        'name': 'browser_action',
        'parameters': {   'properties': {   'action': {   'description': 'open | search | '
                                                                         'read_page | new_tab | '
                                                                         'back',
                                                          'type': 'STRING'},
                                            'query': {   'description': 'Arama motorunda aranacak '
                                                                        'sorgu',
                                                         'type': 'STRING'},
                                            'url': {   'description': 'Açılacak veya okunacak web '
                                                                      'adresi',
                                                       'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Belirtilen URL adresindeki web sayfasının veya makalenin metnini okur ve '
                       "özetler. Kullanıcı bir web linki verip 'bu sayfayı oku', 'bu makaleyi "
                       "özetle', 'bu linkte ne yazıyor' dediğinde kullan.",
        'name': 'fetch_webpage_content',
        'parameters': {   'properties': {   'url': {   'description': 'Okunacak web adresi '
                                                                      '(https://...)',
                                                       'type': 'STRING'}},
                          'required': ['url'],
                          'type': 'OBJECT'}},
    {   'description': 'Hızlı canlı web araması yapar ve ilk birkaç sonucun içeriğini okur. Güncel haberler, '
                       'yeni çıkan ürünler/teknolojiler, yazılım sürümleri, anlık fiyatlar, olgusal sorgular '
                       "veya belirli bir URL'nin içeriğini okumak için birincil canlı araştırma aracıdır.",
        'name': 'web_search',
        'parameters': {   'properties': {   'max_chars': {   'description': 'Döndürülecek maksimum '
                                                                            'karakter sayısı '
                                                                            '(varsayılan: 4000)',
                                                             'type': 'NUMBER'},
                                            'query': {   'description': 'Arama sorgusu veya '
                                                                        'okunacak URL adresi',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': 'Kapsamlı çok kaynaklı araştırma yapar ve yapılandırılmış Markdown raporu '
                       "üretir. Kullanıcı 'araştır', 'rapor hazırla', 'detaylı incele', 'analiz "
                       "et' dediğinde kullan. Rapor otomatik olarak memory/research_reports/ "
                       'dizinine kaydedilir.',
        'name': 'deep_research',
        'parameters': {   'properties': {   'num_sources': {   'description': 'Okunacak kaynak '
                                                                              'sayısı (varsayılan: '
                                                                              '5, maksimum: 10)',
                                                               'type': 'NUMBER'},
                                            'query': {   'description': 'Araştırılacak konu veya '
                                                                        'soru',
                                                         'type': 'STRING'},
                                            'save_report': {   'description': 'Raporu dosyaya '
                                                                              'kaydet (varsayılan: '
                                                                              'true)',
                                                               'type': 'BOOLEAN'},
                                            'topic': {   'description': 'Araştırma konusu (query '
                                                                        'ile aynı, alternatif '
                                                                        'parametre)',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}},
    {   'description': "Kendi İçinde 'Yazılım Şirketi' simülasyonu başlatır. (Multi-Agent Swarm) "
                       "Kullanıcı kapsamlı bir proje (örn: 'bana e-ticaret sitesi yap', 'yılan "
                       "oyunu yaz') istediğinde kullan. Sistem kendi kendine Project Manager "
                       'oluşturur ve görevi RESEARCHER, CODER, QA ajanlarına bölüştürüp otonom '
                       'yürütür.',
        'name': 'start_swarm_project',
        'parameters': {   'properties': {   'project_description': {   'description': 'Projenin '
                                                                                      'tüm '
                                                                                      'kapsamını '
                                                                                      've istenen '
                                                                                      'özellikleri '
                                                                                      'anlatan '
                                                                                      'detaylı '
                                                                                      'açıklama.',
                                                                       'type': 'STRING'}},
                          'required': ['project_description'],
                          'type': 'OBJECT'}},
    {   'description': 'Oyun veya film izlerken ekrana bakıp komik/eğlenceli sesli yorumlar yapan '
                       "'Arkadaş' modunu başlatır.",
        'name': 'start_companion_mode',
        'parameters': {'properties': {}, 'type': 'OBJECT'}},
    {   'description': "Aktif olan 'Arkadaş' (Companion) modunu kapatır.",
        'name': 'stop_companion_mode',
        'parameters': {'properties': {}, 'type': 'OBJECT'}},
    {   'description': "Kullanıcının 'şunu hallet', 'araştırma moduna geç', 'şu dosyaları "
                       "düzenle', 'görevi yap' gibi çok adımlı isteklerini planlar, otonom "
                       'yürütür, doğrular ve tamamlandığında kullanıcıya sonuç raporu döner.',
        'name': 'autonomous_task',
        'parameters': {   'properties': {   'research_mode': {   'description': 'Çok kaynaklı '
                                                                                'araştırma modu '
                                                                                'aktif edilsin mi?',
                                                                 'type': 'BOOLEAN'},
                                            'task_description': {   'description': 'Görevin tam '
                                                                                   'açıklaması '
                                                                                   'veya '
                                                                                   'araştırılacak '
                                                                                   'konu',
                                                                    'type': 'STRING'}},
                          'required': ['task_description'],
                          'type': 'OBJECT'}},
    {   'description': "Kullanıcının 'bu projeye özellik ekle', 'bu hatayı düzelt', 'bu işi başka "
                       "ajana ver' gibi karmaşık yazılım mühendisliği ve çoklu ajan görevlerini "
                       'orkestre eder.',
        'name': 'orchestrate_task',
        'parameters': {   'properties': {   'task_description': {   'description': 'Görevin tam '
                                                                                   'açıklaması '
                                                                                   'veya yapılacak '
                                                                                   'yazılım '
                                                                                   'değişikliği',
                                                                    'type': 'STRING'}},
                          'required': ['task_description'],
                          'type': 'OBJECT'}},
    {   'description': 'Yazılım geliştirme, dosya yazma, syntax kontrolü ve otonom hata düzeltme '
                       '(Self-Correction Loop) işlemlerini yürütür.',
        'name': 'code_action',
        'parameters': {   'properties': {   'action': {   'description': 'write_file | '
                                                                         'execute_and_fix | '
                                                                         'validate_syntax',
                                                          'type': 'STRING'},
                                            'code_content': {   'description': 'Yazılacak kod '
                                                                               'içeriği',
                                                                'type': 'STRING'},
                                            'file_path': {   'description': 'Dosya yolu',
                                                             'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Belirtilen test dosyasını veya test paketini bağımsız Testing Agent ile '
                       'çalıştırır ve detaylı rapor döner.',
        'name': 'run_tests',
        'parameters': {   'properties': {   'test_script_path': {   'description': 'Çalıştırılacak '
                                                                                   'test '
                                                                                   'dosyasının '
                                                                                   'yolu',
                                                                    'type': 'STRING'}},
                          'required': ['test_script_path'],
                          'type': 'OBJECT'}},
    {   'description': 'Kodu veya git diff farklarını güvenlik, mantık hataları ve regresyon '
                       'açısından bağımsız Reviewer Agent ile denetler.',
        'name': 'code_review',
        'parameters': {   'properties': {   'code_or_diff': {   'description': 'İncelenecek kod '
                                                                               'veya diff metni',
                                                                'type': 'STRING'},
                                            'is_diff': {   'description': 'İncelenen metin git '
                                                                          'diff mi?',
                                                           'type': 'BOOLEAN'}},
                          'type': 'OBJECT'}},
    {   'description': 'Kod değişiklikleri öncesi anlık snapshot alır veya regresyon durumunda '
                       'dosyaları geri yükler (Rollback).',
        'name': 'git_snapshot_rollback',
        'parameters': {   'properties': {   'action': {   'description': 'create_snapshot | '
                                                                         'rollback | status | diff',
                                                          'type': 'STRING'},
                                            'label': {   'description': 'Snapshot etiketi',
                                                         'type': 'STRING'},
                                            'snapshot_id': {   'description': 'Geri yüklenecek '
                                                                              'snapshot ID',
                                                               'type': 'STRING'}},
                          'required': ['action'],
                          'type': 'OBJECT'}},
    {   'description': 'Trendyol, Amazon, Hepsiburada gibi e-ticaret sitelerinde ürün arar, Chrome '
                       'tarayıcısında ürün sayfasını anında açar ve sepete ekleme sürecini '
                       "başlatır. Kullanıcı kameradan bir ürün gösterip 'bunu Trendyol'da ara', "
                       "'Amazon'da sepetime ekle', 'fiyatını bul', 'satın al', 'Trendyol'da aç' "
                       "dediğinde KESİNLİKLE bu aracı çağır. Asla 'yeteneğim yok' veya 'hesabına "
                       "erişemem' deme, derhal bu aracı çalıştır.",
        'name': 'shopping_action',
        'parameters': {   'properties': {   'add_to_cart': {   'description': 'Kullanıcı sepete '
                                                                              'ekle veya satın al '
                                                                              'dediyse true, '
                                                                              'sadece arama ve '
                                                                              'sayfayı açma '
                                                                              'istediyse false',
                                                               'type': 'BOOLEAN'},
                                            'platform': {   'description': 'trendyol | amazon | '
                                                                           'hepsiburada | auto '
                                                                           '(varsayılan: auto)',
                                                            'type': 'STRING'},
                                            'product_name': {   'description': 'Kamerada görünen '
                                                                               'veya kullanıcının '
                                                                               'aramak istediği '
                                                                               'ürünün adı / '
                                                                               "tanımı (örn: 'su "
                                                                               "şişesi', 'mavi "
                                                                               "tükenmez kalem', "
                                                                               "'kablosuz "
                                                                               "kulaklık')",
                                                                'type': 'STRING'}},
                          'required': ['product_name'],
                          'type': 'OBJECT'}},
    {   'description': "ULTRON'un otonom derin akıl yürütme, mimari analiz ve stratejik araştırma beynine danışır (OpenClaw & Hibrit Motor). "
                       "Kullanıcı karmaşık teknik mimari analiz, çok adımlı problem çözme, kodlama stratejileri, "
                       "derinlemesine sentez veya 'OpenClaw ne düşünüyor', 'analiz et' dediğinde bu aracı çağır.",
        'name': 'ask_openclaw_brain',
        'parameters': {   'properties': {   'query': {   'description': 'Stratejik olarak analiz edilecek veya araştırılacak konu/talimat.',
                                                         'type': 'STRING'}},
                          'required': ['query'],
                          'type': 'OBJECT'}}]
