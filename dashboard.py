import streamlit as st
import json
import os
import subprocess

# --- Настройки страницы ---
st.set_page_config(page_title="Superhuman OS", page_icon="🧠", layout="wide")
st.title("🧠 Superhuman Command Center")

# --- Загрузка данных (Data Layer) ---
@st.cache_data
def load_framework():
    try:
        with open("modification_framework.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_data_lake_stats():
    stats = {}
    data_dir = "data"
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith(".json"):
                subj = file.replace(".json", "")
                with open(os.path.join(data_dir, file), "r", encoding="utf-8") as f:
                    try:
                        stats[subj] = len(json.load(f))
                    except:
                        stats[subj] = 0
    return stats

def get_vault_analytics():
    vault_dir = "vault"
    stats = {"total": 0, "solved": 0, "errors": 0}
    
    if not os.path.exists(vault_dir):
        return stats
        
    for root, _, files in os.walk(vault_dir):
        for file in files:
            if file.endswith(".md"):
                stats["total"] += 1
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Простой парсинг тегов из всего файла (включая YAML)
                    if "#решено" in content:
                        stats["solved"] += 1
                    if "#ошибка" in content:
                        stats["errors"] += 1
    return stats

framework = load_framework()
lake_stats = get_data_lake_stats()
vault_stats = get_vault_analytics()

# --- Интерфейс (UI Layer) ---
col1, col2 = st.columns([1, 1])

# ЛЕВАЯ КОЛОНКА: Генератор
with col1:
    st.header("⚡ Ручная генерация (Fuzzing)")
    st.markdown("Запуск точечных мутаций через API.")
    
    with st.container(border=True):
        if not framework:
            st.error("Файл modification_framework.json не найден!")
        else:
            subjects = list(framework.keys())
            selected_subject = st.selectbox("Предмет", subjects)
            
            # Динамически подгружаем стратегии для выбранного предмета
            strategies = list(framework[selected_subject].get("strategies", {}).keys())
            selected_strategy = st.selectbox("Стратегия мутации", strategies)
            
            kes_input = st.text_input("Код КЭС (например, 2.5 или 4.1)")
            n_tasks = st.slider("Количество задач", min_value=1, max_value=10, value=3)
            
            if st.button("🚀 Сгенерировать в Vault", use_container_width=True):
                if not kes_input:
                    st.warning("Введи код КЭС!")
                else:
                    cmd = [
                        "python", "generator.py",
                        "--subject", selected_subject,
                        "--kes", kes_input,
                        "--strategy", selected_strategy,
                        "--n", str(n_tasks)
                    ]
                    
                    with st.spinner(f"Отправка запроса к Claude API ({n_tasks} шт.)..."):
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            st.success("Успешно! Файлы добавлены в Obsidian.")
                            st.balloons()
                        else:
                            st.error(f"Ошибка API/Скрипта:\n{result.stderr}")

# ПРАВАЯ КОЛОНКА: Аналитика
with col2:
    st.header("📊 Состояние системы")
    
    st.subheader("Внешний мозг (Obsidian Vault)")
    v_col1, v_col2, v_col3 = st.columns(3)
    v_col1.metric("Сгенерировано", vault_stats["total"])
    v_col2.metric("🟢 Решено", vault_stats["solved"])
    v_col3.metric("🔴 Ошибки", vault_stats["errors"])
    
    st.progress(
        vault_stats["solved"] / vault_stats["total"] if vault_stats["total"] > 0 else 0, 
        text="Процент решенных (Winrate)"
    )
    
    st.divider()
    
    st.subheader("Озеро сырых данных (ФИПИ)")
    for subj, count in lake_stats.items():
        st.metric(f"Сырых задач: {subj}", count)
