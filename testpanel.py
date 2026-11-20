import calendar
import datetime
import hmac
import html
import json
import re

import altair as alt
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
ALL_LABEL = "Razem"

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

# Старая статистика (2025–2026) — arkusz «Panel Poglądowy»
# Dla każdego arkusza: które apartamenty (wzorzec w tytule) i gdzie leży kolumna
# «Suma miesiąc» dla danego roku: {rok: (indeks wiersza nagłówka, {apartament: kolumna})}.
OLD_SPREADSHEET_ID = "13BZQL1WZ7yt6GlofhoLYr5D_X35_PQUtIW4kh5URhaE"
OLD_SHEETS = {
    "Grunwaldzka 515/1": {
        "units": {r"\bleaf\b": 0, r"\bnest\b": 1, r"\bsquare\b": 2, r"\btwig\b": 3},
        "years": {2025: (6, {0: 43, 1: 44, 2: 45, 3: 46}),
                  2026: (22, {0: 43, 1: 44, 2: 45, 3: 46})},
    },
    "Legionów": {
        "units": {r"\bbay\b": 0, r"\bmirror\b": 1, r"\bbeacon\b": 2},
        "years": {2025: (6, {0: 32, 1: 33, 2: 34}),
                  2026: (22, {0: 32, 1: 33, 2: 34})},
    },
    "Jagiellońska 10k/98": {
        "units": {r"\bwave\b": 0},
        "years": {2025: (6, {0: 13}),
                  2026: (22, {0: 13})},
    },
    "Pow 3b/66": {
        "units": {r"\bboho\b": 0},
        "years": {2025: (6, {0: 13}),
                  2026: (22, {0: 13})},
    },
    "Podwale 24/4 - HONEY": {
        "units": {r"\bhoney\b": 0},
        "years": {2025: (6, {0: 13}),
                  2026: (22, {0: 13})},
    },
    "Grota": {
        "units": {r"\bmercury\b": 0, r"\bhostel\b": 1, r"\bearth\b": 2, r"\bmars\b": 3,
                  r"\bjupiter\b": 4, r"\bsaturn\b": 5, r"\buranus\b": 6, r"\bneptune\b": 7,
                  r"\bpluto\b": 8, r"milky ?way": 9, r"\bsunlight\b": 10},
        "years": {2025: (6, {i: 129 + i for i in range(11)}),
                  2026: (22, {i: 129 + i for i in range(11)})},
    },
    "Chlebnicka 37/38 m4": {
        "units": {r"\bluna\b": 0, r"\blibertas\b": 1},
        "years": {2025: (6, {0: 23, 1: 24}),
                  2026: (22, {0: 23, 1: 24})},
    },
    "Wejhera 13/14": {
        "units": {r"\bshark\b": 0, r"\bpiggy\b": 1, r"\bturtle\b": 2},
        "years": {2025: (6, {0: 33, 1: 34, 2: 35}),
                  2026: (22, {0: 33, 1: 34, 2: 35})},
    },
    "Seredyńskiego 13/6": {
        "units": {r"\bblue\b": 0, r"\bgreen\b": 1, r"\brelax\b": 2, r"\bnavy\b": 3},
        "years": {2025: (6, {0: 47, 1: 48, 2: 49, 3: 50}),
                  2026: (22, {0: 47, 1: 48, 2: 49, 3: 50})},
    },
    "Kozietulskiego 15/6 ": {
        "units": {r"\bumbrella\b": 0, r"\bduo\b": 1, r"\bteddy\b": 2, r"\bcircus\b": 3,
                  r"\bbonjour\b": 4},
        "years": {2025: (6, {i: 53 + i for i in range(5)}),
                  2026: (22, {i: 53 + i for i in range(5)})},
    },
    "Starowiejska 62a/233": {
        "units": {r"\blaura\b": 0},
        "years": {2025: (6, {0: 13}),
                  2026: (22, {0: 13})},
    },
    "Zelwerowicza 27": {
        "units": {r"\bocean\b": 0, r"\bsandcastle\b": 1, r"\bcoral\b": 2},
        "years": {2025: (6, {0: 33, 1: 34, 2: 35}),
                  2026: (22, {0: 33, 1: 34, 2: 35})},
    },
    "Swiętego ducha 41/43 M11": {
        "units": {r"\bjungle\b": 0, r"\brose\b": 1, r"\bparis\b": 2},
        "years": {2025: (6, {0: 33, 1: 34, 2: 35}),
                  2026: (22, {0: 33, 1: 34, 2: 35})},
    },
    "Chylońska 106/4": {
        "units": {r"\bsailor\b": 0},
        "years": {2025: (6, {0: 13}),
                  2026: (22, {0: 13})},
    },
    "Pow 3a/15": {
        "units": {r"swish": 0},
        "years": {2025: (6, {0: 11}),
                  2026: (22, {0: 11})},
    },
    "Szemud Więźniów Sztuthofu 18": {
        "units": {r"nawypasie(?!.*grand)": 0, r"grand": 1},
        "years": {2025: (6, {0: 18}),
                  2026: (23, {0: 18, 1: 19})},
    },
}
OLD_YEARS = (2025, 2026)


