(()=>{
  const q=s=>document.querySelector(s), qa=s=>[...document.querySelectorAll(s)];
  const localState={status:null,currentWord:null};
  const html=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function notify(msg){const t=q('#toast');if(!t)return;t.textContent=msg;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),3600)}
  async function get(url){const r=await fetch(url);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:(d.detail?.message||'Request failed'));return d}
  function openDrawer(){qa('.drawer').forEach(d=>{d.classList.remove('open');d.setAttribute('aria-hidden','true')});const d=q('#languageDrawer');d.classList.add('open');d.setAttribute('aria-hidden','false');q('#scrim').classList.remove('hidden');if(!localState.status)loadStatus()}
  function closeDrawer(){const d=q('#languageDrawer');d.classList.remove('open');d.setAttribute('aria-hidden','true');if(!qa('.drawer.open').length)q('#scrim').classList.add('hidden')}
  function parseRef(raw){const m=String(raw||'').trim().match(/^(.+?)\s+(\d+):(\d+)$/);return m?{book:m[1],chapter:Number(m[2]),verse:Number(m[3])}:null}
  async function loadStatus(){
    try{
      const d=await get('/api/original/status');localState.status=d;
      const sources=d.sources||[];const ready=d.ready;
      q('#olStatus').classList.toggle('ready',ready);
      q('#olStatus').innerHTML=`<span class="ol-orb"></span><div><b>${ready?`${Number(d.total_words||0).toLocaleString()} ORIGINAL WORDS INDEXED`:'ORIGINAL CORPUS NOT INSTALLED'}</b><small>${sources.map(s=>`${html(s.source)} · ${Number(s.word_count||0).toLocaleString()}`).join(' // ')||'Rerun START_BIBLE_ENGINE.bat'}</small></div>`;
      q('#olProvenance').innerHTML=(d.provenance||[]).map(p=>`<article><span>${html(p.language)}</span><b>${html(p.source)}</b><p>${html(p.publisher)} · ${html(p.license)}</p><a href="${html(p.url)}" target="_blank" rel="noreferrer">SOURCE ↗</a></article>`).join('');
    }catch(e){q('#olStatus').innerHTML=`<span class="ol-orb bad"></span><div><b>LAB STATUS FAILED</b><small>${html(e.message)}</small></div>`}
  }
  async function openVerse(raw){
    const ref=parseRef(raw||q('#olReference').value);if(!ref)return notify('Use a verse reference like Jude 1:6');
    q('#olReference').value=`${ref.book} ${ref.chapter}:${ref.verse}`;
    try{
      const d=await get(`/api/original/verse?book=${encodeURIComponent(ref.book)}&chapter=${ref.chapter}&verse=${ref.verse}`);
      q('#olVersePanel').classList.remove('hidden');q('#olInspector').classList.add('hidden');q('#olResultsPanel').classList.add('hidden');
      q('#olVerseTitle').textContent=d.reference;q('#olVerseSource').textContent=`${String(d.language||'').toUpperCase()} // ${d.source||''}`;
      q('#olWords').innerHTML=(d.words||[]).map((w,i)=>`<button class="ol-token" data-word-index="${i}"><span class="ol-token-surface">${html(w.surface)}</span><span class="ol-token-translit">${html(w.transliteration)}</span></button>`).join('');
      qa('[data-word-index]').forEach(b=>b.onclick=()=>inspectWord(d.words[Number(b.dataset.wordIndex)],b));
      if(d.words?.length)inspectWord(d.words[0],q('[data-word-index="0"]'));
    }catch(e){notify(e.message)}
  }
  function inspectWord(w,button){
    localState.currentWord=w;qa('.ol-token.active').forEach(x=>x.classList.remove('active'));if(button)button.classList.add('active');
    q('#olInspector').classList.remove('hidden');q('#olLanguageBadge').textContent=String(w.language||'').toUpperCase();q('#olSurface').textContent=w.surface||'—';q('#olSurface').dir=w.language==='greek'?'ltr':'rtl';q('#olTranslit').textContent=w.transliteration||'—';q('#olLemma').textContent=w.lemma||'—';q('#olStrongs').textContent=w.strongs||'—';q('#olMorph').textContent=w.morph_description||w.morph||'—';q('#olMorphRaw').textContent=w.morph&&w.morph_description!==w.morph?`RAW // ${w.morph}`:'';
  }
  function renderResults(items,title,total){
    q('#olResultsPanel').classList.remove('hidden');q('#olResultsTitle').textContent=title;q('#olResultsCount').textContent=`${Number(total??items.length).toLocaleString()} MATCHES`;
    q('#olResults').innerHTML=items.length?items.map(w=>`<button class="ol-occurrence" data-open-ref="${html(`${w.book} ${w.chapter}:${w.verse}`)}"><div><span>${html(w.book)} ${w.chapter}:${w.verse}</span><b class="${w.language==='greek'?'greek':'hebrew'}">${html(w.surface)}</b></div><div><strong>${html(w.transliteration||'')}</strong><small>${html(w.lemma||'')} ${w.strongs?`· ${html(w.strongs)}`:''}</small></div></button>`).join(''):'<div class="empty-mini">No matching forms in the installed original-language corpus.</div>';
    qa('[data-open-ref]').forEach(b=>b.onclick=()=>openVerse(b.dataset.openRef));
  }
  async function findLemma(){
    const w=localState.currentWord;if(!w?.lemma)return notify('This word has no lemma tag');
    try{const d=await get(`/api/original/lemma?lemma=${encodeURIComponent(w.lemma)}&language=${encodeURIComponent(w.language)}&limit=200`);renderResults(d.items||[],`Lemma // ${w.lemma}`,d.total)}catch(e){notify(e.message)}
  }
  async function search(){const term=q('#olSearch').value.trim();if(!term)return;try{const d=await get(`/api/original/search?q=${encodeURIComponent(term)}&limit=150`);renderResults(d.items||[],`Search // ${term}`,d.items?.length||0)}catch(e){notify(e.message)}}

  q('#languageBtn')?.addEventListener('click',openDrawer);
  q('[data-close="languageDrawer"]')?.addEventListener('click',closeDrawer);
  ['#libraryBtn','#studyBtn','#settingsBtn'].forEach(sel=>q(sel)?.addEventListener('click',closeDrawer));
  q('#olOpenVerse')?.addEventListener('click',()=>openVerse());
  q('#olReference')?.addEventListener('keydown',e=>{if(e.key==='Enter')openVerse()});
  qa('[data-ol-ref]').forEach(b=>b.addEventListener('click',()=>openVerse(b.dataset.olRef)));
  q('#olFindLemma')?.addEventListener('click',findLemma);
  q('#olSearchBtn')?.addEventListener('click',search);
  q('#olSearch')?.addEventListener('keydown',e=>{if(e.key==='Enter')search()});
})();

// Independent feature bundles keep the core Oracle script small and make failures
// in an advanced instrument less likely to break normal consultation/search.
(()=>{
  const bundles=[['graph','/graph.css','/graph.js'],['research','/research.css','/research.js']];
  for(const [name,css,js] of bundles){
    if(!document.querySelector(`link[data-bible-${name}]`)){
      const l=document.createElement('link');l.rel='stylesheet';l.href=css;l.dataset[`bible${name[0].toUpperCase()+name.slice(1)}`]='1';document.head.appendChild(l);
    }
    if(!document.querySelector(`script[data-bible-${name}]`)){
      const s=document.createElement('script');s.src=js;s.defer=true;s.dataset[`bible${name[0].toUpperCase()+name.slice(1)}`]='1';document.body.appendChild(s);
    }
  }
})();
