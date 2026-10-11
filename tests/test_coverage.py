from build.brands import build_brands, BrandResolver, COUNTRY_ORDER
from build.build_site import build_kbeauty
from scraper.brands import load_companies

def records():
    return {day:{cc:{'status':('partial' if day=='2026-10-10' and cc=='US' else 'ok'),
        'collected_at':day+'T09:00:00+09:00','items':[{'asin':'A','title':'medicube pad','rank':1}]}
        for cc in COUNTRY_ORDER} for day in ['2026-10-09','2026-10-10','2026-10-11']}

def test_incomplete_country_never_creates_total_or_rank():
    r=BrandResolver({'aliases':{'Medicube':['medicube']},'kbeauty':[]},{})
    out=build_brands(records(),[],r)
    assert out['series']['Medicube']['values']['total']==[6,None,6]
    assert out['series']['Medicube']['values']['US']==[1,None,1]
    assert out['ranks']['total'][1]==[]
    assert out['points'][1]['coverage']['incomplete']==['US']

def test_kbeauty_gaps_do_not_become_declines_or_daily_changes():
    out=build_kbeauty(records(),load_companies(),{})
    assert out['days']['2026-10-10']['grand_total'] is None
    assert out['days']['2026-10-10']['company_totals']['apr'] is None
    assert out['days']['2026-10-11']['grand_total']==6
    assert out['days']['2026-10-11']['grand_total_delta'] is None
    assert out['days']['2026-10-11']['countries']['US']['delta'] is None
