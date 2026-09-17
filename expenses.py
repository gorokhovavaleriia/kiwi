"""Категории расходов и правило разнесения — из data/operation_map.xlsx,
листы "Расходы" (дерево группа -> категория -> подкатегории) и
"Сопоставление" (статья/род.статья исходной таблицы -> название в таблице
фондов = имя категории или подкатегории из дерева "Расходы")."""

from collections import OrderedDict
from pathlib import Path

import openpyxl

MAP_PATH = Path(__file__).resolve().parent / "data" / "operation_map.xlsx"

UNALLOCATED_GROUP = "Нераспределенное"
UNALLOCATED_CATEGORY = "Нераспределенное"

# Как делить общие поступления между группами расходов на виде "План" —
# заданная клиентом доля каждой группы (не из operation_map.xlsx, задана
# прямо в разговоре). Группы, которых здесь нет (например синтетическое
# "Нераспределенное"), получают 0.
INCOME_SHARE_BY_GROUP = {
    "Обязательные": 0.2596,
    "Переменные": 0.7121,
    "Непостоянные платежи": 0.0183,
}


def _norm(text):
    return str(text).strip().casefold() if text else ""


def load_expense_tree():
    """OrderedDict{группа: OrderedDict{категория: [подкатегория, ...]}}.

    Формат листа "Расходы": в столбце A — название группы (строка-маркер),
    сразу под ней — строка с названиями категорий по столбцам (начиная со
    столбца B), под каждой категорией — её подкатегории до первой пустой
    ячейки. Если у столбца нет названия категории, но есть значения ниже —
    это дырка в исходной таблице клиента: каждое такое значение становится
    отдельной самостоятельной категорией (без подкатегорий)."""
    wb = openpyxl.load_workbook(MAP_PATH, data_only=True)
    ws = wb["Расходы"]

    group_starts = []
    for row in range(2, ws.max_row + 1):
        value = ws.cell(row=row, column=1).value
        if value and str(value).strip():
            group_starts.append((row, str(value).strip()))
    group_starts.append((ws.max_row + 1, None))

    groups = OrderedDict()
    for i, (start_row, group_name) in enumerate(group_starts[:-1]):
        end_row = group_starts[i + 1][0]
        header_row = start_row + 1
        categories = OrderedDict()
        for col in range(2, ws.max_column + 1):
            raw_category = ws.cell(row=header_row, column=col).value
            category = str(raw_category).strip() if raw_category and str(raw_category).strip() else None
            subs = []
            for row in range(header_row + 1, end_row):
                value = ws.cell(row=row, column=col).value
                if value is None or not str(value).strip():
                    break
                subs.append(str(value).strip())
            if category:
                categories[category] = subs
            else:
                for orphan in subs:
                    categories[orphan] = []
        groups[group_name] = categories
    return groups


def load_statya_mapping():
    """{статья/род.статья (casefold) -> "название в таблице фондов"} — из
    листа "Сопоставление" (столбцы: Статья, Род. статья, Название в таблице
    фондов). Строится в двух проходах: сначала по "Статья" (годится и когда
    у операции нет род.статьи), затем по "Род. статья" (перекрывает первый
    проход — когда род.статья есть, она главнее конкретной статьи)."""
    wb = openpyxl.load_workbook(MAP_PATH, data_only=True)
    ws = wb["Сопоставление"]

    by_statya = {}
    by_rod_statya = {}
    for row in range(3, ws.max_row + 1):
        statya = ws.cell(row=row, column=1).value
        rod_statya = ws.cell(row=row, column=2).value
        target = ws.cell(row=row, column=3).value
        if not statya or not target:
            continue
        target = str(target).strip()
        by_statya[_norm(statya)] = target
        if rod_statya and str(rod_statya).strip():
            by_rod_statya[_norm(rod_statya)] = target
    return {"by_statya": by_statya, "by_rod_statya": by_rod_statya}


def build_target_location(tree):
    """{название категории/подкатегории (casefold) -> (группа, категория,
    подкатегория_или_None)} — обратный индекс по дереву расходов, чтобы по
    имени из "Сопоставление" найти, куда его положить в сетке."""
    location = {}
    for group, categories in tree.items():
        for category, subs in categories.items():
            location.setdefault(_norm(category), (group, category, None))
            for sub in subs:
                location.setdefault(_norm(sub), (group, category, sub))
    return location


def classify_expense(op, mapping, location):
    """op: словарь из operations.read_operations (amount < 0 уже проверено
    вызывающим кодом). Возвращает (группа, категория, подкатегория) — либо
    найденное по правилам "Сопоставление", либо UNALLOCATED_GROUP, если для
    статьи/род.статьи вообще нет правила (новая статья, не описанная в
    исходном файле клиента) или найденное название не встречается в дереве
    "Расходы" (значит, тоже нужно поправить исходный файл)."""
    statya_norm = _norm(op["statya"])
    rod_norm = _norm(op["rod_statya"])

    target = None
    if rod_norm and rod_norm in mapping["by_rod_statya"]:
        target = mapping["by_rod_statya"][rod_norm]
    elif statya_norm in mapping["by_statya"]:
        target = mapping["by_statya"][statya_norm]

    if target is None:
        return UNALLOCATED_GROUP, UNALLOCATED_CATEGORY, None

    found = location.get(_norm(target))
    if found is None:
        return UNALLOCATED_GROUP, UNALLOCATED_CATEGORY, None
    return found
