import calendar
import datetime
import hmac
import html
import json
import re

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Panel właściciela", page_icon="🏠", layout="centered")

# ===== Настройки =====
SPREADSHEET_ID = "1zQNxhKvx4zf-OQuFIeKS6WR7TDs6-h5oLGEmOcnxn1A"
SHEET_NAME = "Doby"
UNIT_TITLE = "NaWypasie Apartment"
LOGIN = "NaWypasie"  # пароль хранится в st.secrets["OWNER_PASSWORD"]
UNIT_SHEET_NAME = (
    "NaWypasie Apartment with Sauna Beautiful Garden SUP Board and "
    "Just 30 Minutes from Gdańsk and Gdynia"
)
YEAR = 2027

# Структура листа «Doby» (блок квартиры = 5 колонок: Nr id | Data | Portal | Cena | Uwagi)
NAME_ROW = 6          # строка с названием квартиры
DATA_START_ROW = 8    # первая строка с датами
OFF_DATE = 1
OFF_PORTAL = 2
OFF_PRICE = 3
OFF_INFO = 2          # значения «Sprzątanie / Check out / Check in» в строках 1–3
READ_RANGE = "A1:Z1000"  # колонка «Uwagi» не нужна и не читается

OWNER_STAY_WORDS = ("właściciel", "wlasciciel")
MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]


# ===== Загрузка данных =====
@st.cache_data(ttl=300)
def load_grid():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    return worksheet.get(READ_RANGE)


def norm(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def cell(grid, r, c):
    if 0 <= r < len(grid) and 0 <= c < len(grid[r]):
        return str(grid[r][c]).strip()
    return ""


def find_block_start(grid):
    """Возвращает колонку начала блока квартиры (0-based) или None."""
    target = norm(UNIT_SHEET_NAME)
    for i, value in enumerate(grid[NAME_ROW - 1]):
        if norm(value) == target:
            return i - OFF_DATE
    return None


def parse_day(text):
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})", text)
    if not m:
        return None
    try:
        return datetime.date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def parse_money(text):
    s = re.sub(r"[^0-9,.\-]", "", text).replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_unit(grid, c):
    info = {
        "cleaning": cell(grid, 0, c + OFF_INFO),
        "check_out": cell(grid, 1, c + OFF_INFO),
        "check_in": cell(grid, 2, c + OFF_INFO),
    }
    days = []
    for r in range(DATA_START_ROW - 1, len(grid)):
        day = parse_day(cell(grid, r, c + OFF_DATE))
        if day is None or day.year != YEAR:
            continue
        portal = cell(grid, r, c + OFF_PORTAL)
        price = parse_money(cell(grid, r, c + OFF_PRICE))
        if any(word in portal.lower() for word in OWNER_STAY_WORDS):
            kind = "owner"
        elif portal or price > 0:
            kind = "booked"
        else:
            kind = "free"
        days.append({"date": day, "portal": portal, "price": price, "kind": kind})
    days.sort(key=lambda d: d["date"])
    return info, days


def build_stays(days):
    stays, cur = [], None
    for d in days:
        if d["kind"] != "booked":
            if cur:
                stays.append(cur)
                cur = None
            continue
        if cur and d["date"] - cur["last"] == datetime.timedelta(days=1):
            cur["last"] = d["date"]
            cur["nights"] += 1
            cur["revenue"] += d["price"]
            cur["portal"] = cur["portal"] or d["portal"]
        else:
            if cur:
                stays.append(cur)
            cur = {"first": d["date"], "last": d["date"], "nights": 1,
                   "revenue": d["price"], "portal": d["portal"]}
    if cur:
        stays.append(cur)
    return stays


def monthly_stats(days):
    stats = {m: {"nights": 0, "revenue": 0.0, "owner": 0} for m in range(1, 13)}
    for d in days:
        m = d["date"].month
        if d["kind"] == "booked":
            stats[m]["nights"] += 1
            stats[m]["revenue"] += d["price"]
        elif d["kind"] == "owner":
            stats[m]["owner"] += 1
    return stats


def fmt_money(value):
    return f"{value:,.2f} zł".replace(",", " ").replace(".", ",")


