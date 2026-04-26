import streamlit as st
import json
import os
import subprocess

st.set_page_config(page_title="ЕГЭ — панель", page_icon=None, layout="wide")
st.title("ЕГЭ — панель управления")

SUBJECTS = ["math_profile", "physics", "russian", "informatics"]


@st.cache_data
def load_framework():
    try:
        with open("modification_framework.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def get_strategies(framework: dict, subject: str) -> list[str]:
    subj = framework.get("subjects", {}).get(subject, {})
    mods = subj.get("kes_modifications", {})
    names: list[str] = []
    seen = set()
    for data in mods.values():
        for lvl in data.get("levels", []):
            name = lvl.get("name")
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    for gname in framework.get("global_modifications", {}).keys():
        if gname not in seen:
            seen.add(gname)
            names.append(gname)
    return names


def get_data_lake_stats() -> dict:
    stats = {}
    data_dir = "data"
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith(".json"):
                subj = file.replace(".json", "")
                with open(os.path.join(data_dir, file), "r", encoding="utf-8") as f:
                    try:
                        stats[subj] = len(json.load(f))
                    except json.JSONDecodeError:
                        stats[subj] = 0
    return stats


def get_vault_analytics() -> dict:
    vault_dir = "vault"
    stats = {"total": 0, "solved": 0, "errors": 0}
    if not os.path.exists(vault_dir):
        return stats
    for root, _, files in os.walk(vault_dir):
        for file in files:
            if not file.endswith(".md"):
                continue
            stats["total"] += 1
            filepath = os.path.join(root, file)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if "status: \"pass\"" in content or "#решено" in content:
                stats["solved"] += 1
            if "status: \"fail\"" in content or "#ошибка" in content:
                stats["errors"] += 1
    return stats


framework = load_framework()
lake_stats = get_data_lake_stats()
vault_stats = get_vault_analytics()

col1, col2 = st.columns([1, 1])

with col1:
    st.header("Генерация задач")
    st.caption("Запуск `generator.py` с выбранными параметрами.")

    with st.container(border=True):
        if not framework:
            st.error("Файл modification_framework.json не найден.")
        else:
            selected_subject = st.selectbox("Предмет", SUBJECTS)
            strategies = get_strategies(framework, selected_subject)
            if not strategies:
                st.warning("Для выбранного предмета нет стратегий в каркасе.")
                selected_strategy = None
            else:
                selected_strategy = st.selectbox("Стратегия усложнения", strategies)

            kes_input = st.text_input("Код КЭС (например, 2.5 или 4.1)")
            n_tasks = st.slider("Количество задач", min_value=1, max_value=10, value=3)
            out_dir = st.text_input("Каталог вывода", value=f"vault/{selected_subject}")

            if st.button("Сгенерировать", use_container_width=True, disabled=not selected_strategy):
                if not kes_input.strip():
                    st.warning("Укажите код КЭС.")
                else:
                    cmd = [
                        "python", "generator.py",
                        "--subject", selected_subject,
                        "--kes", kes_input.strip(),
                        "--strategy", selected_strategy,
                        "--n", str(n_tasks),
                        "--out", out_dir,
                    ]
                    with st.spinner(f"Запрос к LLM ({n_tasks} шт.)…"):
                        result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        st.success("Готово. Файлы сохранены.")
                        if result.stdout:
                            st.code(result.stdout, language="text")
                    else:
                        st.error("Ошибка выполнения.")
                        if result.stderr:
                            st.code(result.stderr, language="text")

with col2:
    st.header("Состояние")

    st.subheader("Obsidian-хранилище")
    v_col1, v_col2, v_col3 = st.columns(3)
    v_col1.metric("Всего задач", vault_stats["total"])
    v_col2.metric("Решено", vault_stats["solved"])
    v_col3.metric("С ошибками", vault_stats["errors"])

    if vault_stats["total"] > 0:
        st.progress(
            vault_stats["solved"] / vault_stats["total"],
            text="Доля решённых",
        )
    else:
        st.caption("Хранилище пустое.")

    st.divider()

    st.subheader("Банк ФИПИ (data/)")
    if not lake_stats:
        st.caption("Каталог data/ пуст. Запустите scraper.py.")
    else:
        for subj, count in lake_stats.items():
            st.metric(f"{subj}", count)
