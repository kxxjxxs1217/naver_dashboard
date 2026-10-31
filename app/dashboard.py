"""SPA 3사 경쟁 모니터링 대시보드 (브랜드 마케터용).

실행: python -m streamlit run app/dashboard.py
입력: data/processed/ (src/ 스크립트 결과), reports/figures/wordcloud/
흐름: ① 요약·경보 → ② 관심도(검색) → ③ 화제성(뉴스) → ④ 브랜드 인식(자연어) → ⑤ 타깃 → ⑥ 지표 사전
'기준 브랜드'를 고르면 화면의 강조색·서체·카피가 그 브랜드 톤앤매너로 바뀌고, 나머지는 경쟁사로 비교된다.
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
    ("검색량 성장률 YoY(최근3개월,%)", lambda v: v < 0, "주의", "최근 3개월 검색량이 전년보다 줄었습니다"),
    ("SOS 전년 대비(%p)", lambda v: v <= -1, "주의", "검색 점유율이 1년 새 1%p 이상 빠졌습니다"),
    ("초과 보도 점유율 ESOV(%p)", lambda v: v <= -5, "참고", "검색 관심에 비해 보도 노출이 적습니다"),
    ("보도량 가중 부정 비중(%)", lambda v: v >= 5, "경고", "부정 이슈 보도가 보도량의 5% 이상입니다"),
    ("행사 의존도(주별 최고/중앙값)", lambda v: v >= 4, "참고", "검색 관심이 특정 행사 주간에 몰려 있습니다"),
]
STATUS_ICON = {"경고": "🔴", "주의": "🟠", "참고": "🔵", "양호": "✅"}

st.set_page_config(page_title="SPA 3사 경쟁 모니터링", page_icon="📊", layout="wide")


@st.cache_data
def load():
    d = {"kpi": pd.read_csv(PROC / "마케팅_브랜드지표.csv", encoding="utf-8-sig").set_index("브랜드"),
         "news": pd.read_csv(PROC / "마케팅_기사분석.csv", encoding="utf-8-sig", parse_dates=["날짜"]),
         "profile": pd.read_csv(PROC / "마케팅_속성프로필.csv", encoding="utf-8-sig").set_index("브랜드"),
         "share_m": pd.read_csv(PROC / "마케팅_월별검색점유율.csv", encoding="utf-8-sig", parse_dates=["월"]),
         "segidx": pd.read_csv(PROC / "마케팅_세그먼트인덱스.csv", encoding="utf-8-sig"),
         "seg": pd.read_csv(PROC / "검색트렌드_세그먼트_점유율.csv", encoding="utf-8-sig"),
         "monthly": pd.read_csv(PROC / "검색트렌드_월별.csv", encoding="utf-8-sig", parse_dates=["월"]),
         "weekly": pd.read_csv(PROC / "검색트렌드_주별.csv", encoding="utf-8-sig", parse_dates=["주 시작일"]),
         "kw": pd.read_csv(PROC / "SPA_키워드_BoW_TFIDF.csv", encoding="utf-8-sig")}
    return d


D = load()
kpi, news = D["kpi"], D["news"]

# ---- 사이드바: 기준 브랜드 ------------------------------------------------------
st.sidebar.markdown("### 기준 브랜드")
focal = st.sidebar.radio("우리 브랜드", BRANDS, label_visibility="collapsed")
rivals = [b for b in BRANDS if b != focal]
T = THEME[focal]
st.sidebar.markdown(f"경쟁사: **{' · '.join(rivals)}**")
st.sidebar.divider()
st.sidebar.markdown("**모니터링 순서**\n\n① 요약·경보 → ② 관심도 → ③ 화제성 → ④ 브랜드 인식 → ⑤ 타깃\n\n"
                    "지표 뜻은 ⑥ 지표 사전에 있습니다.")
st.sidebar.caption("데이터: 네이버 API HUB 뉴스 검색·검색어 트렌드 · 2026-10-31 수집")

# ---- 브랜드 톤앤매너 스타일 ----------------------------------------------------
fonts = "family=Noto+Sans+KR:wght@400;500;700&family=" + T["font"].replace(" ", "+") + f":wght@{T['weight']}"
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?{fonts}&display=swap');
html, body, p, li, label, input, textarea, .stMarkdown, [data-testid="stCaptionContainer"] {{ font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif; }}
[data-testid="stIconMaterial"] {{ font-family: 'Material Symbols Rounded' !important; }}
[data-baseweb="radio"] [aria-checked="true"] + div, [data-baseweb="radio"] input:checked + div {{ background-color: {T["color"]} !important; border-color: {T["color"]} !important; }}
h1, h2, h3, .brand-font {{ font-family: '{T["font"]}', 'Noto Sans KR', sans-serif !important; font-weight: {T["weight"]}; }}
.hero {{ background: {T["tint"]}; border-left: 8px solid {T["color"]}; border-radius: 6px; padding: 18px 24px; margin-bottom: 8px; }}
.hero .name {{ font-family: '{T["font"]}', sans-serif; font-size: 34px; font-weight: {T["weight"]}; color: {INK}; line-height: 1.2; }}
.hero .tag {{ font-size: 16px; color: {INK2}; margin-top: 4px; }}
.chip {{ display: inline-block; border: 1px solid {T["color"]}; color: {INK}; background: #ffffff; border-radius: 4px;
        padding: 2px 10px; margin: 8px 6px 0 0; font-size: 13px; }}
.chip.solid {{ background: {T["color"]}; color: #ffffff; }}
.kcard {{ background: #ffffff; border: 1px solid {GRID}; border-top: 4px solid {T["color"]}; border-radius: 6px; padding: 12px 14px; min-height: 128px; }}
.kcard .lab {{ font-size: 13px; color: {INK2}; }}
.kcard .val {{ font-size: 28px; font-weight: 700; color: {INK}; margin: 2px 0; }}
.kcard .cmp {{ font-size: 12.5px; color: {INK2}; }}
.stTabs [aria-selected="true"] {{ color: {INK} !important; border-bottom-color: {T["color"]} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {T["color"]} !important; }}
.voice {{ font-size: 13px; color: {MUTED}; }}
</style>""", unsafe_allow_html=True)


