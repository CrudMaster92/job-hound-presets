const state = { catalog: null, companies: [], members: new Map(), details: new Map(), selected: new Map(), drawer: null };
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[char]));
const locationKey = value => [value.city, value.region, value.country].filter(Boolean).join(' · ');
const title = value => String(value || '').replace(/-/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase());
const keyOf = (company, monitor) => `${company}:${monitor}`;

function safePath(path) {
  if (!path || /^([a-z]+:)?\/\//i.test(path) || path.startsWith('/') || path.split('/').includes('..')) throw Error('Unsafe catalog path');
  return path;
}
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}
async function hash(value) {
  const bytes = new TextEncoder().encode(`${canonical(value)}\n`);
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(byte => byte.toString(16).padStart(2, '0')).join('');
}
async function api(path) {
  const response = await fetch(`api/v1/${safePath(path)}`, { cache: 'no-store' });
  if (!response.ok) throw Error(`Could not load ${path}`);
  return response.json();
}
async function artifact(reference) {
  const value = await api(reference.path);
  if (!reference.sha256 || await hash(value) !== reference.sha256) throw Error('Catalog data failed its integrity check');
  return value;
}
function options(id, values) {
  const element = $(id);
  [...new Set(values.filter(Boolean))].sort().forEach(value => element.insertAdjacentHTML('beforeend', `<option value="${esc(value)}">${esc(title(value))}</option>`));
}
function logo(company) {
  const source = company.logo_url || (company.website_url ? new URL('/favicon.ico', company.website_url).toString() : '');
  const initials = company.name.split(/\s+/).map(part => part[0]).join('').slice(0,2).toUpperCase();
  return `<span class="logo">${source ? `<img src="${esc(source)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove();this.parentNode.textContent='${esc(initials)}'">` : esc(initials)}</span>`;
}
function selection(company, monitor) { return { company_id: company.company_id || company.id, monitor_id: monitor.id, revision: monitor.revision }; }
function selectable(monitor) { return ['verified','degraded'].includes(monitor.verification?.status); }
function encodeHandoff(mode, selections, collectionId) {
  const payload = { format:'jobhound-catalog-install', version:1, catalog_version:3, source_commit:state.catalog.source_commit || null, mode, ...(collectionId ? { collection_id:collectionId } : {}), selections:selections.slice(0,200) };
  const bytes = new TextEncoder().encode(JSON.stringify(payload));
  let binary = ''; bytes.forEach(byte => binary += String.fromCharCode(byte));
  return btoa(binary).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
}
function openJobHound(mode, selections, collectionId) {
  if (!selections.length) return;
  window.open(`http://127.0.0.1:4175/companies/presets#install=${encodeHandoff(mode, selections, collectionId)}`, '_blank', 'noopener');
  $('notice').hidden = false;
  $('notice').textContent = 'Selection sent. If JobHound did not open, start JobHound and try again.';
}

