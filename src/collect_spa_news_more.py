"""정제 후 브랜드별 50건을 채우기 위해 최신 기사를 추가 수집한다.

사용법: python collect_spa_news_more.py [시작위치] [끝위치] [출력파일명] [브랜드...]
  기본값: 1 500 spa_news_extended.json 유니클로 스파오 탑텐
결과는 data/raw/<출력파일명> ({브랜드: [item, ...]})에 저장한다.
검색 API는 start를 1000까지만 허용하므로 끝위치는 최대 1000이다.
"""
import json
import sys
from pathlib import Path

from api_test import call

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
args = sys.argv[1:]
lo = int(args[0]) if len(args) > 0 else 1
hi = int(args[1]) if len(args) > 1 else 500
OUT = ROOT / "data" / "raw" / (args[2] if len(args) > 2 else "spa_news_extended.json")
brands = args[3:] or ["유니클로", "스파오", "탑텐"]

out = {}
for brand in brands:
    items = []
    for start in range(lo, hi + 1, 100):
        status, d = call("GET", "/search/v1/news",
                         params={"query": brand, "display": min(100, hi - start + 1), "start": start, "sort": "date"})
        if status != 200:
            print(brand, start, status, d)
            break
        items += d["items"]
    out[brand] = items
    print(brand, len(items), "건", items[-1]["pubDate"] if items else "")

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("저장:", OUT)