def style(fig, height=400, y_title=None, x_title=None, hover="x unified", dates=False):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=36, b=10), plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
                      font=dict(family="Noto Sans KR, Malgun Gothic, sans-serif", color=INK2, size=13),
                      legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center", traceorder="normal"),
                      hoverlabel=dict(bgcolor="white", font_color=INK), hovermode=hover)
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED), title=x_title)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), title=y_title)
    if dates:
        fig.update_xaxes(tickformat="%y.%m", hoverformat="%Y-%m-%d")
    return fig


def width_for(b):
    return 3 if b == focal else 1.6


def opacity_for(b):
    return 1.0 if b == focal else 0.55


def rank(col, higher_better=True):
    s = kpi[col].sort_values(ascending=not higher_better)
    return list(s.index).index(focal) + 1


def card(col, label, value, compare):
    col.markdown(f'<div class="kcard"><div class="lab">{label}</div><div class="val">{value}</div>'
                 f'<div class="cmp">{compare}</div></div>', unsafe_allow_html=True)


def plot(fig, **kw):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, **kw)


# ---- 헤더 (기준 브랜드 톤) -------------------------------------------------------
chips = "".join(f'<span class="chip solid">{t}</span>' for t in T["tone"]) + \
        "".join(f'<span class="chip">#{k}</span>' for k in T["keywords"])
st.markdown(f'<div class="hero"><div class="name">{focal}</div><div class="tag">{T["tagline"]}</div>{chips}'
            f'<div class="voice" style="margin-top:8px">톤앤매너 · {T["voice"]}</div></div>', unsafe_allow_html=True)
st.caption("SPA 3사 경쟁 모니터링 · 브랜드 톤(색·서체·태그라인)은 뉴스 키워드와 연상 속성 분석에서 도출한 해석입니다.")

tabs = st.tabs(["① 요약·경보", "② 관심도 (검색)", "③ 화제성 (뉴스)", "④ 브랜드 인식", "⑤ 타깃", "⑥ 지표 사전"])

