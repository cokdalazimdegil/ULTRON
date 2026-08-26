"""
ULTRON Autonomous Engine — Task Executor & Verification Engine
───────────────────────────────────────────────────────────────
• PLAN -> EXECUTE -> VERIFY -> REPORT döngüsü
• Görev durumu (PENDING, RUNNING, VERIFYING, COMPLETED, FAILED, CANCELLED)
• Arka plan asenkron görev yönetimi & Tamamlanınca kullanıcıya geri bildirim
• İşlem doğrulama (Action Verification) ve Acil Durdurma desteği
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from computer.safety_manager import SafetyManager
from computer.computer_state import current_computer_state
from computer.app_controller import open_application, close_application, is_app_running
from computer.window_manager import get_active_window_info, focus_window
from computer.screen_analyzer import analyze_current_screen

logger = logging.getLogger("ultron.computer.task_executor")

_task_counter = 0
_task_lock = threading.Lock()
_active_tasks: dict[str, AutonomousTask] = {}


@dataclass
class TaskStep:
    name: str
    action_type: str
    params: dict[str, Any]
    status: str = "PENDING"  # PENDING, RUNNING, VERIFIED, FAILED
    result_message: str = ""


@dataclass
class AutonomousTask:
    task_id: str
    description: str
    owner: str = "Nuri Can"
    status: str = "PENDING"  # PENDING, PLANNING, RUNNING, VERIFYING, COMPLETED, FAILED, CANCELLED
    steps: list[TaskStep] = field(default_factory=list)
    progress_message: str = ""
    completion_report: str = ""
    error_message: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    cancel_requested: bool = False


def generate_task_id() -> str:
    global _task_counter
    with _task_lock:
        _task_counter += 1
        return f"ULTRON-TASK-{_task_counter:03d}"


def get_task(task_id: str) -> AutonomousTask | None:
    return _active_tasks.get(task_id)


def list_active_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_id": t.task_id,
            "description": t.description,
            "owner": t.owner,
            "status": t.status,
            "progress": t.progress_message,
            "created_at": t.created_at
        }
        for t in _active_tasks.values()
    ]


def cancel_task(task_id: str) -> bool:
    task = _active_tasks.get(task_id)
    if task:
        task.cancel_requested = True
        task.status = "CANCELLED"
        task.finished_at = time.time()
        current_computer_state.set_task(task.task_id, status="CANCELLED", progress="Görev iptal edildi.")
        return True
    return False


def cancel_all_tasks() -> int:
    SafetyManager.trigger_emergency_stop()
    count = 0
    for t in _active_tasks.values():
        if t.status in ("PENDING", "PLANNING", "RUNNING", "VERIFYING"):
            t.cancel_requested = True
            t.status = "CANCELLED"
            t.finished_at = time.time()
            count += 1
    current_computer_state.set_task(None, status="IDLE", progress="Tüm görevler durduruldu.")
    return count


class TaskEngine:
    """Otonom görevleri planlayan, yürüten ve doğrulayan motor."""

    @classmethod
    def create_task(cls, description: str, owner: str = "Nuri Can") -> AutonomousTask:
        task_id = generate_task_id()
        task = AutonomousTask(task_id=task_id, description=description, owner=owner)
        with _task_lock:
            _active_tasks[task_id] = task
        current_computer_state.set_task(task_id, status="PENDING", progress="Görev kuyruğa alındı.")
        return task

    @classmethod
    def execute_task_sync(cls, task: AutonomousTask) -> str:
        """
        Görevi PLAN -> EXECUTE -> VERIFY -> REPORT (ReAct Loop) akışıyla yürütür.
        """
        task.status = "RUNNING"
        current_computer_state.set_task(task.task_id, status="RUNNING", progress="Planlanıyor ve yürütülüyor...")
        print(f"[Task Engine] ⚙️ Görev başlatıldı: {task.task_id} — '{task.description}'", flush=True)

        if SafetyManager.is_emergency_stopped():
            task.status = "CANCELLED"
            task.finished_at = time.time()
            task.completion_report = "🚨 Görev acil durdurma nedeniyle başlatılmadı/iptal edildi."
            current_computer_state.set_task(task.task_id, status="CANCELLED", progress="Acil durdurma devrede.")
            return task.completion_report

        safety_eval = SafetyManager.evaluate_risk(task.description)
        if safety_eval["requires_confirmation"]:
            task.status = "WAITING"
            task.progress_message = safety_eval["warning"]
            current_computer_state.set_task(task.task_id, status="WAITING_FOR_USER", progress=safety_eval["warning"])
            return safety_eval["warning"]

        from orchestrator.gemini_reasoning import query_gemini_reasoning
        from jarvis_web.agent import execute_tool
        from tool_defs import TOOL_DECLARATIONS
        import json

        MAX_STEPS = 5
        history = []
        is_success = False
        final_message = ""
        
        # Sadece temel bilgileri alarak token tasarrufu yapalım
        tools_summary = [{"name": t["name"], "description": t["description"], "parameters": t.get("parameters", {})} for t in TOOL_DECLARATIONS]
        tools_json = json.dumps(tools_summary, ensure_ascii=False, indent=2)

        for step in range(MAX_STEPS):
            if SafetyManager.is_emergency_stopped() or task.cancel_requested:
                final_message = "Görev iptal edildi veya acil durdurma devrede."
                break
                
            task.progress_message = f"Adım {step+1}/{MAX_STEPS} yürütülüyor..."
            current_computer_state.set_task(task.task_id, status="RUNNING", progress=task.progress_message)
            
            history_str = json.dumps(history, ensure_ascii=False, indent=2)
            prompt = (
                f"Görev: {task.description}\n\n"
                f"Erişebileceğin araçlar:\n{tools_json}\n\n"
                f"Geçmiş Adımlar:\n{history_str}\n\n"
                "Sen otonom bir görev yürütücüsüsün (ReAct pattern). YALNIZCA aşağıdaki JSON formatında yanıt ver (markdown kod bloğu kullanma):\n"
                "Araç çağırmak için:\n"
                '{"action": "TOOL_CALL", "tool_name": "<araç_adı>", "tool_args": {"arg1": "val1"}, "thought": "<düşünce>"}\n\n'
                "Görevi bitirmek için (başarı veya başarısızlık fark etmez):\n"
                '{"action": "FINISH", "status": "COMPLETED" veya "FAILED", "message": "<kullanıcıya nihai rapor>", "thought": "<düşünce>"}'
            )

            try:
                response = query_gemini_reasoning(
                    prompt=prompt,
                    system_instruction="Sen JSON formatında çıktı veren katı bir ReAct ajanısın. Kesinlikle sadece JSON döndür.",
                    model_tier="pro",
                    temperature=0.1
                )
                
                # Temizle
                cleaned = response.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
                
                step_data = json.loads(cleaned)
                action = step_data.get("action")
                thought = step_data.get("thought", "")
                print(f"[Task Engine] 🧠 Düşünce: {thought}", flush=True)
                
                # Socket/UI yayını için adımı ekle (Broadcast)
                if hasattr(current_computer_state, "broadcast_progress"):
                    current_computer_state.broadcast_progress(task.task_id, thought)
                
                if action == "FINISH":
                    is_success = (step_data.get("status") == "COMPLETED")
                    final_message = step_data.get("message", "Görev tamamlandı.")
                    history.append({"step": step, "thought": thought, "action": "FINISH", "result": final_message})
                    break
                elif action == "TOOL_CALL":
                    tool_name = step_data.get("tool_name")
                    tool_args = step_data.get("tool_args", {})
                    print(f"[Task Engine] 🔧 Araç çağrılıyor: {tool_name}({tool_args})", flush=True)
                    
                    try:
                        tool_result = execute_tool(tool_name, tool_args)
                        history.append({"step": step, "thought": thought, "tool": tool_name, "args": tool_args, "result": tool_result})
                    except Exception as e:
                        err = f"Araç çalışma hatası: {str(e)}"
                        history.append({"step": step, "thought": thought, "tool": tool_name, "error": err})
                        print(f"[Task Engine] ⚠️ {err}", flush=True)
                else:
                    history.append({"step": step, "error": "Geçersiz action tipi."})
                    
            except Exception as e:
                print(f"[Task Engine] ⚠️ LLM veya Parsing hatası: {e}\nYanıt: {response if 'response' in locals() else ''}", flush=True)
                history.append({"step": step, "error": f"LLM hatası: {str(e)}"})

        if not final_message:
            final_message = "Maksimum adım sayısına ulaşıldı veya görev tamamlanamadı."

        task.finished_at = time.time()

        if is_success:
            task.status = "COMPLETED"
            task.completion_report = f"Tamamdır {task.owner}. {final_message}"
            current_computer_state.set_task(task.task_id, status="COMPLETED", progress="Görev başarıyla tamamlandı.")
            print(f"[Task Engine] ✅ Görev Tamamlandı: {task.task_id}", flush=True)
            return task.completion_report
        else:
            task.status = "FAILED"
            task.completion_report = f"İşlem tamamlanamadı {task.owner}. Son durum: {final_message}"
            current_computer_state.set_task(task.task_id, status="FAILED", progress="Görev başarısız oldu.")
            print(f"[Task Engine] ❌ Görev Başarısız: {task.task_id}", flush=True)
            return task.completion_report

    @classmethod
    def run_task_in_background(cls, description: str, owner: str = "Nuri Can", on_complete: Callable[[str], None] | None = None) -> str:
        """Görevi arka plan iş parçacığında çalıştırır ve Task ID döner."""
        task = cls.create_task(description, owner=owner)

        def _worker():
            report = cls.execute_task_sync(task)
            if on_complete:
                try:
                    on_complete(report)
                except Exception as e:
                    logger.error(f"Task on_complete callback hatasi: {e}")

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return task.task_id
