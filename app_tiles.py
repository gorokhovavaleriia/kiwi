"""kiwi — плитки. Слева навигация (загрузка файла / поступления / расходы),
как в kaspisales. Поступления и расходы — одна и та же идея сетки
год -> месяц -> неделя, только у расходов дополнительный уровень "группа"
(Обязательные/Переменные/Непостоянные платежи), показанный как
заголовок-разделитель внутри той же таблицы."""

import calendar
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

import aggregate
import categories
import classify
import expenses
import operations
import plan

st.set_page_config(page_title="kiwi — плитки", layout="wide")

TILE_CSS = """
<style>
/* плотнее расстояние между колонками сетки — иначе на большом числе
   столбцов широкие зазоры делают сетку похожей на соты */
div[data-testid="stHorizontalBlock"] { gap: 0.3rem !important; }

/* единый размер и центрирование для всех кнопок сетки — плитка одного
   размера, есть в ней число или нет; ширина/шрифт подобраны так, чтобы
   помещалось 8-значное число ("12 345 678") и слово "Сентябрь" в одну строку */
div[class*="st-key-nav-"] div[data-testid="stButton"],
div[class*="st-key-tile-"] div[data-testid="stButton"],
div[class*="st-key-zero-"] div[data-testid="stButton"],
div[class*="st-key-sel-"] div[data-testid="stButton"],
div[class*="st-key-home-"] div[data-testid="stButton"] { width: 100%; }

div[class*="st-key-nav-"] button,
div[class*="st-key-tile-"] button,
div[class*="st-key-zero-"] button,
div[class*="st-key-sel-"] button,
div[class*="st-key-home-"] button {
    width: 100%; min-height: 2.5rem; display: flex; align-items: center;
    justify-content: center; border: none; box-shadow: none; border-radius: 6px;
    white-space: nowrap; padding: 4px 3px; line-height: 1.15; margin-bottom: 3px;
}

div[class*="st-key-tile-"] button, div[class*="st-key-zero-"] button, div[class*="st-key-sel-"] button {
    font-size: 0.76rem; font-variant-numeric: tabular-nums;
}
div[class*="st-key-tile-"] button { background: #eef3ee; color: #1f2d1f; }
div[class*="st-key-tile-"] button:hover { background: #d7e8d7; color: #14401f; }
div[class*="st-key-zero-"] button { background: #f5f5f5; color: #d5d5d5; }
div[class*="st-key-zero-"] button:hover { background: #ececec; color: #b0b0b0; }
div[class*="st-key-sel-"] button {
    background: #bfe3bf !important; color: #14401f !important;
    border: 2px solid #4a8f4a !important; font-weight: 700;
}

div[class*="st-key-nav-"] button { background: #dfeee0; font-weight: 600; font-size: 0.74rem; }
div[class*="st-key-nav-"] button:hover { background: #c7ddc8; }
div[class*="st-key-home-"] button { background: #d4c9f0; font-weight: 700; font-size: 0.74rem; }
div[class*="st-key-home-"] button:hover { background: #c0b0ea; }

/* расходы — плитки другого (нейтрально-тёплого) оттенка, чтобы визуально
   отличать от зелёных плиток поступлений */
div[class*="st-key-etile-"] button { background: #f3ece0; color: #3a2c1a; }
div[class*="st-key-etile-"] button:hover { background: #e6d7be; color: #2a1f10; }
div[class*="st-key-ezero-"] button { background: #f5f5f5; color: #d5d5d5; }
div[class*="st-key-ezero-"] button:hover { background: #ececec; color: #b0b0b0; }
div[class*="st-key-esel-"] button {
    background: #e3c99a !important; color: #2a1f10 !important;
    border: 2px solid #a9822f !important; font-weight: 700;
}
div[class*="st-key-enav-"] button { background: #ecdfc7; font-weight: 600; font-size: 0.74rem; }
div[class*="st-key-enav-"] button:hover { background: #ddc79f; }

/* столбец TOTAL — крупнее и жирнее остальных ячеек, но с запасом по ширине
   под 8-значное число ("12 345 678") — иначе как раз он и не помещается */
div[class*="st-key-total-cell-"], div[class*="st-key-total-col-"], div[class*="st-key-total-grand-"] {
    background: #e2e2e2; border-radius: 6px; margin-bottom: 3px;
    min-height: 2.9rem; display: flex; align-items: center; justify-content: flex-end;
    padding: 4px 6px; font-weight: 700; font-size: 0.78rem; white-space: nowrap;
    font-variant-numeric: tabular-nums; overflow: visible;
}
div[class*="st-key-total-grand-"] { justify-content: center; font-size: 0.82rem; }

div[class*="st-key-rowlabel-"] {
    display: flex; align-items: center; min-height: 2.5rem;
    padding: 4px 4px; font-size: 0.8rem; line-height: 1.2; margin-bottom: 3px;
}
/* подкатегория-кнопка (разворот по направлениям) выглядит как обычный текст
   строки, а не как отдельная кнопка — подчёркивание только при наведении */
div[class*="st-key-rowlabel-"] div[data-testid="stButton"] { width: 100%; }
div[class*="st-key-rowlabel-"] button {
    width: 100%; background: transparent; border: none; box-shadow: none;
    text-align: left; padding: 0; margin: 0; font-size: 0.8rem; color: inherit;
    font-weight: inherit; white-space: normal;
}
div[class*="st-key-rowlabel-"] button:hover { text-decoration: underline; }

.kiwi-header-cell {
    display: flex; align-items: center; justify-content: center;
    min-height: 2.5rem; font-weight: 600; font-size: 0.78rem; white-space: nowrap;
    margin-bottom: 3px;
}
.kiwi-header-total {
    display: flex; align-items: center; justify-content: center;
    min-height: 2.9rem; font-weight: 800; font-size: 0.95rem; margin-bottom: 3px;
}
/* вся строка-заголовок группы — один сплошной коричневый прямоугольник:
   значения по периодам не кликабельны, поэтому не разбиваем их на плитки —
   только название группы слева остаётся настоящей кнопкой (свернуть/развернуть) */
div[class*="st-key-grouprow-"] {
    background: #5c4a2e; border-radius: 6px; margin: 12px 0 3px 0; padding: 2px 4px;
}

div[class*="st-key-groupdiv-"] div[data-testid="stButton"] { width: 100%; }
div[class*="st-key-groupdiv-"] button {
    width: 100%; min-height: 2.3rem; background: transparent; color: #fff;
    font-weight: 700; font-size: 0.82rem; padding: 4px 8px; border-radius: 4px;
    border: none; box-shadow: none; text-align: left; text-transform: uppercase;
    letter-spacing: 0.02em; white-space: nowrap;
}
div[class*="st-key-groupdiv-"] button:hover { background: rgba(255, 255, 255, 0.12); }

div[class*="st-key-groupval-"] {
    color: #fff; min-height: 2.3rem; display: flex; align-items: center;
    justify-content: flex-end; padding: 4px 6px; font-weight: 700; font-size: 0.78rem;
    white-space: nowrap; font-variant-numeric: tabular-nums;
}
/* строки "Поступления"/"План расходы"/"Факт расходы"/"Остаток" в шапке
   группы на виде "План" — та же тёмная плашка, но подпись слева */
div[class*="st-key-grouplabel-"] {
    color: #fff; min-height: 2.3rem; display: flex; align-items: center;
    justify-content: flex-start; padding: 4px 6px; font-weight: 600; font-size: 0.78rem;
    white-space: nowrap;
}

/* строки План/Факт у каждой категории на виде "План" */
div[class*="st-key-planval-"], div[class*="st-key-factval-"] {
    display: flex; align-items: center; justify-content: flex-end;
    min-height: 2.3rem; padding: 4px 6px; font-size: 0.76rem; margin-bottom: 3px;
    background: #faf7f0; border-radius: 6px; font-variant-numeric: tabular-nums;
}
div[class*="st-key-plantotal-"], div[class*="st-key-facttotal-"] {
    background: #e2e2e2; border-radius: 6px; margin-bottom: 3px;
    min-height: 2.3rem; display: flex; align-items: center; justify-content: flex-end;
    padding: 4px 6px; font-weight: 700; font-size: 0.78rem; white-space: nowrap;
    font-variant-numeric: tabular-nums;
}
div[class*="st-key-plantotal-"] div[data-testid="stTextInput"] { width: 100%; }

/* сводка по всем группам сразу — вверху, другим цветом, чтобы отличалась
   от коричневых плашек отдельных групп */
div[class*="st-key-summaryrow-"] {
    background: #1f4e5c; border-radius: 6px; margin: 4px 0 12px 0; padding: 2px 4px;
}
div[class*="st-key-summarylabel-"] {
    color: #fff; min-height: 2.4rem; display: flex; align-items: center;
    justify-content: flex-start; padding: 4px 6px; font-weight: 700; font-size: 0.82rem;
    white-space: nowrap;
}
div[class*="st-key-summaryval-"] {
    color: #fff; min-height: 2.4rem; display: flex; align-items: center;
    justify-content: flex-end; padding: 4px 6px; font-weight: 700; font-size: 0.82rem;
    white-space: nowrap; font-variant-numeric: tabular-nums;
}
</style>
"""
st.markdown(TILE_CSS, unsafe_allow_html=True)


