"""
Smart Home Skill Handler
Mevcut actions/smarthome.py'yi çağırır.
"""


def execute(args: dict) -> str:
    from actions.smarthome import control_home_device
    entity_id = args.get("entity_id", "")
    action = args.get("action", "")
    value = args.get("value")
    return control_home_device(entity_id=entity_id, action=action, value=value) or "Komut gönderildi."
