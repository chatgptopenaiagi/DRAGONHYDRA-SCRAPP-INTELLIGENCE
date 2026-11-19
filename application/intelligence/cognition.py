"""A deliberately limited, inspectable multilingual baseline, not calibrated prediction."""
import re
from decimal import Decimal
from dragonhydra.domain import identity
from .model import now

WORDS={
 'en':({'good','great','excellent','love','happy','reliable','wonderful'},{'bad','awful','hate','poor','terrible','broken','unreliable'},{'not','never','no'}),
 'ro':({'bun','bună','excelent','iubesc','fericit','minunat'},{'rău','rea','groaznic','urăsc','slab','defect'},{'nu','niciodată'}),
 'de':({'gut','toll','ausgezeichnet','liebe','glücklich','zuverlässig'},{'schlecht','furchtbar','hasse','kaputt','unzuverlässig'},{'nicht','nie','kein'})}

def interpret(row):
    text=row.get('text') or '';language=row.get('metadata',{}).get('language','unknown')
    tokens=re.findall(r'\w+',text.casefold(),re.UNICODE);scores=[];uncertainty=[]
    if language not in WORDS:uncertainty.append('Language unsupported or not supplied')
    else:
        positive,negative,negators=WORDS[language]
        for i,word in enumerate(tokens):
            score=1 if word in positive else -1 if word in negative else 0
            if score and any(w in negators for w in tokens[max(0,i-3):i]):score=-score
            if score:scores.append(score)
    if any(c in text for c in ('"','“','”','«','»')) or row.get('metadata',{}).get('quoted'):
        uncertainty.append('Quoted sentiment is not assigned to the author')
    if any(w in tokens for w in ('maybe','perhaps','poate','vielleicht')) or '/s' in text or '🙄' in text:
        uncertainty.append('Uncertainty or possible sarcasm; baseline cannot resolve intent')
    result='mixed' if 1 in scores and -1 in scores else 'positive' if sum(scores)>0 else 'negative' if sum(scores)<0 else 'neutral'
    if uncertainty:result='uncertain'
    strength=str(Decimal(abs(sum(scores)))/Decimal(max(1,len(scores)))) if not uncertainty else '0'
    interpreted_at=row['received_at'] if row['origin']=='synthetic' else now()
    return dict(id=identity('interpretation',row['id'],'lexicon/1'),observation_id=row['id'],label=result,strength=strength,language=language,uncertainty=uncertainty,engine_version='lexicon/1',interpreted_at=interpreted_at,origin=row['origin'],status='rule_interpretation',topic=row.get('metadata',{}).get('topic','unspecified'),entities=row.get('metadata',{}).get('confirmed_entities',[]),scope='Lexicon signal; no claim about population sentiment, author intent or sporting outcomes')

def trend(values):
    nums=[Decimal(str(v)) for v in values]
    if len(nums)<2:return {'status':'insufficient_history'}
    mean=sum(nums[:-1])/len(nums[:-1]);delta=nums[-1]-nums[-2]
    return {'status':'deterministic_calculation','change':str(delta),'previous_mean':str(mean),'relative_change':str(delta/abs(nums[-2])) if nums[-2] else None,'anomaly':'review' if mean and abs(nums[-1]-mean)>abs(mean)*Decimal('.5') else 'none','causality':'not_established'}
