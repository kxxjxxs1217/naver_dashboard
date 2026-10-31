"""SPA 3사 경쟁 모니터링 대시보드 (브랜드 마케터용).

실행: python -m streamlit run app/dashboard.py
입력: data/processed/ (src/ 스크립트 결과), reports/figures/wordcloud/

- 기준 브랜드를 고르면 강조색·서체·카피가 그 브랜드 톤앤매너로 바뀌고, 나머지는 경쟁사로 비교된다.
- 보기 모드: '대시보드'(탭으로 탐색) / '보고서'(한 페이지 요약 → 섹션 순서, 인쇄·PDF 저장용)
- 화면 상태(브랜드·모드·기간)는 URL에 남아 링크로 같은 화면을 공유할 수 있다. 예) ?brand=스파오&view=보고서&period=24
모니터링 순서: ① 요약·경보 → ② 관심도 → ③ 화제성 → ④ 브랜드 인식 → ⑤ 타깃 → ⑥ 지표 사전
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
WC = ROOT / "reports" / "figures" / "wordcloud"

BRANDS = ["유니클로", "스파오", "탑텐"]
TOPICS = ["제품 출시", "협업", "할인·행사", "실적·사업", "기타"]
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
AS_OF = "2026-10-31"
SRC_SEARCH = "네이버 검색어 트렌드(통합검색)"
SRC_NEWS = "네이버 뉴스 검색 · 정제 기사 150건"

# 브랜드 톤앤매너: 색은 색각이상 검증(validate_palette.js, 전 조합 PASS)을 통과한 조합.
# 톤·태그라인은 뉴스 키워드(TF-IDF)와 연상 속성 분석에서 도출한 해석이며 공식 브랜드 가이드가 아니다.
THEME = {
    "유니클로": {"color": "#d8352d", "tint": "#fbe9e7", "font": "IBM Plex Sans KR", "weight": 700,
               "tagline": "LifeWear, 일상을 위한 글로벌 스탠다드",
               "tone": ["차분한", "미니멀", "신뢰감"], "keywords": ["명동 플래그십", "글로벌 실적", "가격 정책", "디자이너 협업"],
               "voice": "군더더기 없이, 사실과 숫자로 말한다."},
    "스파오": {"color": "#6250d6", "tint": "#ecebfb", "font": "Jua", "weight": 400,
             "tagline": "캐릭터와 놀고, 팬과 함께 만드는 토종 SPA",
             "tone": ["경쾌한", "위트", "팬덤"], "keywords": ["IP 협업", "스파오키즈", "10대 패딩", "체험형 매장"],
             "voice": "가볍고 재치 있게, 팬의 언어로 말한다."},
    "탑텐": {"color": "#1baf7a", "tint": "#e3f5ee", "font": "Gowun Dodum", "weight": 700,
           "tagline": "온 가족이 함께 입는 실속 굿웨어",
           "tone": ["친근한", "따뜻한", "실속"], "keywords": ["텐텐데이", "탑텐키즈", "에어테크", "굿웨어"],
           "voice": "다정하고 쉽게, 가족의 일상으로 말한다."},
}
COLOR = {b: THEME[b]["color"] for b in BRANDS}
TOPIC_COLOR = {"제품 출시": "#2a78d6", "협업": "#eb6834", "할인·행사": "#1baf7a", "실적·사업": "#eda100",
               "기타": "#c3c2b7"}
SENT_COLOR = {"긍정": "#2a78d6", "중립": "#c3c2b7", "부정": "#d03b3b"}

# 경보 기준 (지표 사전과 동일)
RULES = [
    ("검색량 성장률 YoY(최근3개월,%)", lambda v: v < 0, "주의", "최근 3개월 검색량이 전년보다 줄었습니다", "② 관심도"),
    ("SOS 전년 대비(%p)", lambda v: v <= -1, "주의", "검색 점유율이 1년 새 1%p 이상 빠졌습니다", "② 관심도"),
    ("초과 보도 점유율 ESOV(%p)", lambda v: v <= -5, "참고", "검색 관심에 비해 보도 노출이 적습니다", "③ 화제성"),
    ("보도량 가중 부정 비중(%)", lambda v: v >= 5, "경고", "부정 이슈 보도가 보도량의 5% 이상입니다", "③ 화제성"),
    ("행사 의존도(주별 최고/중앙값)", lambda v: v >= 4, "참고", "검색 관심이 특정 행사 주간에 몰려 있습니다", "② 관심도"),
]
STATUS_ICON = {"경고": "🔴", "주의": "🟠", "참고": "🔵"}
SECTIONS = [("summary", "① 요약·경보"), ("search", "② 관심도 (검색)"), ("buzz", "③ 화제성 (뉴스)"),
            ("perception", "④ 브랜드 인식"), ("target", "⑤ 타깃"), ("glossary", "⑥ 지표 사전")]
PERIODS = {"최근 12개월": 12, "최근 24개월": 24, "최근 36개월": 36}

st.set_page_config(page_title="SPA 3사 경쟁 모니터링", page_icon="📊", layout="wide")


@st.cache_data
def load():
    return {"kpi": pd.read_csv(PROC / "마케팅_브랜드지표.csv", encoding="utf-8-sig").set_index("브랜드"),
            "news": pd.read_csv(PROC / "마케팅_기사분석.csv", encoding="utf-8-sig", parse_dates=["날짜"]),
            "profile": pd.read_csv(PROC / "마케팅_속성프로필.csv", encoding="utf-8-sig").set_index("브랜드"),
            "segidx": pd.read_csv(PROC / "마케팅_세그먼트인덱스.csv", encoding="utf-8-sig"),
            "seg": pd.read_csv(PROC / "검색트렌드_세그먼트_점유율.csv", encoding="utf-8-sig"),
            "monthly": pd.read_csv(PROC / "검색트렌드_월별.csv", encoding="utf-8-sig", parse_dates=["월"]),
            "weekly": pd.read_csv(PROC / "검색트렌드_주별.csv", encoding="utf-8-sig", parse_dates=["주 시작일"]),
            "kw": pd.read_csv(PROC / "SPA_키워드_BoW_TFIDF.csv", encoding="utf-8-sig")}


D = load()
kpi, news, prof = D["kpi"], D["news"], D["profile"]

# ---- 상태: URL 쿼리 ↔ 위젯 (링크로 같은 화면 공유) ----------------------------------------
qp = st.query_params
q_brand = qp.get("brand", BRANDS[0])
q_view = qp.get("view", "대시보드")
q_period = qp.get("period", "24")

st.sidebar.markdown("### 기준 브랜드")
focal = st.sidebar.radio("우리 브랜드", BRANDS, index=BRANDS.index(q_brand) if q_brand in BRANDS else 0,
                         label_visibility="collapsed")
rivals = [b for b in BRANDS if b != focal]
T = THEME[focal]
st.sidebar.markdown(f"경쟁사: **{' · '.join(rivals)}**")
st.sidebar.markdown("### 보기 모드")
view = st.sidebar.radio("보기 모드", ["대시보드", "보고서"], index=1 if q_view == "보고서" else 0, horizontal=True,
                        label_visibility="collapsed",
                        help="대시보드: 탭으로 탐색 / 보고서: 요약부터 섹션 순서대로 한 페이지에 펼침 (인쇄·PDF 저장용)")
st.sidebar.markdown("### 검색 추이 기간")
period_label = st.sidebar.radio("기간", list(PERIODS), horizontal=False, label_visibility="collapsed",
                                index=[str(v) for v in PERIODS.values()].index(q_period)
                                if q_period in [str(v) for v in PERIODS.values()] else 1)
months = PERIODS[period_label]
st.query_params.update({"brand": focal, "view": view, "period": str(months)})

# ---- 브랜드 톤앤매너 스타일 + 인쇄 스타일 ------------------------------------------------
fonts = "family=Noto+Sans+KR:wght@400;500;700&family=" + T["font"].replace(" ", "+") + f":wght@{T['weight']}"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?{fonts}&display=swap');
html, body, p, li, label, input, textarea, .stMarkdown, [data-testid="stCaptionContainer"] {{ font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif; }}
[data-testid="stIconMaterial"] {{ font-family: 'Material Symbols Rounded' !important; }}
h1, h2, h3, h4 {{ font-family: '{T["font"]}', 'Noto Sans KR', sans-serif !important; font-weight: {T["weight"]} !important; }}
/* 위젯도 브랜드 색으로: 선택된 라디오, 탭 밑줄, 다운로드 버튼 */
[data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {{ background-color: {T["color"]} !important; border-color: {T["color"]} !important; }}
.stTabs [aria-selected="true"] {{ color: {INK} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {T["color"]} !important; }}
[data-testid="stDownloadButton"] button {{ border-color: {T["color"]}; }}
[data-testid="stDownloadButton"] button:hover {{ border-color: {T["color"]}; color: {T["color"]}; }}
.hero {{ background: {T["tint"]}; border-left: 8px solid {T["color"]}; border-radius: 6px; padding: 18px 24px; margin-bottom: 6px; }}
.hero .name {{ font-family: '{T["font"]}', sans-serif; font-size: 34px; font-weight: {T["weight"]}; color: {INK}; line-height: 1.2; }}
.hero .tag {{ font-size: 16px; color: {INK2}; margin-top: 4px; }}
.chip {{ display: inline-block; border: 1px solid {T["color"]}; color: {INK}; background: #ffffff; border-radius: 4px;
        padding: 2px 10px; margin: 8px 6px 0 0; font-size: 13px; }}
.chip.solid {{ background: {T["color"]}; color: #ffffff; }}
.voice {{ font-size: 13px; color: {INK2}; margin-top: 8px; }}
.meta {{ font-size: 13px; color: {INK2}; margin: 2px 0 10px; }}
.kcard {{ background: #ffffff; border: 1px solid {GRID}; border-top: 4px solid {T["color"]}; border-radius: 6px; padding: 12px 14px; min-height: 128px; }}
.kcard .lab {{ font-size: 13px; color: {INK2}; }}
.kcard .val {{ font-size: 28px; font-weight: 700; color: {INK}; margin: 2px 0; }}
.kcard .cmp {{ font-size: 12.5px; color: {INK2}; }}
.headline {{ border-left: 4px solid {T["color"]}; padding: 2px 0 2px 12px; margin: 22px 0 4px; }}
.headline .kicker {{ font-size: 12.5px; color: {INK2}; letter-spacing: .02em; }}
.headline .title {{ font-size: 19px; font-weight: 700; color: {INK}; line-height: 1.4; }}
.source {{ font-size: 12.5px; color: {MUTED}; margin: -4px 0 14px; }}
.sec {{ font-family: '{T["font"]}', sans-serif; font-weight: {T["weight"]}; font-size: 24px; color: {INK};
       border-bottom: 2px solid {T["color"]}; padding-bottom: 6px; margin: 30px 0 6px; }}
.toc a {{ color: {INK}; text-decoration: none; border-bottom: 1px solid {T["color"]}; margin-right: 14px; font-size: 14px; }}
.exec {{ background: #ffffff; border: 1px solid {GRID}; border-radius: 6px; padding: 14px 18px; }}
@media print {{
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDownloadButton"],
  .no-print {{ display: none !important; }}
  .sec {{ break-before: page; }}
  .sec.first {{ break-before: auto; }}
  .js-plotly-plot, .kcard, .headline {{ break-inside: avoid; }}
  [data-testid="stMain"] {{ padding: 0 !important; }}
}}
</style>""", unsafe_allow_html=True)


