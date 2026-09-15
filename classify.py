"""Автоматическое разнесение операций по категориям поступлений — без единого
вопроса пользователю (см. PLAN.md, "как разносим категории"). Всё, что не
удалось уверенно определить, уходит в "Нераспределенное" — клиент поправит
вручную кликом по ячейке."""

import re

UNALLOCATED = "Нераспределенное"

EXCLUDED_STATYAS = {"Перевод между счетами"}

# "Статья" -> категория из operation_map.xlsx, только для тех статей, что
# прямо названы в плане.
_STATYA_TO_CATEGORY = {
    "продажи текущие": "Продажи текущие",
    "продажи госконтракт": "Продажи контракт",
    "продажи спецпроект": "Спецпроект",
}
_CREDIT_HINT = "кредит"
_OTHER_INCOME_HINT = "прочие поступл"

# Категория -> подкатегория-"свалка" для строк этой категории, для которых не
# нашлось совпадение по направлению — вместо общего "Нераспределенное".
_FALLBACK_SUBCATEGORY = {
    "Спецпроект": "Прочие спецпроекты",
}

# Ручные исключения из PLAN.md: конкретные "направления" не совпадают по
# подстроке ни с одной подкатегорией (или совпали бы не с той) — заданы
# явно. Ключ статьи -> {направление (casefold, nbsp -> пробел): подкатегория}.
_DIRECTION_OVERRIDES = {
    "продажи текущие": {
        "доставка": "КИВИ Кейтеринг",
        "ивент": "КИВИ Кейтеринг",
        "кейтеринг": "КИВИ Кейтеринг",
        "окружное шоссе": "КИВИ Кейтеринг",
        "кафе вилюйск": "Кытылга",
    },
}


def _normalize_direction(direction):
    return direction.strip().replace("\xa0", " ").casefold()


def _normalize_for_match(text):
    """Для сравнения направления с подкатегорией: "СОШ" — это то же самое,
    что "школа" (сокращение из выписки клиента, не из наших категорий), и
    пробелы вокруг "№" пишут то так, то так ("№ 7" / "№7") — оба варианта
    должны совпадать."""
    text = _normalize_direction(text)
    text = re.sub(r"\bсош\b", "школа", text)
    text = re.sub(r"\s*№\s*", "№", text)
    return text


_EXCLUDED_HINTS = ("взаиморасч", "взаимозачет", "взаимозачёт")


def is_excluded(statya):
    """Статьи, которые вообще не считаются ни поступлением, ни расходом
    (переводы между счетами, взаиморасчёты/взаимозачёты) — не должны
    попадать ни в категоризацию, ни в список операций на экране."""
    statya = statya.strip()
    if statya in EXCLUDED_STATYAS:
        return True
    statya_lower = statya.lower()
    return any(hint in statya_lower for hint in _EXCLUDED_HINTS)


def _find_subcategory(direction, subcategories):
    direction_norm = _normalize_for_match(direction)
    if not direction_norm:
        return None
    for sub in subcategories:
        sub_norm = _normalize_for_match(sub)
        if direction_norm in sub_norm or sub_norm in direction_norm:
            return sub
    return None


def classify_income(op, income_categories):
    """op: словарь из operations.read_operations (amount > 0 уже
    проверено вызывающим кодом). Возвращает (категория, подкатегория) или
    None, если операцию вообще не нужно учитывать (переводы/взаиморасчёты)."""
    statya = op["statya"].strip()
    if is_excluded(statya):
        return None

    statya_lower = statya.lower()
    direction = op["direction"].strip()
    category = _STATYA_TO_CATEGORY.get(statya_lower)

    if category:
        override = _DIRECTION_OVERRIDES.get(statya_lower, {}).get(_normalize_direction(direction))
        if override:
            return category, override
        subcategories = income_categories.get(category, [])
        matched_sub = _find_subcategory(direction, subcategories) if direction else None
        if matched_sub:
            return category, matched_sub
        fallback = _FALLBACK_SUBCATEGORY.get(category)
        if fallback and fallback in subcategories:
            return category, fallback
        return UNALLOCATED, None

    if not direction:
        if _CREDIT_HINT in statya_lower:
            return "Кредит", None
        if _OTHER_INCOME_HINT in statya_lower:
            return "Прочие поступл. от фин. операций", None

    return UNALLOCATED, None
