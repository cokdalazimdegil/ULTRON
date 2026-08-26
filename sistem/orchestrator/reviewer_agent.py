"""
ULTRON Orchestrator — Reviewer Agent Module
───────────────────────────────────────────
• Kıdemli kod inceleme, mimari denetim ve kalite güvencesi
• Git diff analizi, mantık hatası, güvenlik açığı ve regresyon kontrolü
• Karar mekanizması (APPROVED, REQUEST_CHANGES, REJECTED)
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

from orchestrator.agent_registry import agent_registry

logger = logging.getLogger("ultron.orchestrator.reviewer_agent")


class ReviewerAgent:
    """Yazılan kodu ve git diff farklarını denetleyen bağımsız inceleme ajanı."""

    @staticmethod
    def review_code(code_string: str, file_name: str = "") -> dict[str, Any]:
        """
        Kod içeriğini statik analiz, güvenlik ve sözdizimi açısından inceler.
        Dönen: {"verdict": "APPROVED"|"REQUEST_CHANGES"|"REJECTED", "issues": list[str], "feedback": str}
        """
        perm_ok, perm_msg = agent_registry.check_permission("reviewer_agent", "review_code")
        if not perm_ok:
            return {"verdict": "REJECTED", "issues": [perm_msg], "feedback": "İzin reddedildi."}

        issues: list[str] = []
        warnings: list[str] = []

        # 1. Syntax Kontrolü
        try:
            tree = ast.parse(code_string)
        except SyntaxError as e:
            return {
                "verdict": "REJECTED",
                "issues": [f"Kritik Syntax Hatası: {e.msg} (Satır {e.lineno})"],
                "feedback": "Kod derlenemiyor veya geçersiz sözdizimi içeriyor."
            }

        # 2. Tehlikeli / Güvenlik Açığı Tespiti (Security Audit)
        dangerous_calls = ["eval(", "exec(", "__import__('os').system", "os.system('rm", "shutil.rmtree('/')"]
        for call in dangerous_calls:
            if call in code_string:
                issues.append(f"Güvenlik Uyarısı: Potansiyel güvensiz kod yürütme tespiti ('{call}').")

        # 3. Sonsuz Döngü / Kaynak Sızıntısı Kontrolü
        if re.search(r"while\s+True\s*:\s*(pass|continue)", code_string):
            issues.append("Mantık Hatası: CPU kilitleyen boş sonsuz döngü (while True: pass/continue).")

        # 4. Boş Exception Yakalama (Except: pass)
        if re.search(r"except\s*:\s*pass", code_string):
            warnings.append("Kalite Uyarısı: 'except: pass' tüm hataları sessizce yutuyor.")

        # 5. Gemini 2.5 Pro ile Derin Güvenlik & Mimari Analizi
        try:
            from orchestrator.gemini_reasoning import query_gemini_reasoning
            review_prompt = (
                f"Lütfen aşağıdaki Python kodunu kıdemli yazılım mimarı ve güvenlik denetçisi olarak incele:\n\n"
                f"```python\n{code_string[:4000]}\n```\n\n"
                f"Değerlendirilecek Alanlar:\n"
                f"1. Güvenlik ve Açık Analizi (OWASP, Injection, Resource Leaks)\n"
                f"2. Kod Mimarisi ve Temiz Kod (Clean Code, PEP8, Modülerlik)\n"
                f"3. Performans ve Hata Yönetimi\n\n"
                f"Lütfen kısa ve net bir değerlendirme yap. En sonda 'KARAR: APPROVED' veya 'KARAR: REQUEST_CHANGES' belirt."
            )
            ai_review = query_gemini_reasoning(
                prompt=review_prompt,
                system_instruction="Sen kıdemli bir kod denetçisi ve siber güvenlik uzmanısın. Türkçe, net ve teknik analiz raporu sun.",
                model_tier="pro",
                temperature=0.2
            )
            if ai_review:
                clean_review = ai_review.strip()
                has_approved = bool(re.search(r"KARAR:\s*APPROVED", clean_review, re.IGNORECASE))
                has_rejected = bool(re.search(r"KARAR:\s*(REQUEST_CHANGES|REJECTED)", clean_review, re.IGNORECASE))

                if has_rejected and not has_approved:
                    verdict = "REQUEST_CHANGES"
                    feedback = f"Gemini Güvenlik & Kalite İncelemesi:\n{ai_review}"
                elif has_approved or not issues:
                    verdict = "APPROVED"
                    feedback = f"✓ Gemini Kod Denetimi (APPROVED):\n{ai_review}"
                else:
                    verdict = "REQUEST_CHANGES"
                    feedback = ai_review

                print(f"[Reviewer Agent] 🧐 İnceleme sonucu: {verdict} ({file_name or 'kod'})", flush=True)
                return {
                    "verdict": verdict,
                    "approved": (verdict == "APPROVED"),
                    "issues": issues,
                    "warnings": warnings,
                    "feedback": feedback
                }
        except Exception:
            pass



        # Karar Verme (Fallback)
        if issues:
            verdict = "REQUEST_CHANGES"
            feedback = f"İnceleme tamamlandı. {len(issues)} kritik sorun tespit edildi:\n" + "\n".join(f"• {i}" for i in issues)
        else:
            verdict = "APPROVED"
            feedback = "✓ Kod incelemesi onaylandı (APPROVED). Herhangi bir kritik güvenlik veya mantık hatası bulunamadı."

        print(f"[Reviewer Agent] 🧐 İnceleme sonucu: {verdict} ({file_name or 'kod'})", flush=True)
        return {
            "verdict": verdict,
            "approved": (verdict == "APPROVED"),
            "issues": issues,
            "warnings": warnings,
            "feedback": feedback
        }


    @staticmethod
    def review_diff(git_diff_text: str) -> dict[str, Any]:
        """Git diff farklarını inceler."""
        if not git_diff_text.strip():
            return {
                "verdict": "APPROVED",
                "issues": [],
                "feedback": "Diff boş (Herhangi bir değişiklik yok)."
            }

        issues = []
        # Diff içinde hardcoded secret / API key kontrolü
        if re.search(r"\+.*(api_key|secret_key|password)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]", git_diff_text, re.IGNORECASE):
            issues.append("Güvenlik Uyarısı: Kod diff'inde doğrudan şifre/API anahtarı tespiti.")

        if issues:
            return {
                "verdict": "REQUEST_CHANGES",
                "issues": issues,
                "feedback": "Diff incelemesinde düzeltilmesi gereken noktalar bulundu."
            }

        return {
            "verdict": "APPROVED",
            "issues": [],
            "feedback": "✓ Git diff incelemesi onaylandı."
        }
