import datetime
import json
import re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import gspread
import pandas as pd
import streamlit as st

# Конфигурация страницы
st.set_page_config(
    page_title="Panel Systemu", page_icon="1.png", layout="centered"
)

# Nazwa Twojego arkusza Google Sheets
SPREADSHEET_NAME = "Panel Poglądowy"

# База данных haseł i przypisanych arkuszy dla właścicieli
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

# Общий пароль для сотрудников
EMPLOYEE_PASSWORD = "0001"

# База данных сотрудников и их Google Calendar ID
EMPLOYEES_CALENDARS = {
    "Michał": (
        "5d133c3132c8c878863e2d73f88f80bd2cd26e135dffb5736584185ca56dbdf3@group.calendar.google.com"
    ),
    "Mariusz": (
        "293f160ed66ea4ee2684afce4826cb834e2471956776c9173fef5160566a2a59@group.calendar.google.com"
    ),
    "Mikołaj G": (
        "79dce86695b483210398140e1482ede1a3f1089027b01541d616ed9ebdf532d0@group.calendar.google.com"
    ),
    "Bartek": (
        "bfb5b90610430dc76b15fe59d1029837430baba69020445217f68bf5b5ee0a6f@group.calendar.google.com"
    ),
    "Szymon": (
        "995bf8491f77234b898ee4f974ee5c16df462c102134f758badaf85918d70cdf@group.calendar.google.com"
    ),
    "Oskar": (
        "1ddcc046d5cae1bc1092bc08cd5e64b1c954785a9a189faa1766f39ca766dbd6@group.calendar.google.com"
    ),
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


# Функция для получения событий из Google Календаря
def get_google_calendar_events(calendar_id, target_date):
  try:
    scope = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar",
    ]
    secret_str = st.secrets["GOOGLE_CREDENTIALS_JSON"]
    creds_dict = json.loads(secret_str)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)

    service = build("calendar", "v3", credentials=creds)

    start_of_day = (
        datetime.datetime.combine(target_date, datetime.datetime.min.time())
        .isoformat()
        + "Z"
    )
    end_of_day = (
        datetime.datetime.combine(target_date, datetime.datetime.max.time())
        .isoformat()
        + "Z"
    )

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return events_result.get("items", [])
  except Exception as e:
    st.error(f"Błąd pobierania kalendarza Google: {e}")
    return []


# Инициализация состояний сессии
if "role" not in st.session_state:
  st.session_state["role"] = None
if "authenticated" not in st.session_state:
  st.session_state["authenticated"] = False
if "emp_authenticated" not in st.session_state:
  st.session_state["emp_authenticated"] = False

# Главный экран выбора роли, если роль еще не выбрана
if st.session_state["role"] is None:
  st.title("🔑 Wybierz portal")
  st.markdown("Wybierz, kim jesteś, aby kontynuować:")

  col1, col2 = st.columns(2)
  with col1:
    if st.button("👨‍💼 Właściciel", use_container_width=True):
      st.session_state["role"] = "owner"
      st.rerun()
  with col2:
    if st.button("👤 Pracownik", use_container_width=True):
      st.session_state["role"] = "employee"
      st.rerun()

