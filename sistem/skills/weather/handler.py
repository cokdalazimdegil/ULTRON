"""
Weather Skill Handler
Mevcut actions/weather.py'yi çağırır.
"""


def execute(args: dict) -> str:
    from actions.weather import get_weather_summary
    location = args.get("location") or None
    return get_weather_summary(location) or "Hava durumu alınamadı."
