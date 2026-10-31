# SPA 3사 경쟁 모니터링 대시보드

네이버 API HUB(뉴스 검색·검색어 트렌드)로 **유니클로·스파오·탑텐**의 뉴스와 검색 관심도를 수집·분석하고, 브랜드 마케터가 경쟁 상황을 점검할 수 있게 만든 Streamlit 대시보드입니다.

## 대시보드 구성

사이드바에서 **기준 브랜드**를 고르면 그 브랜드의 톤앤매너(색·서체·태그라인)로 화면이 바뀌고, 나머지 두 브랜드는 경쟁사로 비교됩니다.

| 순서 | 탭 | 보는 것 |
|---|---|---|
| ① | 요약·경보 | 핵심 KPI 4개, 자동 경보, 3사 스코어카드, 이번 점검의 핵심 |
| ② | 관심도 (검색) | 검색 점유율(SOS) 추이, 검색 모멘텀(YoY), 계절성, 행사 의존도 |
| ③ | 화제성 (뉴스) | 보도 점유율(SOV) vs SOS, 보도 주제·감성 구성, 리스크 기사 |
| ④ | 브랜드 인식 | 연상 속성 히트맵, 경쟁사 대비 차이, 차별 키워드(TF-IDF) |
| ⑤ | 타깃 | 연령·성별·기기별 점유율 지수 |
| ⑥ | 지표 사전 | 지표 산식·기간·판단 기준, 한계, 데이터 갱신 절차 |

평가 기준과 검증 결과는 [reports/대시보드_평가.md](reports/대시보드_평가.md)에 있습니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app/dashboard.py
```

## Streamlit Community Cloud 배포

1. https://share.streamlit.io 에서 **Create app** → **Deploy a public app from GitHub**
2. Repository `kxxjxxs1217/naver_dashboard`, Branch `main`, Main file path **`app/dashboard.py`**
3. Deploy

대시보드는 저장소에 포함된 `data/processed/`와 `reports/figures/wordcloud/`만 읽으므로 API 키(Secrets)가 필요 없습니다. 패키지는 루트의 `requirements.txt`, 테마는 `.streamlit/config.toml`을 사용합니다.

## 데이터 갱신 (로컬)

수집 스크립트는 루트의 `.env`에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`가 있어야 합니다 (저장소에는 포함하지 않음).

```bash
pip install -r requirements-analysis.txt
python src/collect_spa_news.py            # 1. 최신 뉴스 수집 (data/raw)
python src/build_spa_news_csv.py          # 2. CSV 정리
python src/clean_spa_news.py              # 3. 무관·중복 제거 (판단 목록은 수집일 기준, 재검토 필요)
python src/build_spa_news_analysis.py     # 4. 브랜드별 50건 분석용 데이터
python src/classify_spa_news_topics.py    # 5. 주제 분류
python src/keyword_wordcloud.py           # 6. BoW·TF-IDF 키워드, 워드클라우드
python src/search_trend_analysis.py       # 7. 검색어 트렌드 (data/raw/search_trend.json 삭제 시 재수집)
python src/marketing_metrics.py           # 8. 마케터 지표·감성·연상 속성
```

## 폴더 구조

```
app/               Streamlit 대시보드
src/               수집·정제·분석 스크립트
data/raw/          API 원본 응답 (JSON)
data/processed/    정제·분석 결과 (CSV)
reports/           차트, 워드클라우드, 대시보드 평가 문서
.streamlit/        Streamlit 테마 설정
```

## 해석 시 주의

- 검색어 트렌드는 요청마다 최댓값 = 100인 상대값이라 같은 요청 안의 3사 비교만 유효합니다.
- '탑텐'은 일반어(톱10)와 겹쳐 검색량이 크게 잡혔을 수 있습니다.
- 감성·연상 속성은 사전 기반 규칙이며, 브랜드 톤앤매너는 분석에서 도출한 해석으로 각 사의 공식 가이드가 아닙니다.
