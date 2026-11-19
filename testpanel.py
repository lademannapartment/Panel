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
YEAR = 2027
# Владельцы задаются в секретах Streamlit: [owners.ЛОГИН] с полями password и units.
ALL_LABEL = "Razem (obie)"

# Структура листа «Doby» (блок квартиры = 5 колонок: Nr id | Data | Portal | Cena | Uwagi)
NAME_ROW = 6          # строка с названием квартиры
DATA_START_ROW = 8    # первая строка с датами
OFF_DATE = 1
OFF_PORTAL = 2
OFF_PRICE = 3
OFF_INFO = 2          # «Sprzątanie / Check out / Check in» в строках 1–3

OWNER_STAY_WORDS = ("właściciel", "wlasciciel")
MONTHS_PL = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
             "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
WEEKDAYS_PL = ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"]

PORTAL_COLORS = {
    "booking": "#2f6fed",
    "airbnb": "#ff5a5f",
    "przelew": "#1f9d61",
}
OWNER_COLOR = "#8e44ad"
OTHER_PORTAL_COLOR = "#f39c12"
FREE_STYLE = "background:#f3f5f8;color:#9aa3af;"


# ===== Загрузка данных =====
@st.cache_data(ttl=300)
def load_grid():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    return worksheet.get_all_values()


def norm(text):
    return re.sub(r"\s+", " ", str(text)).strip()


def cell(grid, r, c):
    if 0 <= r < len(grid) and 0 <= c < len(grid[r]):
        return str(grid[r][c]).strip()
    return ""


def find_block_start(grid, sheet_name):
    """Колонка начала блока квартиры (0-based) или None."""
    target = norm(sheet_name)
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


