import json
from datetime import datetime

# Загружаем файл
with open("/home/erda/Изображения/Съезд, Иностранцы 3-поток.json", "r", encoding="utf-8") as f:
    data = json.load(f)

def validate_iin(value, path):
    """Проверка ИИН"""
    if isinstance(value, str) and value.isdigit() and len(value) == 12:
        return
    print(f"[IIN ERROR] {path} = {value}")

def validate_birthdate(value, path):
    """Проверка даты рождения"""
    try:
        dt = datetime.strptime(value[:10], "%Y-%m-%d")
        if not (1920 <= dt.year <= 2025):
            print(f"[BIRTHDATE ERROR] {path} = {value} (год вне диапазона)")
    except Exception:
        print(f"[BIRTHDATE ERROR] {path} = {value} (неверный формат)")

def walk_json(obj, path="root"):
    """Рекурсивный обход JSON"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_path = f"{path}.{k}"
            if k.lower() == "iin":
                validate_iin(v, new_path)
            elif k.lower() == "birthdate":
                validate_birthdate(v, new_path)
            walk_json(v, new_path)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk_json(v, f"{path}[{i}]")

# Запуск проверки
walk_json(data)