# --- ПОРТАЛ СОТРУДНИКА ---
elif st.session_state["role"] == "employee":
  if not st.session_state["emp_authenticated"]:
    st.title("👤 Panel Pracownika - Logowanie")
    if st.button("⬅️ Powrót do wyboru roli"):
      st.session_state["role"] = None
      st.rerun()

    with st.form("employee_login_form"):
      emp_password = st.text_input("Hasło dla pracownika", type="password")
      emp_submit = st.form_submit_button("Zaloguj się")

      if emp_submit:
        if emp_password == EMPLOYEE_PASSWORD:
          st.session_state["emp_authenticated"] = True
          st.rerun()
        else:
          st.error("Nieprawidłowe hasło!")
  else:
    st.sidebar.image("1.png", width=160)
    if st.sidebar.button("Wyloguj się"):
      st.session_state["emp_authenticated"] = False
      st.rerun()
    if st.sidebar.button("⬅️ Powrót do wyboru roli"):
      st.session_state["emp_authenticated"] = False
      st.session_state["role"] = None
      st.rerun()

    st.title("👤 Panel Pracownika")
    st.markdown("### Kalendarz zadań z Google Calendar")

    emp_name = st.selectbox(
        "Wpisz/Wybierz swoje imię", ["-- Wybierz --"] + list(EMPLOYEES_CALENDARS.keys())
    )

    if emp_name != "-- Wybierz --":
      calendar_id = EMPLOYEES_CALENDARS[emp_name]

      selected_date = st.date_input(
          "Wybierz dzień", value=datetime.date.today(), key="emp_date"
      )
      st.markdown(
          f"📅 Wyświetlanie zadań na dzień: **{selected_date.strftime('%d.%m.%Y')}**"
      )

      with st.spinner("Pobieranie zadań z Google Calendar..."):
        raw_events = get_google_calendar_events(calendar_id, selected_date)

      if raw_events:
        st.markdown("#### 📋 Lista zadań:")

        # Палитра цветов Google Calendar
        google_event_colors = {
            "1": {"bg": "#7986CB", "name": "Lawenda"},
            "2": {"bg": "#33B679", "name": "Zielony"},
            "3": {"bg": "#8E24AA", "name": "Fioletowy"},
            "4": {"bg": "#E67C73", "name": "Flamingo"},
            "5": {"bg": "#F6BF26", "name": "Żółty"},
            "6": {"bg": "#F4511E", "name": "Pomarańczowy"},
            "7": {"bg": "#039BE5", "name": "Niebieski"},
            "8": {"bg": "#616161", "name": "Grafitowy"},
            "9": {"bg": "#3F51B5", "name": "Jagodowy"},
            "10": {"bg": "#0B8043", "name": "Bazyliowy (Ciemnozielony)"},
            "11": {"bg": "#D50000", "name": "Czerwony"},
        }

        default_color = "#e0e0e0"

        for event in raw_events:
          start = event["start"].get("dateTime", event["start"].get("date"))
          end = event["end"].get("dateTime", event["end"].get("date"))

          if "T" in start:
            time_str = f"{start[11:16]} - {end[11:16] if 'T' in end else 'Cały dzień'}"
          else:
            time_str = "Cały dzień"

          title = event.get("summary", "Brak tytułu")
          description = event.get("description", "").strip()

          # Если описания нет, пишем текст-заглушку
          if not description:
            display_desc = "Brak opisu dla zadania"
            desc_style = "color: #999; font-style: italic;"
          else:
            display_desc = (
                description.replace('"', "&quot;").replace("\n", "<br>")
            )
            desc_style = "color: #555;"

          # Проверка новизны задачи (создана менее 5 минут назад = 300 секунд)
          is_new = False
          created_str = event.get("created", "")
          if created_str:
            try:
              created_time = datetime.datetime.fromisoformat(
                  created_str.replace("Z", "+00:00")
              )
              now = datetime.datetime.now(datetime.timezone.utc)
              if (now - created_time).total_seconds() <= 300:
                is_new = True
            except Exception:
              pass

          # Бейдж и рамка для новых задач
          new_badge = (
              '<span style="background-color: #ff4b4b; color: white; padding:'
              " 2px 8px; border-radius: 10px; font-size: 11px; font-weight:"
              ' bold; margin-left: 8px;">🆕 NOWE</span>'
              if is_new
              else ""
          )
          card_border = (
              "2px solid #ff4b4b"
              if is_new
              else f"6px solid {card_color if (color_id := event.get('colorId')) and color_id in google_event_colors else default_color}"
          )

          # Получаем цвет из Google Календаря
          color_id = event.get("colorId")
          card_color = (
              google_event_colors[color_id]["bg"]
              if color_id and color_id in google_event_colors
              else default_color
          )
          # Переопределяем границу с учетом цвета
          card_border = (
              "3px solid #ff4b4b" if is_new else f"6px solid {card_color}"
          )

          safe_title = title.replace('"', "&quot;")

          # Карточка HTML с поддержкой бейджа NEW
          card_html = f"""
<div style="
    padding: 15px;
    margin-bottom: 10px;
    border-radius: 8px;
    background-color: #f0f2f6;
    border-left: {card_border};
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    word-break: break-word;
    overflow-wrap: break-word;
    max-width: 100%;
    box-sizing: border-box;
">
    <div style="overflow: hidden; word-break: break-word; flex-grow: 1;">
        <strong style="font-size: 16px; color: #31333F; word-break: break-word;">{safe_title}</strong>{new_badge}<br>
        <span style="font-size: 13px; color: #555;">🕒 {time_str}</span><br>
        <span style="font-size: 12px; {desc_style} word-break: break-word; overflow-wrap: break-word; display: block; max-width: 100%;">{display_desc}</span>
    </div>
    <span style="
        background-color: {card_color};
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
        white-space: nowrap;
        margin-left: 10px;
        flex-shrink: 0;
    ">Zadanie</span>
</div>
"""
          st.markdown(card_html, unsafe_allow_html=True)

          found_media = []

          # 1. Проверяем встроенные вложения Google Календаря
          attachments = event.get("attachments", [])
          for att in attachments:
            f_url = att.get("fileUrl", "")
            f_id = att.get("fileId", "")
            mime_type = att.get("mimeType", "")

            if f_id:
              found_media.append((
                  f"https://lh3.googleusercontent.com/d/{f_id}",
                  "video" if "video" in mime_type else "image",
              ))
            elif "drive.google.com" in f_url or "file/d/" in f_url:
              match = re.search(r"/d/([a-zA-Z0-9_-]+)", f_url)
              if match:
                file_id = match.group(1)
                found_media.append((
                    f"https://drive.google.com/uc?export=download&id={file_id}",
                    (
                        "video"
                        if any(
                            ext in f_url.lower()
                            for ext in [".mp4", ".mov", ".avi"]
                        )
                        else "image"
                    ),
                ))

          # 2. Проверяем ссылки внутри описания задачи
          if description:
            urls = re.findall(r"(https?://[^\s]+)", description, re.IGNORECASE)
            for url in urls:
              clean_url = url.rstrip(".,;:!?")
              if "drive.google.com" in clean_url or "file/d/" in clean_url:
                match = re.search(r"/d/([a-zA-Z0-9_-]+)", clean_url)
                if match:
                  file_id = match.group(1)
                  is_vid = any(
                      ext in clean_url.lower()
                      for ext in [".mp4", ".mov", ".avi", ".mkv"]
                  ) or "video" in clean_url.lower()
                  link_type = "video" if is_vid else "image"
                  media_link = (
                      f"https://drive.google.com/uc?export=download&id={file_id}"
                      if is_vid
                      else f"https://lh3.googleusercontent.com/d/{file_id}"
                  )
                  found_media.append((media_link, link_type))
              elif any(
                  ext in clean_url.lower()
                  for ext in [".mp4", ".mov", ".avi", ".mkv"]
              ):
                found_media.append((clean_url, "video"))
              elif any(
                  ext in clean_url.lower()
                  for ext in [".png", ".jpg", ".jpeg", ".webp"]
              ):
                found_media.append((clean_url, "image"))

          # Рендерим уникальные медиафайлы
          for media_link, media_type in list(set(found_media)):
            try:
              if media_type == "video":
                st.video(media_link)
              else:
                st.image(
                    media_link,
                    caption="Zdjęcie z Google Drive / Opisu",
                    use_container_width=True,
                )
            except Exception:
              pass

