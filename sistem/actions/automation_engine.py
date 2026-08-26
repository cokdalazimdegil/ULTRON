"""
ULTRON Automation Engine V1
Dogal dil gorev ayrıstirici + adim yurutucu loop
"""
from __future__ import annotations

import asyncio
import re
import os
import time
import datetime
import logging
import subprocess
from pathlib import Path
from typing import Callable, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger("ultron.actions.automation_engine")


@dataclass
class AutoStep:
    index: int
    description: str
    step_type: str   # shell | file_write | web | open_app | notify | custom
    command: str = ""
    file_path: str = ""
    file_content: str = ""
    url: str = ""
    app_name: str = ""


@dataclass
class AutoTaskResult:
    task: str
    steps: List[AutoStep]
    step_results: List[str] = field(default_factory=list)
    success: bool = True
    summary: str = ""
    elapsed_sec: float = 0.0
    saved_path: str = ""


TASK_REPORTS_DIR = Path(__file__).parent.parent / "memory" / "task_reports"
TASK_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _parse_task_to_steps(task_description: str) -> List[AutoStep]:
    """Dogal dil gorevini adımlara ayırar."""
    steps = []
    idx = 0

    lines = [l.strip() for l in task_description.strip().splitlines() if l.strip()]

    for line in lines:
        line_lower = line.lower()

        # Numaralı madde temizle
        clean = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        if not clean:
            continue

        # Komut tespiti
        if any(kw in line_lower for kw in ["komut calistir", "terminal", "powershell", "shell", "cmd", "git ", "pip ", "python "]):
            cmd_match = re.search(r'["\'](.*?)["\']|:\s*(.+)$', line)
            cmd = cmd_match.group(1) or cmd_match.group(2) if cmd_match else clean
            steps.append(AutoStep(idx, clean, "shell", command=cmd.strip()))
        elif any(kw in line_lower for kw in ["dosya yaz", "dosya oluştur", "kaydet", "yaz ", "write", "create file"]):
            steps.append(AutoStep(idx, clean, "file_write", file_path="output.txt", file_content=clean))
        elif any(kw in line_lower for kw in ["http://", "https://", "web sitesi", "url", "arama yap", "ara "]):
            url_match = re.search(r'https?://\S+', line)
            url = url_match.group(0) if url_match else ""
            steps.append(AutoStep(idx, clean, "web", url=url, command=clean))
        elif any(kw in line_lower for kw in ["uygulama ac", "aç", "başlat", "open "]):
            steps.append(AutoStep(idx, clean, "open_app", app_name=clean))
        elif any(kw in line_lower for kw in ["bildirim", "haber ver", "söyle", "raporla"]):
            steps.append(AutoStep(idx, clean, "notify", command=clean))
        else:
            # Genel adım — shell komutu olarak dene
            steps.append(AutoStep(idx, clean, "custom", command=clean))
        idx += 1

    if not steps:
        steps.append(AutoStep(0, task_description, "custom", command=task_description))

    return steps