# ============================ ① 요약·경보 ======================================
with tabs[0]:
    k = kpi.loc[focal]
    st.markdown(f"#### {focal} 핵심 지표 — 경쟁사 대비")
    c = st.columns(4)
    lead = kpi["검색 점유율 SOS(최근12개월,%)"].drop(focal).idxmax()
    card(c[0], "검색 점유율 SOS · 최근 12개월", f"{k['검색 점유율 SOS(최근12개월,%)']:.1f}%",
         f"3사 중 {rank('검색 점유율 SOS(최근12개월,%)')}위 · 전년 대비 {k['SOS 전년 대비(%p)']:+.1f}%p")
    card(c[1], "검색량 성장률 YoY · 최근 3개월", f"{k['검색량 성장률 YoY(최근3개월,%)']:+.1f}%",
         f"12개월 기준 {k['검색량 성장률 YoY(최근12개월,%)']:+.1f}% · 3사 중 {rank('검색량 성장률 YoY(최근3개월,%)')}위")
    card(c[2], "보도 점유율 SOV · 공통기간", f"{k['공통기간 보도 점유율 SOV(%)']:.1f}%",
         f"ESOV {k['초과 보도 점유율 ESOV(%p)']:+.1f}%p (SOV − 같은 기간 SOS)")
    card(c[3], "순감성 지수 NSI", f"{k['순감성 지수 NSI']:+.0f}",
         f"부정 기사 {k['부정 기사 비중(%)']:.0f}% · 보도량 가중 {k['보도량 가중 부정 비중(%)']:.1f}%")

    st.markdown("#### 경보")
    alerts = []
    for col, cond, level, msg in RULES:
        v = k[col]
        if cond(v):
            unit = "%p" if "%p" in col else ("배" if "배" in col or "의존도" in col else "%")
            val = f"{v:+.1f}{unit}" if unit == "%p" or "YoY" in col else f"{v:.1f}{unit}"
            alerts.append((level, f"**{col.split('(')[0].strip()}** {val} — {msg}"))
    order = {"경고": 0, "주의": 1, "참고": 2}
    if not alerts:
        st.success("✅ 양호 — 기준을 넘은 지표가 없습니다.")
    for level, msg in sorted(alerts, key=lambda a: order[a[0]]):
        box = {"경고": st.error, "주의": st.warning, "참고": st.info}[level]
        box(f"{STATUS_ICON[level]} {level} · {msg}")

    st.markdown("#### 3사 스코어카드")
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
    st.caption("▶ = 기준 브랜드. 열 이름에 마우스를 올리면 산식이 보입니다. 전체 정의는 ⑥ 지표 사전에 있습니다.")

    st.markdown("#### 이번 점검의 핵심")
    best_yoy = kpi["검색량 성장률 YoY(최근3개월,%)"].idxmax()
    top_attr = D["profile"].loc[focal].sort_values(ascending=False)
    gap_attr = (D["profile"].loc[focal] - D["profile"].drop(focal).max()).sort_values()
    st.markdown(
        f"- **관심도:** 3사 검색 1위는 유니클로(점유율 {kpi.loc['유니클로', '검색 점유율 SOS(최근12개월,%)']:.0f}%)이고, "
        f"최근 3개월 성장은 **{best_yoy}**({kpi.loc[best_yoy, '검색량 성장률 YoY(최근3개월,%)']:+.0f}%)가 가장 빠릅니다.\n"
        f"- **{focal}의 강점 연상:** {top_attr.index[0]}({top_attr.iloc[0]:.0f}%), {top_attr.index[1]}({top_attr.iloc[1]:.0f}%) "
        f"— 경쟁사 최고치보다 가장 뒤처진 속성은 **{gap_attr.index[0]}**({gap_attr.iloc[0]:+.0f}%p)입니다.\n"
        f"- **리스크:** 부정 기사 {int((news[(news['브랜드'] == focal)]['감성'] == '부정').sum())}건 — ③ 화제성 탭에서 원문을 확인하세요.")

