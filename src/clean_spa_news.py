"""SPA 브랜드 뉴스에서 무관 기사와 중복 기사를 빼고 정제 CSV를 만든다.

주의: EXCLUDE·CLUSTERS의 번호는 2026-10-31에 수집한 data/raw/spa_news.json 기준으로
기사를 하나씩 읽고 정한 값이다. 뉴스를 다시 수집하면 번호가 달라지므로 다시 검토해야 한다.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
rows = list(csv.DictReader(open(DIR / "SPA_브랜드_최신뉴스.csv", encoding="utf-8-sig")))
key = lambda r: (r["브랜드"], int(r["번호"]))
ORDER = ["유니클로", "스파오", "탑텐"]
NAMES = {"유니클로": ["유니클로", "uniqlo"], "스파오": ["스파오", "spao"], "탑텐": ["탑텐", "topten"]}

# 1) 무관(제외 권장) + 애매 중 제외 권장(이랜드 아카이브)
EXCLUDE = {
    "유니클로": [1, 2, 7, 23, 24, 16, 21, 26, 27, 31, 34, 38, 42, 43, 44, 22, 33, 48, 45, 47],
    "스파오": [2, 16, 38, 39, 45, 50, 47, 48, 49] + [18, 19, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 34],
    "탑텐": [2, 3, 4, 5, 22, 23, 25, 26, 6, 8, 16],
}
# 3) 브랜드 안 같은 이슈 묶음 -> 가장 먼저 보도된 1건만 유지
CLUSTERS = {
    "유니클로": [[3, 4, 8, 12, 13, 15, 17, 18, 19, 20], [32, 36, 37, 40]],
    "스파오": [[3, 4, 12], [1, 20, 36], [8, 17], [40, 41], [13, 15]],
    "탑텐": [[21, 28, 29, 30, 31, 32, 34] + list(range(36, 51)), [1, 18, 19, 20], [10, 15]],
}

excl = {(b, n) for b, ns in EXCLUDE.items() for n in ns}
kept = [r for r in rows if key(r) not in excl]
removed = {"무관/제외 권장": len(rows) - len(kept)}


# 2) 브랜드 간 동일 URL -> 브랜드 언급이 가장 많은 쪽 1건만 유지 (제목 언급 가중)
def score(r):
    ns = NAMES[r["브랜드"]]
    t = any(n in r["제목"].lower() for n in ns)
    d = sum(r["요약"].lower().count(n) for n in ns)
    return (10 * t + d, -ORDER.index(r["브랜드"]))


by_url = defaultdict(list)
for r in kept:
    by_url[r["원문 링크"]].append(r)
also = {}
drop = set()
for group in by_url.values():
    if len(group) > 1:
        best = max(group, key=score)
        also[key(best)] = ", ".join(r["브랜드"] for r in group if r is not best)
        drop |= {key(r) for r in group if r is not best}
kept2 = [r for r in kept if key(r) not in drop]
removed["브랜드 간 중복"] = len(kept) - len(kept2)

# 3) 같은 이슈 묶음
alive = {key(r): r for r in kept2}
drop = set()
issue_count = {}
for b, groups in CLUSTERS.items():
    for g in groups:
        members = [alive[(b, n)] for n in g if (b, n) in alive]
        if len(members) < 2:
            continue
        first = min(members, key=lambda r: r["날짜"])
        issue_count[key(first)] = len(members)
        drop |= {key(r) for r in members if r is not first}
final = [r for r in kept2 if key(r) not in drop]
removed["같은 이슈 반복 보도"] = len(kept2) - len(final)

final.sort(key=lambda r: (ORDER.index(r["브랜드"]), r["날짜"]))
OUT = DIR / "SPA_브랜드_최신뉴스_정제.csv"
with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["브랜드", "원본 번호", "날짜", "제목", "요약", "원문 링크", "함께 수집된 브랜드", "같은 이슈 보도 수"])
    for r in final:
        k = key(r)
        w.writerow([r["브랜드"], r["번호"], r["날짜"], r["제목"], r["요약"], r["원문 링크"],
                    also.get(k, ""), issue_count.get(k, 1)])

print(OUT)
print("제거:", removed, "| 남은 건수:", len(final),
      {b: sum(r["브랜드"] == b for r in final) for b in ORDER})
