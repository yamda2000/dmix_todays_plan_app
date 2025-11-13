import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html import escape
from textwrap import dedent
from typing import Dict, List, Optional

import requests
import streamlit as st

try:
    from zoneinfo import ZoneInfo

    JST = ZoneInfo("Asia/Tokyo")
except Exception:  # pragma: no cover - fallback for Py<3.9
    JST = timezone(timedelta(hours=9))

HOLIDAYS_API_URL = "https://holidays-jp.github.io/api/v1/date.json"
FORECAST_API_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/140000.json"
OVERVIEW_API_URL = "https://www.jma.go.jp/bosai/forecast/data/overview_forecast/140000.json"
YAHOO_NEWS_RSS = "https://news.yahoo.co.jp/rss/topics/top-picks.xml"
FORECAST_AREA_CODE = "140010"  # 横浜市
TEMP_AREA_CODE = "46106"  # 横浜

GARBAGE_SCHEDULE = {
    0: "なし",
    1: "燃やすごみ（燃えないごみ・スプレー缶・乾電池）",
    2: "プラスチック資源",
    3: "なし",
    4: "缶・ビン・ペットボトル（小さな金属類）",
    5: "燃やすごみ（燃えないごみ・スプレー缶・乾電池）",
    6: "なし",
}

WEEKDAYS_JP = ["月", "火", "水", "木", "金", "土", "日"]