# ============================ ② 관심도 ========================================
with tabs[1]:
    st.markdown("#### 검색 점유율(SOS) 추이 — 최근 24개월")
    sm = D["share_m"]
    fig = go.Figure()
    for b in BRANDS:
        fig.add_scatter(x=sm["월"], y=sm[b], name=b, mode="lines+markers",
                        line=dict(color=COLOR[b], width=width_for(b)), opacity=opacity_for(b),
                        marker=dict(size=7 if b == focal else 5, line=dict(color="white", width=1.5)),
                        hovertemplate=f"{b}: %{{y:.1f}}%<extra></extra>")
    plot(style(fig, y_title="세 브랜드 중 검색 점유율 (%)", dates=True))
    st.caption("SOS = 그 달 세 브랜드 검색량 합계 중 해당 브랜드 비중. 굵은 선이 기준 브랜드입니다.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 검색 모멘텀 — 전년 대비 성장률")
        yoy = kpi[["검색량 성장률 YoY(최근12개월,%)", "검색량 성장률 YoY(최근3개월,%)"]]
        fig = go.Figure()
        for lab, col, op in [("최근 12개월", yoy.columns[0], 0.45), ("최근 3개월", yoy.columns[1], 1.0)]:
            fig.add_bar(x=BRANDS, y=yoy.loc[BRANDS, col], name=lab, opacity=op,
                        marker_color=[COLOR[b] for b in BRANDS], marker_line=dict(color="white", width=2),
                        text=[f"{v:+.0f}%" for v in yoy.loc[BRANDS, col]], textposition="outside",
                        hovertemplate=f"%{{x}} · {lab}: %{{y:+.1f}}%<extra></extra>")
        fig.add_hline(y=0, line_color=INK2, line_width=1)
        fig.update_layout(barmode="group", showlegend=False)
        plot(style(fig, height=360, y_title="YoY (%)", hover="closest"))
        st.caption("연한 막대 = 최근 12개월(2025.11–2026.10) vs 직전 12개월, 진한 막대 = 최근 3개월(8–10월) vs 전년 같은 달.")
    with c2:
        st.markdown("#### 계절성 — 언제 관심이 몰리나")
        m = D["monthly"][D["monthly"]["월"].dt.year.between(2023, 2025)]
        season = m.groupby(m["월"].dt.month)[BRANDS].mean()
        season = season / season.mean() * 100
        fig = go.Figure()
        for b in BRANDS:
            fig.add_scatter(x=[f"{i}월" for i in season.index], y=season[b], name=b, mode="lines+markers",
                            line=dict(color=COLOR[b], width=width_for(b)), opacity=opacity_for(b),
                            marker=dict(size=7, line=dict(color="white", width=1.5)),
                            hovertemplate=f"{b}: %{{y:.0f}}<extra></extra>")
        fig.add_hline(y=100, line_color=GRID)
        plot(style(fig, height=360, y_title="계절 지수 (연평균 = 100)"))
        st.caption("2023–2025년 월평균 / 연평균 × 100. 탑텐은 10월(하반기 텐텐데이), 유니클로·스파오는 11월 정점.")

    st.markdown("#### 최근 12개월 주별 검색 — 행사 의존도")
    wk = D["weekly"]
    fig = go.Figure()
    for b in BRANDS:
        fig.add_scatter(x=wk["주 시작일"], y=wk[b], name=f"{b} (최고/중앙값 {kpi.loc[b, '행사 의존도(주별 최고/중앙값)']:.1f}배)",
                        mode="lines", line=dict(color=COLOR[b], width=width_for(b)), opacity=opacity_for(b),
                        hovertemplate=f"{b}: %{{y:.1f}}<extra></extra>")
    plot(style(fig, height=380, y_title="상대 검색량 (기간 최댓값 = 100)", dates=True))
    st.caption("행사 의존도 = 주별 최고치 ÷ 주별 중앙값. 높을수록 평소 관심은 낮고 특정 주간(행사·출시)에 몰립니다. 4배 이상이면 '참고' 경보.")

    with st.expander("장기 추이 (2016–2026) 보기"):
        mo = D["monthly"]
        fig = go.Figure()
        for b in BRANDS:
            fig.add_scatter(x=mo["월"], y=mo[b], name=b, mode="lines", line=dict(color=COLOR[b], width=width_for(b)),
                            opacity=opacity_for(b), hovertemplate=f"{b}: %{{y:.1f}}<extra></extra>")
        fig.add_vline(x=pd.Timestamp("2019-07-01").value / 1e6, line_dash="dash", line_color=MUTED)
        fig.add_annotation(x=pd.Timestamp("2019-07-01"), y=98, text="2019.07 불매운동", showarrow=False,
                           xanchor="left", font=dict(color=INK2))
        plot(style(fig, height=360, y_title="상대 검색량 (최댓값 = 100)", dates=True))