def load_unit(grid, c, title):
    info = {
        "title": title,
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


def fmt_money(value):
    return f"{value:,.2f} zł".replace(",", " ").replace(".", ",")


def average(values):
    return sum(values) / len(values) if values else 0.0


def portal_group(portal):
    text = portal.lower()
    for name, key in (("Booking", "booking"), ("Airbnb", "airbnb"), ("Przelew", "przelew")):
        if key in text:
            return name
    return "Inny"


def portal_color(portal, kind):
    if kind == "owner":
        return OWNER_COLOR
    text = portal.lower()
    for key, color in PORTAL_COLORS.items():
        if key in text:
            return color
    return OTHER_PORTAL_COLOR


def unit_metrics(days):
    booked = [d for d in days if d["kind"] == "booked"]
    owner = sum(1 for d in days if d["kind"] == "owner")
    free = sum(1 for d in days if d["kind"] == "free")
    revenue = sum(d["price"] for d in booked)
    nights = len(booked)
    year_days = (datetime.date(YEAR, 12, 31) - datetime.date(YEAR, 1, 1)).days + 1
    available = year_days - owner
    return {
        "nights": nights,
        "revenue": revenue,
        "owner": owner,
        "free": free,
        "available": available,
        "occupancy": round(100 * nights / available) if available else 0,
        "avg": revenue / nights if nights else 0.0,
        "booked_days": booked,
    }


def longest_free(days):
    best, streak = 0, 0
    for d in days:
        if d["kind"] == "free":
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


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


# ===== Календарь =====
def aggregate_by_date(days):
    agg = {}
    for d in days:
        a = agg.setdefault(d["date"], {"booked": 0, "owner": 0, "total": 0,
                                       "portal": "", "price": 0.0})
        a["total"] += 1
        if d["kind"] == "booked":
            a["booked"] += 1
            a["price"] += d["price"]
            a["portal"] = a["portal"] or d["portal"]
        elif d["kind"] == "owner":
            a["owner"] += 1
    return agg


def render_calendar(days, month):
    agg = aggregate_by_date(days)
    first_weekday, n_days = calendar.monthrange(YEAR, month)
    today = datetime.date.today()

    cells = [f'<div class="cal-head">{w}</div>' for w in WEEKDAYS_PL]
    cells += ['<div></div>'] * first_weekday
    booked_nights, slots = 0, 0

    for day in range(1, n_days + 1):
        date = datetime.date(YEAR, month, day)
        a = agg.get(date)
        label, tip = "", ""
        if a:
            slots += a["total"]
        if a and a["booked"]:
            booked_nights += a["booked"]
            color = portal_color(a["portal"], "booked")
            style = f"background:{color};color:#fff;"
            label = html.escape(a["portal"] or "Rezerwacja")
            if a["total"] > 1:
                label = f"{a['booked']}/{a['total']} · {label}"
            tip = f"{a['portal'] or 'Rezerwacja'} · {fmt_money(a['price'])}"
        elif a and a["owner"]:
            style = f"background:{OWNER_COLOR};color:#fff;"
            label = "Właściciel"
            tip = "Pobyt właściciela"
        elif a:
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
    st.caption(f"{MONTHS_PL[month - 1]}: zajęte noce {booked_nights} z {slots}.")


# ===== Статистика =====
def render_extended_stats(selected, show_per_unit):
    days = [d for u in selected for d in u["days"]]
    stays = [s for u in selected for s in u["stays"]]
    total = unit_metrics(days)
    booked = total["booked_days"]

    weekend = [d["price"] for d in booked if d["date"].weekday() in (4, 5)]
    weekday = [d["price"] for d in booked if d["date"].weekday() not in (4, 5)]
    lengths = [s["nights"] for s in stays]
    best_free = max((longest_free(u["days"]) for u in selected), default=0)

    k1, k2, k3 = st.columns(3)
    k1.metric("Wolne noce", total["free"])
    k2.metric("Najdłuższa przerwa", f"{best_free} nocy")
    k3.metric("Pobyty właściciela", f"{total['owner']} nocy")
    k4, k5, k6 = st.columns(3)
    k4.metric("Średnia długość pobytu", f"{average(lengths):.1f} nocy" if lengths else "—")
    k5.metric("Najdłuższy pobyt", f"{max(lengths)} nocy" if lengths else "—")
    k6.metric("Liczba pobytów", len(stays))
    k7, k8 = st.columns(2)
    k7.metric("RevPAR (przychód / wolne noce)",
              fmt_money(total["revenue"] / total["available"]) if total["available"] else "—")
    k8.metric("Śr. cena pt–sb", fmt_money(average(weekend)) if weekend else "—")
    st.metric("Śr. cena nd–czw", fmt_money(average(weekday)) if weekday else "—")

    if show_per_unit:
        st.markdown("##### Porównanie apartamentów")
        rows = []
        for u in selected:
            m = unit_metrics(u["days"])
            rows.append({
                "Apartament": u["info"]["title"],
                "Noce": m["nights"],
                "Obłożenie": f"{m['occupancy']}%",
                "Przychód": fmt_money(m["revenue"]),
                "Śr. za noc": fmt_money(m["avg"]),
                "Pobyty": len(u["stays"]),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    st.markdown("##### Podział według portali")
    groups = {}
    for d in booked:
        g = groups.setdefault(portal_group(d["portal"]), {"nights": 0, "revenue": 0.0})
        g["nights"] += 1
        g["revenue"] += d["price"]
    if groups:
        st.dataframe(pd.DataFrame([
            {
                "Portal": name,
                "Noce": g["nights"],
                "Udział nocy": f"{100 * g['nights'] / total['nights']:.0f}%",
                "Przychód": fmt_money(g["revenue"]),
                "Śr. za noc": fmt_money(g["revenue"] / g["nights"]),
            }
            for name, g in sorted(groups.items(), key=lambda x: -x[1]["revenue"])
        ]), hide_index=True, use_container_width=True)
    else:
        st.info("Brak rezerwacji w 2027 roku.")

    st.markdown("##### Najdłuższe pobyty")
    if stays:
        top = sorted(stays, key=lambda s: (-s["nights"], s["first"]))[:5]
        st.dataframe(pd.DataFrame([
            {
                "Zameldowanie": s["first"].strftime("%d.%m.%Y"),
                "Noce": s["nights"],
                "Portal": s["portal"] or "—",
                "Przychód": fmt_money(s["revenue"]),
            }
            for s in top
        ]), hide_index=True, use_container_width=True)
    else:
        st.info("Brak pobytów.")

    owner_dates = sorted(d["date"] for d in days if d["kind"] == "owner")
    if owner_dates:
        st.markdown("##### Pobyt właściciela")
        st.write(", ".join(d.strftime("%d.%m.%Y") for d in owner_dates))


# ===== Вход =====
def load_owners():
    raw = st.secrets.get("owners", {})
    return {
        str(login): {"password": str(data["password"]), "units": list(data["units"])}
        for login, data in raw.items()
    }


def short_title(sheet_name):
    return re.split(r" with | -|,", sheet_name)[0].strip()


def check_login():
    if st.session_state.get("authed"):
        return True
    st.title("🏠 Panel właściciela")
    with st.form("login"):
        login = st.text_input("Adres / login")
        password = st.text_input("Hasło", type="password")
        submitted = st.form_submit_button("Zaloguj się")
    if submitted:
        owners = load_owners()
        entry = owners.get(login.strip())
        password_ok = entry is not None and hmac.compare_digest(
            password.encode(), entry["password"].encode())
        if password_ok:
            st.session_state["authed"] = True
            st.session_state["owner_login"] = login.strip()
            st.session_state["owner_units"] = entry["units"]
            st.rerun()
        else:
            st.error("Nieprawidłowy login lub hasło")
    return False


# ===== Панель =====
def show_panel():
    st.sidebar.title("Panel właściciela")
    if st.sidebar.button("Wyloguj się"):
        st.session_state["authed"] = False
        st.rerun()

    with st.spinner("Pobieranie danych..."):
        grid = load_grid()

    units_data = []
    for sheet_name in st.session_state["owner_units"]:
        c = find_block_start(grid, sheet_name)
        if c is None:
            st.error(f"Nie znaleziono apartamentu «{short_title(sheet_name)}» w arkuszu Doby.")
            return
        info, days = load_unit(grid, c, short_title(sheet_name))
        units_data.append({"info": info, "days": days, "stays": build_stays(days)})

    options = [u["info"]["title"] for u in units_data]
    if len(options) > 1:
        options.append(ALL_LABEL)
    choice = st.selectbox("Mieszkanie", options=options)
    selected = units_data if choice == ALL_LABEL else [
        u for u in units_data if u["info"]["title"] == choice
    ]
    days = [d for u in selected for d in u["days"]]
    stays = [s for u in selected for s in u["stays"]]

    st.title(f"📊 {choice}")
    st.caption(f"Rezerwacje {YEAR} (stan na {datetime.date.today().strftime('%d.%m.%Y')})")

    info_table = pd.DataFrame([
        {
            "Apartament": u["info"]["title"],
            "Zameldowanie": u["info"]["check_in"] or "—",
            "Wymeldowanie": u["info"]["check_out"] or "—",
            "Sprzątanie": f"{u['info']['cleaning']} zł" if u["info"]["cleaning"] else "—",
        }
        for u in selected
    ])
    st.dataframe(info_table, hide_index=True, use_container_width=True)

    total = unit_metrics(days)
    k1, k2 = st.columns(2)
    k1.metric("Przychód zaplanowany", fmt_money(total["revenue"]))
    k2.metric("Zarezerwowane noce", total["nights"])
    k3, k4 = st.columns(2)
    k3.metric("Obłożenie roku", f"{total['occupancy']}%")
    k4.metric("Średnia cena za noc", fmt_money(total["avg"]) if total["nights"] else "—")

    tab_cal, tab_month, tab_stats = st.tabs(["🗓️ Kalendarz", "📅 Miesiące", "📈 Statystyka"])

    with tab_cal:
        month = st.selectbox(
            "Miesiąc",
            options=list(range(1, 13)),
            index=datetime.date.today().month - 1 if datetime.date.today().year == YEAR else 0,
            format_func=lambda m: f"{MONTHS_PL[m - 1]} {YEAR}",
        )
        render_calendar(days, month)

    with tab_month:
        stats = monthly_stats(days)
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
                         index=[f"{m:02d} {MONTHS_PL[m - 1][:3]}" for m in range(1, 13)])
        )
        st.dataframe(table, hide_index=True, use_container_width=True)

    with tab_stats:
        render_extended_stats(selected, show_per_unit=(choice == ALL_LABEL))

    st.markdown(
        "<div style='font-size:12px;color:#888;margin-top:20px'>Kwoty podane według cen z tabeli, "
        "przed odjęciem prowizji i kosztów.</div>",
        unsafe_allow_html=True,
    )


if check_login():
    show_panel()
