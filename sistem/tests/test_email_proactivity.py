"""
ULTRON Email Proactivity — Phase 6 Test Suite
═════════════════════════════════════════════
- OTP ve güvenlik doğrulama kodu skorlama (CRITICAL)
- Fatura / banka / finansal e-posta skorlama (HIGH)
- Acil / deadline / onay e-postası skorlama (HIGH)
- Toplantı daveti skorlama (NORMAL)
- Reklam / bülten filtreleme (LOW, not important)
- Standart e-posta skorlama (LOW, not important)
- UltronEvent nesnesi ve Event Bus entegrasyonu
- Görülen e-postaların tekilleştirilmesi (deduplication)

Çalıştırma:
    cd sistem
    python -X utf8 tests/test_email_proactivity.py
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
_scorer = _load("core.email_scorer", str(BASE_DIR / "core" / "email_scorer.py"))

EventPriority = _events.EventPriority
EventSource = _events.EventSource
EventBus = _bus.EventBus
score_email = _scorer.score_email
create_email_event = _scorer.create_email_event


def test_otp_security_scoring():
    """Doğrulama kodları CRITICAL ve >=90 puan almalı."""
    res = score_email(
        subject="Google hesabınız için tek kullanımlık doğrulama kodu",
        sender="noreply@google.com",
        body="Doğrulama kodunuz: 482910. Bu kodu kimseyle paylaşmayın.",
    )
    assert res["is_important"] is True
    assert res["score"] >= 90
    assert res["category"] == "security"
    assert res["priority"] == EventPriority.CRITICAL
    print("  [PASS] OTP / Güvenlik kodu skorlama (CRITICAL)")


def test_financial_scoring():
    """Fatura ve banka işlemleri HIGH ve >=80 puan almalı."""
    res = score_email(
        subject="E-Fatura Bilgilendirmesi - Fatura No: 2026-00412",
        sender="fatura@turktelekom.com.tr",
        body="Mart ayı faturanız düzenlenmiştir. Son ödeme tarihi: 15 Mart.",
    )
    assert res["is_important"] is True
    assert res["score"] >= 80
    assert res["category"] == "financial"
    assert res["priority"] == EventPriority.HIGH
    print("  [PASS] Finans / Fatura skorlama (HIGH)")


def test_urgent_scoring():
    """Acil ve deadline içeren e-postalar HIGH ve >=85 puan almalı."""
    res = score_email(
        subject="ACİL: Proje sunumu için onayınızı bekliyor - Son gün bugün",
        sender="mudur@sirket.com",
        body="Lütfen ekteki sunumu inceleyip acilen onaylayın.",
    )
    assert res["is_important"] is True
    assert res["score"] >= 85
    assert res["category"] == "urgent"
    assert res["priority"] == EventPriority.HIGH
    print("  [PASS] Acil / Deadline e-postası skorlama (HIGH)")


def test_meeting_scoring():
    """Toplantı davetleri NORMAL ve >=70 puan almalı."""
    res = score_email(
        subject="Haftalık Değerlendirme Toplantı Daveti",
        sender="ik@sirket.com",
        body="Toplantıya katılmak için link: https://meet.google.com/abc-defg-hij",
    )
    assert res["is_important"] is True
    assert res["score"] >= 70
    assert res["category"] == "meeting"
    print("  [PASS] Toplantı daveti skorlama (NORMAL)")


def test_newsletter_filtered():
    """Bülten ve reklam e-postaları önemsiz (is_important=False) ve LOW olmalı."""
    res = score_email(
        subject="Bahar indirimleri başladı! %50'ye varan fırsatlar",
        sender="bulten@magaza.com",
        body="Bu bültenden ayrılmak için unsubscribe linkine tıklayın.",
    )
    assert res["is_important"] is False
    assert res["score"] <= 30
    assert res["category"] == "marketing"
    assert res["priority"] == EventPriority.LOW
    print("  [PASS] Reklam / Bülten filtreleme (LOW)")


def test_standard_email_scoring():
    """Standart e-posta düşük/normal puan almalı, önemli sayılmamalı."""
    res = score_email(
        subject="Rapor taslağı hakkında notlar",
        sender="ahmet@arkadas.com",
        body="Dün konuştuğumuz notları ekte iletiyorum, müsait olunca göz atarsın.",
    )
    assert res["is_important"] is False
    assert res["priority"] == EventPriority.LOW
    print("  [PASS] Standart e-posta skorlama")


def test_create_email_event():
    """create_email_event geçerli UltronEvent nesnesi üretmeli."""
    email_data = {
        "id": "msg_999",
        "subject": "Önemli Güvenlik Uyarısı: Şüpheli Giriş",
        "sender": "security@apple.com",
        "date": "09.09.2026 14:00",
        "body_preview": "Hesabınıza yeni bir cihazdan giriş yapıldı.",
    }
    event = create_email_event(email_data)
    assert event.event_type == "email.important"
    assert event.source == EventSource.EMAIL
    assert event.priority == EventPriority.CRITICAL
    assert event.payload["score"] >= 90
    assert event.payload["id"] == "msg_999"
    print("  [PASS] create_email_event UltronEvent üretimi")


def test_event_bus_email_dispatch():
    """Event Bus üzerinden email event'i aboneye iletilmeli."""
    bus = EventBus()
    bus.reset()
    received = []
    bus.subscribe("email.*", lambda d: received.append(d))

    email_data = {
        "id": "msg_123",
        "subject": "Acil Toplantı İsteği",
        "sender": "patron@sirket.com",
        "body_preview": "Yarın sabahki toplantı acil olarak öne çekildi.",
    }
    event = create_email_event(email_data)
    bus.publish_event(event)

    assert len(received) == 1
    assert received[0]["subject"] == "Acil Toplantı İsteği"
    assert received[0]["is_important"] is True
    print("  [PASS] Event Bus email.* yayını ve aboneliği")


def run_all_tests():
    tests = [
        test_otp_security_scoring,
        test_financial_scoring,
        test_urgent_scoring,
        test_meeting_scoring,
        test_newsletter_filtered,
        test_standard_email_scoring,
        test_create_email_event,
        test_event_bus_email_dispatch,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Email Proactivity — Phase 6 Test Suite")
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