# ============================ ③ 화제성 ========================================
with tabs[2]:
    k = kpi.loc[focal]
    st.markdown("#### 보도 점유율(SOV) vs 검색 점유율(SOS) — 공통기간 2026.09.22–10.31")
    fig = go.Figure()
    for lab, col, op in [("검색 점유율 SOS", "공통기간 SOS(%)", 0.45), ("보도 점유율 SOV", "공통기간 보도 점유율 SOV(%)", 1.0)]:
        fig.add_bar(x=BRANDS, y=kpi.loc[BRANDS, col], name=lab, opacity=op, marker_color=[COLOR[b] for b in BRANDS],
                    marker_line=dict(color="white", width=2), text=[f"{v:.0f}%" for v in kpi.loc[BRANDS, col]],
                    textposition="outside", hovertemplate=f"%{{x}} · {lab}: %{{y:.1f}}%<extra></extra>")
    fig.update_layout(barmode="group", showlegend=False)
    plot(style(fig, height=360, y_title="점유율 (%)", hover="closest"))
    st.caption("연한 막대 = 검색 점유율(SOS), 진한 막대 = 보도 점유율(SOV). "
               "SOV = 공통기간 세 브랜드 보도량(같은 이슈 보도 수 합계) 중 비중. ESOV = SOV − SOS. "
               f"{focal} ESOV {k['초과 보도 점유율 ESOV(%p)']:+.1f}%p — 양수면 관심 대비 보도 노출이 많고, 음수면 적습니다.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 보도 주제 구성 (보도량 비중 %)")
        agg = news.groupby(["브랜드", "주제"])["같은 이슈 보도 수"].sum().unstack(fill_value=0)
        agg = agg.div(agg.sum(axis=1), axis=0).mul(100).reindex(BRANDS[::-1])
        fig = go.Figure()
        for t in TOPICS:
            fig.add_bar(y=agg.index, x=agg[t], name=t, orientation="h", marker_color=TOPIC_COLOR[t],
                        marker_line=dict(color="white", width=2),
                        text=[f"{v:.0f}%" if v >= 7 else "" for v in agg[t]], textposition="inside",
                        insidetextfont=dict(color="#0b0b0b" if t in ("실적·사업", "기타") else "#ffffff"),
                        hovertemplate=f"%{{y}} · {t}: %{{x:.1f}}%<extra></extra>")
        fig.update_layout(barmode="stack")
        plot(style(fig, height=320, hover="closest"))
    with c2:
        st.markdown("#### 보도 감성 분포 (기사 비중 %)")
        sent = news.groupby(["브랜드", "감성"]).size().unstack(fill_value=0).reindex(BRANDS[::-1])
        sent = sent.div(sent.sum(axis=1), axis=0).mul(100)
        fig = go.Figure()
        for s in ["긍정", "중립", "부정"]:
            fig.add_bar(y=sent.index, x=sent[s], name=s, orientation="h", marker_color=SENT_COLOR[s],
                        marker_line=dict(color="white", width=2), text=[f"{v:.0f}%" if v >= 7 else "" for v in sent[s]],
                        textposition="inside", insidetextfont=dict(color=INK if s == "중립" else "#ffffff"),
                        hovertemplate=f"%{{y}} · {s}: %{{x:.1f}}%<extra></extra>")
        fig.update_layout(barmode="stack")
        plot(style(fig, height=320, hover="closest"))
    st.caption("감성은 제목·요약의 긍정어(증가·돌파·인기·품절 등)와 부정어(철회·반발·해킹·폐점 등) 개수 차이로 판정한 규칙 기반 결과입니다. "
               "NSI = (긍정 − 부정) 기사 수 ÷ 전체 × 100.")

    st.markdown(f"#### 🔎 {focal} 리스크·이슈 기사")
    risk = news[(news["브랜드"] == focal) & (news["감성"] == "부정")].sort_values("같은 이슈 보도 수", ascending=False)
    if risk.empty:
        st.success("부정으로 분류된 기사가 없습니다.")
    else:
        st.dataframe(risk[["날짜", "제목", "부정어", "같은 이슈 보도 수", "원문 링크"]], hide_index=True, width="stretch",
                     column_config={"날짜": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                    "원문 링크": st.column_config.LinkColumn(display_text="원문"),
                                    "같은 이슈 보도 수": st.column_config.NumberColumn("보도 수")})

    with st.expander(f"{focal} 전체 기사 보기"):
        q = st.text_input("제목·요약 검색", "")
        tbl = news[news["브랜드"] == focal]
        if q:
            tbl = tbl[tbl["제목"].str.contains(q, case=False) | tbl["요약"].str.contains(q, case=False)]
        st.dataframe(tbl.sort_values("같은 이슈 보도 수", ascending=False)[
                         ["날짜", "주제", "감성", "제목", "같은 이슈 보도 수", "원문 링크"]],
                     hide_index=True, width="stretch", height=380,
                     column_config={"날짜": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                    "원문 링크": st.column_config.LinkColumn(display_text="원문"),
                                    "같은 이슈 보도 수": st.column_config.NumberColumn("보도 수")})

