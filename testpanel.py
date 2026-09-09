import datetime
import streamlit as st

# ==========================================
# КОНФИГУРАЦИЯ И БАЗА ДАННЫХ СОТРУДНИКОВ
# ==========================================

# База данных сотрудников, их Google Calendar ID и единый пароль
EMPLOYEES_CALENDARS = {
    "Michał": {
        "calendar_id": "5d133c3132c8c878863e2d73f88f80bd2cd26e135dffb5736584185ca56dbdf3@group.calendar.google.com",
        "password": "0001",
    },
    "Anna": {
        "calendar_id": "another_calendar_id_example@group.calendar.google.com",
        "password": "0001",
    },
}

st.set_page_config(page_title="Portal Zadań", page_icon="👤", layout="centered")

# Инициализация состояния сессии
if "role" not in st.session_state:
    st.session_state["role"] = None

if "emp_authenticated" not in st.session_state:
    st.session_state["emp_authenticated"] = False

# ==========================================
# ГЛАВНОЕ МЕНЮ: ВЫБОР РОЛИ
# ==========================================
if st.session_state["role"] is None:
    st.title("Wybierz portal")
    st.markdown("Zaloguj się jako administrator lub pracownik.")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👑 Administrator", use_container_width=True):
            st.session_state["role"] = "admin"
            st.rerun()

    with col2:
        if st.button("👤 Pracownik", use_container_width=True):
            st.session_state["role"] = "employee"
            st.rerun()

# ==========================================
# ПОРТАЛ АДМИНИСТРАТОРА
# ==========================================
elif st.session_state["role"] == "admin":
    st.sidebar.image("1.png", width=160)
    if st.sidebar.button("⬅️ Powrót do wyboru roli"):
        st.session_state["role"] = None
        st.rerun()

    st.title("👑 Panel Administratora")
    st.markdown("Tutaj możesz zarządzać zadaniami i kalendarzami.")

    # Пример содержимого админ-панели
    admin_action = st.selectbox(
        "Wybierz akcję", ["Dodaj zadanie", "Przeglądaj harmonogram"]
    )

    if admin_action == "Dodaj zadanie":
        st.subheader("Tworzenie nowego zadania")
        with st.form("add_task_form"):
            task_title = st.text_input("Nazwa zadania / Klient")
            task_employee = st.selectbox(
                "Przypisz pracownika", list(EMPLOYEES_CALENDARS.keys())
            )
            task_date = st.date_input("Data zadania", datetime.date.today())
            submit_task = st.form_submit_button("Utwórz zadanie")

            if submit_task:
                if task_title:
                    st.success(
                        f"Zadanie '{task_title}' zostało pomyślnie przypisane do {task_employee} na dzień {task_date.strftime('%d.%m.%Y')}!"
                    )
                else:
                    st.error("Wpisz nazwę zadania!")

    elif admin_action == "Przeglądaj harmonogram":
        st.subheader("Harmonogram wszystkich pracowników")
        st.info("Tutaj pojawi się podgląd kalendarzy.")

# ==========================================
# ПОРТАЛ СОТРУДНИКА
# ==========================================
elif st.session_state["role"] == "employee":
    st.sidebar.image("1.png", width=160)
    if st.sidebar.button("⬅️ Powrót do wyboru roli"):
        st.session_state["role"] = None
        st.session_state["emp_authenticated"] = False
        st.rerun()

    # Проверка авторизации сотрудника
    if not st.session_state["emp_authenticated"]:
        st.title("👤 Panel Pracownika - Logowanie")
        with st.form("emp_login_form"):
            emp_name = st.selectbox(
                "Wybierz swoje imię",
                ["-- Wybierz --"] + list(EMPLOYEES_CALENDARS.keys()),
            )
            password = st.text_input("Hasło", type="password")
            submit_button = st.form_submit_button("Zaloguj się")

            if submit_button:
                if emp_name == "-- Wybierz --":
                    st.error("Proszę wybrać imię!")
                elif EMPLOYEES_CALENDARS[emp_name]["password"] == password:
                    st.session_state["emp_authenticated"] = True
                    st.session_state["current_employee"] = emp_name
                    st.rerun()
                else:
                    st.error("Nieprawidłowe hasło!")
    else:
        emp_name = st.session_state["current_employee"]
        calendar_id = EMPLOYEES_CALENDARS[emp_name]["calendar_id"]

        st.title("👤 Panel Pracownika")
        st.markdown(f"Zalogowany pracownik: **{emp_name}**")

        if st.button("Wyloguj się"):
            st.session_state["emp_authenticated"] = False
            st.rerun()

        st.markdown("### Kalendarz zadań z Google Calendar")

        selected_date = st.date_input(
            "Wybierz dzień", value=datetime.date.today(), key="emp_date"
        )
        st.markdown(
            f"📅 Wyświetlanie zadań na dzień: **{selected_date.strftime('%d.%m.%Y')}**"
        )

        # Здесь вы можете разместить логику интеграции с Google Calendar для получения событий по переменной calendar_id
        st.info(
            f"Pobieranie zadań dla kalendarza ID: `{calendar_id}` на дату {selected_date}..."
        )
