"""뉴스 검색 API로 SPA 브랜드별 최신 기사 50건을 수집해 data/raw/spa_news.json에 저장한다."""
import html
import json
import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

from api_test import call

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "spa_news.json"

clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or ""))
out = {}
for brand in ["유니클로", "스파오", "탑텐"]:
    status, d = call("GET", "/search/v1/news", params={"query": brand, "display": 50, "sort": "date"})
    if status != 200:
        print(brand, status, d)
        continue
    out[brand] = d
    print(f"\n### {brand} (전체 {d['total']:,}건 중 최신 {len(d['items'])}건)")
    for i, it in enumerate(d["items"], 1):
        dt = parsedate_to_datetime(it["pubDate"]).strftime("%m-%d %H:%M")
        src = urlparse(it["originallink"] or it["link"]).netloc.removeprefix("www.")
        print(f"{i:>2} | {dt} | {src} | {clean(it['title'])}")

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n저장: {OUT}")
