"""SPA 3사(유니클로·스파오·탑텐) 뉴스·검색 분석 대시보드.

실행: streamlit run app/dashboard.py
data/processed/ 와 reports/figures/wordcloud/ 의 분석 결과를 읽어서 보여준다.
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
COLOR = {"유니클로": "#2a78d6", "스파오": "#eb6834", "탑텐": "#1baf7a"}
TOPIC_COLOR = {"제품 출시": "#2a78d6", "협업": "#eb6834", "할인·행사": "#1baf7a", "실적·사업": "#eda100",
               "기타": "#898781"}
INK2, MUTED, GRID = "#52514e", "#898781", "#e1e0d9"

st.set_page_config(page_title="SPA 3사 분석 대시보드", page_icon="📊", layout="wide")


@st.cache_data
def load():
    news = pd.read_csv(PROC / "SPA_브랜드_뉴스_주제분류.csv", encoding="utf-8-sig")
    news["날짜"] = pd.to_datetime(news["날짜"])
    kw = pd.read_csv(PROC / "SPA_키워드_BoW_TFIDF.csv", encoding="utf-8-sig")
    monthly = pd.read_csv(PROC / "검색트렌드_월별.csv", encoding="utf-8-sig")
    monthly["월"] = pd.to_datetime(monthly["월"])
    weekly = pd.read_csv(PROC / "검색트렌드_주별.csv", encoding="utf-8-sig")
    weekly["주 시작일"] = pd.to_datetime(weekly["주 시작일"])
    seg = pd.read_csv(PROC / "검색트렌드_세그먼트_점유율.csv", encoding="utf-8-sig")
    return news, kw, monthly, weekly, seg


def style(fig, height=420, y_title=None):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="#fcfcfb",
                      paper_bgcolor="#fcfcfb", font=dict(family="Malgun Gothic, sans-serif", color=INK2),
                      legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center", traceorder="normal"),
                      hoverlabel=dict(bgcolor="white"), hovermode="x unified")
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(color=MUTED), title=y_title)
    return fig


news, kw, monthly, weekly, seg = load()

# ---- 사이드바 ---------------------------------------------------------------
st.sidebar.title("필터")
brands = st.sidebar.multiselect("브랜드", BRANDS, default=BRANDS)
if not brands:
    st.sidebar.warning("브랜드를 하나 이상 고르세요.")
    st.stop()
st.sidebar.caption("데이터: 네이버 API HUB 뉴스 검색·검색어 트렌드 (2026-10-31 수집)")

st.title("SPA 3사 뉴스·검색 분석")
st.caption("유니클로 · 스파오 · 탑텐 — 정제 뉴스 150건, 주제 분류, 키워드, 네이버 검색 추이")

# ---- 핵심 지표 ---------------------------------------------------------------
recent = weekly[BRANDS].sum()
share_recent = recent / recent.sum() * 100
y25 = monthly[monthly["월"].dt.year == 2025][BRANDS].sum()
y24 = monthly[monthly["월"].dt.year == 2024][BRANDS].sum()
cols = st.columns(len(brands))
for col, b in zip(cols, brands):
    nb = news[news["브랜드"] == b]
    top_topic = nb.groupby("주제")["같은 이슈 보도 수"].sum().idxmax()
    col.metric(f"{b} 검색 점유율 (최근 12개월)", f"{share_recent[b]:.0f}%",
               f"2025년 검색량 전년비 {(y25[b] / y24[b] - 1) * 100:+.0f}%", delta_color="off")
    col.caption(f"뉴스 {len(nb)}건 · 보도량 최다 주제: **{top_topic}**")

tab_news, tab_kw, tab_trend, tab_seg = st.tabs(["📰 뉴스 주제", "🔤 키워드", "📈 검색 추이", "👥 연령·성별·기기"])

# ---- 뉴스 주제 ---------------------------------------------------------------
with tab_news:
    measure = st.radio("기준", ["기사 수", "보도량 (같은 이슈 보도 수 합계)"], horizontal=True)
    nf = news[news["브랜드"].isin(brands)]
    if measure == "기사 수":
        agg = nf.groupby(["브랜드", "주제"]).size().rename("값")
    else:
        agg = nf.groupby(["브랜드", "주제"])["같은 이슈 보도 수"].sum().rename("값")
    agg = agg.reset_index()
    fig = go.Figure()
    ys = brands[::-1]  # 가로 막대는 아래부터 그려지므로 뒤집어 유니클로가 위로 오게
    for t in TOPICS:
        d = agg[agg["주제"] == t].set_index("브랜드").reindex(ys).fillna(0)
        fig.add_bar(y=ys, x=d["값"], name=t, orientation="h", marker_color=TOPIC_COLOR[t],
                    marker_line=dict(color="white", width=2), text=d["값"].astype(int), textposition="inside",
                    hovertemplate=f"%{{y}} · {t}: %{{x:,.0f}}<extra></extra>")
    fig.update_layout(barmode="stack", hovermode="closest")
    st.plotly_chart(style(fig, height=110 + 70 * len(brands)), width="stretch")
    st.caption("기사 수는 같은 이슈를 1건으로 묶은 대표 기사 기준, 보도량은 묶기 전 원래 보도 건수 합계입니다. "
               "브랜드마다 기사 기간이 다릅니다 (유니클로 9월, 스파오 8월, 탑텐 6월부터).")

    st.subheader("기사 목록")
    c1, c2 = st.columns([1, 2])
    topics_sel = c1.multiselect("주제", TOPICS, default=TOPICS)
    q = c2.text_input("제목·요약 검색", "")
    table = nf[nf["주제"].isin(topics_sel)]
    if q:
        table = table[table["제목"].str.contains(q, case=False) | table["요약"].str.contains(q, case=False)]
    table = table.sort_values(["같은 이슈 보도 수", "날짜"], ascending=False)
    st.dataframe(
        table[["브랜드", "주제", "날짜", "제목", "같은 이슈 보도 수", "함께 수집된 브랜드", "원문 링크"]],
        width="stretch", hide_index=True, height=420,
        column_config={"날짜": st.column_config.DateColumn(format="YYYY-MM-DD"),
                       "원문 링크": st.column_config.LinkColumn(display_text="열기"),
                       "같은 이슈 보도 수": st.column_config.NumberColumn("보도 수")})
    st.caption(f"{len(table)}건")

# ---- 키워드 ------------------------------------------------------------------
with tab_kw:
    c1, c2, c3 = st.columns([1, 2, 1])
    kind = c1.radio("구분", ["브랜드", "주제"], horizontal=True)
    options = brands if kind == "브랜드" else TOPICS
    group = c2.selectbox("그룹", options)
    n = c3.slider("상위 개수", 5, 30, 15)
    sub = kw[(kw["구분"] == kind) & (kw["그룹"] == group)]
    st.caption(f"{group}: 기사 {int(sub['기사 수'].iloc[0])}건 · BoW는 단어 빈도 합계, "
               "TF-IDF는 기사 150건 기준 기사별 TF-IDF의 그룹 평균입니다.")
    left, right = st.columns(2)
    for col, method in [(left, "BoW"), (right, "TF-IDF")]:
        d = sub[sub["방식"] == method].nsmallest(n, "순위").iloc[::-1]
        other = set(sub[(sub["방식"] != method) & (sub["순위"] <= n)]["키워드"])
        colors = [COLOR.get(group, "#2a78d6") if k in other else "#86b6ef" for k in d["키워드"]]
        fig = go.Figure(go.Bar(x=d["점수"], y=d["키워드"], orientation="h", marker_color=colors,
                               hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
        fig.update_layout(hovermode="closest", title=dict(text=method, font=dict(size=16)))
        col.plotly_chart(style(fig, height=120 + 24 * n), width="stretch")
        img = WC / f"{kind}_{group.replace('·', '_').replace(' ', '')}_{method}.png"
        if img.exists():
            col.image(str(img), caption=f"{group} 워드클라우드 — {method}")
    st.caption("진한 막대 = 두 방식의 상위 목록에 모두 있는 키워드, 연한 막대 = 한 방식에만 있는 키워드")

# ---- 검색 추이 ---------------------------------------------------------------
with tab_trend:
    st.subheader("월별 검색 추이 (2016.01 ~ 2026.10)")
    fig = go.Figure()
    for b in brands:
        fig.add_scatter(x=monthly["월"], y=monthly[b], name=b, mode="lines", line=dict(color=COLOR[b], width=2),
                        hovertemplate=f"{b}: %{{y:.1f}}<extra></extra>")
    fig.add_vline(x=pd.Timestamp("2019-07-01").value / 1e6, line_dash="dash", line_color=MUTED)
    fig.add_annotation(x=pd.Timestamp("2019-07-01"), y=98, text="2019.07 불매운동", showarrow=False,
                       xanchor="left", font=dict(color=INK2))
    st.plotly_chart(style(fig, y_title="상대 검색량 (최댓값=100)"), width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("연도별 검색 점유율")
        yr = monthly.assign(연도=monthly["월"].dt.year).groupby("연도")[BRANDS].sum()
        yr_share = yr.div(yr.sum(axis=1), axis=0) * 100
        fig = go.Figure()
        for b in brands:
            fig.add_bar(x=yr_share.index.astype(str), y=yr_share[b], name=b, marker_color=COLOR[b],
                        marker_line=dict(color="white", width=2), hovertemplate=f"{b}: %{{y:.1f}}%<extra></extra>")
        fig.update_layout(barmode="stack")
        st.plotly_chart(style(fig, height=380, y_title="세 브랜드 중 점유율 (%)"), width="stretch")
        st.caption("점유율은 항상 세 브랜드 합계 기준입니다. 2026년은 1~10월.")
    with c2:
        st.subheader("계절성 (2023~2025 평균)")
        m = monthly[monthly["월"].dt.year.between(2023, 2025)]
        season = m.groupby(m["월"].dt.month)[BRANDS].mean()
        season = season / season.mean() * 100
        fig = go.Figure()
        for b in brands:
            fig.add_scatter(x=[f"{i}월" for i in season.index], y=season[b], name=b, mode="lines+markers",
                            line=dict(color=COLOR[b], width=2), marker=dict(size=8, line=dict(color="white", width=2)),
                            hovertemplate=f"{b}: %{{y:.0f}}<extra></extra>")
        fig.add_hline(y=100, line_color=GRID)
        st.plotly_chart(style(fig, height=380, y_title="계절 지수 (연평균=100)"), width="stretch")
        st.caption("탑텐은 10월(하반기 텐텐데이), 유니클로·스파오는 11월에 정점입니다.")

    st.subheader("최근 12개월 주별 추이")
    fig = go.Figure()
    for b in brands:
        fig.add_scatter(x=weekly["주 시작일"], y=weekly[b], name=b, mode="lines", line=dict(color=COLOR[b], width=2),
                        hovertemplate=f"{b}: %{{y:.1f}}<extra></extra>")
    st.plotly_chart(style(fig, y_title="상대 검색량 (최댓값=100)"), width="stretch")
    st.caption("탑텐 고점은 텐텐데이(10월 하순·5월 하순)와 겹칩니다.")

# ---- 세그먼트 ----------------------------------------------------------------
with tab_seg:
    st.subheader("연령·성별·기기별 검색 점유율 (최근 12개월)")
    order = seg["세그먼트"].tolist()[::-1]
    fig = go.Figure()
    for b in brands:
        s = seg.set_index("세그먼트").loc[order, f"{b} 점유율(%)"]
        fig.add_bar(y=order, x=s, name=b, orientation="h", marker_color=COLOR[b],
                    marker_line=dict(color="white", width=2), text=s.round(0).astype(int).astype(str) + "%",
                    textposition="inside", hovertemplate=f"%{{y}} · {b}: %{{x:.1f}}%<extra></extra>")
    fig.update_layout(barmode="stack", hovermode="closest")
    st.plotly_chart(style(fig, height=560, y_title=None).update_xaxes(range=[0, 100], title="점유율 (%)"),
                    width="stretch")
    st.info("검색어 트렌드 값은 요청마다 최댓값=100으로 맞춘 상대값이라, 세그먼트끼리 검색량 크기는 비교할 수 없습니다. "
            "각 막대는 '그 세그먼트 안에서' 세 브랜드가 차지하는 비중입니다.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**10~20대**: 스파오가 유니클로와 대등 (10대 이하 44% vs 45%)")
    c2.markdown("**30~40대**: 탑텐이 스파오를 앞섬 (40대 21% vs 15%)")
    c3.markdown("**50대 이상**: 유니클로 쏠림 (60세 이상 78%)")
    with st.expander("표로 보기"):
        st.dataframe(seg, hide_index=True, width="stretch")
