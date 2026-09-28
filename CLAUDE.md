# CLAUDE.md — amazon-tracker

아마존 베스트셀러를 매일 자동으로 수집해서 GitHub Pages 정적 사이트
(https://cbturbomax.github.io/amazon-tracker)로 변화를 보여준다.
**알림 봇은 없다. 웹사이트가 유일한 출력이다.**

- **레이어 1 (모니터링)**: K뷰티 회사별로 5개국 Beauty Top 100 안에 든 제품 수와 제품별 순위를 추적한다.
- **레이어 2 (발굴)**: 미국 베스트셀러 여러 카테고리를 넓게 훑어서, 주간 단위로 순위가 급등하거나 평점 수가 급증한 소비재를 찾는다.

---

## 핵심 원칙 (어기지 말 것)

1. **숫자는 코드가 원자료에서 붙인다.** Claude API는 후보 선정과 이유 서술만 한다.
   Claude 응답에 들어 있는 숫자(순위, 가격, 평점, 증가율 등)는 절대 쓰지 않는다.
   화면에 나오는 숫자는 모두 `data/` 원자료나 분석 코드의 계산값에서 가져온다.
   Claude에게는 ASIN(키)을 돌려받고, 숫자는 코드가 그 ASIN으로 다시 조인한다.
2. **수집은 매일, 해석은 주간.** 매일은 원자료 스냅샷만 저장한다. 발굴 분석과 Claude 호출은 매주 월요일에 한 번 한다.
3. **API 키는 코드에 넣지 않는다.** 로컬은 `.env`(git 무시됨), Actions는 GitHub Secrets를 쓴다.
   키가 로그, 커밋, `docs/`에 새어 나가지 않게 한다.
4. **수집 시각은 매일 같은 KST 시각으로 고정한다.** 모든 타임스탬프는 KST(`Asia/Seoul`, UTC+9)로 저장한다.
   Actions cron은 UTC 기준이므로 변환해서 쓴다. (정확한 시각은 1단계 후 정한다.)
5. **원자료는 날짜별 스냅샷으로 보존한다.** 한 번 저장한 스냅샷은 덮어쓰거나 가공하지 않는다.
   분석 로직이 바뀌어도 과거 원자료로 다시 계산할 수 있어야 한다.
   파싱된 필드뿐 아니라 재파싱에 필요한 정보(URL, 수집 시각, 수집 방식, HTTP 상태)도 같이 남긴다.
6. **사이트는 서버 없는 정적 사이트다.** `build/` 스크립트가 원자료로 `docs/data/*.json`을 만들고,
   `docs/index.html`은 그 JSON만 읽어서 그린다. 페이지 안에서 계산을 새로 만들지 않는다.

---

## 디렉터리 구조

```
data/                    원자료 스냅샷 (절대 덮어쓰지 않음)
  kbeauty/               레이어 1: {국가}/{YYYY-MM-DD}.json
  us_scan/               레이어 2: {YYYY-MM-DD}.json (카테고리별 상위 50)
  details/               레이어 2 후보 상세 페이지: {YYYY-MM-DD}.json
  weekly/                주간 분석 결과 + Claude 선정 결과 (주차별)
config/
  brands.json            브랜드 → 회사 매핑 (정규식, 대소문자 무시)
  products.json          ASIN → 한글 제품명
  categories.json        레이어 2 관심 카테고리 목록
scraper/                 수집 (fetcher 인터페이스 + 파서)
analysis/                일별 집계, 주간 분석, Claude 선정
build/                   원자료 → docs/data/*.json 생성
docs/                    GitHub Pages 루트 (index.html + data/)
```

```
tools/                   일회성·진단 스크립트 (block_test.py 등)
tests/                   pytest (fake_amazon.py = 가짜 베스트셀러 HTML)
reports/                 로컬 실행 결과 (git 제외, data/와 섞지 않음)
```

> `.gitignore`의 Python 템플릿 중 `build/` 줄은 지웠다. 우리 `build/` 폴더는 커밋 대상이다.

---

## 레이어 1: K뷰티 모니터링

- **국가**: US(amazon.com), UK(amazon.co.uk), DE(amazon.de), FR(amazon.fr), ES(amazon.es)
- **페이지**: `/gp/bestsellers/beauty`, `pg=1`과 `pg=2` (페이지당 50개, 합계 100개)
- **스크롤 주의**: 첫 로딩에는 30개만 렌더된다. 스크롤(또는 lazy-load 요청)로 50개를 전부 불러와야 한다.
  파싱 결과가 페이지당 50개가 아니면 실패/부분 수집으로 기록한다.
- **수집 필드**: 순위, ASIN, 제품명, 가격, 평점, 평점 수
- **브랜드 매핑** (`config/brands.json`): 대소문자 무시, 정규식 매칭, 회사와 패턴을 계속 추가할 수 있는 구조.

  | 회사 | 패턴 |
  |---|---|
  | 에이피알 | `medicube`, `AGE-R` |
  | 달바글로벌 | `d'Alba`, `dAlba` |
  | 코스알엑스 | `COSRX` |
  | 아누아 | `Anua` |
  | 조선미녀 | `Beauty of Joseon` |

- **한글 제품명** (`config/products.json`): ASIN → 한글명.
  - 미등록 ASIN은 Claude API로 초안을 만들고 `needs_review: true`를 붙인다. 사람이 확인하면 `false`로 바꾼다.
  - 같은 제품도 국가마다 ASIN이 다를 수 있다. 여러 ASIN이 같은 한글명(제품)으로 묶일 수 있게 설계한다.
  - 실제로는 5개국이 대부분 같은 ASIN을 쓴다 (예: 제로모공패드 `B09V7Z4TJG`). products.json에 없는 제품은 ASIN 단위로 묶고 영문명을 보여준다.
  - 첫 수집에서 가격은 UK·DE도 USD로 나왔다 (러너가 미국 IP). 레이어 1은 가격을 쓰지 않지만, 레이어 2에서 쓸 때 주의.
  - 사람이 없으므로 한글명 초안은 Claude(이 세션 또는 API)가 쓰고 `needs_review: true`로 둔다.

## 레이어 2: 미국 발굴 스캔

- 미국 베스트셀러 카테고리 트리를 수집해서 관심 카테고리를 `config/categories.json`에 정리한다.
- **매일**: 카테고리별 상위 50위 수집 — 순위, ASIN, 제품명, 가격, 평점, 평점 수, 판매자 수.
  `brands.json`에 매칭되면 `is_kbeauty: true`.
- **주간 분석** (매주 월요일, 직전 7일):
  - 순위 변화 (신규 진입·이탈 포함)
  - 평점 수 증가: **절대값과 기존 대비 증가율 둘 다** 계산.
    변형 상품(variation) 합산과 Vine 리뷰로 생기는 왜곡을 보정한다.
  - 같은 날 같은 브랜드·카테고리 제품이 동시에 급등하면 `promo_suspect: true`
  - 상위 후보 약 40개를 뽑는다.
- **후보만** 상세 페이지를 추가 수집: 정가, 할인가, 쿠폰 배지, Deal 배지
- **Claude API**: 후보 표를 넘겨서 7개 선정 + 한 줄 이유 + "투자 관점 확인 포인트" 한 줄.
  응답은 JSON(ASIN + 텍스트)으로 받고, 숫자는 코드가 붙인다 (원칙 1).

---

## 웹사이트 (`docs/`)

**상단 공통**: 마지막 수집 시각(KST), 국가별 수집 성공/실패 표시.

**탭 1. K뷰티 오늘**
- 회사 × 국가 제품 수 표 + 합계 + 전일 대비 증감 (▲▼ 색 구분)
- 회사별 제품 순위 리스트 (예: 제로모공패드 — 미국 2위, 영국 1위, 독일 10위 …)
- 신규 진입 / 이탈 제품 하이라이트

**탭 2. K뷰티 추이**
- 회사별 Top 100 제품 수 일별 추이 (국가 선택)
- 제품 클릭 시 5개국 순위 추이 차트 (순위축 뒤집기, 1위가 위)
- 날짜 선택기로 과거 특정일 스냅샷 조회

**탭 3. 이번 주 발굴**
- Claude 선정 7개 카드: 제품명, 카테고리, 순위 변화, 평점 하루 증가, 할인 여부, 이유, 확인 포인트
- "할인으로 오른 것" 분리 섹션
- K뷰티 태그 제품 섹션
- 후보 40개 전체 표 (정렬·필터 가능)
- 지난 주차 리포트 아카이브

## 디자인 (고정 — 임의로 바꾸지 말 것)

- **폰트**: 42dot Sans. **공식 Google Fonts 링크로만** 로드한다.
  jsdelivr 등 다른 CDN 금지, fallback에 Pretendard 금지. `*` 선택자에 `font-family: inherit`.
- **색**: 배경 `#0f1419`. 텍스트는 항상 `#FFFFFF`로 하드코딩한다.
  검정 계열 텍스트 금지, `prefers-color-scheme` 등 다크모드 감지에 의존 금지.
- **팔레트**: `#FFCB05` / `#5B9BD5` / `#ED7D31`
- **차트**: SVG 우선. 엑셀 스타일 막대 + 꺾은선. 데이터 라벨 표시. **정수만** 표시.
- **글자 크기** (최소값):

  | 요소 | 크기 |
  |---|---|
  | 본문 | 20px |
  | 표 셀 | 19px |
  | 주석 | 17px |
  | h1 | 48px 이상 |
  | h2 | 32px 이상 |
  | KPI 숫자 | 54px 이상 |
  | SVG 데이터 라벨 | 26px 이상, bold 800 |
  | 축·범례 | 18px 이상 |

- **레이아웃**: 카드형, 각진 테크 느낌. 긴 글 대신 차트 + 1~3줄 요약. 문장은 짧고 쉽게.

---

## 실행 환경 — **A로 결정** (2026-09-28 차단 테스트)

Actions 러너에서 requests / curl_cffi / Playwright 모두 20/20 성공, CAPTCHA·503 0회.
requests·curl_cffi는 카드 30개만 받고, Playwright만 스크롤로 50개를 받는다 → **수집은 Actions + Playwright**.

- `.github/workflows/daily.yml`: 매일 **09:07 KST**(00:07 UTC) 수집 → `build/` → `data/`·`docs/data/`를 main에 커밋 → `docs/`를 `gh-pages` 브랜치로 배포.
  main에 `docs/index.html`·`build/`·`config/`가 바뀌면 수집 없이 빌드·배포만 한다.
- 사이트 주소: https://cbturbomax.github.io/Amazon-Tracker/ (Pages 소스 = `gh-pages` 브랜치 루트)
- 수집 원본 HTML은 git에 넣지 않는다 (하루 수십 MB). 불완전 수집 페이지만 Actions artifact(`collect-html`, 14일)로 남는다.

처음 비교했던 선택지:

| 옵션 | 내용 |
|---|---|
| A | 전부 GitHub Actions (수집 → 분석 → 빌드 → Pages 배포) |
| B | 회사 PC에서 PM2 cron으로 수집 → git push → Actions가 분석·빌드·배포 |
| C | 유료 API (Rainforest 또는 Keepa) 경유 |

**수집 방식이 바뀌어도 나머지 파이프라인은 그대로 돌아야 한다.**
- `scraper/`에 fetcher 인터페이스를 두고, 방식(requests / curl_cffi / Playwright / 유료 API)은 구현체로 교체한다.
- fetcher는 "URL → HTML(또는 API 응답) + 메타(상태 코드, 차단 여부, 소요 시간)"만 책임진다.
  파싱은 별도 파서가, 저장 형식은 공통 스냅샷 스키마가 맡는다.
- `analysis/`와 `build/`는 `data/` 스냅샷만 읽는다. 수집 방식을 몰라야 한다.

## 개발 순서

1. **차단 테스트** — 완료 (결과: A, Playwright)
   미국 베스트셀러 20개 페이지를 requests / curl_cffi(chrome 임퍼소네이션) / Playwright 세 방식으로 수집.
   요청 간 3~8초 랜덤 딜레이. 방식별 성공·CAPTCHA·503 비율과 페이지당 파싱 제품 수를 표로 출력.
   로컬 실행용 + GitHub Actions `workflow_dispatch`용 둘 다 만든다.
2. 결과로 실행 환경(A/B/C) 결정
3. 레이어 1: 5개국 수집 (`scraper/collect_kbeauty.py`) ← 현재 단계
4. 웹사이트 탭 1·2 + GitHub Pages 배포 (`docs/index.html`, `build/build_site.py`) ← 현재 단계
5. 레이어 2: 수집 → 주간 분석 → 상세 페이지 → Claude API 선정 → 탭 3

---

## 명령어

```bash
pip install -r requirements-dev.txt            # 의존성 + pytest
python -m playwright install chromium          # Playwright 브라우저
python -m pytest                               # 테스트 (네트워크 불필요)
python -m tools.block_test --label local       # 차단 테스트 (실제 amazon.com 요청)
python -m tools.block_test_report reports/block_test/*/results.json   # 결과 합치기
python -m scraper.collect_kbeauty              # 5개국 Beauty Top 100 → data/kbeauty/
python -m build.build_site                     # data/ → docs/data/*.json
```

- 모듈은 항상 레포 루트에서 `python -m ...`으로 실행한다.
- 설치된 Chromium을 쓰려면 `CHROMIUM_PATH` 환경변수로 실행 파일 경로를 준다.
- Claude Code 클라우드 세션은 네트워크 정책상 amazon.com에 접속하지 못할 수 있다.
  그때는 `tests/fake_amazon.py`로 만든 가짜 페이지(로컬 HTTP 서버)로 검증하고, 실제 테스트는 로컬/Actions에서 한다.

## 작업 규칙

- 언어: Python (수집·분석·빌드), 순수 HTML/CSS/JS + SVG (사이트). 사이트에 빌드 도구·프레임워크를 넣지 않는다.
- 스크래핑 예절: 요청 간 랜덤 딜레이(3~8초)를 기본으로 둔다. 차단 신호(CAPTCHA, 503)가 나오면 재시도를 늘리지 말고 기록하고 멈춘다.
- 실패는 숨기지 않는다. 국가·페이지별 성공/실패를 스냅샷에 남기고 사이트 상단에 보여준다.
  부분 수집 데이터를 정상 데이터처럼 집계하지 않는다.
- 비밀값: `ANTHROPIC_API_KEY` 등은 `.env` / GitHub Secrets에서 환경변수로만 읽는다.
- 커밋 전에 `docs/data/`에 원자료 전체나 비밀값이 섞이지 않았는지 확인한다.
