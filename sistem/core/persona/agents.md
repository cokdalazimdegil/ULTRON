# ULTRON — Ajan Ağı Tanımları (Agents File)
> Bu dosya Swarm içindeki her ajanın rolünü, yeteneklerini ve tetiklenme koşullarını tanımlar.
> orchestrator_engine.py bu dosyayı dinamik ajan seçimi için okuyabilir.

## Ajan Rolleri

### Orchestrator (Şef Ajan)
- **Görev:** Gelen isteği analiz eder, alt ajanlara dağıtır, sonuçları birleştirir.
- **Tetiklenme:** Her `orchestrate_task` çağrısında.
- **Araçlar:** start_swarm_project, orchestrate_task, autonomous_task

### Coding Agent (Kodlayıcı)
- **Görev:** Python, JavaScript, ve diğer dillerde kod yazar, değiştirir.
- **Tetiklenme:** Orchestrator'dan görev alır; doğrudan `code_action` ile de tetiklenir.
- **Kurallar:**
  - Değişiklik yapmadan önce mevcut kodu okur.
  - Her değişikliği minimal tutar (sadece gerekeni değiştirir).
  - Syntax doğrulaması yapar.

### Testing Agent (Test Çalıştırıcı)
- **Görev:** Yazılan kodu test eder, hataları raporlar.
- **Tetiklenme:** Coding Agent tamamladıktan sonra otomatik.
- **Araçlar:** run_tests, shell_run

### Reviewer Agent (Kod İnceleyici)
- **Görev:** Güvenlik açıkları, bellek sızıntısı ve kötü pratikleri tarar.
- **Tetiklenme:** Testing Agent başarılı olduktan sonra isteğe bağlı.
- **Araçlar:** code_review

### Research Agent (Araştırmacı)
- **Görev:** Web araştırması, döküman okuma, bilgi derleme.
- **Tetiklenme:** `autonomous_task(research_mode=true)` ile.
- **Araçlar:** web_search, deep_research, browser_action

### Terminal Agent (Sistem Uzmanı)
- **Görev:** Shell komutları, sistem yönetimi.
- **Tetiklenme:** shell_run, file_operations, sys_info gerektiren durumlarda.

## Ajan Seçim Kuralları
```
Yeni proje (>= 5 dosya değişir) → start_swarm_project
Tek modül / bug fix             → orchestrate_task
Araştırma / bilgi toplama       → autonomous_task(research_mode=true)
Belirli dosya değişikliği       → code_action
```

## Paralel Çalışma
Swarm Manager, bağımsız görevleri eş zamanlı çalıştırır. Bağımlı görevler sıralıdır.
Maksimum paralel ajan: 4
