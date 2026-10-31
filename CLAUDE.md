# Naver API HUB 분석실습

## 폴더 구조

```
data/raw/          API 원본 응답(JSON). 저장 후 수정하지 않는다
data/processed/    정리·정제한 데이터(CSV)
src/               수집·정제 스크립트 (api_test.py의 call()로 API 호출)
notebooks/         탐색·분석용 노트북
reports/figures/   차트·결과물
app/               Streamlit 대시보드 (data/processed, reports/figures를 읽음)
.env               API 키 (루트에 둔다)
```

대시보드 실행: `python -m streamlit run app/dashboard.py` (설정: `.claude/launch.json`의 `dashboard`, 테마: `.streamlit/config.toml`)

## 데이터 저장 규칙

- API 원본 응답은 `data/raw/`에, 수집해서 정리한 데이터 파일(CSV 등)은 모두 `data/processed/`에 저장한다. 프로젝트 루트에 두지 않는다.
- 수집·정제에 쓴 스크립트는 다시 실행할 수 있도록 `src/`에 둔다.
