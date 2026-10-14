# Amazon-Tracker
Amazon bestseller tracker — K-beauty 5개국 Top100 + US 카테고리 스캔

프로젝트 목표·원칙·구조는 [CLAUDE.md](CLAUDE.md)를 본다.

## 1단계: 차단 테스트

미국 베스트셀러 20페이지(10개 카테고리 × pg=1,2, `config/block_test_urls.json`)를
requests / curl_cffi / Playwright 세 방식으로 받아 보고 결과를 표로 출력한다.

### 로컬 (회사 PC 등)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   /   macOS·Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

python -m tools.block_test --label company-pc
```

자주 쓰는 옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--methods` | `requests,curl_cffi,playwright` | 테스트할 방식 |
| `--limit` | `20` | 방식마다 요청할 페이지 수 |
| `--delay-min` / `--delay-max` | `3` / `8` | 요청 간 랜덤 딜레이(초) |
| `--cooldown` | `30` | 방식 사이 대기(초) |
| `--stop-after` | `3` | 연속 차단이 이 횟수면 그 방식 중단 (0 = 끝까지) |
| `--shuffle` | 꺼짐 | 방식마다 페이지 순서 섞기 |
| `--headed` | 꺼짐 | Playwright 브라우저 창 띄우기 |
| `--save-html` | `failures` | HTML 저장: none / failures(실패 전부 + 성공 1개) / all |

결과는 `reports/block_test/{KST시각}_{label}/`에 저장된다 (git 제외).
`summary.md`(표), `results.json`(요청별 기록), `html/`(파서 확인용 원본).

여러 번 돌린 결과를 한 표로 합치기:

```bash
python -m tools.block_test_report reports/block_test/*/results.json
```

### GitHub Actions

Actions 탭 → **block-test** → **Run workflow**. 방식마다 별도 러너(다른 IP)에서 돌고,
실행 요약(Summary)에 합계 표가 나온다. 원본은 artifact `block-test-*`로 받는다.

### 테스트

```bash
pip install -r requirements-dev.txt
python -m pytest
```

# 수집 응답 검증 및 재시도

- HTTP 200만으로 정상 수집을 판정하지 않는다. 페이지별 50개 상품과 해당 순위 범위
  (1페이지 1~50위, 2페이지 51~100위), 추천 목록의 ASIN별 순위 일치를 확인한다.
- 차단 없는 빈 응답·통신 오류·불완전 렌더는 기본 최대 3회 요청한다.
  요청 간 기본 3~8초, 두 번째 재시도는 6~16초 대기한다.
  마지막 1페이지 재시도에서는 `pg=1`을 명시한 베스트셀러 경로를 사용한다.
  독일은 기본 첫 요청부터 `pg=1`을 명시한다.
- CAPTCHA(현지어 버튼형 `/errors_page/validateCaptcha` 포함), 503, 403, 429는
  재시도와 다음 페이지 요청을 멈춘다. CAPTCHA 버튼 제출·세션 교체로 차단을 우회하지 않는다.
- `pages[].attempts`에 각 요청의 URL·시각·상태·크기·파싱 개수·완전 여부를 기록한다.
  한 페이지에는 한 응답만 채택한다. 실패 HTML은 시도별 파일로 `reports/`에 저장한다.
- `partial`/`failed`는 0이 아닌 `null`로 취급하며, 국가가 하나라도 불완전하면
  전체 합계·전체 순위·전체 증감을 제외하는 기존 기준을 유지한다.
  과거 날짜 자료를 현재 수집으로 채우지 않는다. 정상 스냅샷 보호 로직도 유지한다.
- 매일 09:07 KST 기본 수집 이후 09:37·10:07 KST에 오늘 불완전한 국가만 다시 수집한다.
  이미 정상인 국가는 요청부터 생략한다. 각 실행에서 차단되면 즉시 중단한다.
  같은 날 복구되면 이전 실패 스냅샷은 `.attempt-*` 파일로 보존한다.
  복구 실행에서는 브랜드 상세 조회를 반복하지 않는다. Actions 시작 시간은 지연될 수 있다.

2026-10-13 DE·FR 실패 원인은 Actions의 `collect-html` artifact에서 확인한 버튼형
로봇 확인 페이지다. 기존 감지기는 `/errors/validateCaptcha`와 영어 문구만 확인해
새 경로를 `parse_fail`로 잘못 분류했다. 위 처리는 차단을 정확히 기록하고 일시 오류를
안전하게 재시도하며, 아마존이 계속 차단할 경우 수집 성공을 보장하지 않는다.

