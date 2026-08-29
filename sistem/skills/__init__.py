"""
ULTRON Skill Loader — Dinamik Plugin/Skill Sistemi
───────────────────────────────────────────────────
Uygulama başlangıcında skills/ klasörünü tarar.
Her skill klasöründe:
  - skill.yaml  → araç adı, açıklama, parametreler (tool_defs.py yerine)
  - handler.py  → execute(args) fonksiyonu

Yeni skill eklemek = yeni klasör + 2 dosya. tool_defs.py ve agent.py'ye dokunmak gerekmez.
Mevcut araçlarla tam geriye dönük uyumluluk korunur.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Callable

logger = logging.getLogger("ultron.skills")

SKILLS_DIR = Path(__file__).resolve().parent

# Yüklenen skill'lerin araç tanımları ve handler'ları
_skill_declarations: list[dict] = []
_skill_handlers: dict[str, Callable[[dict], str]] = {}


def _load_yaml_simple(path: Path) -> dict:
    """PyYAML olmadan basit YAML okuyucu (sadece düz key: value ve listeler)."""
    try:
        import yaml  # type: ignore
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass

    # Fallback: basit satır bazlı parser
    result: dict = {}
    current_list_key: str | None = None
    current_list: list = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("  - "):
                if current_list_key:
                    current_list.append(stripped[4:].strip())
                continue
            if ":" in stripped:
                if current_list_key and current_list:
                    result[current_list_key] = current_list
                    current_list = []
                    current_list_key = None
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if not val:
                    current_list_key = key
                else:
                    # Basit tip dönüşümü
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    elif val.isdigit():
                        val = int(val)
                    result[key] = val

    if current_list_key and current_list:
        result[current_list_key] = current_list

    return result


def _build_parameters(yaml_data: dict) -> dict:
    """skill.yaml'daki parametreleri Gemini tool tanım formatına çevirir."""
    params = yaml_data.get("parameters", {})
    if not params:
        return {"type": "OBJECT", "properties": {}, "required": []}

    properties = {}
    required = []

    for param_name, param_info in params.items():
        if isinstance(param_info, dict):
            p = {
                "type": param_info.get("type", "STRING").upper(),
                "description": param_info.get("description", ""),
            }
            properties[param_name] = p
            if param_info.get("required", False):
                required.append(param_name)
        else:
            properties[param_name] = {"type": "STRING", "description": str(param_info)}

    return {
        "type": "OBJECT",
        "properties": properties,
        "required": required,
    }


def _load_handler(skill_dir: Path) -> Callable[[dict], str] | None:
    """handler.py'deki execute() fonksiyonunu yükler."""
    handler_path = skill_dir / "handler.py"
    if not handler_path.exists():
        return None

    try:
        spec = importlib.util.spec_from_file_location(
            f"ultron_skill_{skill_dir.name}", handler_path
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        if hasattr(module, "execute") and callable(module.execute):
            return module.execute
        logger.warning(f"[SkillLoader] {skill_dir.name}/handler.py 'execute()' fonksiyonu bulunamadı.")
    except Exception as exc:
        logger.error(f"[SkillLoader] {skill_dir.name}/handler.py yükleme hatası: {exc}")
    return None


def load_all_skills() -> tuple[list[dict], dict[str, Callable]]:
    """
    skills/ klasörünü tarar, tüm skill'leri yükler.
    Returns: (tool_declarations, handlers)
    """
    global _skill_declarations, _skill_handlers
    _skill_declarations = []
    _skill_handlers = {}

    if not SKILLS_DIR.exists():
        return [], {}

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        if skill_dir.name.startswith("_") or skill_dir.name.startswith("."):
            continue

        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            continue

        try:
            meta = _load_yaml_simple(yaml_path)
            tool_name = meta.get("name", skill_dir.name)

            declaration = {
                "name": tool_name,
                "description": meta.get("description", ""),
                "parameters": _build_parameters(meta),
            }

            handler = _load_handler(skill_dir)
            if handler is None:
                logger.warning(f"[SkillLoader] '{tool_name}' için handler bulunamadı, atlanıyor.")
                continue

            _skill_declarations.append(declaration)
            _skill_handlers[tool_name] = handler
            logger.info(f"[SkillLoader] ✅ Skill yüklendi: '{tool_name}'")

        except Exception as exc:
            logger.error(f"[SkillLoader] '{skill_dir.name}' yükleme hatası: {exc}")

    logger.info(f"[SkillLoader] Toplam {len(_skill_declarations)} skill yüklendi.")
    return _skill_declarations, _skill_handlers


def get_skill_declarations() -> list[dict]:
    """Yüklü skill'lerin tool tanımlarını döner."""
    return list(_skill_declarations)


def execute_skill(tool_name: str, args: dict) -> str | None:
    """
    Verilen tool_name bir skill ise çalıştırır, değilse None döner.
    None → agent.py'nin mevcut if-elif zincirine devam etmesini sağlar.
    """
    handler = _skill_handlers.get(tool_name)
    if handler is None:
        return None
    try:
        return str(handler(args))
    except Exception as exc:
        logger.error(f"[SkillLoader] '{tool_name}' skill hatası: {exc}")
        return f"Skill hatası ({tool_name}): {exc}"


# Uygulama başlangıcında otomatik yükle
load_all_skills()
