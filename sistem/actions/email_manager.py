"""
ULTRON — E-Posta Okuma, Analiz & Proaktif Bildirim Modülü
─────────────────────────────────────────────────────────
1. IMAP SSL (Gmail, Outlook.com, Hotmail, Yandex, iCloud, Kurumsal E-posta)
2. Windows Outlook (COM / MAPI)
3. Akıllı Önem Filtresi & Doğrulama Kodu / Fatura / Acil E-posta Tespiti
4. Arka plan Proaktif E-Posta Takipçisi (Yeni gelen önemli mailleri haber verme)
"""

from __future__ import annotations

import email
import email.header
import imaplib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from app_config import get_app_config_value
from app_paths import data_path

SEEN_EMAILS_FILE = data_path("memory", "seen_emails.json")

# Otomatik IMAP Sunucu Eşleme
IMAP_SERVERS = {
    "gmail.com": ("imap.gmail.com", 993),
    "googlemail.com": ("imap.gmail.com", 993),
    "outlook.com": ("outlook.office365.com", 993),
    "hotmail.com": ("outlook.office365.com", 993),
    "live.com": ("outlook.office365.com", 993),
    "msn.com": ("outlook.office365.com", 993),
    "icloud.com": ("imap.mail.me.com", 993),
    "me.com": ("imap.mail.me.com", 993),
    "yandex.com": ("imap.yandex.com", 993),
    "yandex.com.tr": ("imap.yandex.com.tr", 993),
    "yahoo.com": ("imap.mail.yahoo.com", 993),
}

IMPORTANT_PATTERNS = [
    (r"(kod|kodu|doğrulama|dogrulama|onay|otp|verification|security code|passcode|şifre|parola)", "Güvenlik / Doğrulama Kodu"),
    (r"(fatura|dekont|ödeme|odeme|tahsilat|ekstre|hesap özeti|banka|kart|havale|eft|iban)", "Finans / Fatura / Banka"),
    (r"(acil|urgent|critical|önemli|onemli|asap|deadline|son gün|son gun|müdür|yonetici|direktör)", "Yüksek Öncelik / Acil"),
    (r"(bilet|rezervasyon|pnr|uçuş|ucus|otel|check-in|boarding)", "Seyahat / Rezervasyon"),
    (r"(kargo|teslimat|gönderi|sipariş|siparis|takip no|yola çıktı)", "Sipariş / Kargo"),
    (r"(toplantı|toplanti|mülakat|görüşme|interview|meeting|davet|zoom|teams|meet)", "Toplantı / Görüşme Daveti"),
]


def _decode_mime_header(header_val: str) -> str:
    if not header_val:
        return ""
    try:
        decoded_fragments = email.header.decode_header(header_val)
        parts = []
        for text, encoding in decoded_fragments:
            if isinstance(text, bytes):
                encoding = encoding or "utf-8"
                try:
                    parts.append(text.decode(encoding, errors="replace"))
                except Exception:
                    parts.append(text.decode("utf-8", errors="replace"))
            else:
                parts.append(str(text))
        return "".join(parts)
    except Exception:
        return str(header_val)


def _load_seen_emails() -> set[str]:
    try:
        if SEEN_EMAILS_FILE.exists():
            data = json.loads(SEEN_EMAILS_FILE.read_text(encoding="utf-8"))
            return set(data.get("seen_ids", []))
    except Exception:
        pass
    return set()


def _save_seen_emails(seen_ids: set[str]) -> None:
    try:
        SEEN_EMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
        valid_list = list(seen_ids)[-500:]  # son 500 ID'yi tut
        SEEN_EMAILS_FILE.write_text(json.dumps({"seen_ids": valid_list}, indent=2), encoding="utf-8")
    except Exception:
        pass


def is_important_email(subject: str, sender: str, body_preview: str = "") -> tuple[bool, str]:
    """E-postanın önemli/acil olup olmadığını ve sebebini tespit eder."""
    text_to_check = f"{subject} {sender} {body_preview}".lower()

    for pattern, reason in IMPORTANT_PATTERNS:
        if re.search(pattern, text_to_check, re.IGNORECASE):
            return True, reason

    return False, "Normal"


def _get_email_credentials() -> tuple[str, str, str, int]:
    """Yapılandırmadan e-posta bilgilerini alır."""
    user = str(get_app_config_value("email_user", "") or get_app_config_value("email_address", "") or "").strip()
    password = str(get_app_config_value("email_password", "") or get_app_config_value("email_app_password", "") or "").strip()
    server = str(get_app_config_value("email_imap_server", "") or "").strip()
    port = int(get_app_config_value("email_imap_port", 993) or 993)

    if user and not server and "@" in user:
        domain = user.split("@")[1].lower()
        if domain in IMAP_SERVERS:
            server, port = IMAP_SERVERS[domain]

    return user, password, server, port


