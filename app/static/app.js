const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const state={health:null,phaseTimer:null};
const phases=['TRACING CANONICAL TEXT','CROSS-READING ANCIENT WITNESSES','SEPARATING AUTHORITY TIERS','SYNTHESIZING CITATIONS'];
function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function detailMessage(d){return typeof d?.detail==='string'?d.detail:(d?.detail?.message||d?.message||'Request failed')}
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),3200)}
async function json(url,opts){const r=await fetch(url,opts);let d={};try{d=await r.json()}catch{}if(!r.ok){const e=new Error(detailMessage(d));e.status=r.status;e.data=d;throw e}return d}
async function boot(){
  try{state.health=await json('/api/health');const ok=state.health.codex.ready;$('#statusDot').className='pulse-dot '+(ok?'live':'bad');
    $('#modelName').textContent=state.health.model;$('#effort').textContent=state.health.reasoning_effort;
    renderLibrary(state.health.library);renderSettings(state.health);
    if(!state.health.esv.configured)setTimeout(()=>{$('#settingsDialog').showModal();$('#esvStatus').innerHTML='<span style="color:#d8b66a">ESV key required for canonical Scripture.</span>'},300);
    if(!ok)toast(state.health.codex.detail||'Codex is not ready');
  }catch(e){$('#statusDot').className='pulse-dot bad';toast(e.message)}
}
function renderSettings(h){$('#esvStatus').innerHTML=h.esv.configured?`<span style="color:#7ba88a">Configured ${esc(h.esv.masked_key||'')}</span>`:'<span style="color:#a34d3f">Not configured</span>'}
function renderLibrary(lib){
  $('#shelfStats').innerHTML=`<div class="stat"><b>${Number(lib.canonical_verses||0).toLocaleString()}</b><span>CANONICAL INDEX</span></div><div class="stat"><b>${Number(lib.deuterocanon_verses||0).toLocaleString()}</b><span>DEUTEROCANON</span></div><div class="stat"><b>${Number(lib.reference_passages||0).toLocaleString()}</b><span>REFERENCE PASSAGES</span></div>`;
  const works=lib.reference_works||[];$('#works').innerHTML=works.length?works.map(w=>`<div class="work"><div class="work-line"><div><h4>${esc(w.name)}</h4><small>${esc(w.category)}</small></div><div class="count">${Number(w.passage_count||0).toLocaleString()} PASSAGES</div></div><p>${esc(w.relevance)}<br>${esc(w.source_label)}</p></div>`).join(''):'<div class="work"><h4>Reference library not indexed yet</h4><p>Run the updated launcher; it installs the public-domain reference shelf automatically.</p></div>';
}
function startPhases(){let i=0;$('#phase').textContent=phases[0];clearInterval(state.phaseTimer);state.phaseTimer=setInterval(()=>{$('#phase').textContent=phases[++i%phases.length]},1700)}
function showConsulting(){clearInterval(state.phaseTimer);$('#hero').classList.add('hidden');$('#result').classList.add('hidden');$('#consulting').classList.remove('hidden');startPhases();window.scrollTo({top:0,behavior:'smooth'})}
function stopConsulting(){clearInterval(state.phaseTimer);$('#consulting').classList.add('hidden')}
function reset(){stopConsulting();$('#result').classList.add('hidden');$('#hero').classList.remove('hidden');setTimeout(()=>$('#question').focus(),50)}
function renderResult(d){stopConsulting();$('#result').classList.remove('hidden');$('#modeChip').textContent=(d.mode||'closed corpus').replaceAll('_',' ').toUpperCase();$('#answerText').textContent=d.answer||'';
  $('#claims').innerHTML=(d.claims||[]).map(c=>`<div class="claim"><div class="claim-meta authority-${esc(c.authority)}"><b>${esc(c.authority)}</b>${esc(c.classification)}</div><div><p>${esc(c.text)}</p><div class="claim-cites">${(c.citations||[]).map(esc).join(' · ')}</div></div></div>`).join('');
  const ev=d.evidence||[];$('#evidenceCount').textContent=`${ev.length} RETRIEVED`;
  $('#evidence').innerHTML=ev.map(e=>`<article class="e-card ${esc(e.tier)}"><div class="e-top"><div class="e-tier">${e.tier==='pseudepigrapha'?'REFERENCE':esc(e.tier)} // ${esc(e.id)}</div><div class="e-tier">${esc(e.source)}</div></div><div class="e-cite">${esc(e.citation)}</div><div class="e-text">${esc(e.text)}</div>${e.source_label?`<div class="e-source">${esc(e.source_label)}</div>`:''}</article>`).join('');
  const hasESV=ev.some(e=>e.source==='ESV');$('#esvNotice').classList.toggle('hidden',!hasESV);window.scrollTo({top:0,behavior:'smooth'})
}
async function ask(){const question=$('#question').value.trim();if(!question)return;showConsulting();
  try{const d=await json('/api/ask',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({question,include_deuterocanon:$('#deutToggle').checked,include_reference:$('#refToggle').checked})});renderResult(d)}
  catch(e){stopConsulting();$('#hero').classList.remove('hidden');const code=e.data?.detail?.code;if(code==='esv_key_required'||code==='esv_error'){toast(e.message);$('#settingsDialog').showModal();$('#esvStatus').innerHTML=`<span style="color:#a34d3f">${esc(e.message)}</span>`}else{toast(e.message)}}
}
async function saveSettings(){const key=$('#esvKey').value.trim();$('#saveSettings').disabled=true;$('#esvStatus').textContent='Verifying with ESV API…';
  try{const d=await json('/api/settings/esv',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({api_key:key})});$('#esvStatus').innerHTML=d.configured?`<span style="color:#7ba88a">Verified ${esc(d.masked_key||'')}</span>`:'<span style="color:#a34d3f">ESV key removed</span>';$('#esvKey').value='';setTimeout(()=>$('#settingsDialog').close(),500);toast('ESV configuration saved')}
  catch(e){$('#esvStatus').innerHTML=`<span style="color:#a34d3f">${esc(e.message)}</span>`}finally{$('#saveSettings').disabled=false}}
function openLibrary(){$('#libraryDrawer').classList.add('open');$('#libraryDrawer').setAttribute('aria-hidden','false');$('#scrim').classList.remove('hidden')}
function closeLibrary(){$('#libraryDrawer').classList.remove('open');$('#libraryDrawer').setAttribute('aria-hidden','true');$('#scrim').classList.add('hidden')}
$('#askBtn').onclick=ask;$('#question').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')ask()});
$$('.examples button').forEach(b=>b.onclick=()=>{$('#question').value=b.dataset.q;ask()});$('#brandBtn').onclick=reset;$('#libraryBtn').onclick=openLibrary;$('#scrim').onclick=closeLibrary;$$('[data-close="libraryDrawer"]').forEach(b=>b.onclick=closeLibrary);$('#settingsBtn').onclick=()=>$('#settingsDialog').showModal();$('#saveSettings').onclick=saveSettings;boot();
