"""DH-ANALYTICS/SPORTS/SENTIMENT: reproducible derivations, never new facts."""
import math,statistics
from decimal import Decimal
from .contracts import fingerprint,now

def calculate(rows,config=None):
    config=config or {};scope={(r['source_id'],r['key'],r['unit'],r['origin']) for r in rows if r['value'] is not None}
    if len(scope)!=1:raise ValueError('Select exactly one source, series, unit and provenance class before numerical analysis')
    selected=[r for r in rows if r['value'] is not None];values=[Decimal(r['value']) for r in selected]
    if not values:raise ValueError('No numerical observations')
    window=int(config.get('window',5))
    if not 1<=window<=1000:raise ValueError('Moving average window must be 1..1000')
    mean=sum(values)/len(values);population=statistics.pstdev(values);sample=statistics.stdev(values) if len(values)>1 else None
    median=statistics.median(values);mad=statistics.median([abs(v-median) for v in values])
    outliers=[{'id':r['id'],'value':str(v),'method':'3 sample standard deviations'} for r,v in zip(selected,values) if sample and abs(v-mean)>3*sample]
    moving=[str(sum(values[max(0,i-window+1):i+1])/min(i+1,window)) for i in range(len(values))]
    low=min(values);high=max(values);bins=[0]*10
    for v in values:bins[min(9,int((v-low)/(high-low)*10)) if high>low else 0]+=1
    half=len(values)//2
    output={'n':len(values),'sum':str(sum(values)),'mean':str(mean),'median':str(median),'minimum':str(low),'maximum':str(high),'population_sd':str(population),'sample_sd':str(sample) if sample is not None else None,'median_absolute_deviation':str(mad),'outliers':outliers,'moving_average':moving,'histogram':{'bins':bins,'min':str(low),'max':str(high)},'first_to_last_change':str(values[-1]-values[0]),'half_mean_change':str(sum(values[half:])/len(values[half:])-sum(values[:half])/half) if half else None,'confidence_interval_95_approx':[str(mean-Decimal('1.96')*sample/Decimal(len(values)).sqrt()),str(mean+Decimal('1.96')*sample/Decimal(len(values)).sqrt())] if sample else None}
    result={'algorithm':'dh.descriptive/2','configuration':{'window':window},'calculated_at':now(),'input_ids':[r['id'] for r in selected],'input_values':[str(v) for v in values],'dataset_fingerprint':fingerprint(selected),'scope':list(next(iter(scope))),'output':output,'limitations':['Observational summary, not a causal model or forecast.','Normal-approximation confidence interval assumes independent samples; autocorrelation can invalidate it.','Query order uses observation time, else a supplied calendar date, else collection time. Same-day records have no inferred intraday order; moving averages are record windows, not elapsed-time windows.','Outlier flags identify review candidates, not proven errors.']}
    result['id']=fingerprint({k:v for k,v in result.items() if k!='calculated_at'});return result
def correlate(left,right):
    for rows in (left,right):
        if len({(r['source_id'],r['key'],r['unit'],r['origin']) for r in rows})!=1:raise ValueError('Each correlation input must be one source, series, unit and provenance')
    def keyed(rows):
        out={}
        for r in rows:
            if r.get('observed_at') and r.get('value') is not None:
                if r['observed_at'] in out:raise ValueError('Duplicate observation time; choose a unique series')
                out[r['observed_at']]=float(r['value'])
        return out
    a,b=keyed(left),keyed(right);times=sorted(a.keys()&b.keys())
    if len(times)<3:raise ValueError('Correlation requires at least three pairs at exact known observation times')
    x=[a[t] for t in times];y=[b[t] for t in times]
    if not statistics.pstdev(x) or not statistics.pstdev(y):raise ValueError('Correlation undefined for a constant series')
    return {'method':'Pearson exact-time pairs/1','r':statistics.correlation(x,y),'n':len(times),'paired_times':times,'dataset_fingerprint':fingerprint([left,right]),'calculated_at':now(),'limitations':'Association is not causation; shared lineage and autocorrelation are not corrected.'}
def evaluate(predictions,outcomes):
    if len(predictions)!=len(outcomes) or not predictions:raise ValueError('Matching nonempty probability/outcome lists required')
    if any(not 0<=p<=1 for p in predictions) or any(y not in (0,1) for y in outcomes):raise ValueError('Binary outcomes and probabilities 0..1 required')
    return {'method':'binary-brier-logloss/1','n':len(outcomes),'brier':sum((p-y)**2 for p,y in zip(predictions,outcomes))/len(outcomes),'log_loss':-sum(y*math.log(max(1e-15,p))+(1-y)*math.log(max(1e-15,1-p)) for p,y in zip(predictions,outcomes))/len(outcomes),'input_fingerprint':fingerprint([predictions,outcomes]),'limitations':'Evaluation requires genuinely recorded pre-event probabilities; this calculation does not establish that chronology.'}
def sentiment(row):
    import re
    words=re.findall(r'\w+',row.get('text','').lower());positive={'good','great','excellent','happy'};negative={'bad','poor','awful','sad'}
    p=sum(w in positive for w in words);n=sum(w in negative for w in words)
    return {'observation_id':row['id'],'classification':'INFERRED','method':'dh.english-word-baseline/1','label':'uncertain' if row.get('metadata',{}).get('language','en')!='en' or 'not' in words else 'positive' if p>n else 'negative' if n>p else 'uncertain','positive_matches':p,'negative_matches':n,'limitations':'Small English lexicon; not a trained multilingual model. Sarcasm, quotations and domain meaning are not resolved.'}
def odds(value):
    from dragonhydra.market_signals import convert_odds,implied_probability
    decimal=convert_odds(str(value),'decimal')
    return {'decimal':str(decimal),'implied_probability':str(implied_probability(decimal)),'engine':'preserved DRAGONHYDRA CORE market_signals','limitation':'Price transform, not a calibrated forecast or live executable price'}