def _execute_shell_step(command: str, timeout: int = 30) -> str:
    """Bir shell komutunu güvenli bicimde calistirir."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode == 0:
            return f"✅ Başarılı\n{out}" if out else "✅ Komut tamamlandı (çıktı yok)"
        else:
            return f"⚠️ Hata kodu {result.returncode}\nSTDOUT: {out}\nSTDERR: {err}"
    except subprocess.TimeoutExpired:
        return f"⏱️ Zaman aşımı ({timeout}s): komut iptal edildi"
    except Exception as e:
        return f"❌ Yürütme hatası: {e}"


def _execute_file_write_step(file_path: str, content: str) -> str:
    try:
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        Path(file_path).write_text(content, encoding="utf-8")
        return f"✅ Dosya yazıldı: {file_path}"
    except Exception as e:
        return f"❌ Dosya yazma hatası: {e}"


def _execute_web_step(url_or_query: str) -> str:
    try:
        from actions.research_engine import simple_web_search
        return simple_web_search(url_or_query, max_chars=2000)
    except Exception as e:
        return f"❌ Web adımı hatası: {e}"


def _execute_open_app_step(app_name: str) -> str:
    try:
        from actions.open_app import open_app
        return open_app(app_name)
    except Exception as e:
        return f"❌ Uygulama açma hatası: {e}"


_DANGEROUS_PATTERNS = re.compile(
    r"\b(rm\s+-rf|del\s+/s|format\s+[a-z]:|\bdd\b|mkfs|fdisk|shutdown|halt|reboot"
    r"|taskkill\s+/f|net\s+user\s+.*\s+/delete|Remove-Item.*-Recurse.*-Force)\b",
    re.IGNORECASE
)

def _is_dangerous_command(cmd: str) -> bool:
    """Potansiyel olarak tehlikeli sistem komutlarını tespit eder."""
    return bool(_DANGEROUS_PATTERNS.search(cmd or ""))


def _gemini_fix_command(original_cmd: str, error_output: str) -> str:
    """
    Başarısız bir komutu Gemini ile düzeltmeye çalışır.
    Yeni komutu döner ya da boş string.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        try:
            from app_config import get_app_config_value
            api_key = str(get_app_config_value("gemini_api_key", "") or "")
        except Exception:
            pass
    if not api_key:
        return ""
    try:
        import google.genai as genai
        import google.genai.types as gtypes
        client = genai.Client(api_key=api_key)
        prompt = (
            f"Aşağıdaki terminal komutu hata verdi.\n\n"
            f"Komut: {original_cmd}\n\n"
            f"Hata çıktısı:\n{error_output[:800]}\n\n"
            f"Windows PowerShell için alternatif, düzeltilmiş bir komut öner. "
            f"Yalnızca tek satır komut yaz, açıklama ekleme."
        )
        resp = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=gtypes.GenerateContentConfig(temperature=0.1, max_output_tokens=200)
        )
        fixed = (resp.text or "").strip().strip("`").strip()
        # Yalnızca tek satır komut kabul et
        if "\n" in fixed:
            fixed = fixed.splitlines()[0].strip()
        return fixed if len(fixed) < 500 else ""
    except Exception as e:
        logger.warning(f"[Auto] Gemini komut düzeltme hatası: {e}")
        return ""