def _fetch_from_outlook_com(limit: int = 5, query: str = "") -> list[dict]:
    """Windows Outlook Masaüstü uygulamasından (COM/MAPI) okur."""
    try:
        import win32com.client
        ol = win32com.client.Dispatch("Outlook.Application")
        ns = ol.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)  # olFolderInbox
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)

        results = []
        count = 0
        for item in items:
            if count >= limit:
                break
            try:
                # Sadece MailItem (olMailItem = 43)
                if getattr(item, "Class", 0) != 43:
                    continue

                subject = str(getattr(item, "Subject", "") or "(Konusuz)")
                sender = str(getattr(item, "SenderName", "") or getattr(item, "SenderEmailAddress", "") or "Bilinmeyen")
                unread = bool(getattr(item, "UnRead", False))
                body = str(getattr(item, "Body", "") or "")[:1500]
                rec_time = str(getattr(item, "ReceivedTime", "") or "")

                if query:
                    q_low = query.lower()
                    if q_low not in subject.lower() and q_low not in sender.lower() and q_low not in body.lower():
                        continue

                important, reason = is_important_email(subject, sender, body[:200])
                msg_id = f"ol_{getattr(item, 'EntryID', '')[:24]}"

                results.append({
                    "id": msg_id,
                    "subject": subject,
                    "sender": sender,
                    "date": rec_time,
                    "unread": unread,
                    "important": important,
                    "reason": reason,
                    "body_preview": body[:300].strip(),
                    "full_body": body,
                    "source": "Outlook",
                })
                count += 1
            except Exception:
                continue

        return results
    except Exception:
        return []


def _fetch_from_imap(limit: int = 5, query: str = "", only_unread: bool = True) -> list[dict]:
    """IMAP SSL üzerinden e-postaları çeker."""
    user, password, server, port = _get_email_credentials()
    if not user or not password or not server:
        return []

    results = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(server, port, timeout=12)
        mail.login(user, password)
        mail.select("INBOX", readonly=True)

        criteria = "UNSEEN" if only_unread and not query else "ALL"
        status, data = mail.search(None, criteria)
        if status != "OK" or not data or not data[0]:
            return []

        mail_ids = data[0].split()
        target_ids = mail_ids[-limit:] if len(mail_ids) > limit else mail_ids
        target_ids.reverse()  # En yeniden en eskiye

        for mid in target_ids:
            try:
                res, msg_data = mail.fetch(mid, "(RFC822.HEADER BODY.PEEK[TEXT])")
                if res != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_mime_header(msg.get("Subject", "(Konusuz)"))
                sender = _decode_mime_header(msg.get("From", "Bilinmeyen"))
                date_str = msg.get("Date", "")
                msg_uid = mid.decode("utf-8")

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        cdispo = str(part.get("Content-Disposition"))
                        if ctype == "text/plain" and "attachment" not in cdispo:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

                body = re.sub(r"\s+", " ", body).strip()

                if query:
                    q_low = query.lower()
                    if q_low not in subject.lower() and q_low not in sender.lower() and q_low not in body.lower():
                        continue

                important, reason = is_important_email(subject, sender, body[:250])

                results.append({
                    "id": f"imap_{msg_uid}",
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "unread": True,
                    "important": important,
                    "reason": reason,
                    "body_preview": body[:300].strip(),
                    "full_body": body[:2000],
                    "source": server,
                })
            except Exception:
                continue

    except Exception:
        pass
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except Exception:
                pass

    return results


def get_unread_emails(limit: int = 5, only_important: bool = False) -> str:
    """
    Kullanıcının gelen kutusundaki okunmamış e-postaları listeler.
    """
    user, password, server, port = _get_email_credentials()
    emails = []

    # 1. IMAP dene
    if user and password:
        emails = _fetch_from_imap(limit=limit * 2, only_unread=True)

    # 2. Outlook COM dene
    if not emails and os.name == "nt":
        emails = _fetch_from_outlook_com(limit=limit * 2)

    if not emails:
        if not user and not password:
            return (
                "E-posta hesabı henüz yapılandırılmamış. "
                "E-postalarınızı okumam için config/api_keys.json dosyasına "
                "'email_user' ve 'email_password' (veya uygulama şifresi) ekleyebilirsiniz. "
                "(Gmail, Outlook, iCloud, Hotmail ve kurumsal IMAP desteklenir.)"
            )
        return "Gelen kutunuzda okunmamış yeni e-posta bulunmuyor."

    if only_important:
        emails = [e for e in emails if e["important"]]
        if not emails:
            return "Okunmamış e-postalarınız arasında acil veya önemli bir mesaj bulunmuyor."

    display_list = emails[:limit]
    lines = [f"📬 Okunmamış E-Postalarınız ({len(display_list)} adet):"]
    for i, m in enumerate(display_list, 1):
        imp_tag = f" 🚨 [{m['reason']}]" if m["important"] else ""
        lines.append(f"{i}. Kimden: {m['sender']}\n   Konu: {m['subject']}{imp_tag}\n   Tarih: {m['date']}\n   Özet: {m['body_preview'][:120]}...\n")

    return "\n".join(lines)


