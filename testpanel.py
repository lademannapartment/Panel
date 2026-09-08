import datetime
import json
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# Konfiguracja strony pod urządzenia mobilne
st.set_page_config(
    page_title="Panel Właściciela", page_icon="🏠", layout="centered"
)

# Nazwa Twojego arkusza Google Sheets
SPREADSHEET_NAME = "Panel Poglądowy"

# Baza danych haseł dla właścicieli
USERS = {
    "Pow 3a/15": {
        "password": "123",
        "sheet_name": "Pow 3a/15",
    },
}


def get_full_sheet_data(sheet_name):
  try:
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # Читаем JSON-строку из секретов и преобразуем в словарь
    secret_str = st.secrets["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(secret_str)

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open(SPREADSHEET_NAME)
    worksheet = spreadsheet.worksheet(sheet_name)
    return worksheet.get_all_values()
  except Exception as e:
    st.error(f"Błąd ładowania danych: {e}")
    return None


def login_screen():
  st.title("🏠 Panel Właściciela")
  with st.form("login_form"):
    owner_name = st.selectbox("Wybierz mieszkanie", options=list(USERS.keys()))
    password = st.text_input("Hasło", type="password")
    submit_button = st.form_submit_button("Zaloguj się")

    if submit_button:
      if USERS[owner_name]["password"] == password:
        st.session_state["authenticated"] = True
        st.session_state["current_owner"] = owner_name
        st.session_state["sheet_name"] = USERS[owner_name]["sheet_name"]
        st.rerun()
      else:
        st.error("Nieprawidłowe hasło!")


if "authenticated" not in st.session_state:
  st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
  login_screen()
else:
  owner = st.session_state["current_owner"]
  sheet = st.session_state["sheet_name"]

  st.sidebar.title(f"🏠 {owner}")
  if st.sidebar.button("Wyloguj się"):
    st.session_state["authenticated"] = False
    st.rerun()

  st.title(f"📊 Statystyki: {owner}")

  with st.spinner("Pobieranie danych..."):
    rows = get_full_sheet_data(sheet)

  if rows:
    # 1. Informacje ogólne (Kolumna C to indeks 2)
    st.markdown("### ⚙️ Informacje ogólne")
    col1, col2 = st.columns(2)
    with col1:
      st.markdown(
          f"**Sprzątanie:** {rows[0][2] if len(rows) > 0 and len(rows[0]) > 2 else ''}"
      )
      st.markdown(
          f"**Check out:** {rows[1][2] if len(rows) > 1 and len(rows[1]) > 2 else ''}"
      )
    with col2:
      st.markdown(
          f"**Check in:** {rows[2][2] if len(rows) > 2 and len(rows[2]) > 2 else ''}"
      )

    if len(rows) > 4 and len(rows[4]) > 2 and rows[4][2]:
      st.markdown(f"🔗 **Link:** [Otwórz link]({rows[4][2]})")

    st.markdown("---")

    def get_full_booking_df(start_col_idx):
      if len(rows) <= 6:
        return pd.DataFrame()
      headers = rows[6][start_col_idx : start_col_idx + 4]
      data_rows = [r[start_col_idx : start_col_idx + 4] for r in rows[7:]]

      unique_headers = []
      seen = {}
      for i, h in enumerate(headers):
        h_str = str(h).strip()
        if h_str == "":
          h_str = f"Kolumna_{i}"
        if h_str in seen:
          seen[h_str] += 1
          h_str = f"{h_str}_{seen[h_str]}"
        else:
          seen[h_str] = 0
        unique_headers.append(h_str)

      return pd.DataFrame(data_rows, columns=unique_headers)

    # Выборочная покраска ячеек графика с подсвечиванием сегодняшней даты и итогов
    def style_cells(df):
      styles = pd.DataFrame("", index=df.index, columns=df.columns)

      # Получаем сегодняшнюю дату (например, в форматах вроде "08.09" или "08.09.2026")
      today_d_m = datetime.date.today().strftime("%d.%m")
      today_full = datetime.date.today().strftime("%d.%m.%Y")

      for idx, row in df.iterrows():
        row_str = " ".join([str(val).upper() for val in row.values])
        is_summary_row = "SUMA" in row_str or "ŚREDNIA" in row_str

        for col in df.columns:
          col_upper = col.upper()
          val = str(row[col]).strip()
          val_upper = val.upper()

          if is_summary_row:
            styles.loc[idx, col] = "background-color: #fff3cd"
          else:
            # Подсветка сегодняшней даты в колонках даты
            if "DATA" in col_upper and (
                today_full in val or today_d_m in val
            ):
              styles.loc[idx, col] = (
                  "background-color: #ffe066; color: #000000; font-weight:"
                  " bold;"
              )
            elif "DATA" in col_upper or "LP" in col_upper:
              styles.loc[idx, col] = "background-color: #e0e0e0"
            elif "PORTAL" in col_upper:
              if "BOOKING" in val_upper:
                styles.loc[idx, col] = "background-color: #b8ccf8"
              else:
                styles.loc[idx, col] = "background-color: #e0e0e0"
            elif "CENA" in col_upper or "KOLUMNA_3" in col_upper:
              if val != "" and val.lower() != "nan":
                styles.loc[idx, col] = "background-color: #d4edda"
              else:
                styles.loc[idx, col] = "background-color: #e0e0e0"
            else:
              styles.loc[idx, col] = "background-color: #e0e0e0"

      return styles

    def get_stats_df(start_row):
      stats_data = []
      # Увеличиваем диапазон, чтобы точно захватить шапку, 12 месяцев и строку suma rok
      for r in range(start_row, start_row + 16):
        if r < len(rows):
          row_vals = rows[r]
          if len(row_vals) >= 12:
            m_val = row_vals[10]
            s_val = row_vals[11]
            if (
                m_val != ""
                or s_val != ""
                or "suma" in str(m_val).lower()
                or "rok" in str(m_val).lower()
            ):
              stats_data.append([m_val, s_val])
      if len(stats_data) > 1:
        return pd.DataFrame(stats_data[1:], columns=stats_data[0])
      return pd.DataFrame()

    def style_stats(df):
      styles = pd.DataFrame("", index=df.index, columns=df.columns)
      for idx, row in df.iterrows():
        row_str = " ".join([str(val).upper() for val in row.values])
        # Точное определение строки итога года
        is_year_sum = "SUMA" in row_str or "ROK" in row_str

        for col in df.columns:
          if is_year_sum:
            # Приятный янтарно-золотой оттенок для строки suma rok
            styles.loc[idx, col] = (
                "background-color: #e6a100; color: #000000; font-weight:"
                " bold;"
            )
          else:
            # Нежный пастельно-желтый фон для месяцев
            styles.loc[idx, col] = "background-color: #fff8e1"
      return styles

    # 2. Вкладки (2026: A-D [индекс 0], 2025: F-I [индекс 5])
    tab1, tab2, tab3 = st.tabs(
        ["📅 Grafik 2026", "📅 Grafik 2025", "📊 Przychody (Statystyka)"]
    )

    with tab1:
      st.markdown("### Grafik rezerwacji 2026")
      df_2026 = get_full_booking_df(0)
      if not df_2026.empty:
        styled_2026 = df_2026.style.apply(style_cells, axis=None)
        st.dataframe(styled_2026, use_container_width=True)
      else:
        st.info("Brak danych.")

    with tab2:
      st.markdown("### Grafik rezerwacji 2025")
      df_2025 = get_full_booking_df(5)
      if not df_2025.empty:
        styled_2025 = df_2025.style.apply(style_cells, axis=None)
        st.dataframe(styled_2025, use_container_width=True)
      else:
        st.info("Brak danych.")

    with tab3:
      st.markdown("### 💰 Przychody za wynajem")

      st.markdown("##### Przychód najem brutto 2026")
      df_stat_2026 = get_stats_df(21)
      if not df_stat_2026.empty:
        styled_stat_2026 = df_stat_2026.style.apply(style_stats, axis=None)
        st.dataframe(styled_stat_2026, use_container_width=True, hide_index=True)

      st.markdown("---")

      st.markdown("##### Przychód najem brutto 2025")
      df_stat_2025 = get_stats_df(5)
      if not df_stat_2025.empty:
        styled_stat_2025 = df_stat_2025.style.apply(style_stats, axis=None)
        st.dataframe(styled_stat_2025, use_container_width=True, hide_index=True)

  else:
    st.warning("Nie udało się pobrać danych z arkusza.")