function matchingCompanyIds(query) {
  if (!query) return new Set(state.companies.map(company => company.id));
  return new Set(state.companies.filter(company => [company.name,company.legal_name,...(company.aliases||[]),...(company.facets?.tags||[]),...(company.facets?.specialties||[])].join(' ').toLowerCase().includes(query)).map(company => company.id));
}
function renderCollections() {
  const query = $('q').value.trim().toLowerCase(), typeValue=$('type').value, industry=$('industry').value, role=$('role').value, location=$('location').value;
  const companyMatches = matchingCompanyIds(query);
  const rows = state.catalog.collections.filter(collection => {
    const facets=collection.facets||{}, own=[collection.name,collection.description,...(collection.tags||[])].join(' ').toLowerCase().includes(query);
    const member=state.companies.some(company => (company.collection_ids||[]).includes(collection.id) && companyMatches.has(company.id));
    return (!query||own||member)&&(!typeValue||(facets.collection_types||[]).includes(typeValue))&&(!industry||(facets.industries||[]).includes(industry))&&(!role||(facets.role_families||[]).includes(role))&&(!location||(facets.locations||[]).some(value=>locationKey(value)===location));
  });
  $('catalog').innerHTML = rows.map((collection,index) => `<article class="preset-card"><div class="eyebrow"><span>${String(index+1).padStart(2,'0')}</span><span>${esc((collection.facets?.collection_types||['collection']).map(title).join(' · '))}</span></div><h2>${esc(collection.name)}</h2><p>${esc(collection.description)}</p><div class="tags">${(collection.tags||[]).map(tag=>`<span>${esc(tag)}</span>`).join('')}</div><div class="logo-stack" data-preview="${esc(collection.id)}"><small>Live from GitHub</small></div><dl><div><dt>Companies</dt><dd>${collection.company_count}</dd></div><div><dt>Monitors</dt><dd>${collection.monitor_count}</dd></div></dl><footer><button class="secondary" data-data="${esc(collection.path)}">Inspect data ↗</button><button class="primary" data-open="${esc(collection.id)}">Choose & install <span>→</span></button></footer></article>`).join('') || '<p class="empty">No presets match these filters.</p>';
  document.querySelectorAll('[data-open]').forEach(button => button.onclick=()=>openCollection(button.dataset.open));
  document.querySelectorAll('[data-data]').forEach(button => button.onclick=()=>window.open(`api/v1/${safePath(button.dataset.data)}`,'_blank','noopener'));
  observePreviews();
}
async function collectionMembers(collection) {
  if (state.members.has(collection.id)) return state.members.get(collection.id);
  const detail = await artifact(collection);
  const pages = await Promise.all((detail.member_pages||[]).map(artifact));
  const members = pages.flatMap(page=>page.companies||[]); state.members.set(collection.id,members); return members;
}
function observePreviews() {
  const observer = new IntersectionObserver(entries => entries.filter(entry=>entry.isIntersecting).forEach(async entry => {
    observer.unobserve(entry.target); const collection=state.catalog.collections.find(item=>item.id===entry.target.dataset.preview);
    try { const members=await collectionMembers(collection); entry.target.innerHTML=members.slice(0,8).map(logo).join('')+(members.length>8?`<span class="logo more">+${members.length-8}</span>`:''); } catch { entry.target.innerHTML='<small>Company preview unavailable</small>'; }
  }),{rootMargin:'180px'});
  document.querySelectorAll('[data-preview]').forEach(element=>observer.observe(element));
}
async function openCollection(id) {
  const collection=state.catalog.collections.find(item=>item.id===id); state.drawer={mode:'collection',collection};
  $('drawer-title').textContent=collection.name; $('drawer-description').textContent=collection.description; $('drawer-list').innerHTML='<p class="loading">Loading company monitors…</p>'; $('drawer').showModal();
  try { const members=await collectionMembers(collection); const chosen=new Map(); members.forEach(company=>company.monitors.forEach(monitor=>{if(selectable(monitor))chosen.set(keyOf(company.company_id,monitor.id),selection(company,monitor));})); state.drawer={...state.drawer,members,chosen}; renderDrawer(); }
  catch(error){$('drawer-list').innerHTML=`<p class="loading">${esc(error.message)}</p>`;}
}
function renderDrawer() {
  const {members,chosen}=state.drawer; $('drawer-count').textContent=`${chosen.size} of ${members.flatMap(company=>company.monitors).length} monitors selected`;
  $('drawer-list').innerHTML=members.map(company=>`<section class="drawer-company"><header>${logo(company)}<span><b>${esc(company.name)}</b><small>${company.monitors.length} monitor${company.monitors.length===1?'':'s'}</small></span></header>${company.monitors.map(monitor=>{const key=keyOf(company.company_id,monitor.id),status=monitor.verification?.status||'unverified';return `<label><input type="checkbox" data-monitor="${esc(key)}" ${chosen.has(key)?'checked':''}><span><b>${esc(title(monitor.adapter))}</b><small>${esc(monitor.id)}</small></span><em class="${esc(status)}">${esc(title(status))}</em></label>`}).join('')}</section>`).join('');
  document.querySelectorAll('[data-monitor]').forEach(input=>input.onchange=()=>{const [companyId,monitorId]=input.dataset.monitor.split(':');const company=members.find(item=>item.company_id===companyId);const monitor=company.monitors.find(item=>item.id===monitorId);if(input.checked&&chosen.size<200)chosen.set(input.dataset.monitor,selection(company,monitor));else chosen.delete(input.dataset.monitor);renderDrawer();});
  $('drawer-install').disabled=!chosen.size;
}

