import datetime
import json
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# Конфигурация страницы
st.set_page_config(
    page_title="Panel Właściciela", page_icon="1.png", layout="centered"
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

  st.sidebar.markdown("---")
  st.sidebar.markdown(
      "<p style='text-align: center; color: gray; font-size: 12px;'>"
      "Stworzone przez Team OverFlow</p>",
      unsafe_allow_html=True,
  )


if "authenticated" not in st.session_state:
  st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
  login_screen()
else:
  owner = st.session_state["current_owner"]
  sheet = st.session_state["sheet_name"]

  st.sidebar.image("1.png", width=160)

  st.sidebar.title(f"{owner}")
  if st.sidebar.button("Wyloguj się"):
    st.session_state["authenticated"] = False
    st.rerun()

  st.sidebar.markdown("---")
  st.sidebar.markdown(
      "<p style='text-align: center; color: gray; font-size: 12px;'>"
      "Stworzone przez Team OverFlow</p>",
      unsafe_allow_html=True,
  )

  st.title(f"📊 Statystyki: {owner}")

  with st.spinner("Pobieranie danych..."):
    rows = get_full_sheet_data(sheet)

  if rows:
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


    def style_cells(df):
      styles = pd.DataFrame("", index=df.index, columns=df.columns)
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


    def get_stats_df(start_row, end_row):
      stats_data = []
      for r in range(start_row, end_row):
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

      if len(stats_data) > 0:
        first_row_str = str(stats_data[0][0]).lower()
        if "miesiac" in first_row_str or "miesiąc" in first_row_str:
          stats_data = stats_data[1:]

        return pd.DataFrame(stats_data, columns=["Miesiąc", "Suma miesiąc"])
      return pd.DataFrame()


    def style_stats(df):
      styles = pd.DataFrame("", index=df.index, columns=df.columns)
      for idx, row in df.iterrows():
        row_str = " ".join([str(val).upper() for val in row.values])
        is_year_sum = "SUMA" in row_str or "ROK" in row_str

        for col in df.columns:
          if is_year_sum:
            styles.loc[idx, col] = (
                "background-color: #e6a100; color: #000000; font-weight:"
                " bold;"
            )
          else:
            styles.loc[idx, col] = "background-color: #fff8e1"
      return styles


    def parse_currency(val):
      if pd.isna(val) or val == "":
        return 0.0
      val_str = (
          str(val)
          .replace(" ", "")
          .replace("zł", "")
          .replace(",", ".")
          .strip()
      )
      try:
        return float(val_str)
      except ValueError:
        return 0.0


    def get_best_month_and_total(start_row, end_row, total_row_idx):
      """Ищет лучший месяц в диапазоне K:L и берет итоговую сумму года из конкретной ячейки L"""
      months_data = []

      for r in range(start_row, end_row):
        if r < len(rows):
          row_vals = rows[r]
          if len(row_vals) >= 12:
            m_name = row_vals[10]  # Колонка K (индекс 10)
            m_sum_str = row_vals[11]  # Колонка L (индекс 11)
            if m_name and m_sum_str:
              val_num = parse_currency(m_sum_str)
              months_data.append(
                  {"miesiąc": m_name, "suma_str": m_sum_str, "val": val_num}
              )

      best_month_str = "Brak"
      if months_data:
        best_obj = max(months_data, key=lambda x: x["val"])
        best_month_str = f"{best_obj['miesiąc']} ({best_obj['suma_str']} zł)"

      total_year_val = 0.0
      if total_row_idx < len(rows) and len(rows[total_row_idx]) >= 12:
        total_year_val = parse_currency(rows[total_row_idx][11])

      return best_month_str, total_year_val


    def calculate_occupancy(df_booking):
      booked_nights = 0
      occupancy_rate = 0.0
      if not df_booking.empty:
        price_col = None
        for col in df_booking.columns:
          if "CENA" in col.upper() or "KOLUMNA_3" in col.upper():
            price_col = col
            break

        if price_col:
          valid_rows = df_booking[
              df_booking[price_col].astype(str).str.strip().str.upper()
              != "BRAK"
          ]
          valid_rows = valid_rows[
              valid_rows[price_col].astype(str).str.strip() != ""
          ]
          valid_rows = valid_rows[
              valid_rows[price_col].astype(str).str.lower() != "nan"
          ]
          booked_nights = len(valid_rows)

        occupancy_rate = (booked_nights / 365) * 100

      return booked_nights, occupancy_rate


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

      df_stat_2026 = get_stats_df(22, 37)
      df_stat_2025 = get_stats_df(6, 20)

      df_b_2026 = (
          df_2026 if "df_2026" in locals() and not df_2026.empty else get_full_booking_df(0)
      )
      df_b_2025 = (
          df_2025 if "df_2025" in locals() and not df_2025.empty else get_full_booking_df(5)
      )

      # 2026 год: месяцы K24:L35 (индексы 23 по 35), итог года в L36 (индекс 35)
      best_26, inc_26 = get_best_month_and_total(23, 35, 35)
      nights_26, occ_26 = calculate_occupancy(df_b_2026)

      # 2025 год: месяцы K8:L19 (индексы 7 по 19), итог года в L20 (индекс 19)
      best_25, inc_25 = get_best_month_and_total(7, 19, 19)
      nights_25, occ_25 = calculate_occupancy(df_b_2025)

      income_diff = inc_26 - inc_25

      st.markdown("---")
      st.markdown("#### 🚀 Podsumowanie roku 2026")
      col_m1, col_m2, col_m3 = st.columns(3)
      with col_m1:
        st.metric(
            label="Łączny przychód (2026)",
            value=f"{inc_26:,.2f} zł".replace(",", " ").replace(".", ","),
            delta=f"{income_diff:,.2f} zł vs 2025".replace(",", " ").replace(
                ".", ","
            ),
        )
      with col_m2:
        st.metric(label="Najbardziej zyskowny miesiąc", value=best_26)
      with col_m3:
        st.metric(
            label="Zarezerwowane noce / Obłożenie",
            value=f"{nights_26} nocy",
            delta=f"{occ_26:.1f}% roku",
        )

      st.markdown("---")
      st.markdown("#### 📜 Podsumowanie roku 2025")
      col_m4, col_m5, col_m6 = st.columns(3)
      with col_m4:
        st.metric(
            label="Łączny przychód (2025)",
            value=f"{inc_25:,.2f} zł".replace(",", " ").replace(".", ","),
        )
      with col_m5:
        st.metric(label="Najbardziej zyskowny miesiąc", value=best_25)
      with col_m6:
        st.metric(
            label="Zarezerwowane noce / Obłożenie",
            value=f"{nights_25} nocy",
            delta=f"{occ_25:.1f}% roku",
        )

      st.markdown("---")
      st.markdown("##### Przychód najem brutto 2026")
      if not df_stat_2026.empty:
        styled_stat_2026 = df_stat_2026.style.apply(style_stats, axis=None)
        st.dataframe(styled_stat_2026, use_container_width=True, hide_index=True)

      st.markdown("---")

      st.markdown("##### Przychód najem brutto 2025")
      if not df_stat_2025.empty:
        styled_stat_2025 = df_stat_2025.style.apply(style_stats, axis=None)
        st.dataframe(styled_stat_2025, use_container_width=True, hide_index=True)

  else:
    st.warning("Nie udało się pobrać danych z arkusza.")
