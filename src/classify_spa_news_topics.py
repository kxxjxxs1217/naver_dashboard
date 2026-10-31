"""분석용 뉴스(SPA_브랜드_뉴스_분석용.csv)에 주제를 붙여 SPA_브랜드_뉴스_주제분류.csv로 저장한다.

주제 기준 (기사의 중심 내용 하나만 고른다)
- 제품 출시: 신제품·컬렉션 출시, 라인업 확대, 시즌 캠페인 화보, 특정 제품의 판매 반응
- 협업: 다른 브랜드·IP·작가·디자이너·구단과 함께 만든 상품이나 프로젝트 (협업 컬렉션은 제품 출시보다 우선)
- 할인·행사: 할인 행사, 프로모션, 팝업, 워크숍, 응원 이벤트, 행사 협찬
- 실적·사업: 매출·실적·재무, 매장 출점·리뉴얼, 가격 정책, 해외 진출, 사업 전략
- 기타: 여러 브랜드를 묶은 소비 트렌드 기사, 사회공헌, 사고, 수상·평가, 인물·채용 등

TOPICS는 분석용 CSV의 행 순서(2026-10-31 생성본)대로 붙인 주제 코드이며,
분석용 CSV가 바뀌면 URL_MD5 검사가 실패하므로 다시 분류해야 한다.
"""
import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
SRC = DIR / "SPA_브랜드_뉴스_분석용.csv"
OUT = DIR / "SPA_브랜드_뉴스_주제분류.csv"

NAMES = {"P": "제품 출시", "C": "협업", "E": "할인·행사", "B": "실적·사업", "O": "기타"}
TOPICS = (
    # 유니클로 1~50
    "OOBBOBOOBC" "BOOOBBBEOC" "OCBOBBOEOB" "OCBOPBCOBB" "BCPBOBOOBB"
    # 스파오 51~100
    "CEEBPOBOPP" "OCOOPBPPCB" "PPBBPOBBBC" "BBBBBBOCBO" "OEPCBPOPEC"
    # 탑텐 101~150
    "BBEPOPEPOO" "POOPOPPPPE" "OBOBPBPOBP" "OPPBPBBBBC" "BBPPBOPPBB"
)
URL_MD5 = "b5d58761a7ba9d0a2b13debfbbdf2f6f"

rows = list(csv.DictReader(SRC.open(encoding="utf-8-sig")))
digest = hashlib.md5("\n".join(r["원문 링크"] for r in rows).encode()).hexdigest()
if URL_MD5 and digest != URL_MD5:
    sys.exit(f"분석용 CSV가 분류 당시와 다릅니다 ({digest}). 주제를 다시 분류해야 합니다.")
assert len(rows) == len(TOPICS), (len(rows), len(TOPICS))

with OUT.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["브랜드", "주제"] + [k for k in rows[0] if k != "브랜드"])
    w.writeheader()
    for r, code in zip(rows, TOPICS):
        w.writerow({**r, "주제": NAMES[code]})

order = list(NAMES.values())
cnt = Counter((r["브랜드"], NAMES[c]) for r, c in zip(rows, TOPICS))
vol = Counter()
for r, c in zip(rows, TOPICS):
    vol[(r["브랜드"], NAMES[c])] += int(r["같은 이슈 보도 수"])
for title, table in [("기사 수", cnt), ("보도량 (같은 이슈 보도 수 합계)", vol)]:
    print(f"\n[{title}]")
    print("브랜드".ljust(6) + "".join(t.rjust(8) for t in order))
    for b in ["유니클로", "스파오", "탑텐"]:
        print(b.ljust(6) + "".join(str(table[(b, t)]).rjust(10) for t in order))
print("\nURL_MD5:", digest)
print(OUT)
