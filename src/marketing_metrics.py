"""브랜드 마케터 관점의 경쟁 지표와 뉴스 자연어 분석 결과를 만든다.

입력: data/processed/SPA_브랜드_뉴스_주제분류.csv, 검색트렌드_월별.csv, 검색트렌드_주별.csv,
      검색트렌드_세그먼트_점유율.csv
출력 (data/processed/)
- 마케팅_기사분석.csv      기사별 감성(규칙 기반)·브랜드 연상 속성 태그
- 마케팅_속성프로필.csv     브랜드별 연상 속성 언급률(%)
- 마케팅_브랜드지표.csv     브랜드별 핵심 지표 (SOS, SOV, 모멘텀, 감성, 행사 의존도 등)
- 마케팅_월별검색점유율.csv  최근 24개월 월별 검색 점유율(SOS)
- 마케팅_세그먼트인덱스.csv  세그먼트별 점유율 지수 (전체 점유율 = 100)

지표 정의는 app/dashboard.py의 '지표 사전'과 같다.
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
PROC = Path(__file__).resolve().parent.parent / "data" / "processed"
BRANDS = ["유니클로", "스파오", "탑텐"]

# 공통 비교 기간: 세 브랜드 뉴스가 모두 있는 기간 (유니클로 정제 기사가 2026-09-22부터)
COMMON_START, COMMON_END = "2026-09-22", "2026-10-31"

# ---- 1. 뉴스 감성 (규칙 기반 사전) ----------------------------------------------
POS = ["증가", "돌파", "최대", "인기", "품절", "흥행", "성장", "호조", "1위", "수상", "대상", "급증", "완판",
       "회복", "오픈런", "껑충", "불티", "역대", "뛰었", "통했", "확대", "대세", "견인"]
NEG = ["철회", "반발", "하락", "해킹", "유출", "부담", "감소", "폐점", "논란", "위기", "백기", "불매", "철수",
       "줄인상", "상폐", "공실", "꼴찌", "우려", "막혔", "중단", "뒤통수", "진퇴양난", "몰락", "정체"]

# ---- 2. 브랜드 연상 속성 사전 ----------------------------------------------------
ATTRS = {
    "가격·가성비": ["가격", "가성비", "할인", "저렴", "반값", "만원", "인상", "원가", "실속"],
    "품질·기능성": ["기능", "소재", "보온", "발열", "냉감", "충전재", "기술", "품질", "에어테크", "히트텍", "웜테크",
                "쿨에어", "씬라이트", "플리스"],
    "협업·IP": ["협업", "콜라보", "컬래버", "IP", "캐릭터", "디자이너", "먼작귀", "산리오"],
    "매장·공간 경험": ["매장", "오픈", "리뉴얼", "플래그십", "팝업", "체험", "공간", "출점"],
    "키즈·가족": ["키즈", "아동", "가족", "아이", "부모", "패밀리", "베이비", "새학기"],
    "트렌드·스타일": ["트렌드", "스타일", "유행", "화보", "캠페인", "컬렉션", "MZ", "10대", "2030"],
    "사회공헌·지속가능": ["수선", "재활용", "사회공헌", "기부", "환경", "ESG", "재해", "취약계층", "학습"],
}


def hits(text, words):
    return [w for w in words if w in text]


news = pd.read_csv(PROC / "SPA_브랜드_뉴스_주제분류.csv", encoding="utf-8-sig")
news["날짜"] = pd.to_datetime(news["날짜"])
text = (news["제목"] + " " + news["요약"]).fillna("")
news["긍정어"] = text.apply(lambda t: ", ".join(hits(t, POS)))
news["부정어"] = text.apply(lambda t: ", ".join(hits(t, NEG)))
score = text.apply(lambda t: len(hits(t, POS)) - len(hits(t, NEG)))
news["감성"] = score.apply(lambda s: "긍정" if s > 0 else ("부정" if s < 0 else "중립"))
for a, words in ATTRS.items():
    news[a] = text.apply(lambda t, w=words: int(bool(hits(t, w))))
news.to_csv(PROC / "마케팅_기사분석.csv", index=False, encoding="utf-8-sig")

profile = news.groupby("브랜드")[list(ATTRS)].mean().mul(100).round(1).reindex(BRANDS)
profile.to_csv(PROC / "마케팅_속성프로필.csv", encoding="utf-8-sig")

# ---- 3. 검색 지표 ---------------------------------------------------------------
monthly = pd.read_csv(PROC / "검색트렌드_월별.csv", encoding="utf-8-sig")
monthly["월"] = pd.to_datetime(monthly["월"])
weekly = pd.read_csv(PROC / "검색트렌드_주별.csv", encoding="utf-8-sig")
weekly["주 시작일"] = pd.to_datetime(weekly["주 시작일"])
seg = pd.read_csv(PROC / "검색트렌드_세그먼트_점유율.csv", encoding="utf-8-sig")


def window(df, start, end):
    return df[(df["월"] >= start) & (df["월"] <= end)][BRANDS].sum()


last12 = window(monthly, "2025-11-01", "2026-10-01")
prev12 = window(monthly, "2024-11-01", "2025-10-01")
last3 = window(monthly, "2026-08-01", "2026-10-01")
prev3 = window(monthly, "2025-08-01", "2025-10-01")
sos12 = last12 / last12.sum() * 100
sos_prev12 = prev12 / prev12.sum() * 100

wk_common = weekly[weekly["주 시작일"] >= COMMON_START][BRANDS].sum()
sos_common = wk_common / wk_common.sum() * 100
promo = weekly[BRANDS].max() / weekly[BRANDS].median()

share_m = monthly[monthly["월"] >= "2024-11-01"].set_index("월")[BRANDS]
share_m = share_m.div(share_m.sum(axis=1), axis=0).mul(100).round(1)
share_m.to_csv(PROC / "마케팅_월별검색점유율.csv", encoding="utf-8-sig")

overall = sos12
idx_rows = []
for _, r in seg.iterrows():
    idx_rows.append([r["구분"], r["세그먼트"]] + [round(r[f"{b} 점유율(%)"] / overall[b] * 100) for b in BRANDS])
pd.DataFrame(idx_rows, columns=["구분", "세그먼트"] + BRANDS).to_csv(
    PROC / "마케팅_세그먼트인덱스.csv", index=False, encoding="utf-8-sig")

# ---- 4. 뉴스 지표 (공통 기간) ------------------------------------------------------
common = news[(news["날짜"] >= COMMON_START) & (news["날짜"] <= COMMON_END)]
vol = common.groupby("브랜드")["같은 이슈 보도 수"].sum().reindex(BRANDS).fillna(0)
sov = vol / vol.sum() * 100

rows = []
for b in BRANDS:
    nb = news[news["브랜드"] == b]
    cb = common[common["브랜드"] == b]
    pos, neg = (nb["감성"] == "긍정").sum(), (nb["감성"] == "부정").sum()
    w = nb["같은 이슈 보도 수"]
    top_attr = profile.loc[b].idxmax()
    rows.append({
        "브랜드": b,
        "검색 점유율 SOS(최근12개월,%)": round(sos12[b], 1),
        "SOS 전년 대비(%p)": round(sos12[b] - sos_prev12[b], 1),
        "검색량 성장률 YoY(최근12개월,%)": round((last12[b] / prev12[b] - 1) * 100, 1),
        "검색량 성장률 YoY(최근3개월,%)": round((last3[b] / prev3[b] - 1) * 100, 1),
        "공통기간 SOS(%)": round(sos_common[b], 1),
        "공통기간 보도 점유율 SOV(%)": round(sov[b], 1),
        "초과 보도 점유율 ESOV(%p)": round(sov[b] - sos_common[b], 1),
        "공통기간 보도량": int(vol[b]),
        "순감성 지수 NSI": round((pos - neg) / len(nb) * 100, 1),
        "부정 기사 비중(%)": round(neg / len(nb) * 100, 1),
        "보도량 가중 부정 비중(%)": round(w[nb["감성"] == "부정"].sum() / w.sum() * 100, 1),
        "행사 의존도(주별 최고/중앙값)": round(promo[b], 1),
        "대표 연상 속성": top_attr,
        "기사 기간": f"{nb['날짜'].min():%Y-%m-%d}~{nb['날짜'].max():%Y-%m-%d}",
    })
kpi = pd.DataFrame(rows)
kpi.to_csv(PROC / "마케팅_브랜드지표.csv", index=False, encoding="utf-8-sig")

pd.set_option("display.width", 200)
print(kpi.T.to_string())
print("\n[속성 프로필 %]\n", profile.to_string())
print("\n[감성 분포]\n", news.groupby(["브랜드", "감성"]).size().unstack(fill_value=0).to_string())
print("\n[공통기간 기사 수]", common.groupby("브랜드").size().to_dict())
