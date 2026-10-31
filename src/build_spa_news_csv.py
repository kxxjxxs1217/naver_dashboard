"""data/raw/spa_news.json을 브랜드·번호·날짜·제목·요약·원문 링크 CSV로 정리한다."""
import csv
import html
import json
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw" / "spa_news.json"
OUT = ROOT / "data" / "processed" / "SPA_브랜드_최신뉴스.csv"

clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
data = json.loads(SRC.read_text(encoding="utf-8"))

# utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않도록 BOM 포함
with OUT.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["브랜드", "번호", "날짜", "제목", "요약", "원문 링크"])
    for brand, d in data.items():
        for i, it in enumerate(d["items"], 1):
            date = parsedate_to_datetime(it["pubDate"]).strftime("%Y-%m-%d %H:%M")
            w.writerow([brand, i, date, clean(it["title"]), clean(it["description"]),
                        it["originallink"] or it["link"]])
print(OUT)