def fmt(v):
    if not v:
        return " "
    return f"{v:,.0f}".replace(",", " ")


def money(v):
    return f"{v:,.0f}".replace(",", " ") if v else "0"


def parse_money(text):
    """Обратное к money() — разбирает то, что человек мог ввести в простое
    текстовое поле плана: пробелы/неразрывные пробелы как разделители
    тысяч, запятая как десятичный разделитель. Мусор — просто 0."""
    cleaned = text.strip().replace(" ", "").replace("\xa0", "").replace(",", ".")
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _display_label(view, label, key):
    """Короткая подпись для заголовка на экране (в Excel-выгрузку и в
    остальной код по-прежнему идёт полный label из aggregate.py) — у недель
    в месячном виде полная подпись "27.07.2026-02.08.2026" не помещается в
    узкую колонку и обрезается, короткая "27.07–02.08" помещается всегда."""
    if view == "month":
        start, end = key
        return f"{start:%d.%m}–{end:%d.%m}"
    return label


def col_period(view, year, key):
    """(start, end) периода, на который указывает ключ столбца."""
    if view == "year":
        month = key
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if view == "month":
        return key
    return key, key  # week: key = сам день


def _render_header(view, period_view, columns, ratios, on_nav, home_target,
                    sel_state_key, view_state_key, nav_prefix, suffix=""):
    header = st.columns(ratios)
    header[0].markdown("**Категория**")
    header[1].markdown("**Подкатегория**")
    for cell, (label, key) in zip(header[2:-1], columns):
        short_label = _display_label(period_view, label, key)
        if on_nav is not None:
            with cell.container(key=f"{nav_prefix}-{view}-{label}{suffix}"):
                if st.button(short_label, key=f"{nav_prefix}btn-{view}-{label}{suffix}", width="stretch"):
                    on_nav(key)
        else:
            cell.markdown(f'<div class="kiwi-header-cell">{short_label}</div>', unsafe_allow_html=True)
    if home_target:
        with header[-1].container(key=f"home-{view}{suffix}"):
            if st.button("🏠 Домой", key=f"homebtn-{view}{suffix}", width="stretch"):
                st.session_state[view_state_key] = home_target
                st.session_state[sel_state_key] = None
                st.rerun()
    else:
        header[-1].markdown('<div class="kiwi-header-total">TOTAL</div>', unsafe_allow_html=True)


def render_grid(view, rows, columns, data, sel_state_key, on_nav, home_target):
    """Сетка поступлений: строки — (категория, подкатегория)."""
    ratios = [1.6, 1.8] + [1] * len(columns) + [1.6]

    def header(suffix=""):
        _render_header(view, view, columns, ratios, on_nav, home_target,
                       sel_state_key, "view", "nav", suffix)

    header()

    selected = st.session_state.get(sel_state_key)
    col_totals = [0.0] * len(columns)
    for category, subcategory in rows:
        row_cells = st.columns(ratios)
        with row_cells[0].container(key=f"rowlabel-cat-{category}-{subcategory}"):
            st.markdown(category)
        with row_cells[1].container(key=f"rowlabel-sub-{category}-{subcategory}"):
            st.markdown(subcategory or "—")
        row_sum = 0.0
        for idx, ((label, key), cell) in enumerate(zip(columns, row_cells[2:-1])):
            value = data[(category, subcategory, key)]
            row_sum += value
            col_totals[idx] += value
            is_selected = selected == (category, subcategory, key)
            tile_key = f"{'sel' if is_selected else ('zero' if not value else 'tile')}-{view}-{category}-{subcategory}-{label}"
            with cell.container(key=tile_key):
                if st.button(fmt(value), key=f"btn-{tile_key}", width="stretch"):
                    st.session_state[sel_state_key] = (category, subcategory, key)
                    st.rerun()
        with row_cells[-1].container(key=f"total-cell-{view}-{category}-{subcategory}"):
            st.markdown(money(row_sum))

    total_cells = st.columns(ratios)
    total_cells[0].markdown("**ИТОГО**")
    total_cells[1].markdown("")
    for (label, _key), total, cell in zip(columns, col_totals, total_cells[2:-1]):
        with cell.container(key=f"total-col-{view}-{label}"):
            st.markdown(money(total))
    with total_cells[-1].container(key=f"total-grand-{view}"):
        st.markdown(f"**{money(sum(col_totals))}**")

    header(suffix="-bottom")


