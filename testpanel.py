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

# Baza danych haseł i przypisanych arkuszy dla właścicieli
USERS = {
    "Pow 3a/15": {
        "password": "123",
        "sheet_name": "Pow 3a/15",
        "type": "single",
    },
    "Legionów": {
        "password": "321",
        "sheet_name": "Legionów",
        "type": "legionow",
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
        st.session_state["owner_type"] = USERS[owner_name]["type"]
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
  owner_type = st.session_state.get("owner_type", "single")

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


    # Функции для Pow 3a/15
    def get_stats_df_single(start_row, end_row):
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

      if len(stats_data) > 1:
        return pd.DataFrame(stats_data[1:], columns=["Miesiąc", "Suma miesiąc"])
      return pd.DataFrame()


    def get_best_month_and_total_single(start_row, end_row, total_row_idx):
      months_data = []
      for r in range(start_row, end_row):
        if r < len(rows):
          row_vals = rows[r]
          if len(row_vals) >= 12:
            m_name = row_vals[10]
            m_sum_str = row_vals[11]
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


    # Функции dla Legionów (суммируем 3 комнаты из колонок AG, AH, AI -> индексы 32, 33, 34)
    def get_stats_df_legionow(start_row, end_row):
      stats_data = []
      for r in range(start_row, end_row):
        if r < len(rows):
          row_vals = rows[r]
          if len(row_vals) > 34:
            m_val = row_vals[31]  # Колонка AF (месяц)
            s1 = parse_currency(row_vals[32])
            s2 = parse_currency(row_vals[33])
            s3 = parse_currency(row_vals[34])
            total_sum = s1 + s2 + s3

            is_sum_row = "suma" in str(m_val).lower() or "rok" in str(
                m_val
            ).lower()

            if m_val != "" or total_sum > 0 or is_sum_row:
              sum_str = (
                  f"{total_sum:,.2f} zł"
                  .replace(",", " ")
                  .replace(".", ",")
                  if total_sum > 0
                  else row_vals[32]
              )
              stats_data.append([m_val, sum_str])

      if len(stats_data) > 0:
        first_row_str = str(stats_data[0][0]).lower()
        if "miesiac" in first_row_str or "miesiąc" in first_row_str:
          stats_data = stats_data[1:]
        return pd.DataFrame(stats_data, columns=["Miesiąc", "Suma miesiąc"])
      return pd.DataFrame()


    def get_best_month_and_total_legionow(start_row, end_row, total_row_idx):
      months_data = []
      for r in range(start_row, end_row):
        if r < len(rows):
          row_vals = rows[r]
          if len(row_vals) > 34:
            m_name = row_vals[31]
            s1 = parse_currency(row_vals[32])
            s2 = parse_currency(row_vals[33])
            s3 = parse_currency(row_vals[34])
            total_sum = s1 + s2 + s3

            if m_name and total_sum > 0 and "suma" not in str(m_name).lower():
              months_data.append(
                  {
                      "miesiąc": m_name,
                      "suma_str": f"{total_sum:,.2f} zł"
                      .replace(",", " ")
                      .replace(".", ","),
                      "val": total_sum,
                  }
              )

      best_month_str = "Brak"
      if months_data:
        best_obj = max(months_data, key=lambda x: x["val"])
        best_month_str = f"{best_obj['miesiąc']} ({best_obj['suma_str']})"

      total_year_val = 0.0
      if total_row_idx < len(rows) and len(rows[total_row_idx]) > 34:
        ts1 = parse_currency(rows[total_row_idx][32])
        ts2 = parse_currency(rows[total_row_idx][33])
        ts3 = parse_currency(rows[total_row_idx][34])
        total_year_val = ts1 + ts2 + ts3

      return best_month_str, total_year_val


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

    if owner_type == "legionow":
      with tab1:
        st.markdown("### Grafik rezerwacji 2026 (Wybierz pokój)")
        room_choice_26 = st.selectbox(
            "Pokój (2026)",
            [
                rows[6][0] if len(rows[6]) > 0 else "Pokój 1",
                rows[6][4] if len(rows[6]) > 4 else "Pokój 2",
                rows[6][8] if len(rows[6]) > 8 else "Pokój 3",
            ],
            key="r26",
        )
        offset_26 = (
            0
            if room_choice_26 == rows[6][0]
            else (4 if room_choice_26 == rows[6][4] else 8)
        )
        df_2026 = get_full_booking_df(offset_26)
        if not df_2026.empty:
          styled_2026 = df_2026.style.apply(style_cells, axis=None)
          st.dataframe(styled_2026, use_container_width=True)
        else:
          st.info("Brak danych.")

      with tab2:
        st.markdown(
            "### Grafik rezerwacji 2025 (Wybierz pokój - kolumny Q:AD)"
        )
        room_choice_25 = st.selectbox(
            "Pokój (2025)",
            [
                rows[6][16] if len(rows[6]) > 16 else "Pokój 1",
                rows[6][20] if len(rows[6]) > 20 else "Pokój 2",
                rows[6][24] if len(rows[6]) > 24 else "Pokój 3",
            ],
            key="r25",
        )
        offset_25 = (
            16
            if room_choice_25 == rows[6][16]
            else (20 if room_choice_25 == rows[6][20] else 24)
        )
        df_2025 = get_full_booking_df(offset_25)
        if not df_2025.empty:
          styled_2025 = df_2025.style.apply(style_cells, axis=None)
          st.dataframe(styled_2025, use_container_width=True)
        else:
          st.info("Brak danych.")

      with tab3:
        st.markdown("### 💰 Przychody za wynajem (Całe mieszkanie Legionów 50/4)")
        df_stat_2026 = get_stats_df_legionow(22, 37)
        df_stat_2025 = get_stats_df_legionow(6, 20)

        # 2026 occupancy (A:N -> 0, 4, 8)
        n1_26, _ = calculate_occupancy(get_full_booking_df(0))
        n2_26, _ = calculate_occupancy(get_full_booking_df(4))
        n3_26, _ = calculate_occupancy(get_full_booking_df(8))
        nights_26 = n1_26 + n2_26 + n3_26
        occ_26 = min((nights_26 / (365 * 3)) * 100, 100)

        # 2025 occupancy (Q:AD -> 16, 20, 24)
        n1_25, _ = calculate_occupancy(get_full_booking_df(16))
        n2_25, _ = calculate_occupancy(get_full_booking_df(20))
        n3_25, _ = calculate_occupancy(get_full_booking_df(24))
        nights_25 = n1_25 + n2_25 + n3_25
        occ_25 = min((nights_25 / (365 * 3)) * 100, 100)

        best_26, inc_26 = get_best_month_and_total_legionow(23, 35, 35)
        best_25, inc_25 = get_best_month_and_total_legionow(7, 19, 19)
        income_diff = inc_26 - inc_25

        st.markdown("---")
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
          st.metric(label="Najbardziej zyskowny miesiąc (2026)", value=best_26)
        with col_m3:
          st.metric(
              label="Zarezerwowane noce (razem)",
              value=f"{nights_26} nocy",
              delta=f"{occ_26:.1f}% obłożenia",
          )

        st.markdown("---")
        col_m4, col_m5, col_m6 = st.columns(3)
        with col_m4:
          st.metric(
              label="Łączny przychód (2025)",
              value=f"{inc_25:,.2f} zł".replace(",", " ").replace(".", ","),
          )
        with col_m5:
          st.metric(label="Najbardziej zyskowny miesiąc (2025)", value=best_25)
        with col_m6:
          st.metric(
              label="Zarezerwowane noce (2025)",
              value=f"{nights_25} nocy",
              delta=f"{occ_25:.1f}% obłożenia",
          )

        st.markdown("---")
        st.markdown(
            "##### Przychód najem brutto 2026 (Suma wszystkich pokoi)"
        )
        if not df_stat_2026.empty:
          styled_stat_2026 = df_stat_2026.style.apply(style_stats, axis=None)
          st.dataframe(
              styled_stat_2026, use_container_width=True, hide_index=True
          )

        st.markdown("---")
        st.markdown(
            "##### Przychód najem brutto 2025 (Suma wszystkich pokoi)"
        )
        if not df_stat_2025.empty:
          styled_stat_2025 = df_stat_2025.style.apply(style_stats, axis=None)
          st.dataframe(
              styled_stat_2025, use_container_width=True, hide_index=True
          )

    else:
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
        df_stat_2026 = get_stats_df_single(22, 37)
        if not df_stat_2026.empty:
          styled_stat_2026 = df_stat_2026.style.apply(style_stats, axis=None)
          st.dataframe(
              styled_stat_2026, use_container_width=True, hide_index=True
          )

        st.markdown("---")

        st.markdown("##### Przychód najem brutto 2025")
        df_stat_2025 = get_stats_df_single(6, 20)
        if not df_stat_2025.empty:
          styled_stat_2025 = df_stat_2025.style.apply(style_stats, axis=None)
          st.dataframe(
              styled_stat_2025, use_container_width=True, hide_index=True
          )

  else:
    st.warning("Nie udało się pobrać danych z arkusza.")