async def run_automation(
    task_description: str,
    output_file: str = "",
    notify_steps: bool = True,
    progress_cb: Optional[Callable[[str, str], None]] = None,
) -> AutoTaskResult:
    """
    Doğal dil görevini adımlara ayırır ve self-healing döngüsüyle yürütür.
    Her adım en fazla 3 kez denenir; hata sonrası Gemini otomatik düzeltme üretir.

    progress_cb(step_desc, step_result) çağrılır.
    """
    t0 = time.time()
    steps = _parse_task_to_steps(task_description)
    step_results = []
    all_success = True
    MAX_RETRIES = 3

    def _progress(step_desc: str, result: str):
        logger.info(f"[Auto] {step_desc} → {result[:80]}")
        if progress_cb:
            try:
                progress_cb(step_desc, result)
            except Exception:
                pass

    for step in steps:
        step_result = ""
        step_ok = False
        current_cmd = step.command

        # Tehlikeli komut güvenlik kontrolü
        if step.step_type in ("shell", "custom") and _is_dangerous_command(current_cmd):
            step_result = (
                f"⛔ GÜVENLİK ENGELİ: '{current_cmd}' komutu tehlikeli olarak işaretlendi ve çalıştırılmadı. "
                f"Silme/format/kapatma gibi yıkıcı komutlar otomatik olarak bloke edilir."
            )
            all_success = False
            step_results.append(step_result)
            _progress(step.description, step_result)
            continue

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if step.step_type == "shell":
                    step_result = _execute_shell_step(current_cmd)
                elif step.step_type == "file_write":
                    step_result = _execute_file_write_step(step.file_path, step.file_content)
                elif step.step_type == "web":
                    query = step.url or current_cmd
                    loop = asyncio.get_event_loop()
                    step_result = await loop.run_in_executor(None, _execute_web_step, query)
                elif step.step_type == "open_app":
                    step_result = _execute_open_app_step(step.app_name)
                elif step.step_type == "notify":
                    step_result = f"📢 Bildirim: {current_cmd}"
                elif step.step_type == "custom":
                    if current_cmd:
                        step_result = _execute_shell_step(current_cmd, timeout=15)
                    else:
                        step_result = f"ℹ️ Adım kaydedildi: {step.description}"

                # Başarılı mı?
                if not ("❌" in step_result or ("Hata" in step_result and "✅" not in step_result)
                        or ("⚠️" in step_result and "hata kodu" in step_result.lower())):
                    step_ok = True
                    break

                # Hata var: Gemini ile düzeltme dene (yalnızca shell/custom)
                if attempt < MAX_RETRIES and step.step_type in ("shell", "custom") and current_cmd:
                    _progress(step.description, f"⚠️ Deneme {attempt} başarısız, düzeltme deneniyor...")
                    fixed_cmd = _gemini_fix_command(current_cmd, step_result)
                    if fixed_cmd and fixed_cmd != current_cmd and not _is_dangerous_command(fixed_cmd):
                        logger.info(f"[Auto] Komut düzeltildi: '{current_cmd}' → '{fixed_cmd}'")
                        current_cmd = fixed_cmd
                    else:
                        time.sleep(0.5)

            except Exception as exc:
                step_result = f"❌ Adım istisnası: {exc}"
                if attempt < MAX_RETRIES:
                    time.sleep(0.5)

        if not step_ok:
            all_success = False

        step_results.append(step_result)
        _progress(step.description, step_result)

    # Özet rapor
    elapsed = round(time.time() - t0, 1)
    steps_summary = ""
    for i, (step, result) in enumerate(zip(steps, step_results), 1):
        icon = "✅" if "✅" in result else ("⛔" if "⛔" in result else "⚠️")
        steps_summary += f"\n### {icon} Adım {i}: {step.description}\n```\n{result[:500]}\n```\n"

    summary_md = (
        f"# Otomasyon Görevi Raporu\n"
        f"**Görev:** {task_description[:200]}\n"
        f"**Tarih:** {datetime.datetime.now().strftime('%d %B %Y %H:%M')}\n"
        f"**Durum:** {'✅ Başarıyla tamamlandı' if all_success else '⚠️ Bazı adımlar hata verdi'}\n"
        f"**Süre:** {elapsed}s | **Adım Sayısı:** {len(steps)}\n\n"
        f"## Adım Sonuçları{steps_summary}"
    )

    saved_path = ""
    if output_file:
        saved_path = output_file
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_path = str(TASK_REPORTS_DIR / f"{timestamp}_task_report.md")
    Path(saved_path).parent.mkdir(parents=True, exist_ok=True)
    Path(saved_path).write_text(summary_md, encoding="utf-8")

    return AutoTaskResult(
        task=task_description,
        steps=steps,
        step_results=step_results,
        success=all_success,
        summary=summary_md,
        elapsed_sec=elapsed,
        saved_path=saved_path,
    )


def handle_autonomous_task(args: dict) -> str:
    """autonomous_task tool icin senkron giris noktasi."""
    task = args.get("task_description", args.get("task", "")).strip()
    if not task:
        return "Hata: 'task_description' parametresi gereklidir."

    research_mode = bool(args.get("research_mode", False))
    output_file = args.get("output_file", "")
    notify_steps = bool(args.get("notify_steps", True))

    if research_mode:
        # Araştırma modunda research_engine'i kullan
        try:
            from actions.research_engine import handle_deep_research
            return handle_deep_research({"query": task, "save_report": True})
        except Exception as e:
            return f"Araştırma modu hatası: {e}"

    import threading
    result_container = {}

    def _thread_run():
        result_container["r"] = asyncio.run(
            run_automation(task, output_file=output_file, notify_steps=notify_steps)
        )

    t = threading.Thread(target=_thread_run, daemon=True)
    t.start()
    t.join(timeout=120)
    result = result_container.get("r")

    if not result:
        return "Otomasyon görevi tamamlanamadı (zaman aşımı)."

    status = "✅ Başarıyla tamamlandı" if result.success else "⚠️ Bazı adımlar hata verdi"
    return (
        f"{status} ({result.elapsed_sec}s, {len(result.steps)} adım)\n\n"
        f"{result.summary}"
        + (f"\n\n📁 Rapor: {result.saved_path}" if result.saved_path else "")
    )
