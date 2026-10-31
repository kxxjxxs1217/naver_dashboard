"""브랜드별·주제별로 BoW와 TF-IDF 키워드를 뽑아 비교하고 워드클라우드를 그린다.

입력: data/processed/SPA_브랜드_뉴스_주제분류.csv (기사 1건 = 문서 1개, 제목 + 요약)
출력: data/processed/SPA_키워드_BoW_TFIDF.csv          그룹·방식별 상위 30개 키워드와 점수
      data/processed/SPA_키워드_비교.csv               그룹별 상위 15개 BoW/TF-IDF 비교
      reports/figures/wordcloud/<구분>_<그룹>_<방식>.png  워드클라우드 각각
      reports/figures/wordcloud_브랜드별.png, wordcloud_주제별.png  한눈에 보는 묶음 그림

- 형태소 분석: kiwipiepy로 일반·고유명사(NNG, NNP)와 영문(SL) 중 2글자 이상만 사용
- 불용어: 세 브랜드명과 운영사명(그룹 구분 자체이므로), 기사 상투어(사진, 기자, 제공 등)
- BoW: 그룹에 속한 기사들의 단어 빈도 합계
- TF-IDF: 기사 150건 전체를 말뭉치로 기사별 TF-IDF(L2 정규화)를 구한 뒤 그룹 안에서 평균
  → 여러 기사에 두루 나오는 단어는 낮아지고, 일부 기사에 집중된 단어가 올라간다
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np
from kiwipiepy import Kiwi
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from wordcloud import WordCloud

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "processed" / "SPA_브랜드_뉴스_주제분류.csv"
OUT_KW = ROOT / "data" / "processed" / "SPA_키워드_BoW_TFIDF.csv"
OUT_CMP = ROOT / "data" / "processed" / "SPA_키워드_비교.csv"
FIG = ROOT / "reports" / "figures"
FONT = r"C:\Windows\Fonts\malgun.ttf"
plt.rcParams["font.family"] = "Malgun Gothic"

BRANDS = ["유니클로", "스파오", "탑텐"]
TOPICS = ["제품 출시", "협업", "할인·행사", "실적·사업", "기타"]
TOP_N, CLOUD_N = 30, 60

# 형태소 분석기가 쪼개는 브랜드·상품명은 한 단어로 등록
USER_WORDS = ["신성통상", "이랜드월드", "에프알엘코리아", "패스트리테일링", "스타필드", "콜라보", "텐텐데이",
              "경량패딩", "플러피플리스", "에어테크", "쿨에어", "웜테크", "씬라이트", "히트텍", "스파오키즈",
              "탑텐키즈", "스파오프렌즈", "먼작귀", "치이카와", "무신사스탠다드", "발열내의", "브라캐미솔",
              "바디수트", "굿웨어", "스새페", "에잇세컨즈", "새학기", "미키마우스"]
STOPWORDS = {
    # 브랜드·운영사 (그룹 구분 자체)
    "유니클로", "UNIQLO", "스파오", "SPAO", "탑텐", "TOPTEN", "신성통상", "이랜드", "이랜드월드",
    "에프알엘코리아", "패스트리테일링",
    # 기사 상투어·일반어
    "브랜드", "SPA", "패션", "사진", "기자", "제공", "운영", "올해", "지난해", "이번", "업계", "관계자",
    "가운데", "전년", "대비", "동기", "이후", "전체", "대상", "시작", "활용", "중심", "공식", "제조",
    "유통", "일괄", "회사", "전개", "국내", "최근", "진행", "기준", "대표", "부문", "통해", "위해",
    "대신", "기록",
    # 캠페인명 'TOGETHER, WE CHEER'가 쪼개진 조각 (CHEER만 남김)
    "TOGETHER", "WE",
}

kiwi = Kiwi()
for w in USER_WORDS:
    kiwi.add_user_word(w, "NNP")


def tokens(text):
    return [t.form for t in kiwi.tokenize(text)
            if t.tag in ("NNG", "NNP", "SL") and len(t.form) >= 2 and t.form not in STOPWORDS]


rows = list(csv.DictReader(SRC.open(encoding="utf-8-sig")))
docs = [" ".join(tokens(r["제목"] + " " + r["요약"])) for r in rows]

vec_kw = dict(token_pattern=r"(?u)\S+", lowercase=False)
bow = CountVectorizer(**vec_kw)
X_bow = bow.fit_transform(docs)
tfidf = TfidfVectorizer(**vec_kw)
X_tfidf = tfidf.fit_transform(docs)
vocab_bow, vocab_tfidf = bow.get_feature_names_out(), tfidf.get_feature_names_out()

groups = [("브랜드", b, [i for i, r in enumerate(rows) if r["브랜드"] == b]) for b in BRANDS] + \
         [("주제", t, [i for i, r in enumerate(rows) if r["주제"] == t]) for t in TOPICS]

scores = {}  # (구분, 그룹, 방식) -> {단어: 점수}
for kind, name, idx in groups:
    s_bow = np.asarray(X_bow[idx].sum(axis=0)).ravel()
    s_tfidf = np.asarray(X_tfidf[idx].mean(axis=0)).ravel()
    scores[(kind, name, "BoW")] = {w: float(v) for w, v in zip(vocab_bow, s_bow) if v > 0}
    scores[(kind, name, "TF-IDF")] = {w: float(v) for w, v in zip(vocab_tfidf, s_tfidf) if v > 0}


def top(d, n):
    return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


# 키워드 표
with OUT_KW.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["구분", "그룹", "기사 수", "방식", "순위", "키워드", "점수"])
    for kind, name, idx in groups:
        for method in ["BoW", "TF-IDF"]:
            for rank, (word, v) in enumerate(top(scores[(kind, name, method)], TOP_N), 1):
                w.writerow([kind, name, len(idx), method, rank, word, round(v, 4)])

# BoW vs TF-IDF 비교 (상위 15개)
with OUT_CMP.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["구분", "그룹", "기사 수", "BoW 상위 15", "TF-IDF 상위 15", "공통", "BoW에만", "TF-IDF에만"])
    for kind, name, idx in groups:
        b = [k for k, _ in top(scores[(kind, name, "BoW")], 15)]
        t = [k for k, _ in top(scores[(kind, name, "TF-IDF")], 15)]
        common = [k for k in b if k in t]
        w.writerow([kind, name, len(idx), ", ".join(b), ", ".join(t), ", ".join(common),
                    ", ".join(k for k in b if k not in t), ", ".join(k for k in t if k not in b)])
        print(f"\n[{kind}: {name}] 기사 {len(idx)}건 | 공통 {len(common)}/15")
        print("  BoW   :", ", ".join(b[:10]))
        print("  TF-IDF:", ", ".join(t[:10]))
        print("  BoW에만   :", ", ".join(k for k in b if k not in t))
        print("  TF-IDF에만:", ", ".join(k for k in t if k not in b))


# 워드클라우드
def cloud(freq):
    return WordCloud(font_path=FONT, width=900, height=600, background_color="white",
                     max_words=CLOUD_N, prefer_horizontal=1.0, colormap="viridis",
                     random_state=42).generate_from_frequencies(dict(top(freq, CLOUD_N)))


(FIG / "wordcloud").mkdir(parents=True, exist_ok=True)
for kind in ["브랜드", "주제"]:
    gs = [g for g in groups if g[0] == kind]
    fig, axes = plt.subplots(len(gs), 2, figsize=(14, 4.6 * len(gs)))
    for row, (_, name, idx) in enumerate(gs):
        for col, method in enumerate(["BoW", "TF-IDF"]):
            wc = cloud(scores[(kind, name, method)])
            wc.to_file(FIG / "wordcloud" / f"{kind}_{name.replace('·', '_').replace(' ', '')}_{method}.png")
            ax = axes[row, col]
            ax.imshow(wc, interpolation="bilinear")
            ax.set_title(f"{name} ({len(idx)}건) — {method}", fontsize=15)
            ax.axis("off")
    fig.suptitle(f"{kind}별 키워드 워드클라우드: BoW(빈도) vs TF-IDF(특징어)", fontsize=18)
    fig.tight_layout(rect=(0, 0, 1, 0.98))
    fig.savefig(FIG / f"wordcloud_{kind}별.png", dpi=110)
    plt.close(fig)

print("\n저장:", OUT_KW, OUT_CMP, FIG / "wordcloud_브랜드별.png", FIG / "wordcloud_주제별.png", sep="\n  ")
