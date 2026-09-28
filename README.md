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
