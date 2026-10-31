"""NAVER API HUB 연동 테스트: 검색 / 검색어 트렌드 / 쇼핑 인사이트 전체 API를 한 번씩 호출한다."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://naverapihub.apigw.ntruss.com"


def load_env(path=Path(__file__).resolve().parent.parent / ".env"):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = load_env()
HEADERS = {
    "X-NCP-APIGW-API-KEY-ID": ENV["NAVER_CLIENT_ID"],
    "X-NCP-APIGW-API-KEY": ENV["NAVER_CLIENT_SECRET"],
}


def call(method, path, params=None, body=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = dict(HEADERS)
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw


def summarize(data):
    """응답에서 핵심만 한 줄로 요약한다."""
    if not isinstance(data, dict):
        return str(data)[:150]
    if "items" in data:
        items = data["items"]
        first = items[0].get("title", "") if items else ""
        return f"total={data.get('total')}, items={len(items)}, 첫 결과: {first[:60]}"
    if "results" in data:
        parts = []
        for r in data["results"]:
            pts = r.get("data", [])
            last = f"{pts[-1].get('period')} ratio={pts[-1].get('ratio')}" if pts else "데이터 없음"
            parts.append(f"[{r.get('title')}] {len(pts)}개 구간, 마지막 {last}")
        return " / ".join(parts)
    return json.dumps(data, ensure_ascii=False)[:150]


# --- 테스트 목록 ---------------------------------------------------------
Q = "커피"
SEARCH = [
    ("뉴스", "/search/v1/news", {"query": Q, "display": 3, "sort": "date"}),
    ("백과사전", "/search/v1/encyc", {"query": Q, "display": 3}),
    ("블로그", "/search/v1/blog", {"query": Q, "display": 3}),
    ("성인 검색어 판별", "/search/v1/adult", {"query": Q}),
    ("오타 변환", "/search/v1/errata", {"query": "zjvl"}),
    ("웹 문서", "/search/v1/webkr", {"query": Q, "display": 3}),
    ("이미지", "/search/v1/image", {"query": Q, "display": 3}),
    ("지식iN", "/search/v1/kin", {"query": Q, "display": 3}),
    ("지역", "/search/v1/local", {"query": "강남역 카페", "display": 5}),
    ("카페글", "/search/v1/cafearticle", {"query": Q, "display": 3}),
]

PERIOD = {"startDate": "2026-04-01", "endDate": "2026-09-30", "timeUnit": "month"}
CAT = "50000000"  # 패션의류

TREND = [
    ("검색어 트렌드", "/search-trend/v1/search", {
        **PERIOD,
        "keywordGroups": [
            {"groupName": "커피", "keywords": ["커피", "아메리카노"]},
            {"groupName": "차", "keywords": ["녹차", "홍차"]},
        ],
    }),
]

SHOPPING = [
    ("분야별 트렌드", "/shopping/v1/categories", {
        **PERIOD,
        "category": [
            {"name": "패션의류", "param": ["50000000"]},
            {"name": "화장품/미용", "param": ["50000002"]},
        ],
    }),
    ("기기별 트렌드", "/shopping/v1/category/device", {**PERIOD, "category": CAT}),
    ("성별 트렌드", "/shopping/v1/category/gender", {**PERIOD, "category": CAT}),
    ("연령별 트렌드", "/shopping/v1/category/age", {**PERIOD, "category": CAT}),
    ("키워드별 트렌드", "/shopping/v1/category/keywords", {
        **PERIOD, "category": CAT,
        "keyword": [{"name": "정장", "param": ["정장"]}, {"name": "패딩", "param": ["패딩"]}],
    }),
    ("키워드 기기별", "/shopping/v1/category/keyword/device", {**PERIOD, "category": CAT, "keyword": "패딩"}),
    ("키워드 성별", "/shopping/v1/category/keyword/gender", {**PERIOD, "category": CAT, "keyword": "패딩"}),
    ("키워드 연령별", "/shopping/v1/category/keyword/age", {**PERIOD, "category": CAT, "keyword": "패딩"}),
]


def run(group, tests, method):
    print(f"\n=== {group} ===")
    ok = 0
    for name, path, payload in tests:
        if method == "GET":
            status, data = call("GET", path, params=payload)
        else:
            status, data = call("POST", path, body=payload)
        mark = "OK " if status == 200 else "ERR"
        ok += status == 200
        print(f"{mark} {status} {name:<12} {path}\n      {summarize(data)}")
    return ok, len(tests)


if __name__ == "__main__":
    total_ok = total = 0
    for group, tests, method in [
        ("검색", SEARCH, "GET"),
        ("검색어 트렌드", TREND, "POST"),
        ("쇼핑 인사이트", SHOPPING, "POST"),
    ]:
        o, n = run(group, tests, method)
        total_ok += o
        total += n
    print(f"\n성공 {total_ok}/{total}")