# ===== Вход =====
def check_login():
    if st.session_state.get("authed"):
        return True
    st.title("🏠 Panel właściciela")
    st.markdown(f"**{UNIT_TITLE}** — rezerwacje {YEAR}")
    with st.form("login"):
        login = st.text_input("Adres / login")
        password = st.text_input("Hasło", type="password")
        submitted = st.form_submit_button("Zaloguj się")
    if submitted:
        login_ok = hmac.compare_digest(login.strip().encode(), LOGIN.encode())
        password_ok = hmac.compare_digest(password.encode(), st.secrets["OWNER_PASSWORD"].encode())
        if login_ok and password_ok:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Nieprawidłowy login lub hasło")
    return False


PORTAL_COLORS = {
    "booking": "#2f6fed",
    "airbnb": "#ff5a5f",
    "przelew": "#1f9d61",
}
OWNER_COLOR = "#8e44ad"
OTHER_PORTAL_COLOR = "#f39c12"
FREE_STYLE = "background:#f3f5f8;color:#9aa3af;"
WEEKDAYS_PL = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]


def portal_color(portal, kind):
    if kind == "owner":
        return OWNER_COLOR
    text = portal.lower()
    for key, color in PORTAL_COLORS.items():
        if key in text:
            return color
    return OTHER_PORTAL_COLOR


