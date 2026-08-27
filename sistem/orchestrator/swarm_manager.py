"""
ULTRON Multi-Agent Swarm Orchestrator (Yazılım Şirketi Simülasyonu)
─────────────────────────────────────────────────────────────────
• Project Manager (PM) ajanı görevi analiz edip alt görevlere böler (JSON formatında).
• SwarmManager alt görevleri sırasıyla ilgili ajanlara atar:
    - RESEARCHER -> Derin araştırma yapar
    - CODER -> Kodları yazar
    - QA -> Yazılan kodu test eder veya kalite kontrolünü yapar
• Süreç sonunda final raporu üretilir.
"""

import json
import logging
import time
from typing import Any

from orchestrator.gemini_reasoning import query_gemini_reasoning
from computer.task_executor import TaskEngine

logger = logging.getLogger("ultron.orchestrator.swarm")

class SwarmManager:
    """Kendi içinde 'Yazılım Şirketi' gibi çalışan otonom çoklu ajan yöneticisi."""
    
    def __init__(self):
        self.team = ["RESEARCHER", "CODER", "QA"]
    def _notify(self, message: str):
        print(message)
        from core.event_bus import bus
        bus.publish("ui_alert", f"🏢 [SWARM ŞİRKETİ]: {message}")
        
    def start_project(self, project_description: str) -> dict[str, Any]:
        """Projeyi başlatır, PM'e parçalatır ve ajanlara dağıtır."""
        start_time = time.time()
        self._notify(f"\n[Swarm Manager] 👔 PROJE YÖNETİCİSİ DEVREDE: '{project_description[:50]}...'")
        
        # 1. Proje Yöneticisi (PM) Planlaması
        pm_prompt = (
            f"Sen bir IT Proje Yöneticisisin. Aşağıdaki projeyi takımın (RESEARCHER, CODER, QA) "
            f"için iş paketlerine (tasks) böl.\nProje: {project_description}\n\n"
            f"Çıktı formatı KESİNLİKLE sadece şu JSON olmalı:\n"
            f"[\n"
            f"  {{\"agent\": \"RESEARCHER\", \"task\": \"Konu hakkında araştırma yap...\"}},\n"
            f"  {{\"agent\": \"CODER\", \"task\": \"Şu dosyayı oluştur ve şu kodu yaz...\"}},\n"
            f"  {{\"agent\": \"QA\", \"task\": \"Yazılan kodu test et...\"}}\n"
            f"]"
        )
        
        pm_response = query_gemini_reasoning(pm_prompt, model_tier="flash", temperature=0.1)
        
        # JSON parsing
        tasks = []
        try:
            if "```json" in pm_response:
                json_str = pm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in pm_response:
                json_str = pm_response.split("```")[1].strip()
            else:
                json_str = pm_response.strip()
                
            tasks = json.loads(json_str)
        except Exception as e:
            logger.error(f"PM JSON Parse Hatası: {e}\nResponse: {pm_response}")
            tasks = [
                {"agent": "RESEARCHER", "task": f"Proje ön araştırması: {project_description}"},
                {"agent": "CODER", "task": f"Geliştirme yap: {project_description}"},
                {"agent": "QA", "task": f"Geliştirmeyi doğrula ve test et: {project_description}"}
            ]

        self._notify(f"[Swarm Manager] 📊 Proje planı oluşturuldu! Toplam {len(tasks)} görev delege ediliyor...")
        
        # 2. Görev Dağıtımı (Execution)
        results = []
        context_accumulator = []
        
        for i, t in enumerate(tasks, start=1):
            agent_role = t.get("agent", "CODER")
            sub_task = t.get("task", "")
            
            self._notify(f"└─ [{i}/{len(tasks)}] Atanan Ajan: {agent_role} | Görev: {sub_task[:40]}...")
            
            # Kümülatif bağlam ekle (Bir ajanın çıktısı diğerine input olsun)
            context_str = "\n".join(context_accumulator[-2:]) if context_accumulator else "Henüz bir bağlam yok."
            
            prompt = (
                f"Sen {agent_role} rolünde bir takımdasın.\n"
                f"Şu anki görevin: {sub_task}\n\n"
                f"Önceki ajanların ürettiği bağlam:\n{context_str}\n\n"
                f"Görevi 'FINISH' ile bitirirken message kısmına ne yaptığını ve bir sonraki ajana devrettiğin notu yaz."
            )
            
            task_obj = TaskEngine.create_task(prompt, owner=f"Swarm - {agent_role}")
            output = TaskEngine.execute_task_sync(task_obj)
            
            results.append({
                "agent": agent_role,
                "task": sub_task,
                "output": output
            })
            context_accumulator.append(f"[{agent_role} ÇIKTISI]: {output}")
            
        elapsed = round(time.time() - start_time, 2)
        final_summary = (
            f"✅ Swarm projesi başarıyla tamamlandı (Süre: {elapsed}s).\n"
            f"Toplam {len(tasks)} görev işlendi.\n"
            f"Son Ajanın Çıktısı: {results[-1]['output']}"
        )
        self._notify(f"\n[Swarm Manager] {final_summary}")
        
        return {
            "status": "COMPLETED",
            "project_description": project_description,
            "tasks_executed": len(tasks),
            "results": results,
            "summary": final_summary
        }

swarm_manager = SwarmManager()
