"""
ULTRON Memory Consolidation & Local RAG — Phase 7 & 8 Test Suite
═════════════════════════════════════════════════════════════════
- UnifiedMemory: Kaydetme, alma, güncelleme ve silme (CRUD)
- UnifiedMemory: Katman bazlı gruplama (USER_PROFILE, SEMANTIC)
- UnifiedMemory: Arama ve LLM prompt formatlama
- UnifiedMemory: Event Bus memory.updated entegrasyonu
- LocalRAG: Sliding window metin parçalama (chunking)
- LocalRAG: Doküman indeksleme ve metadata saklama
- LocalRAG: Semantik / anahtar kelime arama ve skorlama
- LocalRAG: LLM bağlam formatlama (format_context_for_llm)
- LocalRAG: Event Bus rag.indexed ve rag.query entegrasyonu

Çalıştırma:
    cd sistem
    python -X utf8 tests/test_memory_and_rag.py
"""

import sys
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))

import importlib.util

def _load(name, fp):
    spec = importlib.util.spec_from_file_location(name, fp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_events = _load("core.events", str(BASE_DIR / "core" / "events.py"))
_bus = _load("core.event_bus", str(BASE_DIR / "core" / "event_bus.py"))
_unified_mem = _load("core.unified_memory", str(BASE_DIR / "core" / "unified_memory.py"))
_rag = _load("core.local_rag_engine", str(BASE_DIR / "core" / "local_rag_engine.py"))

EventBus = _bus.EventBus
UnifiedMemoryEngine = _unified_mem.UnifiedMemoryEngine
MemoryTier = _unified_mem.MemoryTier
LocalRagEngine = _rag.LocalRagEngine


def test_unified_memory_crud():
    """UnifiedMemory kaydetme, getirme ve silme işlemleri."""
    mem = UnifiedMemoryEngine()
    mem.reset()

    # Kaydet
    mem.store("preferences", "theme", "cyberpunk_dark", importance=0.9)
    assert mem.get("preferences", "theme") == "cyberpunk_dark"

    # Güncelle
    mem.store("preferences", "theme", "ultron_red", importance=0.95)
    assert mem.get("preferences", "theme") == "ultron_red"

    # Sil
    assert mem.delete("preferences", "theme") is True
    assert mem.get("preferences", "theme") is None
    print("  [PASS] UnifiedMemory CRUD (Store, Get, Update, Delete)")


def test_unified_memory_tier_assignment():
    """Kategoriye göre doğru MemoryTier atanmalı."""
    mem = UnifiedMemoryEngine()
    mem.reset()

    rec_user = mem.store("identity", "creator", "Nuri", importance=1.0)
    assert rec_user.tier == MemoryTier.USER_PROFILE

    rec_sem = mem.store("notes", "project_goal", "Autonomous AI", importance=0.8)
    assert rec_sem.tier == MemoryTier.SEMANTIC
    print("  [PASS] UnifiedMemory katman ataması (USER_PROFILE vs SEMANTIC)")


def test_unified_memory_search():
    """Hafıza araması alakalı kayıtları doğru skorlamalı."""
    mem = UnifiedMemoryEngine()
    mem.reset()

    mem.store("preferences", "editor", "VS Code")
    mem.store("preferences", "browser", "Chrome")
    mem.store("projects", "ultron", "Ultron yapay zeka asistanı")

    results = mem.search("editor tercihi", limit=2)
    assert len(results) > 0
    assert results[0]["key"] == "editor"
    assert results[0]["value"] == "VS Code"
    print("  [PASS] UnifiedMemory arama motoru")


def test_unified_memory_format_prompt():
    """format_for_prompt LLM bağlam metnini doğru üretmeli."""
    mem = UnifiedMemoryEngine()
    mem.reset()

    mem.store("identity", "name", "Ultron")
    mem.store("preferences", "language", "Turkish")

    prompt_text = mem.format_for_prompt()
    assert "[ULTRON HAFIZA BAĞLAMI]" in prompt_text
    assert "language: Turkish" in prompt_text
    print("  [PASS] UnifiedMemory LLM prompt formatı")


def test_unified_memory_event_bus():
    """Hafıza güncellendiğinde Event Bus'a memory.updated yayınlanmalı."""
    mem = UnifiedMemoryEngine()
    mem.reset()
    bus = EventBus()
    bus.reset()
    mem._bus = bus

    events = []
    bus.subscribe("memory.updated", lambda d: events.append(d))

    mem.store("facts", "earth", "blue_planet")
    assert len(events) == 1
    assert events[0]["category"] == "facts"
    assert events[0]["key"] == "earth"
    print("  [PASS] UnifiedMemory Event Bus entegrasyonu")


def test_rag_chunking():
    """Metin parçalama örtüşme ile doğru çalışmalı."""
    rag = LocalRagEngine()
    text = "A" * 900
    chunks = rag.chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) == 3
    assert len(chunks[0]) == 400
    print("  [PASS] LocalRAG sliding window metin parçalama")