# ============================ ④ 브랜드 인식 =====================================
with tabs[3]:
    st.markdown("#### 브랜드 연상 속성 — 기사에서 함께 언급된 비율")
    prof = D["profile"].reindex(BRANDS)
    attrs = list(prof.columns)
    tint = T["tint"]
    fig = go.Figure(go.Heatmap(
        z=prof.values, x=attrs, y=BRANDS, colorscale=[[0, "#fcfcfb"], [0.35, tint], [1, T["color"]]],
        zmin=0, zmax=float(prof.values.max()), text=[[f"{v:.0f}%" for v in row] for row in prof.values],
        texttemplate="%{text}", textfont=dict(size=13), xgap=3, ygap=3, showscale=False,
        hovertemplate="%{y} · %{x}: %{z:.0f}%<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    plot(style(fig, height=300, hover="closest").update_yaxes(gridcolor="rgba(0,0,0,0)"))
    gap = (prof.loc[focal] - prof.drop(focal).mean()).sort_values()
    fig = go.Figure(go.Bar(x=gap.values, y=gap.index, orientation="h",
                           marker_color=[T["color"] if v >= 0 else "#c3c2b7" for v in gap.values],
                           text=[f"{v:+.0f}%p" for v in gap.values], textposition="outside",
                           hovertemplate="%{y}: %{x:+.1f}%p<extra></extra>"))
    fig.add_vline(x=0, line_color=INK2, line_width=1)
    st.markdown(f"#### {focal} vs 경쟁사 평균 — 속성별 차이")
    plot(style(fig, height=330, x_title="언급률 차이 (%p)", hover="closest"))
    st.caption("속성 사전(가격·가성비: 가격·할인·반값… / 협업·IP: 협업·콜라보·캐릭터… 등)의 단어가 제목·요약에 하나라도 있으면 그 속성 언급으로 셉니다. "
               "브랜드색 막대는 경쟁사보다 강한 연상, 회색은 약한 연상입니다.")

    st.markdown(f"#### {focal} 특징 키워드 (TF-IDF) — 경쟁사와 무엇이 다른가")
    c1, c2 = st.columns([1, 1])
    kw = D["kw"]
    sub = kw[(kw["구분"] == "브랜드") & (kw["그룹"] == focal) & (kw["방식"] == "TF-IDF")].nsmallest(15, "순위").iloc[::-1]
    rival_top = set(kw[(kw["구분"] == "브랜드") & (kw["그룹"].isin(rivals)) & (kw["방식"] == "TF-IDF")
                       & (kw["순위"] <= 15)]["키워드"])
    fig = go.Figure(go.Bar(x=sub["점수"], y=sub["키워드"], orientation="h",
                           marker_color=[T["color"] if w not in rival_top else "#c3c2b7" for w in sub["키워드"]],
                           hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
    with c1:
        plot(style(fig, height=470, x_title="평균 TF-IDF", hover="closest"))
        st.caption("브랜드색 = 경쟁사 상위 15개에 없는 우리만의 키워드, 회색 = 경쟁사와 겹치는 키워드.")
    with c2:
        img = WC / f"브랜드_{focal}_TF-IDF.png"
        if img.exists():
            st.image(str(img), caption=f"{focal} TF-IDF 워드클라우드")

# ============================ ⑤ 타깃 ==========================================
with tabs[4]:
    st.markdown("#### 세그먼트 점유율 지수 — 전체 점유율 = 100")
    si = D["segidx"]
    labels = si["세그먼트"].tolist()
    z = si[BRANDS].T.values
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=BRANDS, zmid=100, zmin=40, zmax=260,
        colorscale=[[0, "#c3c2b7"], [0.27, "#f0efec"], [0.27, "#f0efec"], [1, T["color"]]],
        text=[[str(v) for v in row] for row in z], texttemplate="%{text}", textfont=dict(size=13),
        xgap=3, ygap=3, showscale=False, hovertemplate="%{y} · %{x}: 지수 %{z}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    plot(style(fig, height=280, hover="closest").update_yaxes(gridcolor="rgba(0,0,0,0)"))
    # 마크다운에서 '~'는 취소선이 되므로 세그먼트명의 물결표를 대시로 바꿔 표시
    strong = [x.replace("~", "–") for x in si.loc[si[focal] >= 120, "세그먼트"]]
    weak = [x.replace("~", "–") for x in si.loc[si[focal] <= 80, "세그먼트"]]
    c1, c2 = st.columns(2)
    c1.success(f"**강세 타깃 (지수 120 이상):** {', '.join(strong) if strong else '없음'}")
    c2.warning(f"**약세 타깃 (지수 80 이하):** {', '.join(weak) if weak else '없음'}")
    st.caption("지수 = (세그먼트 안 점유율 ÷ 전체 점유율) × 100. 120 이상은 그 세그먼트에서 평균보다 강하고, 80 이하는 약합니다. "
               "검색어 트렌드는 요청마다 상대값이라 세그먼트끼리 검색 '규모'는 비교하지 않습니다.")

    st.markdown("#### 세그먼트별 검색 점유율")
    seg = D["seg"]
    order = seg["세그먼트"].tolist()[::-1]
    fig = go.Figure()
    for b in BRANDS:
        s = seg.set_index("세그먼트").loc[order, f"{b} 점유율(%)"]
        fig.add_bar(y=order, x=s, name=b, orientation="h", marker_color=COLOR[b],
                    marker_line=dict(color=INK if b == focal else "white", width=2.5 if b == focal else 2),
                    text=[f"{v:.0f}%" for v in s], textposition="inside",
                    insidetextfont=dict(color=INK if b == "탑텐" else "#ffffff"),
                    hovertemplate=f"%{{y}} · {b}: %{{x:.1f}}%<extra></extra>")
    fig.update_layout(barmode="stack")
    plot(style(fig, height=520, x_title="세그먼트 안 점유율 (%)", hover="closest").update_xaxes(range=[0, 100]))

# ============================ ⑥ 지표 사전 =====================================
with tabs[5]:
    st.markdown("#### 지표 정의")
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

    st.markdown("#### 해석할 때 주의할 점")
    st.markdown(
        "- **검색어 트렌드는 상대값**입니다. 요청마다 최댓값=100으로 맞추므로 같은 요청에 묶인 3사 비교만 유효하고, 세그먼트끼리 규모는 비교할 수 없습니다.\n"
        "- **'탑텐'은 일반어(톱10)와 겹쳐** 검색량이 실제 브랜드 관심보다 크게 잡혔을 수 있습니다.\n"
        "- **뉴스는 브랜드마다 수집 기간이 다릅니다** (유니클로 9월, 스파오 8월, 탑텐 6월부터). 점유율 비교(SOV)는 공통기간만 씁니다.\n"
        "- **감성·연상 속성은 사전 기반 규칙**이라 문맥(예: '가격 인상 철회')을 완전히 반영하지 못합니다. 경보가 뜨면 원문을 확인하세요.\n"
        "- **브랜드 톤앤매너**(색·서체·태그라인)는 분석 결과에서 도출한 해석이며 각 사의 공식 가이드가 아닙니다.")

    st.markdown("#### 갱신 절차 (src/)")
    st.code("python src/collect_spa_news.py            # 1. 최신 뉴스 수집 (data/raw)\n"
            "python src/build_spa_news_csv.py          # 2. CSV 정리\n"
            "python src/clean_spa_news.py              # 3. 무관·중복 제거 (판단 목록은 수집일 기준, 재검토 필요)\n"
            "python src/build_spa_news_analysis.py     # 4. 브랜드별 50건 분석용 데이터\n"
            "python src/classify_spa_news_topics.py    # 5. 주제 분류\n"
            "python src/keyword_wordcloud.py           # 6. BoW·TF-IDF 키워드, 워드클라우드\n"
            "python src/search_trend_analysis.py       # 7. 검색어 트렌드 (data/raw/search_trend.json 삭제 시 재수집)\n"
            "python src/marketing_metrics.py           # 8. 마케터 지표·감성·연상 속성\n"
            "python -m streamlit run app/dashboard.py  # 9. 대시보드", language="bash")
