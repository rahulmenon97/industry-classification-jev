const $=s=>document.querySelector(s);let offset=0;
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
const money=v=>v==null?'Unknown':'$'+v.toFixed(5);
async function api(path,options){
  const r=await fetch(path,options);
  let data;
  try{data=await r.json()}
  catch{throw Error(r.ok?'The server returned an invalid response. Refresh the page and try again.':`Server error (HTTP ${r.status}). Please try again; if it persists, restart the local demo server.`)}
  if(!r.ok)throw Error(typeof data.detail==='string'?data.detail:`Request failed (HTTP ${r.status}). Check the input and try again.`);
  return data;
}
function card(title){const c=node('section',undefined,'card');c.append(node('h2',title));return c}
function disclosure(title){const d=node('details',undefined,'disclosure');d.append(node('summary',title));return d}
function table(headers,rows){const t=node('table'),head=node('thead'),hr=node('tr');headers.forEach(h=>hr.append(node('th',h)));head.append(hr);t.append(head);const body=node('tbody');for(const values of rows){const tr=node('tr');values.forEach(v=>tr.append(node('td',v??'—')));body.append(tr)}t.append(body);return t}
function render(r){
  const root=$('#result');root.replaceChildren();
  const c=card(r.request.company_name),cl=r.classification;
  const source=r.selected_source_index!=null?r.sources[r.selected_source_index]:null;
  if(r.error)c.append(node('p',r.error,'error'));
  if(r.review_reason)c.append(node('p',r.review_reason,'muted'));
  const metrics=node('div',undefined,'metrics result-fields');
  function field(label,value,wide=false,url=null){
    const m=node('div',undefined,'metric'+(wide?' wide':''));
    const v=node(url?'a':'strong',value,'field-value');
    if(url){v.href=url;v.target='_blank';v.rel='noopener noreferrer'}
    m.append(node('span',label,'muted'),v);metrics.append(m);return m;
  }
  field('Status',r.status.replaceAll('_',' '));
  field('Company URL',source?.url||'Unavailable',true,source?.url);
  field('Classification',cl?(cl.path_names?cl.path_names.join(' → '):cl.answer.choice.replaceAll('_',' ')):'Not classified',true);
  field('Industry code',cl?.industry_code||'—');
  const timeCard=field('Time',(r.elapsed_ms/1000).toFixed(2)+' s');
  const costCard=field('Estimated cost',money(r.estimated_cost_usd));
  function breakdown(card,label,value){const row=node('div',undefined,'metric-breakdown');row.append(node('span',label),node('span',value));card.append(row)}
  for(const [provider,label] of [['exa','Exa'],['typesafe','Jev']]){
    const stages=r.stages.filter(s=>s.provider===provider);
    const elapsed=stages.reduce((sum,s)=>sum+s.elapsed_ms,0);
    const cost=stages.length&&stages.every(s=>s.estimated_cost_usd!=null)?stages.reduce((sum,s)=>sum+s.estimated_cost_usd,0):null;
    breakdown(timeCard,label,stages.length?(elapsed/1000).toFixed(3)+' s':'Not called');
    breakdown(costCard,label,stages.length?money(cost):'Not called');
  }
  const overhead=Math.max(0,r.elapsed_ms-r.stages.reduce((sum,s)=>sum+s.elapsed_ms,0));
  breakdown(timeCard,'App overhead',(overhead/1000).toFixed(3)+' s');
  field('Confidence',cl?(cl.answer.confidence*100).toFixed(1)+'%':'—');
  c.append(metrics);
  root.append(c);
  const taxonomy=disclosure('Tier information · hierarchy table and definition');
  const nodes=new Map((r.taxonomy_snapshot.nodes||[]).map(n=>[n.id,n]));
  if(cl?.path_ids){taxonomy.append(table(['Tier','Industry','Description'],cl.path_ids.map((id,i)=>{const n=nodes.get(id);return ['Tier '+(i+1),n?.name||cl.path_names[i],n?.description||'Unavailable']})));
    const criteria=r.stages.find(s=>s.name==='classification')?.request?.questions?.industry?.criteria;
    taxonomy.append(node('h3','Complete classification definition'),node('p',criteria?.[cl.answer.choice]||'Definition unavailable for this saved run.','definition'));
  }else taxonomy.append(node('p','No industry path was selected.'));
  taxonomy.append(node('p',r.taxonomy_version,'muted'));root.append(taxonomy);
  const probabilities=disclosure('Class probabilities');
  if(cl)probabilities.append(table(['Class','Probability'],Object.entries(cl.answer.probabilities).sort((a,b)=>b[1]-a[1]).map(([id,p])=>[nodes.get(id)?.name||id.replaceAll('_',' '),(p*100).toFixed(2)+'%'])));
  else probabilities.append(node('p','No classification probabilities available.'));
  root.append(probabilities);
  const json=disclosure('Raw JSON output · Choice, Noul and metrics');
  const actions=node('div',undefined,'json-actions'),copy=node('button','Copy JSON','secondary'),download=node('a','Download JSON'),feedback=node('span',undefined,'muted');
  copy.type='button';feedback.setAttribute('role','status');
  const formatted=JSON.stringify(r,null,2);
  copy.onclick=async()=>{try{await navigator.clipboard.writeText(formatted);feedback.textContent='Copied'}catch{feedback.textContent='Copy unavailable. Use Download JSON.'}};
  download.href='/api/runs/'+r.id+'/export';actions.append(copy,download,feedback);
  json.append(actions,node('pre',formatted,'json-result'));root.insertBefore(json,probabilities);
  const evidence=node('section',undefined,'card');
  evidence.append(node('h3',r.description_kind==='exa_synthesis'?'Exa company description used for classification':'Description used for classification'));
  const usedDescription=r.stages.find(s=>s.name==='classification')?.request?.state?.description;
  if(usedDescription){evidence.append(node('p',usedDescription,'source'))}
  else evidence.append(node('p','No description was used for classification.','muted'));
  if(r.exa_results?.length){const citations=disclosure('Supporting source URLs');for(const s of r.exa_results){const link=node('a',s.title||s.url);link.href=s.url;link.target='_blank';link.rel='noopener noreferrer';const p=node('p');p.append(link);citations.append(p)}evidence.append(citations)}
  root.append(evidence);
}
async function history(reset=true){if(reset){offset=0;$('#history').replaceChildren()}const rows=await api('/api/runs?limit=20&offset='+offset);for(const r of rows){const b=node('button',r.company_name,'history-item');b.append(node('small',r.status+' · '+new Date(r.created_at).toLocaleString()));b.onclick=async()=>{try{const saved=await api('/api/runs/'+r.id);render(saved);$('#status').textContent='Saved result · '+saved.request.company_name+' · '+saved.status.replaceAll('_',' ')}catch(e){$('#status').textContent=e.message}};$('#history').append(b)}offset+=rows.length;$('#more').hidden=rows.length<20}
$('#more').onclick=()=>history(false);
$('#form').onsubmit=async e=>{e.preventDefault();$('#submit').disabled=true;$('#status').textContent='Retrieving evidence and running Jev… This can take up to a few minutes.';try{const r=await api('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_name:$('#company').value,taxonomy:'industry_v2'})});render(r);$('#status').textContent='Result saved · '+r.status;await history()}catch(e){$('#status').textContent=e.message}finally{$('#submit').disabled=false}};
history().catch(e=>$('#status').textContent=e.message);