# ---- 공통 표현 도구 -------------------------------------------------------------
def style(fig, height=400, y_title=None, x_title=None, hover="x unified", dates=False):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=20, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(family="Noto Sans KR, Malgun Gothic, sans-serif", color=INK2, size=13),
                      legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", traceorder="normal"),
                      hoverlabel=dict(bgcolor="white", font_color=INK), hovermode=hover)
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED), title=x_title)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), title=y_title)
    if dates:
        fig.update_xaxes(tickformat="%y.%m", hoverformat="%Y-%m-%d")
    return fig


def plot(fig, name):
    """보고용: 마우스를 올리면 PNG 저장 버튼만 보이도록 (파일명 = 브랜드_차트명)."""
    st.plotly_chart(fig, width="stretch", config={
        "displaylogo": False, "modeBarButtonsToRemove": ["zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d",
                                                         "zoomOut2d", "autoScale2d", "resetScale2d"],
        "toImageButtonOptions": {"format": "png", "filename": f"{focal}_{name}", "scale": 2}})


def headline(kicker, title):
    """액션 타이틀: 차트 위에 '무엇을 봐야 하는지'를 한 문장으로."""
    st.markdown(f'<div class="headline"><div class="kicker">{kicker}</div><div class="title">{title}</div></div>',
                unsafe_allow_html=True)


