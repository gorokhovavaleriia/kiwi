"""Категории и подкатегории поступлений — из data/operation_map.xlsx.
Формат листа: в строке 1 названия категорий по столбцам, ниже в каждом
столбце — подкатегории этой категории (до первой пустой ячейки)."""

from pathlib import Path

import openpyxl

MAP_PATH = Path(__file__).resolve().parent / "data" / "operation_map.xlsx"


def load_income_categories():
    """OrderedDict {категория: [подкатегория, ...]} — порядок столбцов и
    строк как в самом файле. Название листа ищем без учёта регистра/опечаток
    (в примере лист называется "Постулпения")."""
    wb = openpyxl.load_workbook(MAP_PATH, data_only=True)
    sheet_name = next(
        (name for name in wb.sheetnames if name.strip().lower().startswith("пост")),
        wb.sheetnames[0],
    )
    ws = wb[sheet_name]

    categories = {}
    for col in range(2, ws.max_column + 1):
        category = ws.cell(row=1, column=col).value
        if not category or not str(category).strip():
            continue
        category = str(category).strip()
        subcats = []
        for row in range(2, ws.max_row + 1):
            value = ws.cell(row=row, column=col).value
            if value is None or not str(value).strip():
                break
            subcats.append(str(value).strip())
        categories[category] = subcats
    return categories