def render_calendar(days, month):
    by_date = {d["date"]: d for d in days}
    first_weekday, n_days = calendar.monthrange(YEAR, month)
    today = datetime.date.today()

    cells = [f'<div class="cal-head">{w}</div>' for w in WEEKDAYS_PL]
    cells += ['<div></div>'] * first_weekday
    booked_nights = 0

    for day in range(1, n_days + 1):
        date = datetime.date(YEAR, month, day)
        d = by_date.get(date)
        label, tip = "", ""
        if d and d["kind"] == "booked":
            booked_nights += 1
            color = portal_color(d["portal"], "booked")
            style = f"background:{color};color:#fff;"
            label = html.escape(d["portal"] or "Rezerwacja")
            tip = f"{d['portal'] or 'Rezerwacja'} · {fmt_money(d['price'])}"
        elif d and d["kind"] == "owner":
            style = f"background:{OWNER_COLOR};color:#fff;"
            label = "Właściciel"
            tip = "Pobyt właściciela"
        elif d:
            style = FREE_STYLE
        else:
            style = "background:#fafbfc;color:#c4cad3;"
        today_cls = " today" if date == today else ""
        cells.append(
            f'<div class="cal-cell{today_cls}" style="{style}" title="{html.escape(tip)}">'
            f'<div class="cal-day">{day}</div>'
            f'<div class="cal-lbl">{label}</div></div>'
        )

    st.markdown(
        """
<style>
.cal-grid {display:grid; grid-template-columns:repeat(7,1fr); gap:6px;}
.cal-head {text-align:center; font-size:12px; color:#6b7585; font-weight:600; padding-bottom:2px;}
.cal-cell {border-radius:10px; padding:6px 4px; min-height:60px; font-size:13px;}
.cal-day {font-weight:700;}
.cal-lbl {font-size:10px; margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.cal-cell.today {outline:2px solid #1c2430; outline-offset:1px;}
.cal-legend {display:flex; flex-wrap:wrap; gap:12px; font-size:12px; color:#4b5563; margin-top:10px;}
.cal-dot {display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:4px; vertical-align:-1px;}
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="cal-grid">{"".join(cells)}</div>', unsafe_allow_html=True)

    legend = [
        ("#2f6fed", "Booking"),
        ("#ff5a5f", "Airbnb"),
        ("#1f9d61", "Przelew (bezpośrednio)"),
        (OWNER_COLOR, "Pobyt właściciela"),
        (OTHER_PORTAL_COLOR, "Inny portal"),
        ("#f3f5f8", "Wolne"),
    ]
    items = "".join(
        f'<span><i class="cal-dot" style="background:{c}"></i>{t}</span>' for c, t in legend
    )
    st.markdown(f'<div class="cal-legend">{items}</div>', unsafe_allow_html=True)
    st.caption(f"{MONTHS_PL[month - 1]}: zajęte noce {booked_nights} z {n_days}.")


# ===== Панель =====
def show_panel():
    st.sidebar.title(UNIT_TITLE)
    if st.sidebar.button("Wyloguj się"):
        st.session_state["authed"] = False
        st.rerun()

    with st.spinner("Pobieranie danych..."):
        grid = load_grid()

    c = find_block_start(grid)
    if c is None:
        st.error("Nie znaleziono tej kwatery w arkuszu. Sprawdź nazwę w zakładce Doby.")
        return

    info, days = load_unit(grid, c)
    if not days:
        st.warning(f"Brak danych na {YEAR} rok.")
        return

    st.title(f"📊 {UNIT_TITLE}")
    st.caption(f"Rezerwacje {YEAR} (stan na {datetime.date.today().strftime('%d.%m.%Y')})")

    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Zameldowanie:** {info['check_in'] or '—'}")
    col2.markdown(f"**Wymeldowanie:** {info['check_out'] or '—'}")
    col3.markdown(f"**Sprzątanie:** {info['cleaning'] or '—'} zł")
    st.markdown("---")

    stays = build_stays(days)
    stats = monthly_stats(days)

    total_nights = sum(s["nights"] for s in stats.values())
    total_revenue = sum(s["revenue"] for s in stats.values())
    owner_nights = sum(s["owner"] for s in stats.values())
    available = sum(calendar.monthrange(YEAR, m)[1] for m in range(1, 13)) - owner_nights
    occupancy = round(100 * total_nights / available) if available else 0
    avg_price = total_revenue / total_nights if total_nights else 0.0

    k1, k2 = st.columns(2)
    k1.metric("Przychód zaplanowany", fmt_money(total_revenue))
    k2.metric("Zarezerwowane noce", total_nights)
    k3, k4 = st.columns(2)
    k3.metric("Obłożenie roku", f"{occupancy}%")
    k4.metric("Średnia cena za noc", fmt_money(avg_price) if total_nights else "—")

    tab_cal, tab_month, tab_stays = st.tabs(["🗓️ Kalendarz", "📅 Miesiące", "🧾 Pobyty"])

    with tab_cal:
        month = st.selectbox(
            "Miesiąc",
            options=list(range(1, 13)),
            index=datetime.date.today().month - 1 if datetime.date.today().year == YEAR else 0,
            format_func=lambda m: f"{MONTHS_PL[m - 1]} {YEAR}",
        )
        render_calendar(days, month)

    with tab_month:
        table = pd.DataFrame([
            {
                "Miesiąc": MONTHS_PL[m - 1],
                "Noce": stats[m]["nights"],
                "Przychód": fmt_money(stats[m]["revenue"]),
                "Pobyt właściciela (dni)": stats[m]["owner"],
            }
            for m in range(1, 13)
        ])
        st.bar_chart(
            pd.DataFrame({"Przychód, zł": [stats[m]["revenue"] for m in range(1, 13)]},
                         index=[MONTHS_PL[m - 1][:3] for m in range(1, 13)])
        )
        st.dataframe(table, hide_index=True, use_container_width=True)

    with tab_stays:
        if not stays:
            st.info("Brak rezerwacji.")
        else:
            stays_table = pd.DataFrame([
                {
                    "Zameldowanie": s["first"].strftime("%d.%m.%Y"),
                    "Wymeldowanie": (s["last"] + datetime.timedelta(days=1)).strftime("%d.%m.%Y"),
                    "Noce": s["nights"],
                    "Portal": s["portal"] or "—",
                    "Przychód": fmt_money(s["revenue"]),
                }
                for s in stays
            ])
            st.dataframe(stays_table, hide_index=True, use_container_width=True)

        owner_dates = [d["date"] for d in days if d["kind"] == "owner"]
        if owner_dates:
            st.markdown("##### Pobyt właściciela")
            st.write(", ".join(d.strftime("%d.%m.%Y") for d in owner_dates))

    st.markdown(
        "<div style='font-size:12px;color:#888;margin-top:20px'>Kwoty podane według cen z tabeli, "
        "przed odjęciem prowizji i kosztów.</div>",
        unsafe_allow_html=True,
    )


if check_login():
    show_panel()
