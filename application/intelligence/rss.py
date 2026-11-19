"""Bounded RSS/Atom text extraction; no entity expansion or implicit authorship."""
import hashlib
from xml.etree import ElementTree
from email.utils import parsedate_to_datetime
from .model import normalize,stamp
from .acquisition import SchemaMismatch

def parse_feed(body,source,received_at):
    if len(body)>2_000_000 or b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():raise SchemaMismatch('Unsafe or oversized XML feed')
    try:root=ElementTree.fromstring(body)
    except ElementTree.ParseError:raise SchemaMismatch('Malformed XML feed') from None
    ns='{http://www.w3.org/2005/Atom}'
    if root.tag=='rss':entries=root.findall('./channel/item');atom=False
    elif root.tag==ns+'feed':entries=root.findall(ns+'entry');atom=True
    else:raise SchemaMismatch('Expected RSS or Atom feed')
    if not 1<=len(entries)<=250:raise SchemaMismatch('Empty or oversized feed entry list')
    rows=[]
    for item in entries:
        title=item.findtext((ns if atom else '')+'title')
        if not title or len(title)>4000:raise SchemaMismatch('Missing or oversized feed title')
        publication=item.findtext(ns+'published') or item.findtext(ns+'updated') if atom else item.findtext('pubDate')
        if publication:
            try:publication=stamp(publication) if atom else stamp(parsedate_to_datetime(publication).isoformat())
            except (ValueError,TypeError):raise SchemaMismatch('Malformed publication timestamp') from None
        uid=item.findtext(ns+'id' if atom else 'guid') or title
        rows.append(normalize({'source_id':source['id'],'source_url':source['url'],'key':'feed:'+hashlib.sha256(uid.encode()).hexdigest(),'kind':'SHORT_TEXT','text':title,'published_at':publication,'metadata':{'language':source.get('language','unknown'),'quoted':True,'context':'Feed headline; no author sentiment attribution'}},origin='observed',received_at=received_at))
    return rows