def source(text):
    st.markdown(f'<div class="source">출처: {text} · 기준일 {AS_OF}</div>', unsafe_allow_html=True)


def width_for(b):
    return 3 if b == focal else 1.6


def opacity_for(b):
    return 1.0 if b == focal else 0.55


def rank(col):
    return list(kpi[col].sort_values(ascending=False).index).index(focal) + 1


def card(col, label, value, compare):
    col.markdown(f'<div class="kcard"><div class="lab">{label}</div><div class="val">{value}</div>'
                 f'<div class="cmp">{compare}</div></div>', unsafe_allow_html=True)


def safe(s):
    """마크다운에서 '~'가 취소선이 되지 않도록."""
    return str(s).replace("~", "–")


k = kpi.loc[focal]


def alerts_for(brand):
    out = []
    kb = kpi.loc[brand]
    for col, cond, level, msg, where in RULES:
        v = kb[col]
        if cond(v):
            unit = "%p" if "%p" in col else ("배" if "의존도" in col else "%")
            val = f"{v:+.1f}{unit}" if unit == "%p" or "YoY" in col else f"{v:.1f}{unit}"
            out.append((level, col.split("(")[0].strip(), val, msg, where))
    return sorted(out, key=lambda a: {"경고": 0, "주의": 1, "참고": 2}[a[0]])


ALERTS = alerts_for(focal)
gap_attr = (prof.loc[focal] - prof.drop(focal).mean()).sort_values()
best_yoy = kpi["검색량 성장률 YoY(최근3개월,%)"].idxmax()
risk_n = int((news[news["브랜드"] == focal]["감성"] == "부정").sum())
EXEC = [
    f"**관심도** — 검색 점유율 {k['검색 점유율 SOS(최근12개월,%)']:.0f}%로 3사 중 {rank('검색 점유율 SOS(최근12개월,%)')}위, "
    f"최근 3개월 검색량은 전년 대비 {k['검색량 성장률 YoY(최근3개월,%)']:+.0f}%"
    + (" (3사 중 성장 1위)." if best_yoy == focal else
       f" (성장 1위 {best_yoy} {kpi.loc[best_yoy, '검색량 성장률 YoY(최근3개월,%)']:+.0f}%)."),
    f"**화제성** — 공통기간 보도 점유율 {k['공통기간 보도 점유율 SOV(%)']:.0f}%, 검색 대비 노출 "
    f"{'과다' if k['초과 보도 점유율 ESOV(%p)'] > 0 else '부족'}({k['초과 보도 점유율 ESOV(%p)']:+.0f}%p). "
    f"순감성 {k['순감성 지수 NSI']:+.0f}, 부정 기사 {risk_n}건.",
    f"**브랜드 인식** — 경쟁사 대비 가장 강한 연상은 '{gap_attr.index[-1]}'({gap_attr.iloc[-1]:+.0f}%p), "
    f"가장 약한 연상은 '{gap_attr.index[0]}'({gap_attr.iloc[0]:+.0f}%p).",
]