def test_rag_indexing_and_search():
    """Doküman indekslenmeli ve sorgu ile geri çağrılabilmeli."""
    rag = LocalRagEngine()
    rag.reset()

    doc_text = (
        "ULTRON mimarisinde Event Bus asenkron ve tipli event yapısına sahiptir. "
        "Wildcard dinleyiciler sayesinde camera.* ve user.* gibi event grupları "
        "kolayca yakalanabilir. NotificationEngine bu event'leri çoklu kanallara dağıtır."
    )
    chunk_ids = rag.index_document("Event Bus Mimarisi", doc_text, doc_id="doc_eventbus")
    assert len(chunk_ids) > 0

    # Arama yap
    results = rag.search("Wildcard dinleyiciler ve Event Bus", limit=2)
    assert len(results) > 0
    assert "Event Bus" in results[0].text
    print("  [PASS] LocalRAG doküman indeksleme ve arama")


def test_rag_context_formatting():
    """format_context_for_llm bağlam başlıklarını ve metnini içermeli."""
    rag = LocalRagEngine()
    rag.reset()

    rag.index_document("Güvenlik Protokolü", "ULTRON API token doğrulaması zorunludur.", doc_id="sec_doc")
    context = rag.format_context_for_llm("API token doğrulaması")

    assert "[YEREL BİLGİ TABANI (RAG) BAĞLAMI]" in context
    assert "Güvenlik Protokolü" in context
    assert "token" in context
    print("  [PASS] LocalRAG LLM bağlam metni formatlama")


def test_rag_event_bus():
    """İndeksleme ve sorguda Event Bus event'leri fırlatılmalı."""
    rag = LocalRagEngine()
    rag.reset()
    bus = EventBus()
    bus.reset()
    rag._bus = bus

    indexed_events = []
    query_events = []
    bus.subscribe("rag.indexed", lambda d: indexed_events.append(d))
    bus.subscribe("rag.query", lambda d: query_events.append(d))

    rag.index_document("Test Doc", "Test içerik metni.")
    assert len(indexed_events) == 1

    rag.search("Test")
    assert len(query_events) == 1
    print("  [PASS] LocalRAG Event Bus rag.indexed ve rag.query")


def run_all_tests():
    tests = [
        test_unified_memory_crud,
        test_unified_memory_tier_assignment,
        test_unified_memory_search,
        test_unified_memory_format_prompt,
        test_unified_memory_event_bus,
        test_rag_chunking,
        test_rag_indexing_and_search,
        test_rag_context_formatting,
        test_rag_event_bus,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Memory Consolidation & Local RAG — Phase 7 & 8 Test Suite")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {test.__name__}: {e}")

    print("\n" + "-" * 60)
    print(f"  Sonuç: {passed} PASSED, {failed} FAILED / {len(tests)} toplam")
    print("-" * 60 + "\n")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
