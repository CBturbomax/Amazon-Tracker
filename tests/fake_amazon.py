"""테스트용 가짜 베스트셀러 페이지.

실제 아마존 마크업 구조(#gridItemRoot, .zg-bdg-text, data-client-recs-list 등)를 흉내 낸다.
`lazy=True`면 처음 30개만 렌더하고 스크롤하면 나머지를 JS로 붙인다 (Playwright 스크롤 검증용).
"""

from __future__ import annotations

import json


def asin(i: int) -> str:
    return f"B0TEST{i:04d}"


def item_html(rank: int) -> str:
    a = asin(rank)
    return f"""
<div id="gridItemRoot" class="a-column a-span12 a-text-center _cDEzb_grid-column_2hIsc">
  <div class="zg-grid-general-faceout">
    <div class="a-cardui _cDEzb_grid-cell_1uMOS">
      <div class="zg-bdg-ctr"><span class="zg-bdg-text">#{rank}</span></div>
      <div id="{a}" data-asin="{a}" class="p13n-sc-uncoverable-faceout">
        <a class="a-link-normal aok-block" href="/Test-Product-{rank}/dp/{a}/ref=zg_bs_g_beauty_d_sccl_{rank}">
          <img alt="Test Product {rank} Serum 50ml" src="x.jpg">
        </a>
        <a class="a-link-normal aok-block" href="/Test-Product-{rank}/dp/{a}/ref=zg_bs_g_beauty_d_sccl_{rank}">
          <span><div class="_cDEzb_p13n-sc-css-line-clamp-3_g3dy1">medicube Test Product {rank} Serum 50ml</div></span>
        </a>
        <div class="a-icon-row">
          <a class="a-link-normal" title="4.{rank % 10} out of 5 stars, {rank * 1000:,} ratings"
             href="/product-reviews/{a}/ref=zg_bs_g_beauty_d_cr_{rank}">
            <i class="a-icon a-icon-star-small a-star-small-4-5 aok-align-top">
              <span class="a-icon-alt">4.{rank % 10} out of 5 stars</span></i>
            <span class="a-size-small">{rank * 1000:,}</span>
          </a>
        </div>
        <div class="a-row"><a class="a-link-normal a-text-normal" href="/dp/{a}">
          <span class="a-size-base a-color-price"><span class="_cDEzb_p13n-sc-price_3mJ9Z">${rank + 0.99:.2f}</span></span>
        </a></div>
      </div>
    </div>
  </div>
</div>"""


def bestseller_page(n_rendered: int = 30, n_total: int = 50, lazy: bool = False) -> str:
    recs = [{"id": asin(i), "metadataMap": {"render.zg.rank": str(i), "render.zg.bsms.percentageChange": ""},
             "linkParameters": {}} for i in range(1, n_total + 1)]
    recs_attr = json.dumps(recs).replace('"', "&quot;")
    first = "".join(item_html(i) for i in range(1, n_rendered + 1))
    script = ""
    if lazy:
        rest = json.dumps([item_html(i) for i in range(n_rendered + 1, n_total + 1)])
        script = f"""
<script>
  const rest = {rest};
  let loaded = false;
  window.addEventListener('scroll', () => {{
    if (loaded || window.scrollY < 200) return;
    loaded = true;
    setTimeout(() => {{
      document.querySelector('.p13n-gridRow').insertAdjacentHTML('beforeend', rest.join(''));
    }}, 300);
  }});
</script>"""
    return f"""<!doctype html><html><head><title>Amazon.com Best Sellers: Best Beauty</title></head>
<body>
<div class="p13n-desktop-grid" data-client-recs-list="{recs_attr}">
  <div class="p13n-gridRow _cDEzb_grid-row_3Cywl" style="min-height:4000px">{first}</div>
</div>
<div style="height:3000px"></div>
{script}
</body></html>"""


CAPTCHA_PAGE = """<!doctype html><html><head><title>Amazon.com</title></head><body>
<h4>Enter the characters you see below</h4>
<p class="a-last">Sorry, we just need to make sure you're not a robot.</p>
<form method="get" action="/errors/validateCaptcha" name="">
<input type="text" id="captchacharacters" name="field-keywords"></form>
</body></html>"""

DOG_503_PAGE = """<!doctype html><html><head><title>Sorry! Something went wrong!</title></head><body>
<a href="/ref=cs_503_logo"><img alt="Amazon.com"></a>
<b>Sorry! Something went wrong on our end.</b></body></html>"""
