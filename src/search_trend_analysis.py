"""검색어 트렌드 API로 유니클로·스파오·탑텐의 네이버 통합검색 추이를 비교 분석한다.

수집 (data/raw/search_trend.json이 없을 때만 API 호출, 총 13회)
- 월별 장기 추이: 2016-01 ~ 2026-10 (전체 사용자)
- 주별 최근 추이: 최근 12개월
- 연령대별 / 성별 / 기기별: 최근 12개월 월별, 조건마다 1회씩
출력
- data/processed/검색트렌드_월별.csv, 검색트렌드_주별.csv, 검색트렌드_세그먼트_점유율.csv
- reports/figures/검색트렌드_*.png

주의: 검색어 트렌드의 ratio는 '한 번의 요청 안에서 최댓값=100'인 상대값이다.
같은 요청에 묶인 세 브랜드끼리는 비교할 수 있지만, 요청이 다른 연령대·성별 간 크기는 비교할 수 없다.
그래서 세그먼트 분석은 '그 세그먼트 안에서 세 브랜드의 검색량 점유율'로 본다.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from api_test import call  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "search_trend.json"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "reports" / "figures"

BRANDS = ["유니클로", "스파오", "탑텐"]
KEYWORD_GROUPS = [
    {"groupName": "유니클로", "keywords": ["유니클로", "uniqlo"]},
    {"groupName": "스파오", "keywords": ["스파오", "spao"]},
    {"groupName": "탑텐", "keywords": ["탑텐", "topten"]},
]
RECENT = {"startDate": "2025-11-01", "endDate": "2026-10-31"}
AGES = [("10대 이하", ["1", "2"]), ("19~24세", ["3"]), ("25~29세", ["4"]), ("30대", ["5", "6"]),
        ("40대", ["7", "8"]), ("50대", ["9", "10"]), ("60세 이상", ["11"])]

# 차트 색: 검증된 기본 팔레트의 1~3번 슬롯 (브랜드 = 정체성, 순서 고정)
COLOR = {"유니클로": "#2a78d6", "스파오": "#eb6834", "탑텐": "#1baf7a"}
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE, "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "legend.frameon": False, "legend.labelcolor": INK2,
})


def end_labels(ax, x, ys_by_brand, min_gap):
    """선 끝 직접 라벨: 값이 가까우면 겹치지 않게 위아래로 벌린다."""
    items = sorted(ys_by_brand.items(), key=lambda kv: kv[1])
    placed = []
    for b, y in items:
        y_txt = max(y, placed[-1] + min_gap) if placed else y
        placed.append(y_txt)
        ax.annotate(b, (x, y), xytext=(x, y_txt), textcoords="data", color=INK2, fontsize=11, va="center",
                    ha="left", annotation_clip=False)


def request(name, **extra):
    body = {"timeUnit": "month", "keywordGroups": KEYWORD_GROUPS, **extra}
    status, data = call("POST", "/search-trend/v1/search", body=body)
    if status != 200:
        sys.exit(f"{name} 요청 실패: {status} {data}")
    return {"request": body, "response": data}


def collect():
    raw = {"월별_장기": request("월별_장기", startDate="2016-01-01", endDate="2026-10-31"),
           "주별_최근": request("주별_최근", **{**RECENT, "timeUnit": "week"})}
    for label, ages in AGES:
        raw[f"연령_{label}"] = request(label, **RECENT, ages=ages)
    for code, label in [("f", "여성"), ("m", "남성")]:
        raw[f"성별_{label}"] = request(label, **RECENT, gender=code)
    for code, label in [("pc", "PC"), ("mo", "모바일")]:
        raw[f"기기_{label}"] = request(label, **RECENT, device=code)
    RAW.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    return raw


raw = json.loads(RAW.read_text(encoding="utf-8")) if RAW.exists() else collect()


def series(key):
    """{브랜드: {기간: ratio}}"""
    return {r["title"]: {d["period"]: d["ratio"] for d in r["data"]} for r in raw[key]["response"]["results"]}


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ---- 1. 월별 장기 추이 -------------------------------------------------------
monthly = series("월별_장기")
periods = sorted({p for s in monthly.values() for p in s})
write_csv(PROC / "검색트렌드_월별.csv", ["월"] + BRANDS,
          [[p[:7]] + [monthly[b].get(p, 0) for b in BRANDS] for p in periods])

years = sorted({p[:4] for p in periods})
yearly = {b: {y: sum(v for p, v in monthly[b].items() if p[:4] == y) for y in years} for b in BRANDS}
share = {y: {b: yearly[b][y] / sum(yearly[x][y] for x in BRANDS) * 100 for b in BRANDS} for y in years}

fig, ax = plt.subplots(figsize=(13, 5.6))
xs = range(len(periods))
for b in BRANDS:
    ys = [monthly[b].get(p, 0) for p in periods]
    ax.plot(xs, ys, color=COLOR[b], linewidth=2, label=b)
end_labels(ax, len(periods) + 0.5, {b: monthly[b][periods[-1]] for b in BRANDS}, min_gap=5)
ticks = [i for i, p in enumerate(periods) if p[5:7] == "01"]
ax.set_xticks(ticks, [periods[i][:4] for i in ticks])
i19 = periods.index("2019-07-01")
ax.axvline(i19, color=MUTED, linewidth=1, linestyle="--")
ax.annotate("2019.07 일본 제품\n불매운동", (i19, 95), xytext=(6, 0), textcoords="offset points",
            color=INK2, fontsize=10, va="top")
ax.set_ylim(0, 105)
ax.set_ylabel("상대 검색량 (기간 내 최댓값 = 100)")
ax.set_title("월별 검색 추이 (2016.01 ~ 2026.10)", loc="left")
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.08))
fig.tight_layout()
fig.savefig(FIG / "검색트렌드_월별추이.png", dpi=120)
plt.close(fig)

# ---- 2. 연도별 검색 점유율 -----------------------------------------------------
fig, ax = plt.subplots(figsize=(13, 5.2))
bottom = [0] * len(years)
for b in BRANDS:
    vals = [share[y][b] for y in years]
    ax.bar(years, vals, bottom=bottom, color=COLOR[b], label=b, edgecolor=SURFACE, linewidth=2, width=0.7)
    for i, (v, bt) in enumerate(zip(vals, bottom)):
        if v >= 8:
            ax.text(i, bt + v / 2, f"{v:.0f}%", ha="center", va="center", color="#ffffff", fontsize=10)
    bottom = [x + v for x, v in zip(bottom, vals)]
ax.set_ylim(0, 100)
ax.set_ylabel("세 브랜드 검색량 중 점유율 (%)")
ax.set_title("연도별 검색 점유율 (2026년은 1~10월)", loc="left")
ax.grid(axis="x", visible=False)
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.07))
fig.tight_layout()
fig.savefig(FIG / "검색트렌드_연도별점유율.png", dpi=120)
plt.close(fig)

# ---- 3. 계절성: 최근 3년(2023~2025) 월별 평균, 브랜드별 연평균 = 100 ---------------
season = {}
for b in BRANDS:
    by_month = defaultdict(list)
    for p, v in monthly[b].items():
        if p[:4] in ("2023", "2024", "2025"):
            by_month[int(p[5:7])].append(v)
    avg = {m: sum(v) / len(v) for m, v in by_month.items()}
    base = sum(avg.values()) / 12
    season[b] = {m: avg[m] / base * 100 for m in range(1, 13)}

fig, ax = plt.subplots(figsize=(11, 5))
for b in BRANDS:
    ys = [season[b][m] for m in range(1, 13)]
    ax.plot(range(1, 13), ys, color=COLOR[b], linewidth=2, marker="o", markersize=7,
            markeredgecolor=SURFACE, markeredgewidth=2, label=b)
end_labels(ax, 12.25, {b: season[b][12] for b in BRANDS}, min_gap=9)
ax.axhline(100, color=AXIS, linewidth=1)
ax.set_xticks(range(1, 13), [f"{m}월" for m in range(1, 13)])
ax.set_ylabel("계절 지수 (브랜드별 연평균 = 100)")
ax.set_title("검색 계절성 (2023~2025년 평균)", loc="left")
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.08))
fig.tight_layout()
fig.savefig(FIG / "검색트렌드_계절성.png", dpi=120)
plt.close(fig)

# ---- 4. 최근 12개월 주별 추이 ----------------------------------------------------
weekly = series("주별_최근")
weeks = sorted({p for s in weekly.values() for p in s})
write_csv(PROC / "검색트렌드_주별.csv", ["주 시작일"] + BRANDS,
          [[p] + [weekly[b].get(p, 0) for b in BRANDS] for p in weeks])
fig, ax = plt.subplots(figsize=(13, 5.4))
for b in BRANDS:
    ys = [weekly[b].get(p, 0) for p in weeks]
    ax.plot(range(len(weeks)), ys, color=COLOR[b], linewidth=2, label=b)
    peak = max(range(len(weeks)), key=lambda i: ys[i])
    ax.annotate(f"{b} 최고 {weeks[peak][5:].replace('-', '.')} 주", (peak, ys[peak]), xytext=(0, 8),
                textcoords="offset points", ha="center", color=INK2, fontsize=9)
mticks = [i for i, p in enumerate(weeks) if i > 0 and p[5:7] != weeks[i - 1][5:7]]
ax.set_xticks(mticks, [weeks[i][2:7].replace("-", ".") for i in mticks])
ax.set_ylim(0, 110)
ax.set_ylabel("상대 검색량 (기간 내 최댓값 = 100)")
ax.set_title("최근 12개월 주별 검색 추이 (2025.11 ~ 2026.10)", loc="left")
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.08))
fig.tight_layout()
fig.savefig(FIG / "검색트렌드_주별추이.png", dpi=120)
plt.close(fig)

# ---- 5. 세그먼트(연령·성별·기기)별 검색 점유율 ---------------------------------------
seg_rows, seg = [], []
for key in raw:
    if key.split("_")[0] not in ("연령", "성별", "기기"):
        continue
    kind, label = key.split("_", 1)
    s = series(key)
    tot = {b: sum(s[b].values()) for b in BRANDS}
    allv = sum(tot.values())
    shares = {b: tot[b] / allv * 100 for b in BRANDS}
    seg.append((kind, label, shares))
    seg_rows.append([kind, label] + [round(shares[b], 1) for b in BRANDS])
write_csv(PROC / "검색트렌드_세그먼트_점유율.csv", ["구분", "세그먼트"] + [f"{b} 점유율(%)" for b in BRANDS], seg_rows)

all_s = series("주별_최근")
overall = {b: sum(all_s[b].values()) for b in BRANDS}
overall = {b: v / sum(overall.values()) * 100 for b, v in overall.items()}
seg = [("전체", "전체", overall)] + seg

fig, ax = plt.subplots(figsize=(12, 7.2))
labels = [f"{label}" for _, label, _ in seg][::-1]
data = [s for _, _, s in seg][::-1]
left = [0] * len(data)
for b in BRANDS:
    vals = [d[b] for d in data]
    ax.barh(labels, vals, left=left, color=COLOR[b], label=b, edgecolor=SURFACE, linewidth=2, height=0.7)
    for i, (v, lf) in enumerate(zip(vals, left)):
        if v >= 6:
            ax.text(lf + v / 2, i, f"{v:.0f}%", ha="center", va="center", color="#ffffff", fontsize=10)
    left = [x + v for x, v in zip(left, vals)]
# 구분선: 전체 / 연령 / 성별 / 기기
n_dev, n_gen, n_age = 2, 2, len(AGES)
for y in (n_dev - 0.5, n_dev + n_gen - 0.5, n_dev + n_gen + n_age - 0.5):
    ax.axhline(y, color=INK2, linewidth=1)
ax.set_xlim(0, 100)
ax.set_xlabel("세그먼트 안에서 세 브랜드 검색량 점유율 (%)")
ax.set_title("연령·성별·기기별 검색 점유율 (최근 12개월)", loc="left")
ax.grid(axis="y", visible=False)
ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.08))
fig.tight_layout()
fig.savefig(FIG / "검색트렌드_세그먼트점유율.png", dpi=120)
plt.close(fig)

# ---- 6. 연령대별 최근 12개월 월별 점유율 추이 (스몰 멀티플) ----------------------------
fig, axes = plt.subplots(1, len(AGES), figsize=(18, 4.2), sharey=True)
for ax, (label, _) in zip(axes, AGES):
    s = series(f"연령_{label}")
    ps = sorted({p for v in s.values() for p in v})
    for b in BRANDS:
        sh = [s[b].get(p, 0) / max(sum(s[x].get(p, 0) for x in BRANDS), 1e-9) * 100 for p in ps]
        ax.plot(range(len(ps)), sh, color=COLOR[b], linewidth=2, label=b)
    ax.set_title(label, fontsize=12, loc="left")
    ax.set_xticks([0, len(ps) - 1], [ps[0][2:7].replace("-", "."), ps[-1][2:7].replace("-", ".")])
    ax.set_ylim(0, 100)
axes[0].set_ylabel("월별 점유율 (%)")
axes[len(AGES) // 2].legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.12))
fig.suptitle("연령대별 월별 검색 점유율 추이 (2025.11 ~ 2026.10)", x=0.01, ha="left", fontsize=14,
             fontweight="bold", color=INK)
fig.tight_layout()
fig.savefig(FIG / "검색트렌드_연령별월추이.png", dpi=120)
plt.close(fig)

# ---- 요약 출력 ----------------------------------------------------------------
print("[연도별 점유율 %]")
for y in years:
    print(" ", y, "  ".join(f"{b} {share[y][b]:5.1f}" for b in BRANDS))
print("\n[연도별 월평균 상대 검색량]")
for y in years:
    n = sum(1 for p in periods if p[:4] == y)
    print(" ", y, "  ".join(f"{b} {yearly[b][y] / n:5.1f}" for b in BRANDS))
print("\n[계절 지수 (연평균=100)]")
for b in BRANDS:
    print(" ", b, " ".join(f"{m}월 {season[b][m]:.0f}" for m in range(1, 13)))
print("\n[주별 최고점]")
for b in BRANDS:
    ys = weekly[b]
    top3 = sorted(ys.items(), key=lambda kv: -kv[1])[:3]
    print(" ", b, ", ".join(f"{p} ({v:.1f})" for p, v in top3))
print("\n[세그먼트 점유율 %]")
for kind, label, sh in seg:
    print(f"  {kind:3} {label:7}", "  ".join(f"{b} {sh[b]:5.1f}" for b in BRANDS))