# --- ПОРТАЛ ВЛАДЕЛЬЦА ---
elif st.session_state["role"] == "owner":
  if not st.session_state["authenticated"]:
    st.title("🏠 Panel Właściciela - Logowanie")
    if st.button("⬅️ Powrót do wyboru roli"):
      st.session_state["role"] = None
      st.rerun()

    with st.form("login_form"):
      options = ["Wybierz adres"] + list(USERS.keys())
      owner_name = st.selectbox("Wybierz mieszkanie", options=options, index=0)
      password = st.text_input("Hasło", type="password")
      submit_button = st.form_submit_button("Zaloguj się")

      if submit_button:
        if owner_name == "Wybierz adres":
          st.error("Proszę wybrać adres!")
        elif owner_name in USERS and USERS[owner_name]["password"] == password:
          st.session_state["authenticated"] = True
          st.session_state["current_owner"] = owner_name
          st.session_state["sheet_name"] = USERS[owner_name]["sheet_name"]
          st.session_state["owner_type"] = USERS[owner_name]["type"]
          st.rerun()
        else:
          st.error("Nieprawidłowe hasło!")
  else:
    owner = st.session_state["current_owner"]
    sheet = st.session_state["sheet_name"]
    owner_type = st.session_state.get("owner_type", "single")

    st.sidebar.image("1.png", width=160)
    st.sidebar.title(f"{owner}")
    if st.sidebar.button("Wyloguj się"):
      st.session_state["authenticated"] = False
      st.rerun()
    if st.sidebar.button("⬅️ Wybór roli"):
      st.session_state["authenticated"] = False
      st.session_state["role"] = None
      st.rerun()

    st.title(f"📊 Statystyki: {owner}")

    with st.spinner("Pobieranie danych..."):
      rows = get_full_sheet_data(sheet)

    if rows:
      st.markdown("### ⚙️ Informacje ogólne")
      col1, col2 = st.columns(2)
      with col1:
        st.markdown(
            f"**Sprzątanie:**"
            f" {rows[0][2] if len(rows) > 0 and len(rows[0]) > 2 else ''}"
        )
        st.markdown(
            f"**Check out:**"
            f" {rows[1][2] if len(rows) > 1 and len(rows[1]) > 2 else ''}"
        )
      with col2:
        st.markdown(
            f"**Check in:**"
            f" {rows[2][2] if len(rows) > 2 and len(rows[2]) > 2 else ''}"
        )

      if owner_type == "legionow":
        link_bay = rows[4][2] if len(rows) > 4 and len(rows[4]) > 2 else ""
        link_mirror = rows[4][7] if len(rows) > 4 and len(rows[4]) > 7 else ""
        link_beacon = rows[4][12] if len(rows) > 4 and len(rows[4]) > 12 else ""

        if link_bay or link_mirror or link_beacon:
          st.markdown("🔗 **Linki:**")
          if link_bay:
            st.markdown(f"- Legionów 50/4 (1) BAY: [Otwórz link]({link_bay})")
          if link_mirror:
            st.markdown(
                f"- Legionów 50/4 (2) MIRROR: [Otwórz"
                f" link]({link_mirror})"
            )
          if link_beacon:
            st.markdown(
                f"- Legionów 50/4 (3) BEACON: [Otwórz"
                f" link]({link_beacon})"
            )
      else:
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
        val_str = str(val).strip()
        val_str = re.sub(r"\s+", "", val_str)
        val_str = val_str.replace("zł", "").replace("PLN", "")
        if "." in val_str and "," in val_str:
          val_str = val_str.replace(".", "").replace(",", ".")
        else:
          val_str = val_str.replace(",", ".")
        try:
          return float(val_str)
        except ValueError:
          return 0.0

      def get_stats_df_single(start_row, end_row):
        stats_data = []
        for r in range(start_row, end_row):
          if r < len(rows):
            row_vals = rows[r]
            if len(row_vals) >= 12:
              m_val = row_vals[10]
              s_val = row_vals[11]
              m_val_lower = str(m_val).lower()
              if "miesiąc" in m_val_lower or "miesiac" in m_val_lower:
                continue
              if (
                  m_val != ""
                  or s_val != ""
                  or "suma" in m_val_lower
                  or "rok" in m_val_lower
              ):
                stats_data.append([m_val, s_val])
        if len(stats_data) > 0:
          return pd.DataFrame(stats_data, columns=["Miesiąc", "Suma miesiąc"])
        return pd.DataFrame()

      def get_stats_df_legionow(start_row, end_row):
        stats_data = []
        for r in range(start_row, end_row):
          if r < len(rows):
            row_vals = rows[r]
            if len(row_vals) > 34:
              m_val = row_vals[31]
              s1 = row_vals[32]
              s2 = row_vals[33]
              s3 = row_vals[34]
              m_val_lower = str(m_val).lower()
              if "miesiąc" in m_val_lower or "miesiac" in m_val_lower:
                continue
              is_sum_rok = (
                  "suma rok" in m_val_lower and "razem" not in m_val_lower
              )
              is_razem = "razem" in m_val_lower
              is_month = m_val != "" and not is_sum_rok and not is_razem
              if (
                  m_val != ""
                  or s1 != ""
                  or s2 != ""
                  or s3 != ""
                  or is_sum_rok
                  or is_razem
              ):
                v1 = parse_currency(s1)
                v2 = parse_currency(s2)
                v3 = parse_currency(s3)
                total_m = v1 + v2 + v3
                if is_month or is_sum_rok:
                  total_m_str = (
                      f"{total_m:,.2f}".replace(",", " ").replace(".", ",")
                      if total_m > 0
                      else ""
                  )
                  stats_data.append([m_val, total_m_str, s1, s2, s3])
                elif is_razem:
                  stats_data.append([m_val, s1, "", "", ""])
                else:
                  stats_data.append([m_val, "", s1, s2, s3])
        if len(stats_data) > 0:
          return pd.DataFrame(
              stats_data,
              columns=[
                  "Miesiąc",
                  "Suma miesiąc",
                  "Legionów (1) BAY",
                  "Legionów (2) MIRROR",
                  "Legionów (3) BEACON",
              ],
          )
        return pd.DataFrame()

      def style_stats(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for idx, row in df.iterrows():
          row_str = " ".join([str(val).upper() for val in row.values])
          is_year_sum = "SUMA" in row_str or "ROK" in row_str
          for col in df.columns:
            if is_year_sum:
              styles.loc[idx, col] = (
                  "background-color: #c8e6c9; color: #000000; font-weight:"
                  " bold;"
              )
            else:
              if col == "Suma miesiąc":
                styles.loc[idx, col] = (
                    "background-color: #e8f5e9; font-weight: bold;"
                )
              else:
                styles.loc[idx, col] = "background-color: #fff8e1"
        return styles

      tab1, tab2, tab3 = st.tabs(
          ["📅 Grafik 2026", "📅 Grafik 2025", "📊 Przychody (Statystyka)"]
      )

      if owner_type == "legionow":
        with tab1:
          st.markdown("### Grafik rezerwacji 2026")
          room_choice_26 = st.selectbox(
              "Wybierz pokój (2026)",
              [
                  "Legionów 50/4 (1) BAY",
                  "Legionów 50/4 (2) MIRROR",
                  "Legionów 50/4 (3) BEACON",
              ],
              key="r26",
          )
          offset_26 = 0
          if "MIRROR" in room_choice_26:
            offset_26 = 5
          elif "BEACON" in room_choice_26:
            offset_26 = 10
          df_2026 = get_full_booking_df(offset_26)
          if not df_2026.empty:
            styled_2026 = df_2026.style.apply(style_cells, axis=None)
            st.dataframe(styled_2026, use_container_width=True)
          else:
            st.info("Brak danych.")

        with tab2:
          st.markdown("### Grafik rezerwacji 2025")
          room_choice_25 = st.selectbox(
              "Wybierz pokój (2025)",
              [
                  "Legionów 50/4 (1) BAY",
                  "Legionów 50/4 (2) MIRROR",
                  "Legionów 50/4 (3) BEACON",
              ],
              key="r25",
          )
          offset_25 = 16
          if "MIRROR" in room_choice_25:
            offset_25 = 21
          elif "BEACON" in room_choice_25:
            offset_25 = 26
          df_2025 = get_full_booking_df(offset_25)
          if not df_2025.empty:
            styled_2025 = df_2025.style.apply(style_cells, axis=None)
            st.dataframe(styled_2025, use_container_width=True)
          else:
            st.info("Brak danych.")

        with tab3:
          df_stat_2026 = get_stats_df_legionow(22, 37)
          df_stat_2025 = get_stats_df_legionow(6, 21)
          st.markdown(
              "##### Przychód najem brutto 2026 (Podział na pokoje i suma)"
          )
          if not df_stat_2026.empty:
            styled_stat_2026 = df_stat_2026.style.apply(
                style_stats, axis=None
            )
            st.dataframe(
                styled_stat_2026, use_container_width=True, hide_index=True
            )
          st.markdown("---")
          st.markdown(
              "##### Przychód najem brutto 2025 (Podział na pokoje i suma)"
          )
          if not df_stat_2025.empty:
            styled_stat_2025 = df_stat_2025.style.apply(
                style_stats, axis=None
            )
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
            styled_stat_2026 = df_stat_2026.style.apply(
                style_stats, axis=None
            )
            st.dataframe(
                styled_stat_2026, use_container_width=True, hide_index=True
            )
          st.markdown("---")
          st.markdown("##### Przychód najem brutto 2025")
          df_stat_2025 = get_stats_df_single(6, 20)
          if not df_stat_2025.empty:
            styled_stat_2025 = df_stat_2025.style.apply(
                style_stats, axis=None
            )
            st.dataframe(
                styled_stat_2025, use_container_width=True, hide_index=True
            )
    else:
      st.warning("Nie udało się pobrać danych z arkusza.")
