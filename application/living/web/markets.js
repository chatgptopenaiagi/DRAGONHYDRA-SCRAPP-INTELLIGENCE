'use strict';
window.MarketDesk = (() => {
  const percent = v => (Number(v) * 100).toFixed(2) + '%';
  const decimal = v => Number(v).toFixed(4);
  let calculation, boardData, boardKey, boardRequest = 0, model;
  const league = $('board-league'), day = $('board-day');
  day.value = new Date().toISOString().slice(0,10);
  try {
    const saved = JSON.parse(localStorage.getItem('dh.scoreboard.preference') || '{}');
    if ([...league.options].some(o => o.value === saved.league)) league.value = saved.league;
    if (saved.day) day.value = saved.day;
  } catch {}
  function download(name, data) {
    const a = el('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}));
    a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }
  function table(head, rows) {
    const wrap = el('div', undefined, 'table-scroll'), t = el('table', undefined, 'market-table');
    const tr = t.createTHead().insertRow();
    head.forEach(h => { const th = el('th', h); th.scope = 'col'; tr.append(th); });
    const body = t.createTBody();
    rows.forEach(row => { const line = body.insertRow(); row.forEach(v => line.insertCell().textContent = v); });
    wrap.append(t); return wrap;
  }
  function clearCalc() {
    calculation = null; $('market-export').disabled = true; $('market-ai').disabled = true; clear($('market-output')); $('market-state').textContent = '';
  }
  function prices() {
    const keys = $('market-type').value === '1X2' ? ['home','draw','away'] : ['first','second'];
    const examples = {decimal:['2.5','3','2.8'],fractional:['3/2','2/1','9/5'],american:['+150','+200','+180']};
    const area = $('market-prices'); clear(area); clear($('ev-outcome')); clearCalc();
    keys.forEach((key,i) => {
      const lab = el('label', key[0].toUpperCase()+key.slice(1)), input = el('input');
      input.name = key; input.required = true; input.maxLength = 80; input.placeholder = examples[$('market-format').value][i];
      lab.append(input); area.append(lab); option($('ev-outcome'),key,key);
    });
  }
  $('market-type').onchange = prices; $('market-format').onchange = prices; prices();
  let calcRequest = 0;
  $('market-form').oninput = () => { calcRequest++; clearCalc(); };
  $('market-form').onsubmit = async e => {
    e.preventDefault(); const serial = ++calcRequest; clearCalc();
    const inputs = [...$('market-prices').querySelectorAll('input')];
    const req = {market:$('market-type').value,format:$('market-format').value,prices:Object.fromEntries(inputs.map(i=>[i.name,i.value]))};
    if ($('ev-p').value || $('ev-basis').value) req.assumption = {outcome:$('ev-outcome').value,probability:$('ev-p').value,basis:$('ev-basis').value};
    try {
      const r = await api('/api/market/calculation',req); if (serial !== calcRequest) return;
      calculation = r; $('market-export').disabled = false; $('market-ai').disabled = false;
      $('market-state').textContent = 'Mathematical calculation · Overround '+ percent(r.overround)+' · Theoretical margin '+percent(r.theoretical_margin);
      $('market-output').append(table(['Outcome','Decimal','Implied','Normalized','Fair odds'],Object.entries(r.outcomes).map(([k,v])=>[k,decimal(v.decimal),percent(v.implied),percent(v.normalized),decimal(v.fair_decimal)])));
      if(r.expected_value) $('market-output').append(el('p','Expected net per unit '+decimal(r.expected_value.net_per_unit)+' at assumed '+percent(r.expected_value.probability)+' for '+r.expected_value.outcome+' · '+r.expected_value.basis));
    } catch(err) { if(serial===calcRequest) $('market-state').textContent=err.message; }
  };
  $('market-ai').onclick = async () => {
    const current = calculation;
    try {
      const r = await api('/api/ai/explain', {market:current.input});
      if (calculation === current) evidence(r);
    } catch(e) { showError(e); }
  };
  $('market-export').onclick = () => download('dragonhydra-market.json',calculation);
  function modelView() {
    const group=model.leagues[$('model-league').value], area=$('model-results'); clear(area);
    area.append(el('p',group.train.n+' training matches. Validation seasons share a frozen model. Each fixture receives the same league-level probabilities.'),
      table(['Season','Matches','Brier · prior','Brier · uniform','Log loss · prior','Log loss · uniform'],group.holdouts.map(v=>[v.source.season,v.source.n,decimal(v.frequency.brier),decimal(v.uniform.brier),decimal(v.frequency.log_loss),decimal(v.uniform.log_loss)])),
      button('Export scores, calibration and sources',()=>download('dragonhydra-backtest.json',model)));
  }
  $('model-league').onchange=()=>{if(model)modelView();};
  $('model-panel').ontoggle=async()=>{if(!$('model-panel').open)return;try{model ||= await api('/backtest.json');modelView();}catch(e){$('model-results').textContent=e.message;}};
  function selected(){return {league:league.value,day:day.value};}
  async function board(force=false) {
    const query=selected(), key=JSON.stringify(query);
    if (!force && boardKey===key) return;
    boardKey=key; const serial=++boardRequest; boardData=null; $('board-export').disabled=true;
    const area=$('board-events'); clear(area); $('board-state').textContent='Reading saved events…';
    try {
      localStorage.setItem('dh.scoreboard.preference',key);
    } catch {}
    try {
      const r=await api('/api/scoreboard/events?'+params(query));
      if(serial!==boardRequest)return;
      boardData=r; $('board-export').disabled=!r.events.length&&!r.snapshot_receipt;
      $('board-state').textContent=r.events.length ? r.events.length+' events · '+r.stored_observations+' saved observations · ESPN · Latest capture '+(r.snapshot_receipt?.acquired_at||'unknown') : r.snapshot_receipt ? 'Provider reported zero events · Captured '+r.snapshot_receipt.acquired_at : 'No saved events for this league and date. Collection requires connected mode.';
      for(const row of r.events){
        const item=el('article',undefined,'board-event'), h=row.participants.home,a=row.participants.away;
        item.append(el('small',row.competition),el('h3',h.name+' — '+a.name),
          el('p',(row.snapshot_presence==='ABSENT'?'Absent from latest snapshot':row.conflicting_latest?'Conflicting updates':row.status || 'Status unknown')+' · '+(row.scheduled_at || 'Start time unknown')),
          el('p','Observed scores · '+(h.score??'—')+' / '+(a.score??'—')),
          el('small',row.origin+' · Collected '+row.collected_at),
          button('Inspect event',async()=>evidence(row)));area.append(item);
      }
    }catch(e){if(serial===boardRequest){boardKey=null;$('board-state').textContent=e.message;}}
  }
  $('board-form').onsubmit=e=>{e.preventDefault();board(true);}; league.onchange=day.onchange=()=>board(true);
  $('board-export').onclick=()=>download('dragonhydra-scoreboard.json',boardData);
  $('board-collect').onclick=async()=>{
    const query=selected(), key=JSON.stringify(query); $('board-collect').disabled=true;
    try{
      const {task}=await api('/api/scoreboard/collect',query);
      $('board-state').textContent='Collecting scoreboard…';
      for(let n=0;n<40;n++){
        await new Promise(resolve=>setTimeout(resolve,1000));
        const item=(await api('/api/tasks')).find(x=>x.id===task);
        if(!item||['QUEUED','RUNNING'].includes(item.state))continue;
        if(key!==JSON.stringify(selected()))return;
        if(item.state==='COMPLETE')await board(true);
        else $('board-state').textContent=item.state+' · '+(item.result?.error||'See Recovery center');
        return;
      }
      $('board-state').textContent='Collection continues. See Recovery center for its receipt.';
    }catch(e){$('board-state').textContent=e.message;}finally{$('board-collect').disabled=false;}
  };
  function addHistory(item,match){
    const h=match.history;
    if(!h||!match.odds.length)return;
    const details=el('details',undefined,'movement'); details.append(el('summary','Historical market movement')); item.append(details);
    details.ontoggle=()=>{
      if(!details.open||details.dataset.ready)return; details.dataset.ready='yes';
      details.append(el('p',h.excluded_time_or_identity+' quotes excluded for missing time or market identity.'));
      if(!h.series.length){details.append(el('p','No timestamped series available.'));return;}
      const groups=new Map();
      for(const s of h.series){const k=JSON.stringify([s.market,s.outcome,s.line,s.period,s.settlement]);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(s);}
      const filter=el('select'),lab=el('label','Market and outcome');lab.append(filter);details.append(lab);
      for(const k of groups.keys())option(filter,k,JSON.parse(k).filter(Boolean).join(' · '));
      const graph=el('div');details.append(graph);
      function render(){
        clear(graph);const series=groups.get(filter.value),canvas=el('canvas');canvas.width=760;canvas.height=220;canvas.setAttribute('aria-label','Recorded decimal prices over time. Values appear in the data table.');
        graph.append(canvas);
        const rows=[],colors=['#62ddbe','#f8c87a','#90b6ff','#ed97c8','#baa0ff'], all=series.flatMap(s=>s.points), valid=all.filter(p=>p.decimal!==null);
        if(valid.length){
          const xx=all.map(p=>Date.parse(p.at)),yy=valid.map(p=>Number(p.decimal));
          const minX=Math.min(...xx),maxX=Math.max(...xx),minY=Math.min(...yy),maxY=Math.max(...yy),ctx=canvas.getContext('2d');
          const x=n=>64+(maxX===minX ? 0.5 :(n-minX)/(maxX-minX))*670,y=n=>168-(maxY===minY ? 0.5 :(n-minY)/(maxY-minY))*136;
          ctx.font='14px Segoe UI';ctx.fillStyle='#b5c8d1';ctx.fillText(maxY.toFixed(2),6,34);ctx.fillText(minY.toFixed(2),6,170);
          ctx.fillText(new Date(minX).toISOString().slice(0,16)+'Z',64,205);ctx.textAlign='right';ctx.fillText(new Date(maxX).toISOString().slice(0,16)+'Z',734,205);
          series.forEach((s,i)=>{let prev=null;ctx.strokeStyle=ctx.fillStyle=colors[i%colors.length];for(const p of s.points){
            if(p.decimal===null){prev=null;continue;}const point=[x(Date.parse(p.at)),y(Number(p.decimal))];
            if(prev){ctx.beginPath();ctx.moveTo(...prev);ctx.lineTo(...point);ctx.stroke();}ctx.beginPath();ctx.arc(...point,4,0,2*Math.PI);ctx.fill();prev=point;
          }});
        }
        for(const [i,s] of series.entries()){
          const legend=el('p','● '+s.bookmaker+' · First-to-last implied change '+(s.implied_change===null?'unavailable':(Number(s.implied_change)*100).toFixed(2)+' pp'));
          legend.classList.add('legend-'+(i%colors.length));graph.append(legend);
          for(const p of s.points)rows.push([s.bookmaker,p.at,p.decimal??'Unavailable',p.phase.join(', ')||'Unspecified',p.state]);
        }
        const comparisons=h.comparisons.filter(c=>JSON.stringify([c.market,c.outcome,c.line,c.period,c.settlement])===filter.value);
        if(comparisons.length)graph.append(table(['Synchronized quotes','Bookmakers','Decimal range'],comparisons.map(c=>[c.at,c.bookmakers.join(', '),c.decimal_range])));
        graph.append(table(['Bookmaker','Source time','Decimal','Reported phase','Quality'],rows));
      }
      filter.onchange=render;render();details.append(button('Export movement with observation IDs',()=>download('dragonhydra-movement.json',{event_id:match.id,source:match.source,origin:match.origin,history:h})));
    };
  }
  return {board,addHistory};
})();