# ============================ ① 요약·경보 ======================================
def sec_summary():
    headline("① 요약 · 경쟁사 대비",
             f"{focal}, 검색 점유율 {k['검색 점유율 SOS(최근12개월,%)']:.0f}%(3사 중 {rank('검색 점유율 SOS(최근12개월,%)')}위) · "
             f"최근 3개월 검색 {k['검색량 성장률 YoY(최근3개월,%)']:+.0f}% · 경보 {len(ALERTS)}건")
    c = st.columns(4)
    card(c[0], "검색 점유율 SOS · 최근 12개월", f"{k['검색 점유율 SOS(최근12개월,%)']:.1f}%",
         f"3사 중 {rank('검색 점유율 SOS(최근12개월,%)')}위 · 전년 대비 {k['SOS 전년 대비(%p)']:+.1f}%p")
    card(c[1], "검색량 성장률 YoY · 최근 3개월", f"{k['검색량 성장률 YoY(최근3개월,%)']:+.1f}%",
         f"12개월 기준 {k['검색량 성장률 YoY(최근12개월,%)']:+.1f}% · 3사 중 {rank('검색량 성장률 YoY(최근3개월,%)')}위")
    card(c[2], "보도 점유율 SOV · 공통기간", f"{k['공통기간 보도 점유율 SOV(%)']:.1f}%",
         f"ESOV {k['초과 보도 점유율 ESOV(%p)']:+.1f}%p (SOV − 같은 기간 SOS)")
    card(c[3], "순감성 지수 NSI", f"{k['순감성 지수 NSI']:+.0f}",
         f"부정 기사 {k['부정 기사 비중(%)']:.0f}% · 보도량 가중 {k['보도량 가중 부정 비중(%)']:.1f}%")

    headline("경보", "기준을 넘은 지표" if ALERTS else "기준을 넘은 지표가 없습니다")
    if not ALERTS:
        st.success("✅ 양호 — 다섯 가지 경보 기준을 모두 통과했습니다.")
    for level, name, val, msg, where in ALERTS:
        box = {"경고": st.error, "주의": st.warning, "참고": st.info}[level]
        anchor = next(key for key, label in SECTIONS if label.startswith(where))
        link = f"[{where} 섹션으로 이동 →](#{anchor})" if view == "보고서" else f"→ {where} 탭에서 원인 확인"
        box(f"{STATUS_ICON[level]} {level} · **{name}** {val} — {msg}  \n{link}")

    headline("3사 스코어카드", "▶ 표시가 기준 브랜드입니다. 열 이름에 마우스를 올리면 산식이 보입니다.")
    show = kpi[["검색 점유율 SOS(최근12개월,%)", "SOS 전년 대비(%p)", "검색량 성장률 YoY(최근3개월,%)",
                "공통기간 보도 점유율 SOV(%)", "초과 보도 점유율 ESOV(%p)", "순감성 지수 NSI",
                "보도량 가중 부정 비중(%)", "행사 의존도(주별 최고/중앙값)", "대표 연상 속성"]].copy()
    show.index = [f"▶ {b}" if b == focal else b for b in show.index]
    show.columns = ["SOS (%)", "SOS 전년비 (%p)", "검색 YoY 3개월 (%)", "SOV (%)", "ESOV (%p)", "NSI",
                    "부정 보도 비중 (%)", "행사 의존도 (배)", "대표 연상 속성"]
    num = st.column_config.NumberColumn
    st.dataframe(show, width="stretch", column_config={
        "SOS (%)": num(format="%.1f", help="최근 12개월 세 브랜드 검색량 중 비중"),
        "SOS 전년비 (%p)": num(format="%+.1f", help="최근 12개월 SOS − 직전 12개월 SOS"),
        "검색 YoY 3개월 (%)": num(format="%+.1f", help="2026년 8–10월 검색량 ÷ 2025년 8–10월 − 1"),
        "SOV (%)": num(format="%.1f", help="공통기간(9.22–10.31) 보도량 비중"),
        "ESOV (%p)": num(format="%+.1f", help="SOV − 같은 기간 SOS"),
        "NSI": num(format="%+.0f", help="(긍정 − 부정 기사) ÷ 전체 × 100"),
        "부정 보도 비중 (%)": num(format="%.1f", help="부정 기사 보도량 ÷ 전체 보도량"),
        "행사 의존도 (배)": num(format="%.1f", help="주별 최고 검색량 ÷ 주별 중앙값")})
    source(f"{SRC_SEARCH}, {SRC_NEWS}")


# ============================ ② 관심도 ========================================
def sec_search():
    mo = D["monthly"]
    rng = mo[mo["월"] > mo["월"].max() - pd.DateOffset(months=months)]
    sh = rng.set_index("월")[BRANDS]
    sh = sh.div(sh.sum(axis=1), axis=0) * 100
    first, last = sh[focal].iloc[:3].mean(), sh[focal].iloc[-3:].mean()
    headline(f"② 관심도 · 검색 점유율 추이 ({period_label})",
             f"{focal} 검색 점유율, {period_label} 처음 3개월 평균 {first:.0f}% → 최근 3개월 평균 {last:.0f}% ({last - first:+.1f}%p)")
    fig = go.Figure()
    for b in BRANDS:
        fig.add_scatter(x=sh.index, y=sh[b], name=b, mode="lines+markers",
                        line=dict(color=COLOR[b], width=width_for(b)), opacity=opacity_for(b),
                        marker=dict(size=7 if b == focal else 5, line=dict(color="white", width=1.5)),
                        hovertemplate=f"{b}: %{{y:.1f}}%<extra></extra>")
    plot(style(fig, height=380, y_title="세 브랜드 중 검색 점유율 (%)", dates=True), "검색점유율추이")
    source(f"{SRC_SEARCH} 월별 · SOS = 그 달 세 브랜드 검색량 합계 중 비중 · 굵은 선 = 기준 브랜드 · 기간은 사이드바에서 변경")

    c1, c2 = st.columns(2)
    with c1:
        fv = k["검색량 성장률 YoY(최근3개월,%)"]
        if best_yoy == focal:
            headline("검색 모멘텀", f"{focal}, 최근 3개월 검색 {fv:+.0f}%로 3사 중 성장 1위")
        else:
            headline("검색 모멘텀", f"{focal} 최근 3개월 검색 {fv:+.0f}% — 성장 1위는 {best_yoy}"
                                  f"({kpi.loc[best_yoy, '검색량 성장률 YoY(최근3개월,%)']:+.0f}%)")
        yoy = kpi[["검색량 성장률 YoY(최근12개월,%)", "검색량 성장률 YoY(최근3개월,%)"]]
        fig = go.Figure()
        for lab, col, op in [("최근 12개월", yoy.columns[0], 0.45), ("최근 3개월", yoy.columns[1], 1.0)]:
            fig.add_bar(x=BRANDS, y=yoy.loc[BRANDS, col], name=lab, opacity=op,
                        marker_color=[COLOR[b] for b in BRANDS], marker_line=dict(color="white", width=2),
                        text=[f"{v:+.0f}%" for v in yoy.loc[BRANDS, col]], textposition="outside",
                        hovertemplate=f"%{{x}} · {lab}: %{{y:+.1f}}%<extra></extra>")
        fig.add_hline(y=0, line_color=INK2, line_width=1)
        fig.update_layout(barmode="group", showlegend=False)
        plot(style(fig, height=340, y_title="전년 대비 (%)", hover="closest"), "검색모멘텀")
        source(f"{SRC_SEARCH} 월별 · 연한 막대 = 최근 12개월 vs 직전 12개월 · 진한 막대 = 2026년 8–10월 vs 2025년 같은 달")
    with c2:
        m = mo[mo["월"].dt.year.between(2023, 2025)]
        season = m.groupby(m["월"].dt.month)[BRANDS].mean()
        season = season / season.mean() * 100
        pk = int(season[focal].idxmax())
        headline("계절성", f"{focal}의 검색 성수기는 {pk}월 (연평균 대비 {season[focal].max():.0f})")
        fig = go.Figure()
        for b in BRANDS:
            fig.add_scatter(x=[f"{i}월" for i in season.index], y=season[b], name=b, mode="lines+markers",
                            line=dict(color=COLOR[b], width=width_for(b)), opacity=opacity_for(b),
                            marker=dict(size=7, line=dict(color="white", width=1.5)),
                            hovertemplate=f"{b}: %{{y:.0f}}<extra></extra>")
        fig.add_hline(y=100, line_color=GRID)
        plot(style(fig, height=340, y_title="계절 지수 (연평균 = 100)"), "계절성")
        source(f"{SRC_SEARCH} 2023–2025 월평균 ÷ 연평균 × 100")

    wk = D["weekly"]
    peak_wk = wk.loc[wk[focal].idxmax(), "주 시작일"]
    headline("주별 검색 · 행사 의존도",
             f"{focal} 최근 12개월 최고점은 {peak_wk:%Y.%m.%d} 주 — 평소(중앙값)의 "
             f"{k['행사 의존도(주별 최고/중앙값)']:.1f}배")
    fig = go.Figure()
    for b in BRANDS:
        fig.add_scatter(x=wk["주 시작일"], y=wk[b], name=f"{b} (최고/중앙값 {kpi.loc[b, '행사 의존도(주별 최고/중앙값)']:.1f}배)",
                        mode="lines", line=dict(color=COLOR[b], width=width_for(b)), opacity=opacity_for(b),
                        hovertemplate=f"{b}: %{{y:.1f}}<extra></extra>")
    fig.add_annotation(x=peak_wk, y=float(wk[focal].max()), text=f"{focal} 최고점", showarrow=True, arrowhead=0,
                       ax=-40, ay=-44, font=dict(color=INK2, size=12), arrowcolor=MUTED)
    plot(style(fig, height=360, y_title="상대 검색량 (기간 최댓값 = 100)", dates=True), "주별검색")
    source(f"{SRC_SEARCH} 주별 2025.11–2026.10 · 행사 의존도 = 주별 최고치 ÷ 주별 중앙값 (4배 이상 '참고' 경보)")