async function companyDetail(reference) { if(!state.details.has(reference.id))state.details.set(reference.id,artifact(reference)); return state.details.get(reference.id); }
function renderCompanies() {
  const query=$('company-q').value.trim().toLowerCase(),industry=$('company-industry').value,adapter=$('company-adapter').value,verification=$('company-verification').value;
  const rows=state.companies.filter(company=>{const facets=company.facets||{},hay=[company.name,company.legal_name,...(company.aliases||[]),...(facets.tags||[]),...(facets.specialties||[])].join(' ').toLowerCase();return(!query||hay.includes(query))&&(!industry||(facets.industries||[]).includes(industry))&&(!adapter||(company.adapters||[]).includes(adapter))&&(!verification||(company.verification_statuses||[]).includes(verification));});
  $('company-status').textContent=`${rows.length} catalog companies · choose up to 200 monitors`;
  $('companies').innerHTML=rows.map(company=>`<article class="company-card" id="company-${esc(company.id)}"><header>${logo(company)}<span><h2>${esc(company.name)}</h2><p>${esc((company.facets?.industries||[]).map(title).join(' · ')||'Company')}</p></span></header><div class="tags">${(company.facets?.tags||[]).slice(0,4).map(tag=>`<span>${esc(tag)}</span>`).join('')}</div><p>${company.monitor_count||1} monitor${company.monitor_count===1?'':'s'} · ${esc((company.adapters||[]).map(title).join(' · '))}</p><button data-company="${esc(company.id)}">Choose monitors <span>+</span></button><div class="company-monitors"></div></article>`).join('')||'<p class="empty">No companies match these filters.</p>';
  document.querySelectorAll('[data-company]').forEach(button=>button.onclick=()=>toggleCompany(button.dataset.company));
}
async function toggleCompany(id) {
  const article=document.getElementById(`company-${CSS.escape(id)}`),panel=article.querySelector('.company-monitors');
  if(panel.dataset.open){panel.innerHTML='';delete panel.dataset.open;return;} panel.innerHTML='<p>Loading monitors…</p>';
  try { const company=await companyDetail(state.companies.find(item=>item.id===id)); panel.dataset.open='1'; panel.innerHTML=company.monitors.map(monitor=>{const key=keyOf(company.id,monitor.id),status=monitor.verification?.status||'unverified';return `<label><input type="checkbox" data-advanced="${esc(key)}" ${state.selected.has(key)?'checked':''}><span><b>${esc(title(monitor.adapter))}</b><small>${esc(monitor.id)}</small></span><em class="${esc(status)}">${esc(title(status))}</em></label>`}).join(''); document.querySelectorAll('[data-advanced]').forEach(input=>input.onchange=()=>{const monitor=company.monitors.find(item=>keyOf(company.id,item.id)===input.dataset.advanced);if(input.checked&&state.selected.size<200)state.selected.set(input.dataset.advanced,selection(company,monitor));else state.selected.delete(input.dataset.advanced);renderBasket();}); }
  catch(error){panel.innerHTML=`<p>${esc(error.message)}</p>`;}
}
function renderBasket(){ $('basket').hidden=!state.selected.size;$('basket-count').textContent=state.selected.size; }

$('preset-tab').onclick=()=>{$('preset-view').hidden=false;$('company-view').hidden=true;$('preset-tab').setAttribute('aria-selected','true');$('company-tab').setAttribute('aria-selected','false');};
$('company-tab').onclick=()=>{$('preset-view').hidden=true;$('company-view').hidden=false;$('preset-tab').setAttribute('aria-selected','false');$('company-tab').setAttribute('aria-selected','true');renderCompanies();};
$('drawer-close').onclick=()=>$('drawer').close(); $('drawer').onclick=event=>{if(event.target===$('drawer'))$('drawer').close();};
$('drawer-clear').onclick=()=>{state.drawer.chosen.clear();renderDrawer();}; $('drawer-all').onclick=()=>{state.drawer.members.forEach(company=>company.monitors.forEach(monitor=>{if(selectable(monitor)&&state.drawer.chosen.size<200)state.drawer.chosen.set(keyOf(company.company_id,monitor.id),selection(company,monitor));}));renderDrawer();};
$('drawer-install').onclick=()=>openJobHound('collection',[...state.drawer.chosen.values()],state.drawer.collection.id);
$('basket-clear').onclick=()=>{state.selected.clear();renderBasket();renderCompanies();}; $('basket-install').onclick=()=>openJobHound('monitors',[...state.selected.values()]);

api('catalog.json').then(async catalog=>{
  if(catalog.catalog_version!==3)throw Error('This viewer requires catalog version 3.'); state.catalog=catalog;
  const pages=await Promise.all(catalog.search_pages.map(artifact));state.companies=pages.flatMap(page=>page.companies||[]);
  $('preset-count').textContent=catalog.collections.length;$('status').textContent=`${catalog.company_count} companies · updated ${new Date(catalog.generated_at).toLocaleDateString()}`;
  options('type',catalog.collections.flatMap(value=>value.facets?.collection_types||[]));options('industry',catalog.collections.flatMap(value=>value.facets?.industries||[]));options('role',catalog.collections.flatMap(value=>value.facets?.role_families||[]));options('location',catalog.collections.flatMap(value=>(value.facets?.locations||[]).map(locationKey)));options('company-industry',state.companies.flatMap(value=>value.facets?.industries||[]));options('company-adapter',state.companies.flatMap(value=>value.adapters||[]));
  ['q','type','industry','role','location'].forEach(id=>$(id).addEventListener('input',renderCollections));['company-q','company-industry','company-adapter','company-verification'].forEach(id=>$(id).addEventListener('input',renderCompanies));renderCollections();
}).catch(error=>$('status').textContent=error.message);