def render_expense_grid(view, period_view, year, rows, columns, data, classified,
                         sel_state_key, on_nav, home_target):
    """Сетка расходов: строки — (группа, категория, подкатегория). Группа
    показана как заголовок-разделитель на всю ширину перед первой строкой
    этой группы (см. выбор пользователя — не отдельный столбец, не вкладки).

    У подкатегорий, где встречается больше одного значения "Направление" в
    исходной таблице, название подкатегории — кнопка-разворот: показывает
    построчную разбивку по направлениям под основной строкой. period_view
    ("year"/"month"/"week") и year — чтобы посчитать даты периода каждого
    столбца для этой разбивки (col_period)."""
    ratios = [1.6, 1.8] + [1] * len(columns) + [1.6]

    def header(suffix=""):
        _render_header(view, period_view, columns, ratios, on_nav, home_target,
                       sel_state_key, "exp_view", "enav", suffix)

    header()

    group_col_totals = {}
    for group, category, subcategory in rows:
        acc = group_col_totals.setdefault(group, [0.0] * len(columns))
        for idx, (_label, key) in enumerate(columns):
            acc[idx] += data[(group, category, subcategory, key)]

    collapsed = st.session_state.setdefault(f"exp_collapsed_{view}", set())
    expanded_dirs = st.session_state.setdefault(f"exp_dirs_{view}", set())

    selected = st.session_state.get(sel_state_key)
    col_totals = [0.0] * len(columns)
    current_group = None
    for group, category, subcategory in rows:
        if group != current_group:
            current_group = group
            is_collapsed_group = group in collapsed
            icon = "▸" if is_collapsed_group else "▾"
            with st.container(key=f"grouprow-{view}-{group}"):
                group_cells = st.columns(ratios)
                with group_cells[0].container(key=f"groupdiv-{view}-{group}"):
                    if st.button(f"{icon} {group}", key=f"groupdivbtn-{view}-{group}", width="stretch"):
                        if is_collapsed_group:
                            collapsed.discard(group)
                        else:
                            collapsed.add(group)
                        st.rerun()
                with group_cells[1].container(key=f"groupval-{view}-{group}-sub"):
                    st.markdown("")
                for idx, ((label, _key), cell) in enumerate(zip(columns, group_cells[2:-1])):
                    with cell.container(key=f"groupval-{view}-{group}-{label}"):
                        st.markdown(money(group_col_totals[group][idx]))
                with group_cells[-1].container(key=f"groupval-{view}-{group}-total"):
                    st.markdown(money(sum(group_col_totals[group])))

        row_values = [data[(group, category, subcategory, key)] for _, key in columns]
        for idx, value in enumerate(row_values):
            col_totals[idx] += value

        if group in collapsed:
            continue

        row_key3 = (group, category, subcategory)
        directions = aggregate.expense_directions(classified, group, category, subcategory)
        expandable = len(directions) > 1
        is_expanded = expandable and row_key3 in expanded_dirs

        row_sum = sum(row_values)
        row_cells = st.columns(ratios)
        with row_cells[0].container(key=f"rowlabel-cat-{view}-{group}-{category}-{subcategory}"):
            st.markdown(category)
        with row_cells[1].container(key=f"rowlabel-sub-{view}-{group}-{category}-{subcategory}"):
            if expandable:
                icon = "▾" if is_expanded else "▸"
                if st.button(f"{icon} {subcategory}", key=f"dirtoggle-{view}-{group}-{category}-{subcategory}"):
                    if is_expanded:
                        expanded_dirs.discard(row_key3)
                    else:
                        expanded_dirs.add(row_key3)
                    st.rerun()
            else:
                st.markdown(subcategory or "—")
        for idx, ((label, key), cell) in enumerate(zip(columns, row_cells[2:-1])):
            value = row_values[idx]
            is_selected = selected == (group, category, subcategory, None, key)
            tile_key = (f"{'esel' if is_selected else ('ezero' if not value else 'etile')}"
                        f"-{view}-{group}-{category}-{subcategory}-{label}")
            with cell.container(key=tile_key):
                if st.button(fmt(value), key=f"btn-{tile_key}", width="stretch"):
                    st.session_state[sel_state_key] = (group, category, subcategory, None, key)
                    st.rerun()
        with row_cells[-1].container(key=f"total-cell-{view}-{group}-{category}-{subcategory}"):
            st.markdown(money(row_sum))

        if not is_expanded:
            continue

        for direction in directions:
            dir_label = direction if direction else "(без направления)"
            dir_row = st.columns(ratios)
            with dir_row[0].container(key=f"rowlabel-dircat-{view}-{group}-{category}-{subcategory}-{direction}"):
                st.markdown("")
            with dir_row[1].container(key=f"rowlabel-dir-{view}-{group}-{category}-{subcategory}-{direction}"):
                st.markdown(f"↳ {dir_label}")
            dir_row_sum = 0.0
            for idx, ((label, key), cell) in enumerate(zip(columns, dir_row[2:-1])):
                start, end = col_period(period_view, year, key)
                value = aggregate.expense_direction_period_total(
                    classified, group, category, subcategory, direction, start, end
                )
                dir_row_sum += value
                is_selected = selected == (group, category, subcategory, direction, key)
                tile_key = (f"{'esel' if is_selected else ('ezero' if not value else 'etile')}"
                            f"-{view}-{group}-{category}-{subcategory}-{direction}-{label}")
                with cell.container(key=tile_key):
                    if st.button(fmt(value), key=f"btn-{tile_key}", width="stretch"):
                        st.session_state[sel_state_key] = (group, category, subcategory, direction, key)
                        st.rerun()
            with dir_row[-1].container(key=f"total-cell-dir-{view}-{group}-{category}-{subcategory}-{direction}"):
                st.markdown(money(dir_row_sum))

    total_cells = st.columns(ratios)
    total_cells[0].markdown("**ИТОГО**")
    total_cells[1].markdown("")
    for (label, _key), total, cell in zip(columns, col_totals, total_cells[2:-1]):
        with cell.container(key=f"total-col-{view}-{label}"):
            st.markdown(money(total))
    with total_cells[-1].container(key=f"total-grand-{view}"):
        st.markdown(f"**{money(sum(col_totals))}**")

    header(suffix="-bottom")


# ---------------------------------------------------------------- страницы