# ============================ ③ 화제성 ========================================
def sec_buzz():
    esov = k["초과 보도 점유율 ESOV(%p)"]
    headline("③ 화제성 · 보도 점유율(SOV) vs 검색 점유율(SOS), 공통기간 2026.09.22–10.31",
             f"{focal} 보도 점유율 {k['공통기간 보도 점유율 SOV(%)']:.0f}% vs 검색 점유율 {k['공통기간 SOS(%)']:.0f}% "
             f"— 관심 대비 노출 {'과다' if esov > 0 else '부족'} ({esov:+.0f}%p)")
    fig = go.Figure()
    for lab, col, op in [("검색 점유율 SOS", "공통기간 SOS(%)", 0.45), ("보도 점유율 SOV", "공통기간 보도 점유율 SOV(%)", 1.0)]:
        fig.add_bar(x=BRANDS, y=kpi.loc[BRANDS, col], name=lab, opacity=op, marker_color=[COLOR[b] for b in BRANDS],
                    marker_line=dict(color="white", width=2), text=[f"{v:.0f}%" for v in kpi.loc[BRANDS, col]],
                    textposition="outside", hovertemplate=f"%{{x}} · {lab}: %{{y:.1f}}%<extra></extra>")
    fig.update_layout(barmode="group", showlegend=False)
    plot(style(fig, height=340, y_title="점유율 (%)", hover="closest"), "SOV_SOS")
    source(f"{SRC_NEWS}, {SRC_SEARCH} 주별 · 연한 막대 = SOS, 진한 막대 = SOV · ESOV = SOV − SOS")

    c1, c2 = st.columns(2)
    agg = news.groupby(["브랜드", "주제"])["같은 이슈 보도 수"].sum().unstack(fill_value=0)
    agg = agg.div(agg.sum(axis=1), axis=0).mul(100)
    with c1:
        top_t = agg.loc[focal].idxmax()
        headline("보도 주제 구성 (보도량 비중 %)", f"{focal} 보도량의 최대 주제는 '{top_t}'({agg.loc[focal, top_t]:.0f}%)")
        a2 = agg.reindex(BRANDS[::-1])
        fig = go.Figure()
        for t in TOPICS:
            fig.add_bar(y=a2.index, x=a2[t], name=t, orientation="h", marker_color=TOPIC_COLOR[t],
                        marker_line=dict(color="white", width=2),
                        text=[f"{v:.0f}%" if v >= 7 else "" for v in a2[t]], textposition="inside",
                        insidetextfont=dict(color=INK if t in ("실적·사업", "기타") else "#ffffff"),
                        hovertemplate=f"%{{y}} · {t}: %{{x:.1f}}%<extra></extra>")
        fig.update_layout(barmode="stack")
        plot(style(fig, height=300, hover="closest"), "보도주제")
        source(f"{SRC_NEWS} · 보도량 = 같은 이슈 보도 수 합계")
    with c2:
        headline("보도 감성 분포 (기사 비중 %)", f"{focal} 순감성 {k['순감성 지수 NSI']:+.0f} — 부정 기사 {risk_n}건")
        sent = news.groupby(["브랜드", "감성"]).size().unstack(fill_value=0).reindex(BRANDS[::-1])
        sent = sent.div(sent.sum(axis=1), axis=0).mul(100)
        fig = go.Figure()
        for s in ["긍정", "중립", "부정"]:
            fig.add_bar(y=sent.index, x=sent[s], name=s, orientation="h", marker_color=SENT_COLOR[s],
                        marker_line=dict(color="white", width=2), text=[f"{v:.0f}%" if v >= 7 else "" for v in sent[s]],
                        textposition="inside", insidetextfont=dict(color=INK if s == "중립" else "#ffffff"),
                        hovertemplate=f"%{{y}} · {s}: %{{x:.1f}}%<extra></extra>")
        fig.update_layout(barmode="stack")
        plot(style(fig, height=300, hover="closest"), "보도감성")
        source(f"{SRC_NEWS} · 긍정어·부정어 사전 기반 규칙 · NSI = (긍정 − 부정) ÷ 전체 × 100")

    headline(f"리스크·이슈 기사", f"{focal} 부정 분류 기사 {risk_n}건 — 보도 수가 많은 순")
    risk = news[(news["브랜드"] == focal) & (news["감성"] == "부정")].sort_values("같은 이슈 보도 수", ascending=False)
    cfg = {"날짜": st.column_config.DateColumn(format="YYYY-MM-DD"),
           "원문 링크": st.column_config.LinkColumn(display_text="원문"),
           "같은 이슈 보도 수": st.column_config.NumberColumn("보도 수")}
    if risk.empty:
        st.success("부정으로 분류된 기사가 없습니다.")
    else:
        st.dataframe(risk[["날짜", "제목", "부정어", "같은 이슈 보도 수", "원문 링크"]], hide_index=True, width="stretch",
                     column_config=cfg)
    if view == "대시보드":
        with st.expander(f"{focal} 전체 기사 검색"):
            q = st.text_input("제목·요약 검색", "", placeholder="예: 패딩, 협업, 매장")
            tbl = news[news["브랜드"] == focal]
            if q:
                tbl = tbl[tbl["제목"].str.contains(q, case=False) | tbl["요약"].str.contains(q, case=False)]
            st.caption(f"{len(tbl)}건")
            if tbl.empty:
                st.info("검색 결과가 없습니다. 다른 단어로 찾아보세요.")
            else:
                st.dataframe(tbl.sort_values("같은 이슈 보도 수", ascending=False)[
                                 ["날짜", "주제", "감성", "제목", "같은 이슈 보도 수", "원문 링크"]],
                             hide_index=True, width="stretch", height=360, column_config=cfg)
    source(SRC_NEWS)


