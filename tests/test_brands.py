from scraper.brands import load_companies, match_company

C = load_companies()


def company_id(title):
    c = match_company(title, C)
    return c.id if c else None


def test_matches():
    assert company_id("medicube Zero Pore Pads 2.0") == "apr"
    assert company_id("MEDICUBE AGE-R Booster Pro") == "apr"
    assert company_id("d'Alba Italian White Truffle First Spray Serum") == "dalba"
    assert company_id("d’Alba Mist") == "dalba"
    assert company_id("dAlba Waterfull Sunscreen") == "dalba"
    assert company_id("COSRX Snail Mucin 96% Power Repairing Essence") == "cosrx"
    assert company_id("Anua Heartleaf 77% Soothing Toner") == "anua"
    assert company_id("Beauty of Joseon Relief Sun : Rice + Probiotics") == "joseon"


def test_no_false_positives():
    assert company_id("CeraVe Moisturizing Cream") is None
    assert company_id("Guanua Herbal Tea") is None
    assert company_id("Vidalba cream") is None
    assert company_id(None) is None
