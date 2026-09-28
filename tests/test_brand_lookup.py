from scraper.brand_lookup import parse_brand


def test_po_brand_row():
    html = """<table><tr class="a-spacing-small po-brand"><td class="a-span3"><span>Brand</span></td>
    <td class="a-span9"><span class="a-size-base po-break-word">La Roche-Posay</span></td></tr></table>
    <a id="bylineInfo">Visit the LRP Store</a>"""
    assert parse_brand(html) == ("La Roche-Posay", "po-brand")


def test_byline_variants():
    assert parse_brand('<a id="bylineInfo">Visit the medicube Store</a>') == ("medicube", "byline")
    assert parse_brand('<a id="bylineInfo">Besuche den CeraVe-Store</a>') == ("CeraVe", "byline")
    assert parse_brand('<a id="bylineInfo">Visiter la boutique Garnier</a>') == ("Garnier", "byline")
    assert parse_brand('<a id="bylineInfo">Visita la tienda de ISDIN</a>') == ("ISDIN", "byline")
    assert parse_brand('<a id="bylineInfo">Visita lo Store di Rilastil</a>') == ("Rilastil", "byline")
    assert parse_brand('<a id="bylineInfo">Brand: Amazon Basics</a>') == ("Amazon Basics", "byline")


def test_missing():
    assert parse_brand("<html></html>") == (None, None)
