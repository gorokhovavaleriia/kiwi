"""План расходов — вводится вручную, только по неделям (одно число на всю
неделю, независимо от того, в каком виде — год/месяц/неделя — оно сейчас
показывается). Хранится в data/plan.json, чтобы переживать перезагрузку
страницы и загрузку нового файла операций."""

import json
from pathlib import Path

PLAN_PATH = Path(__file__).resolve().parent / "data" / "plan.json"

# Разделитель полей в строковом ключе плана — символ, которого точно не
# будет в названиях категорий/направлений.
_SEP = "␟"


def _key(group, category, subcategory, direction, week_start):
    return _SEP.join([group, category, subcategory or "", direction or "", week_start.isoformat()])


def load_plan():
    if not PLAN_PATH.exists():
        return {}
    with open(PLAN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_plan(plan):
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAN_PATH, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def get_week(plan, group, category, subcategory, direction, week_start):
    return plan.get(_key(group, category, subcategory, direction, week_start), 0.0)


def set_week(plan, group, category, subcategory, direction, week_start, value):
    plan[_key(group, category, subcategory, direction, week_start)] = value


def sum_weeks(plan, group, category, subcategory, direction, week_starts):
    """Сумма плана по недельным значениям, которые попадают в более крупный
    период (месяц/год) — сам план хранится только по неделям, крупные
    периоды показывают сумму подходящих недель, но не редактируются."""
    return sum(get_week(plan, group, category, subcategory, direction, w) for w in week_starts)
