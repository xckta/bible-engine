(()=>{
  const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
  const S={data:null,selectedEdge:null};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function toast(msg){const t=$('#toast');if(!t)return;t.textContent=msg;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),3500)}
  async function api(url){const r=await fetch(url);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:(d.detail?.message||'Request failed'));return d}
  function installUI(){
    if($('#graphBtn'))return;
    const btn=document.createElement('button');btn.className='ghost';btn.id='graphBtn';btn.textContent='GRAPH';
    const actions=$('.top-actions');actions?.insertBefore(btn,$('#languageBtn')||actions.firstChild);
    const drawer=document.createElement('aside');drawer.className='drawer graph-drawer';drawer.id='graphDrawer';drawer.setAttribute('aria-hidden','true');drawer.innerHTML=`
      <div class="drawer-head"><div><p class="eyebrow">INTERTEXTUAL GRAPH</p><h2>Scripture Neural Map</h2></div><button class="x" id="graphClose">×</button></div>
      <p class="drawer-copy">Explore typed relationships without flattening authority. Every edge declares what kind of connection it claims and where that claim came from.</p>
      <div class="graph-controls">
        <div><label class="field-label">CENTER REFERENCE</label><div class="graph-input"><input id="graphRef" value="Jude 1:6" placeholder="Jude 1:6"><button class="consult" id="graphLoad">MAP</button></div></div>
        <div><label class="field-label">DEPTH</label><select id="graphDepth"><option value="1">1 hop</option><option value="2">2 hops</option><option value="3">3 hops</option></select></div>
      </div>
      <div class="graph-quick"><button data-graph-ref="Jude 1:6">JUDE 6</button><button data-graph-ref="Jude 1:14">JUDE 14</button><button data-graph-ref="Genesis 6:1">GENESIS 6</button><button data-graph-ref="Daniel 7:13">DANIEL 7</button></div>
      <div class="graph-status" id="graphStatus">Loading graph index…</div>
      <div class="graph-filters" id="graphFilters"></div>
      <div class="graph-stage"><svg id="graphSvg" viewBox="0 0 720 520" role="img" aria-label="Intertextual relationship graph"></svg><div class="graph-empty hidden" id="graphEmpty">No indexed connections for this center reference.</div></div>
      <div class="graph-legend"><span class="canonical">CANONICAL</span><span class="deuterocanon">DEUTEROCANON</span><span class="reference">REFERENCE</span></div>
      <section class="graph-inspector hidden" id="graphInspector"><p class="eyebrow">EDGE INSPECTOR</p><h3 id="graphEdgeTitle"></h3><div class="graph-edge-badges"><span id="graphEdgeType"></span><span id="graphEdgeStrength"></span><span id="graphEdgeClass"></span></div><p id="graphRationale"></p><small id="graphProvenance"></small></section>
    `;
    document.body.appendChild(drawer);
    btn.onclick=open;
    $('#graphClose').onclick=close;
    $('#graphLoad').onclick=load;
    $('#graphRef').addEventListener('keydown',e=>{if(e.key==='Enter')load()});
    $$('[data-graph-ref]').forEach(b=>b.onclick=()=>{$('#graphRef').value=b.dataset.graphRef;load()});
    $('#graphDepth').onchange=load;
    ['#libraryBtn','#studyBtn','#languageBtn','#settingsBtn'].forEach(sel=>$(sel)?.addEventListener('click',close));
  }
  function open(){
    $$('.drawer').forEach(d=>{d.classList.remove('open');d.setAttribute('aria-hidden','true')});
    $('#graphDrawer').classList.add('open');$('#graphDrawer').setAttribute('aria-hidden','false');$('#scrim').classList.remove('hidden');
    if(!S.data)loadStatus().then(load).catch(e=>toast(e.message));
  }
  function close(){const d=$('#graphDrawer');if(!d)return;d.classList.remove('open');d.setAttribute('aria-hidden','true');if(!$$('.drawer.open').length)$('#scrim').classList.add('hidden')}
  async function loadStatus(){
    const d=await api('/api/graph/status');
    $('#graphStatus').textContent=`${Number(d.edge_count||0).toLocaleString()} INDEXED RELATIONSHIPS`;
    const types=d.edge_types||{};
    $('#graphFilters').innerHTML=Object.entries(types).map(([k,v])=>`<label><input type="checkbox" value="${esc(k)}" checked><span>${esc(v)}</span></label>`).join('');
    $$('#graphFilters input').forEach(x=>x.onchange=load);
  }
  function activeTypes(){return $$('#graphFilters input:checked').map(x=>x.value)}
  async function load(){
    const ref=$('#graphRef')?.value.trim();if(!ref)return;
    const depth=Number($('#graphDepth')?.value||1);const types=activeTypes().join(',');
    try{S.data=await api(`/api/graph?reference=${encodeURIComponent(ref)}&depth=${depth}&types=${encodeURIComponent(types)}&limit=180`);render(S.data)}catch(e){toast(e.message)}
  }
  function positions(nodes){
    const root=nodes.find(n=>n.root)||nodes[0];const others=nodes.filter(n=>n!==root);const cx=360,cy=260;
    const pos=new Map();if(root)pos.set(root.id,{x:cx,y:cy});
    const byTier={canonical:[],deuterocanon:[],reference:[],unknown:[]};others.forEach(n=>(byTier[n.tier]||byTier.unknown).push(n));
    const all=[...byTier.canonical,...byTier.deuterocanon,...byTier.reference,...byTier.unknown];
    all.forEach((n,i)=>{const angle=(Math.PI*2*i/Math.max(1,all.length))-Math.PI/2;const tierOffset=n.tier==='reference'?205:n.tier==='deuterocanon'?185:165;const jitter=(i%3)*14;pos.set(n.id,{x:cx+Math.cos(angle)*(tierOffset+jitter),y:cy+Math.sin(angle)*(tierOffset+jitter)})});
    return pos;
  }
  function edgeClass(type){return `edge-${type.replace(/[^a-z_]/g,'')}`}
  function nodeClass(tier,root){return `graph-node ${tier||'unknown'}${root?' root':''}`}
  function render(d){
    const svg=$('#graphSvg'),empty=$('#graphEmpty');const nodes=d.nodes||[],edges=d.edges||[];empty.classList.toggle('hidden',edges.length>0);svg.innerHTML='';$('#graphInspector').classList.add('hidden');
    if(!nodes.length)return;
    const p=positions(nodes);const ns='http://www.w3.org/2000/svg';
    const edgeLayer=document.createElementNS(ns,'g'),nodeLayer=document.createElementNS(ns,'g');svg.append(edgeLayer,nodeLayer);
    edges.forEach(e=>{const a=p.get(e.source),b=p.get(e.target);if(!a||!b)return;const g=document.createElementNS(ns,'g');g.setAttribute('class',`graph-edge ${edgeClass(e.type)}`);g.dataset.edgeId=e.id;const line=document.createElementNS(ns,'line');line.setAttribute('x1',a.x);line.setAttribute('y1',a.y);line.setAttribute('x2',b.x);line.setAttribute('y2',b.y);line.setAttribute('stroke-width',String(1+e.strength*2.5));line.setAttribute('stroke-opacity',String(.35+e.strength*.55));const hit=document.createElementNS(ns,'line');hit.setAttribute('x1',a.x);hit.setAttribute('y1',a.y);hit.setAttribute('x2',b.x);hit.setAttribute('y2',b.y);hit.setAttribute('class','graph-edge-hit');hit.onclick=()=>inspectEdge(e);g.append(line,hit);edgeLayer.appendChild(g)});
    nodes.forEach(n=>{const xy=p.get(n.id);const g=document.createElementNS(ns,'g');g.setAttribute('class',nodeClass(n.tier,n.root));g.setAttribute('transform',`translate(${xy.x} ${xy.y})`);g.setAttribute('tabindex','0');g.setAttribute('role','button');const c=document.createElementNS(ns,'circle');c.setAttribute('r',n.root?'38':'27');const t=document.createElementNS(ns,'text');t.setAttribute('text-anchor','middle');t.setAttribute('dy','4');const parts=n.label.split(' ');const label=n.label.length>18?n.label.slice(0,17)+'…':n.label;t.textContent=label;g.append(c,t);g.onclick=()=>{$('#graphRef').value=n.id;load()};g.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();g.onclick()}};nodeLayer.appendChild(g)});
  }
  function inspectEdge(e){S.selectedEdge=e;$('#graphInspector').classList.remove('hidden');$('#graphEdgeTitle').textContent=`${e.source} ↔ ${e.target}`;$('#graphEdgeType').textContent=e.type_label||e.type;$('#graphEdgeStrength').textContent=`${Math.round(e.strength*100)}% strength`;$('#graphEdgeClass').textContent=(e.provenance_class||'').replaceAll('_',' ');$('#graphRationale').textContent=e.rationale||'No rationale recorded.';$('#graphProvenance').textContent=e.provenance?`PROVENANCE // ${e.provenance}`:'';$('#graphInspector').scrollIntoView({behavior:'smooth',block:'nearest'})}
  installUI();
})();
