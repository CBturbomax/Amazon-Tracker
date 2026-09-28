"""응답이 차단(CAPTCHA·503)인지, 정상인지 판정한다."""

from __future__ import annotations

# 아마존 로봇 확인 페이지에 나오는 표식들 (소문자로 비교).
CAPTCHA_MARKERS = (
    "/errors/validatecaptcha",
    "type the characters you see in this image",
    "enter the characters you see below",
    "sorry, we just need to make sure you're not a robot",
    "opfcaptcha",
    # 2024년 이후 나오는 "Continue shopping" 버튼형 로봇 확인 페이지
    "click the button below to continue shopping",
)

# 503과 함께 오는 "강아지" 오류 페이지.
SERVICE_ERROR_MARKERS = (
    "sorry! something went wrong",
    "we're sorry, an error occurred",
)

OUTCOMES = ("ok", "captcha", "http_503", "http_other", "parse_fail", "error", "skipped")


def detect_block(status: int | None, html: str) -> str | None:
    """차단이면 "captcha" 또는 "http_503", 아니면 None."""
    text = (html or "").lower()
    if any(m in text for m in CAPTCHA_MARKERS):
        return "captcha"
    if status == 503:
        return "http_503"
    if status in (200, None) and len(text) < 20000 and any(m in text for m in SERVICE_ERROR_MARKERS):
        # 상태 코드는 200인데 본문이 오류 페이지인 경우
        return "http_503"
    return None


def classify(status: int | None, block: str | None, error: str | None, parsed_count: int) -> str:
    """한 번의 요청 결과를 OUTCOMES 중 하나로 분류한다."""
    if error:
        return "error"
    if block:
        return block
    if status != 200:
        return "http_other"
    if parsed_count == 0:
        return "parse_fail"
    return "ok"