def inject_global_styles() -> None:
    st.markdown(
        """
        <style>
            .app-card {
                background-color: #f5f7fb;
                border: 1px solid #dde3ee;
                border-radius: 16px;
                padding: 1.5rem 1.8rem;
                margin-bottom: 1.2rem;
                box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08);
                color: inherit;
            }
            .app-card h3 {
                margin-top: 0;
                margin-bottom: 0.2rem;
            }
            .app-card-caption {
                color: #5c6473;
                font-size: 0.9rem;
                margin-bottom: 1rem;
            }
            .app-card-main {
                font-size: 1.5rem;
                font-weight: 600;
                margin-bottom: 0.2rem;
            }
            .app-card-note {
                color: #5c6473;
                font-size: 0.9rem;
                margin: 0.2rem 0;
            }
            .app-metrics {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 0.8rem;
                margin: 1rem 0;
            }
            .app-metric {
                background: #ffffff;
                border-radius: 12px;
                padding: 0.9rem 1rem;
                border: 1px solid #e3e8f2;
            }
            .app-metric-label {
                font-size: 0.85rem;
                color: #5c6473;
            }
            .app-metric-value {
                font-size: 1.4rem;
                font-weight: 600;
            }
            .app-cols {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin: 0.8rem 0 1rem;
            }
            .app-table {
                width: 100%;
                border-collapse: collapse;
                margin: 0.8rem 0;
            }
            .app-table th,
            .app-table td {
                border: 1px solid #d5dce9;
                padding: 0.4rem 0.6rem;
                text-align: left;
            }
            .app-table th {
                background: #edf1fb;
            }
            .app-link {
                font-weight: 600;
            }
            .app-alert {
                padding: 0.85rem 1rem;
                border-radius: 10px;
                margin: 0.6rem 0;
                border-left: 4px solid transparent;
            }
            .app-alert-info {
                background: #eef4ff;
                color: #1d3b8b;
                border-color: #4f74ff;
            }
            .app-alert-success {
                background: #e6f4ea;
                color: #1b5e20;
                border-color: #2e7d32;
            }
            .app-alert-warning {
                background: #fff8e1;
                color: #8c6d1f;
                border-color: #f7b500;
            }
            .app-alert-error {
                background: #fdecea;
                color: #7a1c1c;
                border-color: #e53935;
            }
            .app-news-item + .app-news-item {
                margin-top: 0.8rem;
            }
            @media (prefers-color-scheme: dark) {
                .app-card {
                    background-color: #1f2533;
                    border-color: #364152;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.45);
                }
                .app-card-caption,
                .app-card-note {
                    color: #c4cde0;
                }
                .app-metric {
                    background: #101522;
                    border-color: #2c364a;
                }
                .app-metric-label {
                    color: #c4cde0;
                }
                .app-table th {
                    background: #2b3449;
                }
                .app-table td,
                .app-table th {
                    border-color: #3a445c;
                }
                .app-alert-info {
                    background: #223455;
                    color: #c7dbff;
                    border-color: #5f8bff;
                }
                .app-alert-success {
                    background: #1a3a2a;
                    color: #c3f1cd;
                    border-color: #3cb371;
                }
                .app-alert-warning {
                    background: #463a17;
                    color: #ffe5a2;
                    border-color: #ffce67;
                }
                .app-alert-error {
                    background: #3d1c1c;
                    color: #ffc6c6;
                    border-color: #ff6b6b;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_card(title: str, caption: str, body_html: str) -> None:
    card_html = dedent(
        f"""
        <div class="app-card">
            <h3>{escape(title)}</h3>
            <p class="app-card-caption">{escape(caption)}</p>
            <div class="app-card-body">
                {body_html}
            </div>
        </div>
        """
    ).strip()
    st.markdown(card_html, unsafe_allow_html=True)


def alert_html(message: str, level: str = "info") -> str:
    level_class = {
        "info": "app-alert-info",
        "success": "app-alert-success",
        "warning": "app-alert-warning",
        "error": "app-alert-error",
    }.get(level, "app-alert-info")
    return f'<div class="app-alert {level_class}">{escape(message)}</div>'


def to_jst_datetime(iso_str: str) -> datetime:
    dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone(JST)
    return dt.astimezone(JST)


def format_date_jp(target: date) -> str:
    return f"{target.year}年{target.month}月{target.day}日"


def format_weekday(day: date) -> str:
    return WEEKDAYS_JP[day.weekday()]


def normalize_text(value: Optional[str]) -> str:
    return (value or "").replace("\u3000", " ").strip()


def find_area_block(areas: List[Dict], code: str) -> Optional[Dict]:
    for area in areas:
        if area.get("area", {}).get("code") == code:
            return area
    return None


def format_temperature(value: Optional[float]) -> str:
    if value is None:
        return "―"
    text = f"{value:.1f}"
    return text.rstrip("0").rstrip(".")


def multiline_html(text: Optional[str]) -> str:
    if not text:
        return ""
    return "<br>".join(escape(text).splitlines())


@st.cache_data(ttl=12 * 60 * 60)
def fetch_holidays() -> Dict[date, str]:
    resp = requests.get(HOLIDAYS_API_URL, timeout=10)
    resp.raise_for_status()
    raw = resp.json()
    return {date.fromisoformat(key): value for key, value in raw.items()}


@st.cache_data(ttl=30 * 60)
def fetch_forecast():
    resp = requests.get(FORECAST_API_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30 * 60)
def fetch_overview():
    resp = requests.get(OVERVIEW_API_URL, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=10 * 60)
def fetch_news(limit: int = 5) -> List[Dict[str, str]]:
    resp = requests.get(YAHOO_NEWS_RSS, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    items: List[Dict[str, str]] = []
    for item in root.findall("./channel/item"):
        title = normalize_text(item.findtext("title"))
        link = normalize_text(item.findtext("link"))
        pub_date = normalize_text(item.findtext("pubDate"))
        items.append({"title": title, "link": link, "pub_date": pub_date})
        if len(items) >= limit:
            break
    return items


def get_holiday_status(today: date) -> Dict[str, Optional[str]]:
    holidays = fetch_holidays()
    is_holiday = today in holidays
    today_name = holidays.get(today)
    next_date = None
    for target in sorted(holidays):
        if target > today:
            next_date = target
            break
    next_name = holidays.get(next_date) if next_date else None
    return {
        "is_holiday": is_holiday,
        "today_name": today_name,
        "next_date": next_date,
        "next_name": next_name,
    }


def get_weather_payload(today: date) -> Dict:
    forecast = fetch_forecast()
    overview = fetch_overview()
    payload = {
        "weather_text": None,
        "weather_time": None,
        "pops": [],
        "min_temp": None,
        "max_temp": None,
        "temp_source_date": None,
        "overview_text": normalize_text(overview.get("text")),
        "report_datetime": None,
    }

    if forecast:
        report_dt = forecast[0].get("reportDatetime")
        if report_dt:
            payload["report_datetime"] = to_jst_datetime(report_dt)

        time_series = forecast[0].get("timeSeries", [])
        weather_series = time_series[0] if len(time_series) > 0 else None
        pop_series = time_series[1] if len(time_series) > 1 else None
        temp_series = time_series[2] if len(time_series) > 2 else None

        if weather_series:
            area_weather = find_area_block(weather_series.get("areas", []), FORECAST_AREA_CODE)
            time_defines = weather_series.get("timeDefines", [])
            if area_weather:
                for idx, iso_time in enumerate(time_defines):
                    if idx >= len(area_weather.get("weathers", [])):
                        continue
                    target_dt = to_jst_datetime(iso_time)
                    if target_dt.date() == today:
                        payload["weather_text"] = normalize_text(area_weather["weathers"][idx])
                        payload["weather_time"] = target_dt
                        break
                if payload["weather_text"] is None and area_weather.get("weathers"):
                    payload["weather_text"] = normalize_text(area_weather["weathers"][0])

        if pop_series:
            area_pop = find_area_block(pop_series.get("areas", []), FORECAST_AREA_CODE)
            time_defines = pop_series.get("timeDefines", [])
            if area_pop:
                pops = area_pop.get("pops", [])
                for idx, iso_time in enumerate(time_defines):
                    if idx >= len(pops):
                        continue
                    value = pops[idx]
                    if not value:
                        continue
                    target_dt = to_jst_datetime(iso_time)
                    if target_dt.date() == today:
                        payload["pops"].append(
                            {"label": target_dt.strftime("%H:%M"), "value": f"{value}%"}
                        )

        if temp_series:
            area_temp = find_area_block(temp_series.get("areas", []), TEMP_AREA_CODE)
            time_defines = temp_series.get("timeDefines", [])
            if area_temp:
                temps = area_temp.get("temps", [])
                for idx, iso_time in enumerate(time_defines):
                    if idx >= len(temps):
                        continue
                    value = temps[idx]
                    if not value:
                        continue
                    target_dt = to_jst_datetime(iso_time)
                    if target_dt.date() == today:
                        temp_value = float(value)
                        payload["min_temp"] = (
                            temp_value
                            if payload["min_temp"] is None
                            else min(payload["min_temp"], temp_value)
                        )
                        payload["max_temp"] = (
                            temp_value
                            if payload["max_temp"] is None
                            else max(payload["max_temp"], temp_value)
                        )
                        payload["temp_source_date"] = today
                if payload["temp_source_date"] is None and temps:
                    try:
                        payload["min_temp"] = float(temps[0])
                    except ValueError:
                        pass
                    if len(temps) > 1:
                        try:
                            payload["max_temp"] = float(temps[1])
                        except ValueError:
                            pass
                    if time_defines:
                        payload["temp_source_date"] = to_jst_datetime(time_defines[0]).date()
    return payload


def render_date_section(today: date, now: datetime) -> None:
    with st.container():
        body = (
            f'<p class="app-card-main">{escape(format_date_jp(today))}'
            f"（{escape(format_weekday(today))}曜日）</p>"
        )
        render_card("項目1：今日の日付", "", body)


def render_holiday_section(today: date) -> None:
    with st.container():
        try:
            info = get_holiday_status(today)
        except requests.RequestException as exc:
            body = alert_html(f"祝日情報の取得に失敗しました：{exc}", "error")
            render_card("項目2：祝日情報", "データ提供：holidays-jp API", body)
            return

        parts: List[str] = []
        if info["is_holiday"]:
            name = info["today_name"] or "名称未取得"
            parts.append(alert_html(f"今日は祝日です（{name}）。", "success"))
        else:
            parts.append(alert_html("今日は祝日ではありません。", "info"))

        if info["next_date"]:
            formatted = format_date_jp(info["next_date"])
            next_name = info["next_name"] or "名称未取得"
            parts.append(
                f"<p>次の祝日：<strong>{escape(formatted)}（{escape(next_name)}）</strong></p>"
            )
        else:
            parts.append("<p>次に予定されている祝日情報はありません。</p>")

        render_card("項目2：祝日情報", "データ提供：holidays-jp API", "".join(parts))


def render_weather_section(today: date) -> None:
    with st.container():
        try:
            weather = get_weather_payload(today)
        except requests.RequestException as exc:
            body = alert_html(f"気象庁APIからの取得に失敗しました：{exc}", "error")
            render_card("項目3：今日の天気", "データ提供：気象庁 API", body)
            return
        except Exception as exc:  # pragma: no cover - defensive
            body = alert_html(f"天気データの処理中にエラーが発生しました：{exc}", "error")
            render_card("項目3：今日の天気", "データ提供：気象庁 API", body)
            return

        parts: List[str] = []
        if weather["weather_text"]:
            label = f"横浜市の天気：{weather['weather_text']}"
            parts.append(f"<p><strong>{escape(label)}</strong></p>")
        else:
            parts.append(alert_html("天気のテキスト情報を取得できませんでした。", "warning"))

        if weather["weather_time"]:
            parts.append(
                f'<p class="app-card-note">対象時刻：'
                f"{escape(weather['weather_time'].strftime('%Y-%m-%d %H:%M'))}</p>"
            )

        parts.append(
            f"""
            <div class="app-metrics">
                <div class="app-metric">
                    <div class="app-metric-label">最低気温 (℃)</div>
                    <div class="app-metric-value">{format_temperature(weather['min_temp'])}</div>
                </div>
                <div class="app-metric">
                    <div class="app-metric-label">最高気温 (℃)</div>
                    <div class="app-metric-value">{format_temperature(weather['max_temp'])}</div>
                </div>
            </div>
            """
        )

        if weather["temp_source_date"]:
            parts.append(
                f'<p class="app-card-note">気温データ対象日：'
                f"{escape(format_date_jp(weather['temp_source_date']))}</p>"
            )

        if weather["pops"]:
            rows = "".join(
                f"<tr><td>{escape(entry['label'])}</td>"
                f"<td>{escape(entry['value'])}</td></tr>"
                for entry in weather["pops"]
            )
            parts.append(
                "<p><strong>今日の時間帯別降水確率</strong></p>"
                '<table class="app-table"><thead><tr><th>時間</th><th>降水確率</th></tr></thead>'
                f"<tbody>{rows}</tbody></table>"
            )
        else:
            parts.append(alert_html("今日の降水確率データは取得できませんでした。", "warning"))

        if weather["overview_text"]:
            parts.append("<p><strong>天気の概要</strong></p>")
            parts.append(f"<p>{multiline_html(weather['overview_text'])}</p>")

        if weather["report_datetime"]:
            parts.append(
                f'<p class="app-card-note">発表：'
                f"{escape(weather['report_datetime'].strftime('%Y-%m-%d %H:%M'))}</p>"
            )

        render_card("項目3：今日の天気", "データ提供：気象庁 API", "".join(parts))


def render_garbage_section(today: date) -> None:
    with st.container():
        tomorrow = today + timedelta(days=1)
        today_info = GARBAGE_SCHEDULE.get(today.weekday(), "情報なし")
        tomorrow_info = GARBAGE_SCHEDULE.get(tomorrow.weekday(), "情報なし")
        body = dedent(
            f"""
            <div class="app-cols">
                <div>
                    <p><strong>今日（{escape(format_weekday(today))}）</strong></p>
                    <p>{escape(today_info)}</p>
                </div>
                <div>
                    <p><strong>明日（{escape(format_weekday(tomorrow))}）</strong></p>
                    <p>{escape(tomorrow_info)}</p>
                </div>
            </div>
            <p>
                <a class="app-link" href="https://www.city.yokohama.lg.jp/kurashi/sumai-kurashi/gomi-recycle/gomi/shushuyobi/tsuzuki/nagyou.html" target="_blank" rel="noopener">
                    横浜市都筑区の収集カレンダー
                </a>
            </p>
        """
        ).strip()
        render_card("項目4：ゴミ収集情報", "API不使用 / 横浜市都筑区", body)


def render_news_section() -> None:
    with st.container():
        try:
            news_items = fetch_news(limit=5)
        except (requests.RequestException, ET.ParseError) as exc:
            body = alert_html(f"ニュースの取得に失敗しました：{exc}", "error")
            render_card("項目5：Yahoo!ニュース トップニュース", "データ提供：Yahoo!ニュース", body)
            return

        if not news_items:
            body = alert_html("表示できるニュース項目がありません。", "info")
            render_card("項目5：Yahoo!ニュース トップニュース", "データ提供：Yahoo!ニュース", body)
            return

        list_items = []
        for item in news_items:
            title = escape(item.get("title") or "タイトル未取得")
            link = escape(item.get("link") or "#")
            pub = escape(item.get("pub_date") or "")
            list_items.append(
                f'<div class="app-news-item"><a class="app-link" href="{link}" target="_blank" rel="noopener">{title}</a>'
                f'<div class="app-card-note">{pub}</div></div>'
            )

        render_card(
            "項目5：Yahoo!ニュース トップニュース",
            "データ提供：Yahoo!ニュース",
            "".join(list_items),
        )


def main() -> None:
    st.set_page_config(page_title="今日の予定確認アプリ", layout="wide")
    inject_global_styles()
    st.title("今日の予定確認APP")
    st.caption("各情報は無料API・公的データを利用し、適切な間隔でキャッシュしています。")

    now = datetime.now(JST)
    today = now.date()
    st.write(f"最終更新：{now.strftime('%Y-%m-%d %H:%M')}")

    render_date_section(today, now)
    render_holiday_section(today)
    render_weather_section(today)
    render_garbage_section(today)
    render_news_section()


if __name__ == "__main__":
    main()
