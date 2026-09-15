from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

import aggregate
import categories
import classify
import operations

st.set_page_config(page_title="kiwi", layout="wide")


def fmt(v):
    return f"{v:,.0f}".replace(",", " ") if v else ""


def build_dataframe(rows, columns, data):
    """rows: [(категория, подкатегория)], columns: [(подпись, ключ)]."""
    table = []
    for category, subcategory in rows:
        values = [data[(category, subcategory, key)] for _, key in columns]
        table.append([category, subcategory or "", *values, sum(values)])
    col_labels = ["Категория", "Подкатегория"] + [label for label, _ in columns] + ["TOTAL"]
    df = pd.DataFrame(table, columns=col_labels)
    totals_row = ["", "ИТОГО"] + [df[c].sum() for c in col_labels[2:]]
    df.loc[len(df)] = totals_row
    return df


def display_dataframe(df):
    display_df = df.copy()
    for c in display_df.columns[2:]:
        display_df[c] = display_df[c].apply(fmt)
    st.dataframe(display_df, use_container_width=True, hide_index=True, height=min(38 * (len(df) + 1), 700))


def nav_buttons(columns, on_click_key, home_target=None):
    """Кнопки-«стрелочки» под заголовками столбцов (в st.dataframe саму
    ячейку заголовка кликабельной не сделать) +, если задан home_target,
    кнопка «Домой» рядом с TOTAL."""
    n = len(columns) + (1 if home_target else 0)
    cols = st.columns([1] * n)
    for col, (label, key) in zip(cols, columns):
        if col.button(f"▸ {label}", key=f"{on_click_key}_{key}", use_container_width=True):
            return key
    if home_target and cols[-1].button("🏠 Домой (TOTAL)", key=f"{on_click_key}_home", use_container_width=True):
        st.session_state.view = home_target
        st.rerun()
    return None


st.markdown("## kiwi — поступления")

ops_file = st.file_uploader("Выписка операций (Деньги-операции)", type=["xlsx"])
if not ops_file:
    st.info("Загрузите файл операций.")
    st.stop()

if st.session_state.get("_ops_file_name") != ops_file.name:
    st.session_state._ops_raw = operations.read_operations(BytesIO(ops_file.getvalue()))
    st.session_state._ops_file_name = ops_file.name
    st.session_state.overrides = {}
    st.session_state.view = "year"

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
    st.markdown(f"### {year} год")
    if len(years) > 1:
        year = st.selectbox("Год", years, index=years.index(year))
        st.session_state.year = year
    rows, columns, data = aggregate.year_table(classified, income_categories, year)
    df = build_dataframe(rows, columns, data)
    display_dataframe(df)
    clicked_month = nav_buttons(columns, "year_nav")
    if clicked_month:
        st.session_state.month = clicked_month
        st.session_state.view = "month"
        st.rerun()
    period_start, period_end = date(year, 1, 1), date(year, 12, 31)

elif view == "month":
    month = st.session_state.month
    st.markdown(f"### {aggregate.MONTH_NAMES[month - 1]} {year}")
    rows, columns, data = aggregate.month_table(classified, income_categories, year, month)
    df = build_dataframe(rows, columns, data)
    display_dataframe(df)
    clicked_week = nav_buttons(columns, "month_nav", "year")
    if clicked_week:
        st.session_state.week = clicked_week
        st.session_state.view = "week"
        st.rerun()
    period_start = date(year, month, 1)
    import calendar as _cal
    period_end = date(year, month, _cal.monthrange(year, month)[1])

else:  # week
    week_start, week_end = st.session_state.week
    st.markdown(f"### {aggregate.MONTH_NAMES[week_start.month - 1]}, неделя {week_start.strftime('%d.%m')}–{week_end.strftime('%d.%m.%Y')}")
    rows, columns, data = aggregate.week_table(classified, income_categories, week_start, week_end)
    df = build_dataframe(rows, columns, data)
    display_dataframe(df)
    if st.button("🏠 Домой", key="week_home"):
        st.session_state.view = "month"
        st.rerun()
    period_start, period_end = week_start, week_end

st.divider()
st.markdown("#### Операции за период")
st.caption("Кликнуть по конкретной ячейке таблицы выше средствами Streamlit нельзя — "
           "выберите строку и (необязательно) конкретный столбец из списков ниже.")

row_options = ["Все строки"] + [f"{c} / {s}" if s else c for c, s in rows]
col_options = ["Весь период"] + [label for label, _ in columns]
col_row, col_col = st.columns(2)
picked_row = col_row.selectbox("Строка", row_options, key=f"row_pick_{view}")
picked_col = col_col.selectbox("Столбец", col_options, key=f"col_pick_{view}")

if picked_col == "Весь период":
    slice_start, slice_end = period_start, period_end
else:
    key = next(k for label, k in columns if label == picked_col)
    if view == "year":
        import calendar as _cal
        slice_start = date(year, key, 1)
        slice_end = date(year, key, _cal.monthrange(year, key)[1])
    elif view == "month":
        slice_start, slice_end = key
    else:
        slice_start = slice_end = key

if picked_row == "Все строки":
    row_filter = None
else:
    row_filter = next((c, s) for c, s in rows if (f"{c} / {s}" if s else c) == picked_row)

matching_indices = [
    i for i, op in enumerate(classified)
    if slice_start <= op["date"] <= slice_end and not op["excluded"]
    and (row_filter is None or (op["category"], op["subcategory"]) == row_filter)
]

if not matching_indices:
    st.caption("Нет операций для этого выбора.")
else:
    shown = pd.DataFrame([
        {
            "#": i, "Дата": classified[i]["date"], "Сумма": classified[i]["amount"],
            "Статья": classified[i]["statya"], "Направление": classified[i]["direction"],
            "Категория": classified[i]["category"] or "", "Подкатегория": classified[i]["subcategory"] or "",
            "Описание": classified[i]["description"][:150],
        }
        for i in matching_indices
    ])
    st.caption("Отметьте галочками слева операции, которым нужно поменять категорию (можно несколько).")
    select_key = f"ops_select_{view}_{picked_row}_{picked_col}"
    result = st.dataframe(
        shown.drop(columns="#"), use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="multi-row", key=select_key,
    )
    selected_rows = result.selection.rows

    if selected_rows:
        picked_indices = [matching_indices[r] for r in selected_rows]
        if len(picked_indices) == 1:
            op = classified[picked_indices[0]]
            amount_str = f"{op['amount']:,.0f}".replace(",", " ")
            st.markdown(
                f"###### Изменить категорию операции от {op['date'].strftime('%d.%m.%Y')} "
                f"на {amount_str} ({op['description'][:80]})"
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
buf = BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Таблица")
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