# ===== Загрузка данных =====
@st.cache_data(ttl=300)
def load_grid():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    return worksheet.get_all_values()


@st.cache_data(ttl=3600)
def load_old_sheet(sheet_name):
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS_JSON"])
    creds = Credentials.from_service_account_info(
        creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    client = gspread.authorize(creds)
    grid = client.open_by_key(OLD_SPREADSHEET_ID).worksheet(sheet_name).get_all_values()
    return parse_old_sheet(grid, OLD_SHEETS[sheet_name])


def old_num(text):
    cleaned = re.sub(r"[\s\xa0]", "", text or "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_old_sheet(grid, config):
    """{indeks apartamentu: {rok: [12 kwot]}} z kolumn «Suma miesiąc»."""
    def cell(r, c):
        return grid[r][c] if r < len(grid) and c < len(grid[r]) else ""

    result = {}
    for year, (header_row, columns) in config["years"].items():
        for unit_idx, col in columns.items():
            monthly = [old_num(cell(header_row + 1 + m, col)) for m in range(12)]
            result.setdefault(unit_idx, {})[year] = monthly
    return result


def old_history(units):
    """{rok: {tytuł apartamentu: [12 kwot]}} tylko dla apartamentów z arkuszy historycznych."""
    history = {year: {} for year in OLD_YEARS}
    for sheet_name, config in OLD_SHEETS.items():
        parsed = None
        for u in units:
            title = u["info"]["title"]
            idx = next((i for pattern, i in config["units"].items()
                        if re.search(pattern, title, re.IGNORECASE)), None)
            if idx is None:
                continue
            if parsed is None:
                parsed = load_old_sheet(sheet_name)
            for year, monthly in parsed.get(idx, {}).items():
                history[year][title] = monthly
    return history


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


def parse_pct(text):
    m = re.search(r"-?\d+(?:[.,]\d+)?", text)
    return float(m.group().replace(",", ".")) if m else 0.0


def parse_int(text):
    try:
        return int(float(text.strip().replace(",", ".")))
    except ValueError:
        return 0


def load_unit(grid, c, title):
    info = {
        "title": title,
        "cleaning": cell(grid, 0, c + OFF_INFO),
        "check_out": cell(grid, 1, c + OFF_INFO),
        "check_in": cell(grid, 2, c + OFF_INFO),
    }
    # Итоги месяца из самой таблицы: строка «SUMA» (доход), «Ob» (занятость),
    # следующая строка «ŚREDNIA» (средняя цена за ночь) и количество броней.
    monthly = {}
    last_day = None
    for r in range(DATA_START_ROW - 1, len(grid)):
        day = parse_day(cell(grid, r, c + OFF_DATE))
        if day is not None and day.year == YEAR:
            last_day = day
        if cell(grid, r, c + OFF_PORTAL) == "SUMA" and last_day is not None:
            monthly[last_day.month] = {
                "ob": parse_pct(cell(grid, r, c + OFF_DATE)),
                "suma": parse_money(cell(grid, r, c + OFF_PRICE)),
                "avg": parse_money(cell(grid, r + 1, c + OFF_PRICE)),
                "bookings": parse_int(cell(grid, r + 1, c + OFF_DATE)),
            }
    info["monthly"] = monthly
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


def monthly_summary(selected, days):
    """Итоги по месяцам: для одной квартиры берём строки таблицы,
    для «Razem» суммируем квартиры и пересчитываем занятость и среднюю цену."""
    result = {}
    if len(selected) == 1:
        sheet = selected[0]["info"]["monthly"]
        for m in range(1, 13):
            row = sheet.get(m, {"suma": 0.0, "avg": 0.0, "ob": 0.0, "bookings": 0})
            result[m] = dict(row)
        return result

    stats = monthly_stats(days)
    for m in range(1, 13):
        suma = sum(u["info"]["monthly"].get(m, {}).get("suma", 0.0) for u in selected)
        bookings = sum(u["info"]["monthly"].get(m, {}).get("bookings", 0) for u in selected)
        nights = stats[m]["nights"]
        available = calendar.monthrange(YEAR, m)[1] * len(selected) - stats[m]["owner"]
        result[m] = {
            "suma": suma,
            "avg": suma / nights if nights else 0.0,
            "ob": round(100 * nights / available, 2) if available else 0.0,
            "bookings": bookings,
        }
    return result


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
        label, tip, price_lbl = "", "", ""
        if a:
            slots += a["total"]
        if a and a["booked"]:
            booked_nights += a["booked"]
            color = portal_color(a["portal"], "booked")
            style = f"background:{color};color:#fff;"
            label = html.escape(a["portal"] or "Rezerwacja")
            if a["total"] > 1:
                label = f"{a['booked']}/{a['total']} · {label}"
            price_lbl = fmt_money(a["price"])
            tip = f"{a['portal'] or 'Rezerwacja'} · {price_lbl}"
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
            f'<div class="cal-lbl">{label}</div>'
            f'<div class="cal-price">{price_lbl}</div></div>'
        )

    st.markdown(
        """
<style>
.cal-grid {display:grid; grid-template-columns:repeat(7,1fr); gap:6px;}
.cal-head {text-align:center; font-size:12px; color:#6b7585; font-weight:600; padding-bottom:2px;}
.cal-cell {border-radius:10px; padding:6px 4px; min-height:72px; font-size:13px;}
.cal-price {font-size:11px; font-weight:700; margin-top:2px; white-space:nowrap;}
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
def build_matrix(values):
    """values: {nazwa pokoju: [12 kwot]} -> miesiące w wierszach, kolumna Razem, wiersz łączny."""
    df = pd.DataFrame(values, index=MONTHS_PL)
    df.index.name = "Miesiąc"
    df[ALL_LABEL] = df.sum(axis=1)
    df.loc["Razem za rok"] = df.sum()
    return df


def show_matrix(values, heading):
    df = build_matrix(values)
    room_cols = list(df.columns[:-1])
    year_totals = df.loc["Razem za rok", room_cols]
    best_room = year_totals.idxmax() if year_totals.max() > 0 else None

    def highlight(frame):
        styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
        if best_room:
            styles.loc[:, best_room] = "background-color: #ffe08a; font-weight: bold;"
        styles.loc["Razem za rok", :] = "background-color: #d4edda; font-weight: bold;"
        return styles

    st.subheader(heading)
    st.dataframe(
        df.style.format(fmt_money).apply(highlight, axis=None),
        use_container_width=True,
        height=(len(df) + 1) * 35 + 3,
    )
    if best_room:
        st.caption(f"Najlepszy pokój za rok: {best_room} (wyróżniony żółtym). "
                   "Zielony wiersz to suma za rok.")


def show_rooms_table(units):
    values = {
        u["info"]["title"]: [m["suma"] for m in monthly_summary([u], u["days"]).values()]
        for u in units
    }
    show_matrix(values, "Przychód według pokojów")


def show_old_history(history):
    for year in OLD_YEARS:
        if history[year]:
            show_matrix(history[year], f"Przychód {year}")

    rows = [
        {"Miesiąc": MONTHS_PL[m], "Rok": str(year),
         "Dochód": sum(values[m] for values in history[year].values())}
        for year in OLD_YEARS if history[year]
        for m in range(12)
    ]
    chart_df = pd.DataFrame(rows)
    base = alt.Chart(chart_df).encode(
        x=alt.X("Miesiąc:N", sort=MONTHS_PL, axis=alt.Axis(labelAngle=-45, title=None)),
        xOffset="Rok:N",
        y=alt.Y("Dochód:Q", title="zł", scale=alt.Scale(domainMin=0)),
        color=alt.Color("Rok:N", legend=alt.Legend(title=None),
                        scale=alt.Scale(domain=[str(y) for y in OLD_YEARS],
                                        range=["#c9d7f7", "#2f6fed"])),
        tooltip=[alt.Tooltip("Miesiąc:N"), alt.Tooltip("Rok:N"),
                 alt.Tooltip("Dochód:Q", format=",.2f", title="Dochód, zł")],
    )
    st.altair_chart(base.mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                    .properties(height=320), use_container_width=True)
    st.caption("Dane z arkuszy historycznych (wiersze sum miesięcznych).")


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

    old_hist = old_history(selected)
    has_old = any(old_hist[y] for y in OLD_YEARS)
    labels = [f"🗓️ Kalendarz {YEAR}", f"📅 Przychód najem brutto {YEAR}", f"📈 Statystyka {YEAR}"]
    if has_old:
        labels.append(f"🕰️ Historia {OLD_YEARS[0]}–{OLD_YEARS[-1]}")
    tabs = st.tabs(labels)
    tab_cal, tab_month, tab_stats = tabs[0], tabs[1], tabs[2]

    with tab_cal:
        month = st.selectbox(
            "Miesiąc",
            options=list(range(1, 13)),
            index=datetime.date.today().month - 1 if datetime.date.today().year == YEAR else 0,
            format_func=lambda m: f"{MONTHS_PL[m - 1]} {YEAR}",
        )
        summary = monthly_summary(selected, days)
        m_sum = summary[month]
        k1, k2 = st.columns(2)
        k1.metric(f"Dochód — {MONTHS_PL[month - 1]}", fmt_money(m_sum["suma"]))
        k2.metric("Rezerwacje", m_sum["bookings"])
        k3, k4 = st.columns(2)
        k3.metric("Obłożenie", f"{m_sum['ob']:.2f}%")
        k4.metric("Średnia cena za noc", fmt_money(m_sum["avg"]) if m_sum["suma"] else "—")
        render_calendar(days, month)

    with tab_month:
        summary = monthly_summary(selected, days)
        year_suma = sum(summary[m]["suma"] for m in range(1, 13))
        year_bookings = sum(summary[m]["bookings"] for m in range(1, 13))
        year_metrics = unit_metrics(days)
        year_nights = year_metrics["nights"]
        year_ob = (100 * year_nights / year_metrics["available"]
                   if year_metrics["available"] else 0.0)
        year_avg = year_suma / year_nights if year_nights else 0.0
        rows = [
            {
                "Miesiąc": MONTHS_PL[m - 1],
                "Suma (dochód)": fmt_money(summary[m]["suma"]),
                "Średnia za noc": fmt_money(summary[m]["avg"]) if summary[m]["suma"] else "—",
                "Obłożenie": f"{summary[m]['ob']:.2f}%",
                "Rezerwacje": summary[m]["bookings"],
            }
            for m in range(1, 13)
        ]
        rows.append({
            "Miesiąc": f"Razem za rok {YEAR}",
            "Suma (dochód)": fmt_money(year_suma),
            "Średnia za noc": fmt_money(year_avg) if year_suma else "—",
            "Obłożenie": f"{year_ob:.2f}%",
            "Rezerwacje": year_bookings,
        })
        table = pd.DataFrame(rows)
        chart_df = pd.DataFrame({
            "Miesiąc": [MONTHS_PL[m - 1] for m in range(1, 13)],
            "Kolejność": list(range(1, 13)),
            "Dochód": [summary[m]["suma"] for m in range(1, 13)],
            "Rezerwacje": [summary[m]["bookings"] for m in range(1, 13)],
            "Obłożenie": [summary[m]["ob"] for m in range(1, 13)],
            "Wybrany": [m == month for m in range(1, 13)],
        })
        base = alt.Chart(chart_df).encode(
            x=alt.X("Miesiąc:N", sort=MONTHS_PL,
                    axis=alt.Axis(labelAngle=-45, title=None)),
            y=alt.Y("Dochód:Q", title="zł", scale=alt.Scale(domainMin=0)),
            color=alt.condition(alt.datum.Wybrany, alt.value("#2f6fed"), alt.value("#c9d7f7")),
            tooltip=[
                alt.Tooltip("Miesiąc:N"),
                alt.Tooltip("Dochód:Q", format=",.2f", title="Dochód, zł"),
                alt.Tooltip("Rezerwacje:Q", title="Rezerwacje"),
                alt.Tooltip("Obłożenie:Q", format=".2f", title="Obłożenie, %"),
            ],
        )
        bars = base.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        labels = (base.transform_filter(alt.datum.Dochód > 0)
                  .mark_text(dy=-8, fontSize=11, color="#1c2430")
                  .encode(text=alt.Text("Dochód:Q", format=",.0f")))
        st.altair_chart((bars + labels).properties(height=320), use_container_width=True)
        last_row = len(table) - 1

        def highlight_total(row):
            style = "background-color: #d4edda; font-weight: bold;" if row.name == last_row else ""
            return [style] * len(row)

        if choice == ALL_LABEL:
            show_rooms_table(units_data)
        else:
            st.dataframe(table.style.apply(highlight_total, axis=1),
                         hide_index=True, use_container_width=True,
                         height=(len(table) + 1) * 35 + 3)

    with tab_stats:
        render_extended_stats(selected, show_per_unit=(choice == ALL_LABEL))

    if has_old:
        with tabs[3]:
            show_old_history(old_hist)

    st.markdown(
        "<div style='font-size:12px;color:#888;margin-top:20px'>Kwoty podane według cen z tabeli.</div>",
        unsafe_allow_html=True,
    )


if check_login():
    show_panel()