def render_income_page(classified, income_categories):
    st.markdown("## 📈 Поступления")

    st.session_state.setdefault("view", "year")
    st.session_state.setdefault("sel_year", None)
    st.session_state.setdefault("sel_month", None)
    st.session_state.setdefault("sel_week", None)

    view = st.session_state.view
    year = st.session_state.year

    if view == "year":
        period_title = f"{year} год"
        st.markdown(f"### {period_title}")
        years = st.session_state._years
        if len(years) > 1:
            year = st.selectbox("Год", years, index=years.index(year), key="income_year_pick")
            st.session_state.year = year
            period_title = f"{year} год"
        rows, columns, data = aggregate.year_table(classified, income_categories, year)

        def go_month(month):
            st.session_state.month = month
            st.session_state.view = "month"
            st.session_state.sel_month = None
            st.rerun()

        render_grid("year", rows, columns, data, "sel_year", go_month, home_target=None)
        period_start, period_end = date(year, 1, 1), date(year, 12, 31)
        sel = st.session_state.get("sel_year")

    elif view == "month":
        month = st.session_state.month
        period_title = f"{aggregate.MONTH_NAMES[month - 1]} {year}"
        st.markdown(f"### {period_title}")
        rows, columns, data = aggregate.month_table(classified, income_categories, year, month)

        def go_week(week_key):
            st.session_state.week = week_key
            st.session_state.view = "week"
            st.session_state.sel_week = None
            st.rerun()

        render_grid("month", rows, columns, data, "sel_month", go_week, home_target="year")
        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])
        sel = st.session_state.get("sel_month")

    else:  # week
        week_start, week_end = st.session_state.week
        period_title = (f"{aggregate.MONTH_NAMES[week_start.month - 1]}, "
                         f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}")
        st.markdown(f"### {period_title}")
        if st.button("🏠 Домой (к месяцу)", key="income_week_home"):
            st.session_state.view = "month"
            st.rerun()
        rows, columns, data = aggregate.week_table(classified, income_categories, week_start, week_end)
        render_grid("week", rows, columns, data, "sel_week", on_nav=None, home_target=None)
        period_start, period_end = week_start, week_end
        sel = st.session_state.get("sel_week")

    st.caption(f"📅 {period_title}")
    st.divider()
    st.markdown("#### Операции")

    if sel:
        category, subcategory, col_key = sel
        slice_start, slice_end = col_period(view, year, col_key)
        label = f"{category}" + (f" / {subcategory}" if subcategory else "") + \
            f", {slice_start.strftime('%d.%m.%Y')}–{slice_end.strftime('%d.%m.%Y')}"
        st.caption(f"Показаны операции по клику на плитку: **{label}**")
        if st.button("✕ Показать все операции периода", key="income_clear_sel"):
            st.session_state[{"year": "sel_year", "month": "sel_month", "week": "sel_week"}[view]] = None
            st.rerun()
        matching_indices = [
            i for i, op in enumerate(classified)
            if slice_start <= op["date"] <= slice_end
            and op["category"] == category and op["subcategory"] == subcategory
        ]
    else:
        st.caption("Клик по плитке в таблице выше отфильтрует операции здесь. Сейчас показан весь период.")
        matching_indices = [
            i for i, op in enumerate(classified)
            if period_start <= op["date"] <= period_end and not op["excluded"]
        ]

    overrides = st.session_state.overrides

    if not matching_indices:
        st.caption("Нет операций для этого выбора.")
    else:
        shown = pd.DataFrame([
            {
                "Дата": classified[i]["date"], "Сумма": classified[i]["amount"],
                "Статья": classified[i]["statya"], "Направление": classified[i]["direction"],
                "Категория": classified[i]["category"] or "", "Подкатегория": classified[i]["subcategory"] or "",
                "Описание": classified[i]["description"][:150],
            }
            for i in matching_indices
        ])
        st.caption("Отметьте галочками слева операции, которым нужно поменять категорию (можно несколько).")
        select_key = f"ops_select_{view}_{sel}"
        result = st.dataframe(
            shown, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="multi-row", key=select_key,
        )
        selected_rows = result.selection.rows

        if selected_rows:
            picked_indices = [matching_indices[r] for r in selected_rows]
            if len(picked_indices) == 1:
                op = classified[picked_indices[0]]
                st.markdown(
                    f"###### Изменить категорию операции от {op['date'].strftime('%d.%m.%Y')} "
                    f"на {money(op['amount'])} ({op['description'][:80]})"
                )
            else:
                st.markdown(f"###### Изменить категорию у {len(picked_indices)} выбранных операций")
            all_cat_options = list(income_categories.keys()) + [classify.UNALLOCATED]
            new_cat = st.selectbox("Новая категория", all_cat_options, key=f"new_cat_{select_key}")
            subs = income_categories.get(new_cat, [])
            new_sub = st.selectbox("Новая подкатегория", ["—"] + subs, key=f"new_sub_{select_key}") if subs else None
            if st.button("💾 Сохранить изменения", type="primary", key=f"save_{select_key}"):
                for picked_index in picked_indices:
                    overrides[picked_index] = (new_cat, new_sub if new_sub and new_sub != "—" else None)
                st.success(f"Обновлено операций: {len(picked_indices)}")
                st.rerun()

    st.divider()
    st.markdown("#### Скачать этот срез")
    grid_rows_export = []
    for category, subcategory in rows:
        values = [data[(category, subcategory, key)] for _, key in columns]
        grid_rows_export.append([category, subcategory or "", *values, sum(values)])
    export_df = pd.DataFrame(
        grid_rows_export,
        columns=["Категория", "Подкатегория"] + [label for label, _ in columns] + ["TOTAL"],
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Таблица")
        period_ops = pd.DataFrame([
            {
                "Дата": op["date"], "Сумма": op["amount"], "Статья": op["statya"],
                "Направление": op["direction"], "Категория": op["category"] or "",
                "Подкатегория": op["subcategory"] or "", "Описание": op["description"],
            }
            for op in classified if period_start <= op["date"] <= period_end
        ])
        period_ops.to_excel(writer, index=False, sheet_name="Все операции")
    st.download_button(
        "⬇️ Скачать (2 вкладки)", data=buf.getvalue(), file_name="kiwi_поступления.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="income_download",
    )


def render_expense_page(classified, tree):
    st.markdown("## 📉 Расходы")

    st.session_state.setdefault("exp_view", "year")
    st.session_state.setdefault("exp_sel_year", None)
    st.session_state.setdefault("exp_sel_month", None)
    st.session_state.setdefault("exp_sel_week", None)

    view = st.session_state.exp_view
    year = st.session_state.exp_year

    if view == "year":
        period_title = f"{year} год"
        st.markdown(f"### {period_title}")
        years = st.session_state._years
        if len(years) > 1:
            year = st.selectbox("Год", years, index=years.index(year), key="expense_year_pick")
            st.session_state.exp_year = year
            period_title = f"{year} год"
        rows, columns, data = aggregate.expense_year_table(classified, tree, year)

        def go_month(month):
            st.session_state.exp_month = month
            st.session_state.exp_view = "month"
            st.session_state.exp_sel_month = None
            st.rerun()

        render_expense_grid("eyear", "year", year, rows, columns, data, classified,
                             "exp_sel_year", go_month, home_target=None)
        period_start, period_end = date(year, 1, 1), date(year, 12, 31)
        sel = st.session_state.get("exp_sel_year")

    elif view == "month":
        month = st.session_state.exp_month
        period_title = f"{aggregate.MONTH_NAMES[month - 1]} {year}"
        st.markdown(f"### {period_title}")
        rows, columns, data = aggregate.expense_month_table(classified, tree, year, month)

        def go_week(week_key):
            st.session_state.exp_week = week_key
            st.session_state.exp_view = "week"
            st.session_state.exp_sel_week = None
            st.rerun()

        render_expense_grid("emonth", "month", year, rows, columns, data, classified,
                             "exp_sel_month", go_week, home_target="year")
        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])
        sel = st.session_state.get("exp_sel_month")

    else:  # week
        week_start, week_end = st.session_state.exp_week
        period_title = (f"{aggregate.MONTH_NAMES[week_start.month - 1]}, "
                         f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}")
        st.markdown(f"### {period_title}")
        if st.button("🏠 Домой (к месяцу)", key="expense_week_home"):
            st.session_state.exp_view = "month"
            st.rerun()
        rows, columns, data = aggregate.expense_week_table(classified, tree, week_start, week_end)
        render_expense_grid("eweek", "week", year, rows, columns, data, classified,
                             "exp_sel_week", on_nav=None, home_target=None)
        period_start, period_end = week_start, week_end
        sel = st.session_state.get("exp_sel_week")

    st.caption(f"📅 {period_title}")
    st.divider()
    st.markdown("#### Операции")

    if sel:
        group, category, subcategory, direction, col_key = sel
        slice_start, slice_end = col_period(view, year, col_key)
        label = f"{group} / {category}" + (f" / {subcategory}" if subcategory else "") + \
            (f" / {direction or '(без направления)'}" if direction is not None else "") + \
            f", {slice_start.strftime('%d.%m.%Y')}–{slice_end.strftime('%d.%m.%Y')}"
        st.caption(f"Показаны операции по клику на плитку: **{label}**")
        if st.button("✕ Показать все операции периода", key="expense_clear_sel"):
            st.session_state[{"year": "exp_sel_year", "month": "exp_sel_month", "week": "exp_sel_week"}[view]] = None
            st.rerun()
        matching_indices = [
            i for i, op in enumerate(classified)
            if slice_start <= op["date"] <= slice_end and op["exp_group"] == group
            and op["exp_category"] == category and op["exp_subcategory"] == subcategory
            and (direction is None or op["direction"].strip() == direction)
        ]
    else:
        st.caption("Клик по плитке в таблице выше отфильтрует операции здесь. Сейчас показан весь период.")
        matching_indices = [
            i for i, op in enumerate(classified)
            if period_start <= op["date"] <= period_end and op["amount"] < 0 and not op["excluded"]
        ]

    expense_overrides = st.session_state.expense_overrides

    if not matching_indices:
        st.caption("Нет операций для этого выбора.")
    else:
        shown = pd.DataFrame([
            {
                "Дата": classified[i]["date"], "Сумма": classified[i]["amount"],
                "Статья": classified[i]["statya"], "Род.статья": classified[i]["rod_statya"],
                "Группа": classified[i]["exp_group"] or "", "Категория": classified[i]["exp_category"] or "",
                "Подкатегория": classified[i]["exp_subcategory"] or "",
                "Описание": classified[i]["description"][:150],
            }
            for i in matching_indices
        ])
        st.caption("Отметьте галочками слева операции, которым нужно поменять категорию (можно несколько).")
        select_key = f"exp_ops_select_{view}_{sel}"
        result = st.dataframe(
            shown, use_container_width=True, hide_index=True,
            on_select="rerun", selection_mode="multi-row", key=select_key,
        )
        selected_rows = result.selection.rows

        if selected_rows:
            picked_indices = [matching_indices[r] for r in selected_rows]
            if len(picked_indices) == 1:
                op = classified[picked_indices[0]]
                st.markdown(
                    f"###### Изменить категорию операции от {op['date'].strftime('%d.%m.%Y')} "
                    f"на {money(abs(op['amount']))} ({op['description'][:80]})"
                )
            else:
                st.markdown(f"###### Изменить категорию у {len(picked_indices)} выбранных операций")
            group_options = list(tree.keys()) + [expenses.UNALLOCATED_GROUP]
            new_group = st.selectbox("Новая группа", group_options, key=f"new_group_{select_key}")
            cat_options = list(tree.get(new_group, {}).keys()) or [expenses.UNALLOCATED_CATEGORY]
            new_cat = st.selectbox("Новая категория", cat_options, key=f"new_ecat_{select_key}")
            subs = tree.get(new_group, {}).get(new_cat, [])
            new_sub = st.selectbox("Новая подкатегория", ["—"] + subs, key=f"new_esub_{select_key}") if subs else None
            if st.button("💾 Сохранить изменения", type="primary", key=f"esave_{select_key}"):
                for picked_index in picked_indices:
                    expense_overrides[picked_index] = (
                        new_group, new_cat, new_sub if new_sub and new_sub != "—" else None
                    )
                st.success(f"Обновлено операций: {len(picked_indices)}")
                st.rerun()

    st.divider()
    st.markdown("#### Скачать этот срез")
    grid_rows_export = []
    for group, category, subcategory in rows:
        values = [data[(group, category, subcategory, key)] for _, key in columns]
        grid_rows_export.append([group, category, subcategory or "", *values, sum(values)])
    export_df = pd.DataFrame(
        grid_rows_export,
        columns=["Группа", "Категория", "Подкатегория"] + [label for label, _ in columns] + ["TOTAL"],
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Таблица")
        period_ops = pd.DataFrame([
            {
                "Дата": op["date"], "Сумма": op["amount"], "Статья": op["statya"],
                "Род.статья": op["rod_statya"], "Группа": op["exp_group"] or "",
                "Категория": op["exp_category"] or "", "Подкатегория": op["exp_subcategory"] or "",
                "Описание": op["description"],
            }
            for op in classified
            if period_start <= op["date"] <= period_end and op["amount"] < 0 and not op["excluded"]
        ])
        period_ops.to_excel(writer, index=False, sheet_name="Все операции")
    st.download_button(
        "⬇️ Скачать (2 вкладки)", data=buf.getvalue(), file_name="kiwi_расходы.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="expense_download",
    )


def _plan_col_value(period_view, year, plan_data, group, category, subcategory, direction, key):
    """Плановое число за один столбец сетки — план хранится только по
    неделям: в году/месяце это сумма подходящих недель (см. plan.py), в
    недельном виде план не по дням, поэтому None (см. render_plan_page)."""
    if period_view == "year":
        weeks = aggregate.month_weeks(year, key)
        return plan.sum_weeks(plan_data, group, category, subcategory, direction, [s for s, _ in weeks])
    if period_view == "month":
        start, _end = key
        return plan.get_week(plan_data, group, category, subcategory, direction, start)
    return None


def render_plan_page(classified, tree):
    st.markdown("## 📋 План")

    st.session_state.setdefault("plan_view", "year")
    year = st.session_state.setdefault("plan_year", st.session_state._years[-1])
    view = st.session_state.plan_view

    plan_data = plan.load_plan()

    if view == "year":
        period_title = f"{year} год"
        st.markdown(f"### {period_title}")
        years = st.session_state._years
        if len(years) > 1:
            year = st.selectbox("Год", years, index=years.index(year), key="plan_year_pick")
            st.session_state.plan_year = year
            period_title = f"{year} год"
        rows, columns, data = aggregate.expense_year_table(classified, tree, year)
        period_view = "year"

        def on_nav(month):
            st.session_state.plan_month = month
            st.session_state.plan_view = "month"
            st.rerun()

        home_target = None

    elif view == "month":
        month = st.session_state.plan_month
        period_title = f"{aggregate.MONTH_NAMES[month - 1]} {year}"
        st.markdown(f"### {period_title}")
        rows, columns, data = aggregate.expense_month_table(classified, tree, year, month)
        period_view = "month"

        def on_nav(week_key):
            st.session_state.plan_week = week_key
            st.session_state.plan_view = "week"
            st.rerun()

        home_target = "year"

    else:
        week_start, week_end = st.session_state.plan_week
        period_title = (f"{aggregate.MONTH_NAMES[week_start.month - 1]}, "
                         f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}")
        st.markdown(f"### {period_title}")
        if st.button("🏠 Домой (к месяцу)", key="plan_week_home"):
            st.session_state.plan_view = "month"
            st.rerun()
        rows, columns, data = aggregate.expense_week_table(classified, tree, week_start, week_end)
        period_view = "week"
        on_nav = None
        home_target = None

    ratios = [1.1, 0.7, 1.4] + [1] * len(columns) + [1.6]

    def header(suffix=""):
        h = st.columns(ratios)
        h[0].markdown("**Категория**")
        h[1].markdown("")
        h[2].markdown("**Подкатегория**")
        for cell, (label, key) in zip(h[3:-1], columns):
            short_label = _display_label(period_view, label, key)
            if on_nav is not None:
                with cell.container(key=f"nav-plan-{view}-{label}{suffix}"):
                    if st.button(short_label, key=f"navbtn-plan-{view}-{label}{suffix}", width="stretch"):
                        on_nav(key)
            else:
                cell.markdown(f'<div class="kiwi-header-cell">{short_label}</div>', unsafe_allow_html=True)
        if home_target:
            with h[-1].container(key=f"home-plan-{view}{suffix}"):
                if st.button("🏠 Домой", key=f"homebtn-plan-{view}{suffix}", width="stretch"):
                    st.session_state.plan_view = home_target
                    st.rerun()
        else:
            h[-1].markdown('<div class="kiwi-header-total">TOTAL</div>', unsafe_allow_html=True)

    header()

    collapsed = st.session_state.setdefault(f"plan_collapsed_{view}", set())
    expanded_dirs = st.session_state.setdefault(f"plan_dirs_{view}", set())

    period_ranges = [col_period(period_view, year, key) for _, key in columns]
    income_values = [aggregate.total_income_for_period(classified, s, e) for s, e in period_ranges]

    pending_inputs = []  # [(group, category, subcategory, direction, input_key)] — только на недельном виде
    week_start_for_input = columns[0][1] if period_view == "week" else None

    # На недельном виде план хранится одним числом на всю неделю (не по
    # дням) — _plan_col_value возвращает None для дневных столбцов, поэтому
    # для группы план на этом виде считаем отдельно, через plan.get_week,
    # а не суммированием (несуществующих) значений по дням.
    group_fact_totals, group_plan_totals, group_plan_week_total = {}, {}, {}
    for group, category, subcategory in rows:
        fact_acc = group_fact_totals.setdefault(group, [0.0] * len(columns))
        plan_acc = group_plan_totals.setdefault(group, [0.0] * len(columns))
        for idx, (_label, key) in enumerate(columns):
            fact_acc[idx] += data[(group, category, subcategory, key)]
            v = _plan_col_value(period_view, year, plan_data, group, category, subcategory, None, key)
            if v is not None:
                plan_acc[idx] += v
        if period_view == "week":
            group_plan_week_total[group] = group_plan_week_total.get(group, 0.0) + plan.get_week(
                plan_data, group, category, subcategory, None, week_start_for_input
            )

    if period_view == "week":
        grand_plan_values = [None] * len(columns)
        grand_plan_total = sum(group_plan_week_total.values())
    else:
        grand_plan_values = [sum(group_plan_totals[g][idx] for g in group_plan_totals) for idx in range(len(columns))]
        grand_plan_total = sum(grand_plan_values)
    grand_fact_values = [sum(group_fact_totals[g][idx] for g in group_fact_totals) for idx in range(len(columns))]
    grand_fact_total = sum(grand_fact_values)

    summary_rows = [
        ("Поступления", income_values, sum(income_values)),
        ("План расходы (всего)", grand_plan_values, grand_plan_total),
        ("Факт расходы (всего)", grand_fact_values, grand_fact_total),
        ("Остаток", [None] * len(columns), None),
    ]
    with st.container(key=f"summaryrow-plan-{view}"):
        for label_text, values, total_val in summary_rows:
            srow = st.columns(ratios)
            with srow[0].container(key=f"summarylabel-plan-{view}-{label_text}-c0"):
                st.markdown("")
            with srow[1].container(key=f"summarylabel-plan-{view}-{label_text}-c1"):
                st.markdown("")
            with srow[2].container(key=f"summarylabel-plan-{view}-{label_text}-c2"):
                st.markdown(f"**{label_text}**")
            for idx, cell in enumerate(srow[3:-1]):
                with cell.container(key=f"summaryval-plan-{view}-{label_text}-{idx}"):
                    st.markdown(money(values[idx]) if values[idx] is not None else "")
            with srow[-1].container(key=f"summaryval-plan-{view}-{label_text}-total"):
                st.markdown(f"**{money(total_val)}**" if total_val is not None else "")

    col_totals_fact = [0.0] * len(columns)
    current_group = None
    for group, category, subcategory in rows:
        if group != current_group:
            current_group = group
            is_collapsed = group in collapsed
            icon = "▸" if is_collapsed else "▾"
            with st.container(key=f"grouprow-plan-{view}-{group}"):
                with st.container(key=f"groupdiv-plan-{view}-{group}"):
                    if st.button(f"{icon} {group}", key=f"groupdivbtn-plan-{view}-{group}", width="stretch"):
                        if is_collapsed:
                            collapsed.discard(group)
                        else:
                            collapsed.add(group)
                        st.rerun()
                # Строки "Поступления/План/Факт/Остаток" — всегда видны, даже
                # при свёрнутой группе; свёртывание скрывает только строки
                # категорий/подкатегорий ниже (см. "if group in collapsed").
                if period_view == "week":
                    plan_row_values = [None] * len(columns)
                    plan_row_total = group_plan_week_total.get(group, 0.0)
                else:
                    plan_row_values = group_plan_totals[group]
                    plan_row_total = sum(plan_row_values)
                share = expenses.INCOME_SHARE_BY_GROUP.get(group, 0.0)
                group_income_values = [v * share for v in income_values]
                metric_rows = [
                    (f"Поступления ({share:.2%})", group_income_values, sum(group_income_values)),
                    ("План расходы", plan_row_values, plan_row_total),
                    ("Факт расходы", group_fact_totals[group], sum(group_fact_totals[group])),
                    ("Остаток", [None] * len(columns), None),
                ]
                for label_text, values, total_val in metric_rows:
                    mrow = st.columns(ratios)
                    with mrow[0].container(key=f"grouplabel-plan-{view}-{group}-{label_text}-c0"):
                        st.markdown("")
                    with mrow[1].container(key=f"grouplabel-plan-{view}-{group}-{label_text}-c1"):
                        st.markdown("")
                    with mrow[2].container(key=f"grouplabel-plan-{view}-{group}-{label_text}-c2"):
                        st.markdown(label_text)
                    for idx, cell in enumerate(mrow[3:-1]):
                        with cell.container(key=f"groupval-plan-{view}-{group}-{label_text}-{idx}"):
                            st.markdown(money(values[idx]) if values[idx] is not None else "")
                    with mrow[-1].container(key=f"groupval-plan-{view}-{group}-{label_text}-total"):
                        st.markdown(money(total_val) if total_val is not None else "")

        row_fact_values = [data[(group, category, subcategory, key)] for _, key in columns]
        row_plan_values = [
            _plan_col_value(period_view, year, plan_data, group, category, subcategory, None, key)
            for _, key in columns
        ]
        for idx in range(len(columns)):
            col_totals_fact[idx] += row_fact_values[idx]

        if group in collapsed:
            continue

        directions = aggregate.expense_directions(classified, group, category, subcategory)
        expandable = len(directions) > 1
        row_key3 = (group, category, subcategory)
        is_expanded = expandable and row_key3 in expanded_dirs

        # ---- строка "План" ----
        if period_view == "week":
            plan_total_row = plan.get_week(plan_data, group, category, subcategory, None, week_start_for_input)
        else:
            plan_total_row = sum(row_plan_values)

        prow = st.columns(ratios)
        with prow[0].container(key=f"rowlabel-cat-plan-{view}-{group}-{category}-{subcategory}-p"):
            st.markdown(category)
        with prow[1].container(key=f"rowlabel-tag-plan-{view}-{group}-{category}-{subcategory}-p"):
            st.markdown("План")
        with prow[2].container(key=f"rowlabel-sub-plan-{view}-{group}-{category}-{subcategory}-p"):
            if expandable:
                icon = "▾" if is_expanded else "▸"
                if st.button(f"{icon} {subcategory}", key=f"dirtoggle-plan-{view}-{group}-{category}-{subcategory}"):
                    if is_expanded:
                        expanded_dirs.discard(row_key3)
                    else:
                        expanded_dirs.add(row_key3)
                    st.rerun()
            else:
                st.markdown(subcategory or "—")
        for idx, cell in enumerate(prow[3:-1]):
            with cell.container(key=f"planval-{view}-{group}-{category}-{subcategory}-{idx}"):
                st.markdown("" if period_view == "week" else money(row_plan_values[idx]))
        with prow[-1].container(key=f"plantotal-{view}-{group}-{category}-{subcategory}"):
            if period_view == "week":
                input_key = f"planinput-{view}-{group}-{category}-{subcategory}-none"
                st.text_input(
                    "план", value=money(plan_total_row), key=input_key, label_visibility="collapsed",
                )
                pending_inputs.append((group, category, subcategory, None, input_key))
            else:
                st.markdown(money(plan_total_row))

        # ---- строка "Факт" ----
        frow = st.columns(ratios)
        with frow[0].container(key=f"rowlabel-cat-plan-{view}-{group}-{category}-{subcategory}-f"):
            st.markdown("")
        with frow[1].container(key=f"rowlabel-tag-plan-{view}-{group}-{category}-{subcategory}-f"):
            st.markdown("Факт")
        with frow[2].container(key=f"rowlabel-sub-plan-{view}-{group}-{category}-{subcategory}-f"):
            st.markdown(subcategory or "—")
        for idx, cell in enumerate(frow[3:-1]):
            with cell.container(key=f"factval-{view}-{group}-{category}-{subcategory}-{idx}"):
                st.markdown(money(row_fact_values[idx]))
        with frow[-1].container(key=f"facttotal-{view}-{group}-{category}-{subcategory}"):
            st.markdown(money(sum(row_fact_values)))

        if not is_expanded:
            continue

        for direction in directions:
            dir_label = direction if direction else "(без направления)"
            dir_plan_values = [
                _plan_col_value(period_view, year, plan_data, group, category, subcategory, direction, key)
                for _, key in columns
            ]
            if period_view == "week":
                dir_plan_total = plan.get_week(plan_data, group, category, subcategory, direction, week_start_for_input)
            else:
                dir_plan_total = sum(dir_plan_values)

            pdrow = st.columns(ratios)
            with pdrow[0].container(key=f"rowlabel-cat-plan-{view}-{group}-{category}-{subcategory}-{direction}-p"):
                st.markdown("")
            with pdrow[1].container(key=f"rowlabel-tag-plan-{view}-{group}-{category}-{subcategory}-{direction}-p"):
                st.markdown("План")
            with pdrow[2].container(key=f"rowlabel-dir-plan-{view}-{group}-{category}-{subcategory}-{direction}-p"):
                st.markdown(f"↳ {dir_label}")
            for idx, cell in enumerate(pdrow[3:-1]):
                with cell.container(key=f"planval-{view}-{group}-{category}-{subcategory}-{direction}-{idx}"):
                    st.markdown("" if period_view == "week" else money(dir_plan_values[idx]))
            with pdrow[-1].container(key=f"plantotal-{view}-{group}-{category}-{subcategory}-{direction}"):
                if period_view == "week":
                    input_key = f"planinput-{view}-{group}-{category}-{subcategory}-{direction}"
                    st.text_input(
                        "план", value=money(dir_plan_total), key=input_key, label_visibility="collapsed",
                    )
                    pending_inputs.append((group, category, subcategory, direction, input_key))
                else:
                    st.markdown(money(dir_plan_total))

            dir_fact_values = [
                aggregate.expense_direction_period_total(classified, group, category, subcategory, direction, s, e)
                for s, e in period_ranges
            ]
            fdrow = st.columns(ratios)
            with fdrow[0].container(key=f"rowlabel-cat-plan-{view}-{group}-{category}-{subcategory}-{direction}-f"):
                st.markdown("")
            with fdrow[1].container(key=f"rowlabel-tag-plan-{view}-{group}-{category}-{subcategory}-{direction}-f"):
                st.markdown("Факт")
            with fdrow[2].container(key=f"rowlabel-dir-plan-{view}-{group}-{category}-{subcategory}-{direction}-f"):
                st.markdown(f"↳ {dir_label}")
            for idx, cell in enumerate(fdrow[3:-1]):
                with cell.container(key=f"factval-{view}-{group}-{category}-{subcategory}-{direction}-{idx}"):
                    st.markdown(money(dir_fact_values[idx]))
            with fdrow[-1].container(key=f"facttotal-{view}-{group}-{category}-{subcategory}-{direction}"):
                st.markdown(money(sum(dir_fact_values)))

    total_cells = st.columns(ratios)
    total_cells[0].markdown("**ИТОГО**")
    total_cells[1].markdown("")
    total_cells[2].markdown("Факт")
    for idx, cell in enumerate(total_cells[3:-1]):
        with cell.container(key=f"facttotal-{view}-grand-{idx}"):
            st.markdown(money(col_totals_fact[idx]))
    with total_cells[-1].container(key=f"facttotal-{view}-grand-total"):
        st.markdown(f"**{money(sum(col_totals_fact))}**")

    header(suffix="-bottom")

    if period_view == "week" and pending_inputs:
        st.divider()
        st.caption(
            "Если разворачиваете категорию по направлениям и заполняете план там — "
            "итог по категории пересчитается как сумма направлений."
        )
        if st.button("💾 Сохранить план", type="primary", key=f"save_plan_{view}"):
            dir_sums = {}  # (group, category, subcategory) -> сумма введённых направлений
            parent_input_key = {}  # (group, category, subcategory) -> ключ поля самой категории
            for group, category, subcategory, direction, input_key in pending_inputs:
                value = parse_money(st.session_state[input_key])
                plan.set_week(plan_data, group, category, subcategory, direction, week_start_for_input, value)
                row_key3 = (group, category, subcategory)
                if direction is not None:
                    dir_sums[row_key3] = dir_sums.get(row_key3, 0.0) + value
                else:
                    parent_input_key[row_key3] = input_key
            # категория развёрнута и хотя бы одно направление заполнено —
            # итог категории — не то, что вписано в её собственное поле, а
            # сумма направлений (план на всю категорию сразу написать нельзя,
            # если уже расписываете по направлениям). Поле самой категории
            # уже отрисовано в этом прогоне скрипта — Streamlit не даёт
            # напрямую переписать session_state уже созданного виджета,
            # поэтому удаляем его ключ: при st.rerun() виджет пересоздастся
            # и возьмёт значение из уже сохранённого plan_data (свежий money()).
            for row_key3, total in dir_sums.items():
                if total:
                    group, category, subcategory = row_key3
                    plan.set_week(plan_data, group, category, subcategory, None, week_start_for_input, total)
                    if row_key3 in parent_input_key:
                        st.session_state.pop(parent_input_key[row_key3], None)
            plan.save_plan(plan_data)
            st.success("План сохранён")
            st.rerun()

    st.caption(f"📅 {period_title}")


# --------------------------------------------------------------- навигация

st.sidebar.markdown("## kiwi")
page = st.sidebar.radio(
    "Раздел", ["📥 Загрузка файла", "📈 Поступления", "📉 Расходы", "📋 План"], key="page",
)

ops_file = st.sidebar.file_uploader("Выписка операций (Деньги-операции)", type=["xlsx"])
if ops_file and st.session_state.get("_ops_file_name") != ops_file.name:
    st.session_state._ops_raw = operations.read_operations(BytesIO(ops_file.getvalue()))
    st.session_state._ops_file_name = ops_file.name
    st.session_state.overrides = {}
    st.session_state.expense_overrides = {}
    st.session_state.view = "year"
    st.session_state.exp_view = "year"
    st.session_state.plan_view = "year"
    st.session_state.sel_year = None
    st.session_state.sel_month = None
    st.session_state.sel_week = None
    st.session_state.exp_sel_year = None
    st.session_state.exp_sel_month = None
    st.session_state.exp_sel_week = None

if "_ops_raw" not in st.session_state:
    st.title("kiwi")
    st.info("Загрузите файл операций в панели слева, чтобы начать.")
    st.stop()

overrides = st.session_state.setdefault("overrides", {})
expense_overrides = st.session_state.setdefault("expense_overrides", {})
income_categories = categories.load_income_categories()
tree = expenses.load_expense_tree()
mapping = expenses.load_statya_mapping()
location = expenses.build_target_location(tree)
raw_ops = st.session_state._ops_raw
classified = aggregate.classify_operations(
    raw_ops, income_categories, overrides,
    expense_tree=tree, expense_mapping=mapping, expense_location=location,
    expense_overrides=expense_overrides,
)

years = aggregate.years_present(raw_ops)
st.session_state._years = years
st.session_state.setdefault("year", years[-1])
st.session_state.setdefault("exp_year", years[-1])

st.sidebar.caption(f"Файл: {st.session_state._ops_file_name}")
st.sidebar.caption(f"Операций: {len(raw_ops)}")

if page == "📥 Загрузка файла":
    st.title("kiwi")
    st.success(f"Загружен файл: {st.session_state._ops_file_name} ({len(raw_ops)} операций)")
    st.caption("Выберите раздел слева — «Поступления», «Расходы» или «План».")
elif page == "📈 Поступления":
    render_income_page(classified, income_categories)
elif page == "📉 Расходы":
    render_expense_page(classified, tree)
else:
    render_plan_page(classified, tree)