def read_email_detail(index_or_query: str) -> str:
    """
    Belirli bir e-postanın tam metnini okur.
    index_or_query: 1, 2 gibi sıra numarası veya konu başlığı / gönderen adı.
    """
    user, password, server, port = _get_email_credentials()
    emails = []
    if user and password:
        emails = _fetch_from_imap(limit=10, only_unread=False)
    if not emails and os.name == "nt":
        emails = _fetch_from_outlook_com(limit=10)

    if not emails:
        return "Okunacak e-posta bulunamadı veya e-posta hesabı yapılandırılmamış."

    target_email = None
    clean = str(index_or_query).strip()

    if clean.isdigit():
        idx = int(clean) - 1
        if 0 <= idx < len(emails):
            target_email = emails[idx]
    else:
        q_low = clean.lower()
        for e in emails:
            if q_low in e["subject"].lower() or q_low in e["sender"].lower():
                target_email = e
                break

    if not target_email and emails:
        target_email = emails[0]

    if not target_email:
        return f"'{index_or_query}' ile eşleşen e-posta bulunamadı."

    imp_str = f"\nÖnem Derecesi: 🚨 {target_email['reason']}" if target_email["important"] else ""
    return (
        f"📧 E-Posta Detayı:\n"
        f"Kimden: {target_email['sender']}\n"
        f"Konu: {target_email['subject']}\n"
        f"Tarih: {target_email['date']}{imp_str}\n"
        f"─────────────────────────────────────\n"
        f"{target_email['full_body'] or target_email['body_preview']}"
    )


def search_emails(query: str, limit: int = 5) -> str:
    """
    E-postalar arasında konu, gönderen veya kelime araması yapar.
    """
    if not query:
        return "Aranacak kelime veya kişi belirtilmedi."

    user, password, server, port = _get_email_credentials()
    emails = []
    if user and password:
        emails = _fetch_from_imap(limit=15, query=query, only_unread=False)
    if not emails and os.name == "nt":
        emails = _fetch_from_outlook_com(limit=15, query=query)

    if not emails:
        return f"'{query}' ifadesiyle eşleşen e-posta bulunamadı."

    display = emails[:limit]
    lines = [f"🔍 '{query}' İçeren E-Postalar ({len(display)} adet):"]
    for i, m in enumerate(display, 1):
        lines.append(f"{i}. Kimden: {m['sender']}\n   Konu: {m['subject']}\n   Özet: {m['body_preview'][:100]}...\n")

    return "\n".join(lines)


def check_new_important_emails() -> list[dict]:
    """
    Arka plan proaktif cron servisi tarafından periyodik çağrılır.
    Henüz kullanıcıya bildirilmemiş YENİ ve ÖNEMLİ e-postaları döner.
    """
    seen = _load_seen_emails()
    user, password, server, port = _get_email_credentials()
    emails = []

    if user and password:
        emails = _fetch_from_imap(limit=6, only_unread=True)
    elif os.name == "nt":
        emails = _fetch_from_outlook_com(limit=6)

    if not emails:
        return []

    new_important = []
    for e in emails:
        eid = e.get("id") or f"{e['sender']}_{e['subject']}"
        if eid not in seen:
            seen.add(eid)
            if e["important"]:
                new_important.append(e)

    _save_seen_emails(seen)
    return new_important


def send_email(to_address: str, subject: str, body: str) -> str:
    """
    E-posta gönderir. Windows'ta Outlook varsa onu dener, yoksa SMTP ile gönderir.
    """
    if not to_address or not subject:
        return "Alıcı adresi ve konu boş olamaz."

    # 1. Outlook Masaüstü (Windows) ile Göndermeyi Dene
    if os.name == "nt":
        try:
            import win32com.client
            ol = win32com.client.Dispatch("Outlook.Application")
            msg = ol.CreateItem(0)  # olMailItem
            msg.To = to_address
            msg.Subject = subject
            msg.Body = body
            msg.Send()
            return f"✅ E-posta Outlook üzerinden başarıyla gönderildi: {to_address}"
        except Exception:
            pass

    # 2. SMTP ile Göndermeyi Dene
    user, password, server, port = _get_email_credentials()
    if not user or not password or not server:
        return "❌ E-posta gönderilemedi: E-posta hesabı yapılandırılmamış ve Outlook bulunamadı."

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_server = server.replace("imap.", "smtp.")
    smtp_port = 587

    # Bazı sunucular için özel eşlemeler
    if "outlook" in smtp_server or "office365" in smtp_server:
        smtp_server = "smtp.office365.com"
    elif "gmail" in smtp_server:
        smtp_server = "smtp.gmail.com"

    try:
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        conn = smtplib.SMTP(smtp_server, smtp_port)
        conn.starttls()
        conn.login(user, password)
        conn.send_message(msg)
        conn.quit()
        return f"✅ E-posta SMTP üzerinden başarıyla gönderildi: {to_address}"
    except Exception as e:
        return f"❌ E-posta SMTP ile gönderilirken hata oluştu: {e}"
