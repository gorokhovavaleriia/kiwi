"""Альтернативный интерфейс — та же логика (aggregate/classify/categories),
но сетка отображается цветными кликабельными плитками вместо st.dataframe.
Текущая табличная версия (app.py) оставлена как есть для сравнения —
запускать эту версию отдельно: `streamlit run app_tiles.py`."""

import calendar
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

import aggregate
import categories
import classify
import operations

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

.kiwi-header-cell {
    display: flex; align-items: center; justify-content: center;
    min-height: 2.5rem; font-weight: 600; font-size: 0.78rem; white-space: nowrap;
    margin-bottom: 3px;
}
.kiwi-header-total {
    display: flex; align-items: center; justify-content: center;
    min-height: 2.9rem; font-weight: 800; font-size: 0.95rem; margin-bottom: 3px;
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


def render_grid(view, rows, columns, data, year, sel_state_key, on_nav, home_target):
    """Строит сетку плитками. on_nav(col_key) вызывается при клике по
    заголовку столбца (year/month, весь заголовок кликабелен — без стрелки,
    это и так понятно) — None, если у уровня нет кликабельных заголовков
    (week). home_target — что открыть по кнопке "Домой" у TOTAL (None =>
    просто заголовок TOTAL без кнопки)."""
    ratios = [1.6, 1.8] + [1] * len(columns) + [1.6]

    def render_header(suffix=""):
        header = st.columns(ratios)
        header[0].markdown("**Категория**")
        header[1].markdown("**Подкатегория**")
        for cell, (label, key) in zip(header[2:-1], columns):
            short_label = _display_label(view, label, key)
            if on_nav is not None:
                with cell.container(key=f"nav-{view}-{label}{suffix}"):
                    if st.button(short_label, key=f"navbtn-{view}-{label}{suffix}", width="stretch"):
                        on_nav(key)
            else:
                cell.markdown(f'<div class="kiwi-header-cell">{short_label}</div>', unsafe_allow_html=True)
        if home_target:
            with header[-1].container(key=f"home-{view}{suffix}"):
                if st.button("🏠 Домой", key=f"homebtn-{view}{suffix}", width="stretch"):
                    st.session_state.view = home_target
                    st.session_state[sel_state_key] = None
                    st.rerun()
        else:
            header[-1].markdown('<div class="kiwi-header-total">TOTAL</div>', unsafe_allow_html=True)

    render_header()

    selected = st.session_state.get(sel_state_key)
    col_totals = [0.0] * len(columns)
    for category, subcategory in rows:
        row_cells = st.columns(ratios)
        with row_cells[0].container(key=f"rowlabel-cat-{category}-{subcategory}"):
            st.markdown(category)
        with row_cells[1].container(key=f"rowlabel-sub-{category}-{subcategory}"):
            st.markdown(subcategory or "—")
        row_sum = 0.0
        for i, ((label, key), cell) in enumerate(zip(columns, row_cells[2:-1])):
            value = data[(category, subcategory, key)]
            row_sum += value
            col_totals[i] += value
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

    render_header(suffix="-bottom")


st.markdown("## kiwi — поступления (плитки)")

ops_file = st.file_uploader("Выписка операций (Деньги-операции)", type=["xlsx"])
if not ops_file:
    st.info("Загрузите файл операций.")
    st.stop()

if st.session_state.get("_ops_file_name") != ops_file.name:
    st.session_state._ops_raw = operations.read_operations(BytesIO(ops_file.getvalue()))
    st.session_state._ops_file_name = ops_file.name
    st.session_state.overrides = {}
    st.session_state.view = "year"
    st.session_state.sel_year = None
    st.session_state.sel_month = None
    st.session_state.sel_week = None

overrides = st.session_state.setdefault("overrides", {})
income_categories = categories.load_income_categories()
raw_ops = st.session_state._ops_raw
classified = aggregate.classify_operations(raw_ops, income_categories, overrides)

years = aggregate.years_present(raw_ops)
st.session_state.setdefault("year", years[-1])
st.session_state.setdefault("view", "year")

view = st.session_state.view
year = st.session_state.year

st.divider()

if view == "year":
    period_title = f"{year} год"
    st.markdown(f"### {period_title}")
    if len(years) > 1:
        year = st.selectbox("Год", years, index=years.index(year))
        st.session_state.year = year
        period_title = f"{year} год"
    rows, columns, data = aggregate.year_table(classified, income_categories, year)

    def go_month(month):
        st.session_state.month = month
        st.session_state.view = "month"
        st.session_state.sel_month = None
        st.rerun()

    render_grid("year", rows, columns, data, year, "sel_year", go_month, home_target=None)
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

    render_grid("month", rows, columns, data, year, "sel_month", go_week, home_target="year")
    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])
    sel = st.session_state.get("sel_month")

else:  # week
    week_start, week_end = st.session_state.week
    period_title = (f"{aggregate.MONTH_NAMES[week_start.month - 1]}, "
                     f"{week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}")
    st.markdown(f"### {period_title}")
    if st.button("🏠 Домой (к месяцу)"):
        st.session_state.view = "month"
        st.rerun()
    rows, columns, data = aggregate.week_table(classified, income_categories, week_start, week_end)
    render_grid("week", rows, columns, data, year, "sel_week", on_nav=None, home_target=None)
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
    if st.button("✕ Показать все операции периода"):
        st.session_state[{"year": "sel_year", "month": "sel_month", "week": "sel_week"}[view]] = None
        st.rerun()
    matching_indices = [
        i for i, op in enumerate(classified)
        if slice_start <= op["date"] <= slice_end and op["category"] == category and op["subcategory"] == subcategory
    ]
else:
    st.caption("Клик по плитке в таблице выше отфильтрует операции здесь. Сейчас показан весь период.")
    matching_indices = [
        i for i, op in enumerate(classified)
        if period_start <= op["date"] <= period_end and not op["excluded"]
    ]

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
        if st.button("💾 Сохранить изменения", type="primary"):
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
    "⬇️ Скачать (2 вкладки)", data=buf.getvalue(), file_name="kiwi_срез.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
