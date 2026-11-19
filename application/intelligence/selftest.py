"""Checks bundled runtime dependencies without touching a database or provider."""
def verify():
    import pyodbc
    from decimal import Decimal
    from .model import decimal_value,stamp
    from .acquisition import extract_field
    from .classification import classify
    assert decimal_value('0.1')+decimal_value('0.2')==Decimal('0.3')
    assert stamp('2026-07-01T14:00:00','Europe/Berlin')=='2026-07-01T12:00:00.000000Z'
    rule={'selector':'#value','field':'wind','unit':'m/s','min':'0','max':'100'}
    assert extract_field('<span id="value" data-field="wind" data-unit="m/s">4.5</span>',rule)=='4.5'
    assert classify('2.1')['kind']=='NUMBER'
    return {'status':'PASS','checks':['exact_decimal','bundled_timezone','HTML_extractor','conservative_classification','pyodbc_import'],'sql_connection':'NOT_TESTED','odbc_drivers':pyodbc.drivers()}