# ============================ ④ 브랜드 인식 =====================================
def sec_perception():
    p = prof.reindex(BRANDS)
    attrs = list(p.columns)
    headline("④ 브랜드 인식 · 연상 속성 (기사에서 함께 언급된 비율)",
             f"{focal}의 차별 연상은 '{gap_attr.index[-1]}'({gap_attr.iloc[-1]:+.0f}%p), "
             f"약점은 '{gap_attr.index[0]}'({gap_attr.iloc[0]:+.0f}%p) — 경쟁사 평균 대비")
    fig = go.Figure(go.Heatmap(
        z=p.values, x=attrs, y=BRANDS, colorscale=[[0, "#fcfcfb"], [0.35, T["tint"]], [1, T["color"]]],
        zmin=0, zmax=float(p.values.max()), text=[[f"{v:.0f}%" for v in row] for row in p.values],
        texttemplate="%{text}", textfont=dict(size=13), xgap=3, ygap=3, showscale=False,
        hovertemplate="%{y} · %{x}: %{z:.0f}%<extra></extra>"))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    plot(style(fig, height=280, hover="closest"), "연상속성")
    fig = go.Figure(go.Bar(x=gap_attr.values, y=gap_attr.index, orientation="h",
                           marker_color=[T["color"] if v >= 0 else "#c3c2b7" for v in gap_attr.values],
                           text=[f"{v:+.0f}%p" for v in gap_attr.values], textposition="outside",
                           hovertemplate="%{y}: %{x:+.1f}%p<extra></extra>"))
    fig.add_vline(x=0, line_color=INK2, line_width=1)
    plot(style(fig, height=300, x_title="경쟁사 평균 대비 언급률 차이 (%p)", hover="closest"), "속성차이")
    source(f"{SRC_NEWS} · 속성 사전 단어가 제목·요약에 있으면 언급으로 집계 · 브랜드색 = 강한 연상, 회색 = 약한 연상")

    kw = D["kw"]
    sub = kw[(kw["구분"] == "브랜드") & (kw["그룹"] == focal) & (kw["방식"] == "TF-IDF")].nsmallest(15, "순위").iloc[::-1]
    rival_top = set(kw[(kw["구분"] == "브랜드") & (kw["그룹"].isin(rivals)) & (kw["방식"] == "TF-IDF")
                       & (kw["순위"] <= 15)]["키워드"])
    own = [w for w in sub["키워드"][::-1] if w not in rival_top]
    headline("차별 키워드 (TF-IDF)", f"{focal}만의 키워드: {', '.join(own[:4])}")
    c1, c2 = st.columns(2)
    fig = go.Figure(go.Bar(x=sub["점수"], y=sub["키워드"], orientation="h",
                           marker_color=[T["color"] if w not in rival_top else "#c3c2b7" for w in sub["키워드"]],
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    with c1:
        plot(style(fig, height=440, x_title="평균 TF-IDF", hover="closest"), "차별키워드")
    with c2:
        img = WC / f"브랜드_{focal}_TF-IDF.png"
        if img.exists():
            st.image(str(img), caption=f"{focal} TF-IDF 워드클라우드")
    source(f"{SRC_NEWS} · 브랜드색 = 경쟁사 상위 15개에 없는 키워드, 회색 = 경쟁사와 겹치는 키워드")


# ============================ ⑤ 타깃 ==========================================
def sec_target():
    si = D["segidx"]
    strong = [safe(x) for x in si.loc[si[focal] >= 120, "세그먼트"]]
    weak = [safe(x) for x in si.loc[si[focal] <= 80, "세그먼트"]]
    headline("⑤ 타깃 · 세그먼트 점유율 지수 (전체 점유율 = 100)",
             f"{focal} 강세 타깃 {', '.join(strong) if strong else '없음'} / 약세 타깃 {', '.join(weak) if weak else '없음'}")
    labels = si["세그먼트"].tolist()
    z = si[BRANDS].T.values
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=BRANDS, zmin=40, zmax=260,
        colorscale=[[0, "#c3c2b7"], [0.27, "#f0efec"], [1, T["color"]]],
        text=[[str(v) for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=13),
        xgap=3, ygap=3, showscale=False, hovertemplate="%{y} · %{x}: 지수 %{z}<extra></extra>"))
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    plot(style(fig, height=260, hover="closest"), "세그먼트지수")
    c1, c2 = st.columns(2)
    c1.success(f"**강세 타깃 (지수 120 이상):** {', '.join(strong) if strong else '없음'}")
    c2.warning(f"**약세 타깃 (지수 80 이하):** {', '.join(weak) if weak else '없음'}")
    source(f"{SRC_SEARCH} 연령·성별·기기별 2025.11–2026.10 · 지수 = 세그먼트 안 점유율 ÷ 전체 점유율 × 100")

    seg = D["seg"]
    order = seg["세그먼트"].tolist()[::-1]
    headline("세그먼트별 검색 점유율", "막대 테두리 = 기준 브랜드")
    fig = go.Figure()
    for b in BRANDS:
        s = seg.set_index("세그먼트").loc[order, f"{b} 점유율(%)"]
        fig.add_bar(y=order, x=s, name=b, orientation="h", marker_color=COLOR[b],
                    marker_line=dict(color=INK if b == focal else "white", width=2.5 if b == focal else 2),
                    text=[f"{v:.0f}%" for v in s], textposition="inside",
                    insidetextfont=dict(color=INK if b == "탑텐" else "#ffffff"),
                    hovertemplate=f"%{{y}} · {b}: %{{x:.1f}}%<extra></extra>")
    fig.update_layout(barmode="stack")
    plot(style(fig, height=480, x_title="세그먼트 안 점유율 (%)", hover="closest").update_xaxes(range=[0, 100]),
         "세그먼트점유율")
    source(f"{SRC_SEARCH} · 검색어 트렌드는 요청마다 상대값이라 세그먼트끼리 검색 '규모'는 비교하지 않음")


# ============================ ⑥ 지표 사전 =====================================
def sec_glossary():
    headline("⑥ 지표 사전", "지표 산식 · 데이터 · 판단 기준")
    defs = pd.DataFrame([
        ["검색 점유율 SOS", "브랜드 검색량 ÷ 세 브랜드 검색량 합계 × 100", "검색어 트렌드 월별 (2025.11–2026.10)", "%", "관심도의 시장 내 위치"],
        ["SOS 전년 대비", "최근 12개월 SOS − 직전 12개월 SOS", "검색어 트렌드 월별", "%p", "≤ −1%p 주의"],
        ["검색량 성장률 YoY", "(기간 검색량 ÷ 전년 같은 기간 검색량 − 1) × 100 / 최근 12개월·최근 3개월", "검색어 트렌드 월별", "%", "최근 3개월 < 0 주의"],
        ["보도 점유율 SOV", "공통기간 브랜드 보도량 ÷ 세 브랜드 보도량 × 100 (보도량 = 같은 이슈 보도 수 합계)", "정제 뉴스, 2026.09.22–10.31", "%", "브랜드별 수집 기간이 달라 공통기간만 사용"],
        ["초과 보도 점유율 ESOV", "공통기간 SOV − 같은 기간 SOS", "뉴스 + 주별 검색", "%p", "≤ −5%p 참고 (관심 대비 노출 부족)"],
        ["순감성 지수 NSI", "(긍정 기사 − 부정 기사) ÷ 전체 기사 × 100", "정제 뉴스 50건/브랜드", "−100–100", "규칙 기반 사전"],
        ["보도량 가중 부정 비중", "부정 기사의 보도량 ÷ 전체 보도량 × 100", "정제 뉴스", "%", "≥ 5% 경고"],
        ["행사 의존도", "주별 검색 최고치 ÷ 주별 중앙값", "검색어 트렌드 주별 (최근 12개월)", "배", "≥ 4배 참고"],
        ["연상 속성 언급률", "속성 사전 단어가 제목·요약에 있는 기사 수 ÷ 브랜드 기사 수 × 100", "정제 뉴스", "%", "7개 속성"],
        ["세그먼트 점유율 지수", "세그먼트 안 점유율 ÷ 전체 점유율 × 100", "검색어 트렌드 연령·성별·기기", "지수", "≥120 강세, ≤80 약세"],
        ["계절 지수", "2023–2025 월평균 ÷ 연평균 × 100", "검색어 트렌드 월별", "지수", "100 = 평균"],
    ], columns=["지표", "산식", "데이터·기간", "단위", "판단 기준·비고"])
    st.dataframe(defs, hide_index=True, width="stretch")
    st.markdown(
        "**해석할 때 주의할 점**\n"
        "- **검색어 트렌드는 상대값**입니다. 요청마다 최댓값 = 100으로 맞추므로 같은 요청에 묶인 3사 비교만 유효하고, 세그먼트끼리 규모는 비교할 수 없습니다.\n"
        "- **'탑텐'은 일반어(톱10)와 겹쳐** 검색량이 실제 브랜드 관심보다 크게 잡혔을 수 있습니다.\n"
        "- **뉴스는 브랜드마다 수집 기간이 다릅니다** (유니클로 9월, 스파오 8월, 탑텐 6월부터). 점유율 비교(SOV)는 공통기간만 씁니다.\n"
        "- **감성·연상 속성은 사전 기반 규칙**이라 문맥(예: '가격 인상 철회')을 완전히 반영하지 못합니다. 경보가 뜨면 원문을 확인하세요.\n"
        "- **브랜드 톤앤매너**(색·서체·태그라인)는 분석 결과에서 도출한 해석이며 각 사의 공식 가이드가 아닙니다.")
    if view == "대시보드":
        st.markdown("**갱신 절차** — README의 '데이터 갱신' 9단계를 순서대로 실행한 뒤 대시보드를 다시 엽니다.")


SECTION_FN = {"summary": sec_summary, "search": sec_search, "buzz": sec_buzz, "perception": sec_perception,
              "target": sec_target, "glossary": sec_glossary}


# ---- 내보내기 (보고용) ------------------------------------------------------------
def report_markdown():
    lines = [f"# {focal} 경쟁 모니터링 요약 보고", "",
             f"- 기준일: {AS_OF} · 경쟁사: {', '.join(rivals)}",
             f"- 데이터: {SRC_SEARCH}, {SRC_NEWS}", "", "## 핵심 요약", ""]
    lines += [f"- {safe(e)}" for e in EXEC]
    lines += ["", "## 경보", ""]
    lines += [f"- {STATUS_ICON[l]} {l} · {n} {v} — {m} ({w})" for l, n, v, m, w in ALERTS] or ["- ✅ 기준을 넘은 지표 없음"]
    cols = ["검색 점유율 SOS(최근12개월,%)", "SOS 전년 대비(%p)", "검색량 성장률 YoY(최근3개월,%)",
            "공통기간 보도 점유율 SOV(%)", "초과 보도 점유율 ESOV(%p)", "순감성 지수 NSI", "보도량 가중 부정 비중(%)",
            "행사 의존도(주별 최고/중앙값)"]
    lines += ["", "## 3사 스코어카드", "", "| 브랜드 | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for b in BRANDS:
        lines.append(f"| {'**' + b + '**' if b == focal else b} | " + " | ".join(f"{kpi.loc[b, c]:g}" for c in cols) + " |")
    si = D["segidx"]
    lines += ["", "## 리스크 기사", ""]
    risk = news[(news["브랜드"] == focal) & (news["감성"] == "부정")].sort_values("같은 이슈 보도 수", ascending=False)
    lines += [f"- {r['날짜']:%Y-%m-%d} {r['제목']} (보도 {r['같은 이슈 보도 수']}건) {r['원문 링크']}" for _, r in risk.iterrows()] \
        or ["- 없음"]
    lines += ["", "## 타깃", "",
              f"- 강세(지수 ≥120): {', '.join(si.loc[si[focal] >= 120, '세그먼트']) or '없음'}",
              f"- 약세(지수 ≤80): {', '.join(si.loc[si[focal] <= 80, '세그먼트']) or '없음'}", "",
              "_지표 정의와 한계는 대시보드 ⑥ 지표 사전 참고. 감성·속성은 사전 기반 규칙, 검색량은 상대값._"]
    return "\n".join(lines)


st.sidebar.markdown("### 보고용 내보내기")
st.sidebar.download_button("📝 요약 보고서 (.md)", report_markdown().encode("utf-8"),
                           file_name=f"{focal}_경쟁모니터링_{AS_OF}.md", mime="text/markdown", width="stretch")
st.sidebar.download_button("📊 3사 스코어카드 (.csv)", kpi.to_csv(encoding="utf-8-sig").encode("utf-8-sig"),
                           file_name=f"SPA3사_스코어카드_{AS_OF}.csv", mime="text/csv", width="stretch")
st.sidebar.download_button(f"📰 {focal} 기사 분석 (.csv)",
                           news[news["브랜드"] == focal].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                           file_name=f"{focal}_기사분석_{AS_OF}.csv", mime="text/csv", width="stretch")
st.sidebar.caption("차트는 마우스를 올리면 오른쪽 위 📷 버튼으로 PNG 저장. 보고서 모드에서 Ctrl+P로 PDF 저장. "
                   "주소창 링크를 복사하면 같은 브랜드·모드·기간 화면이 열립니다.")
st.sidebar.caption(f"데이터 기준일 {AS_OF} · 네이버 API HUB")

# ---- 헤더 (기준 브랜드 톤) -------------------------------------------------------
chips = "".join(f'<span class="chip solid">{t}</span>' for t in T["tone"]) + \
        "".join(f'<span class="chip">#{w}</span>' for w in T["keywords"])
title = "경쟁 모니터링 보고서" if view == "보고서" else "경쟁 모니터링 대시보드"
st.markdown(f'<div class="hero"><div class="name">{focal} · {title}</div><div class="tag">{T["tagline"]}</div>{chips}'
            f'<div class="voice">톤앤매너 · {T["voice"]}</div></div>', unsafe_allow_html=True)
st.markdown(f'<div class="meta">기준일 {AS_OF} · 경쟁사 {", ".join(rivals)} · 검색 2016.01–2026.10, 뉴스 정제 150건 · '
            f'톤앤매너는 분석에서 도출한 해석입니다</div>', unsafe_allow_html=True)

# ---- 본문 ---------------------------------------------------------------------
if view == "대시보드":
    tabs = st.tabs([label for _, label in SECTIONS])
    for tab, (key, _) in zip(tabs, SECTIONS):
        with tab:
            SECTION_FN[key]()
else:
    toc = "".join(f'<a href="#{key}">{label}</a>' for key, label in SECTIONS)
    st.markdown(f'<div class="toc no-print">{toc}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sec first">핵심 요약</div>', unsafe_allow_html=True)
    st.markdown('<div class="exec">' + "".join(f"<p>• {e}</p>" for e in
                                               [x.replace("**", "<b>", 1).replace("**", "</b>", 1) for x in EXEC])
                + "</div>", unsafe_allow_html=True)
    for key, label in SECTIONS:
        # 인쇄 시 '핵심 요약'과 '① 요약·경보'는 첫 장에 함께, 나머지 섹션은 새 페이지에서 시작
        cls = "sec first" if key == "summary" else "sec"
        st.markdown(f'<div class="{cls}" id="{key}">{label}</div>', unsafe_allow_html=True)
        SECTION_FN[key]()
