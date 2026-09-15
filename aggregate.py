"""Разбивка операций по годам/месяцам/неделям для сетки на экране — плюс
границы недель (понедельник-воскресенье, с заходом в соседние месяцы, как в
макете) и сборка итоговых таблиц по категориям/подкатегориям."""

import calendar
from datetime import date, timedelta

import classify

MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


def classify_operations(operations, income_categories, overrides=None):
    """Помечает каждую операцию category/subcategory: для положительных сумм
    — по classify.classify_income (или вручную заданному overrides), для
    остальных — None (в сетку не идут, но остаются для скачивания "все
    операции"). overrides: {id(op) в списке -> (категория, подкатегория)} —
    ручная правка побеждает автоматическую.

    Отдельно помечает "excluded" (переводы между счетами, взаиморасчёты) —
    независимо от знака суммы: это не поступление и не расход, такие строки
    не должны попадать даже в список операций на экране (см. classify.is_excluded)."""
    overrides = overrides or {}
    result = []
    for i, op in enumerate(operations):
        op = dict(op)
        op["excluded"] = classify.is_excluded(op["statya"])
        if i in overrides:
            op["category"], op["subcategory"] = overrides[i]
        elif op["amount"] > 0:
            classified = classify.classify_income(op, income_categories)
            if classified is None:
                op["category"], op["subcategory"] = None, None
            else:
                op["category"], op["subcategory"] = classified
        else:
            op["category"], op["subcategory"] = None, None
        result.append(op)
    return result


def years_present(operations):
    years = sorted({op["date"].year for op in operations})
    return years or [date.today().year]


def month_weeks(year, month):
    """[(start, end), ...] — недели пн-вс, покрывающие весь месяц (первая и
    последняя неделя могут заходить в соседние месяцы, см. макет)."""
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    start = first - timedelta(days=first.weekday())
    weeks = []
    while start <= last:
        end = start + timedelta(days=6)
        weeks.append((start, end))
        start = end + timedelta(days=1)
    return weeks


def category_rows(income_categories):
    """[(category, subcategory_or_None), ...] в порядке из operation_map —
    строки итоговой таблицы. Категория без подкатегорий — одна строка на
    саму категорию (subcategory=None), плюс всегда строка "Нераспределенное"
    в конце."""
    rows = []
    for category, subs in income_categories.items():
        if subs:
            for sub in subs:
                rows.append((category, sub))
        else:
            rows.append((category, None))
    if (classify.UNALLOCATED, None) not in rows:
        rows.append((classify.UNALLOCATED, None))
    return rows


def _matches_row(op, category, subcategory):
    return op["category"] == category and op["subcategory"] == subcategory


def period_total(classified_ops, category, subcategory, start, end):
    return sum(
        op["amount"] for op in classified_ops
        if _matches_row(op, category, subcategory) and start <= op["date"] <= end
    )


def year_table(classified_ops, income_categories, year):
    """rows: [(category, subcategory)], columns: [(label, month_int)] за все
    12 месяцев + значения, плюс месячные и построчные итоги."""
    rows = category_rows(income_categories)
    columns = [(MONTH_NAMES[m - 1], m) for m in range(1, 13)]
    data = {}
    for category, subcategory in rows:
        for _, month in columns:
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
            data[(category, subcategory, month)] = period_total(
                classified_ops, category, subcategory, start, end
            )
    return rows, columns, data


def month_table(classified_ops, income_categories, year, month):
    rows = category_rows(income_categories)
    weeks = month_weeks(year, month)
    columns = [(f"{s.strftime('%d.%m.%Y')}-{e.strftime('%d.%m.%Y')}", (s, e)) for s, e in weeks]
    data = {}
    for category, subcategory in rows:
        for _, key in columns:
            start, end = key
            data[(category, subcategory, key)] = period_total(
                classified_ops, category, subcategory, start, end
            )
    return rows, columns, data


def week_table(classified_ops, income_categories, start, end):
    rows = category_rows(income_categories)
    days = [(start + timedelta(days=i)) for i in range((end - start).days + 1)]
    columns = [(d.strftime("%d.%m"), d) for d in days]
    data = {}
    for category, subcategory in rows:
        for _, d in columns:
            data[(category, subcategory, d)] = period_total(classified_ops, category, subcategory, d, d)
    return rows, columns, data
