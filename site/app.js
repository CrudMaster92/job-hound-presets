const state = { catalog: null, companies: [], members: new Map() };
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const api = path => fetch(`api/v1/${path}`).then(response => {
  if (!response.ok) throw Error(`Could not load ${path}`);
  return response.json();
});
const locationKey = value => [value.city, value.region, value.country].filter(Boolean).join(' · ');

function options(id, values) {
  const element = $(id);
  [...new Set(values.filter(Boolean))].sort().forEach(value => {
    element.insertAdjacentHTML('beforeend', `<option value="${esc(value)}">${esc(value)}</option>`);
  });
}

function matchingCompanyIds(query) {
  if (!query) return new Set(state.companies.map(company => company.id));
  return new Set(state.companies.filter(company =>
    [company.name, company.legal_name, ...(company.aliases || [])].join(' ').toLowerCase().includes(query)
  ).map(company => company.id));
}

function render() {
  const query = $('q').value.trim().toLowerCase();
  const type = $('type').value;
  const industry = $('industry').value;
  const role = $('role').value;
  const location = $('location').value;
  const companyMatches = matchingCompanyIds(query);
  const rows = state.catalog.collections.filter(collection => {
    const facets = collection.facets || {};
    const collectionMatches = [collection.name, collection.description, ...(collection.tags || [])]
      .join(' ').toLowerCase().includes(query);
    const hasCompanyMatch = state.companies.some(company =>
      company.collection_ids.includes(collection.id) && companyMatches.has(company.id));
    return (!query || collectionMatches || hasCompanyMatch)
      && (!type || (facets.collection_types || []).includes(type))
      && (!industry || (facets.industries || []).includes(industry))
      && (!role || (facets.role_families || []).includes(role))
      && (!location || (facets.locations || []).some(value => locationKey(value) === location));
  });
  $('status').textContent = `${rows.length} curated collection${rows.length === 1 ? '' : 's'} · ${state.catalog.company_count} companies · updated ${new Date(state.catalog.generated_at).toLocaleString()}`;
  $('catalog').innerHTML = rows.map(collection => `
    <article id="collection-${esc(collection.id)}">
      <div class="eyebrow">${esc((collection.facets.collection_types || []).join(' · '))}</div>
      <h2>${esc(collection.name)}</h2><p>${esc(collection.description)}</p>
      <div class="tags">${(collection.tags || []).map(tag => `<span>${esc(tag)}</span>`).join('')}</div>
      <dl><div><dt>Companies</dt><dd>${collection.company_count}</dd></div><div><dt>Monitors</dt><dd>${collection.monitor_count}</dd></div></dl>
      <div class="members" hidden></div>
      <footer><a href="api/v1/${esc(collection.path)}">Collection data</a><button data-id="${esc(collection.id)}">View monitors</button><a class="primary" download href="api/v1/${esc(collection.bundle_path)}">Download optional full bundle</a></footer>
    </article>`).join('') || '<p>No collections match these filters.</p>';
  document.querySelectorAll('button[data-id]').forEach(button => button.addEventListener('click', () => toggleDetails(button.dataset.id)));
}

async function loadMembers(collection) {
  if (state.members.has(collection.id)) return state.members.get(collection.id);
  const detail = await api(collection.path);
  const memberPages = await Promise.all(detail.member_pages.map(reference => api(reference.path)));
  const members = memberPages.flatMap(page => page.companies);
  state.members.set(collection.id, members);
  return members;
}

async function toggleDetails(collectionId) {
  const article = document.getElementById(`collection-${CSS.escape(collectionId)}`);
  const panel = article.querySelector('.members');
  const button = article.querySelector('button[data-id]');
  if (!panel.hidden) {
    panel.hidden = true;
    button.textContent = 'View monitors';
    return;
  }
  button.disabled = true;
  button.textContent = 'Loading…';
  try {
    const collection = state.catalog.collections.find(value => value.id === collectionId);
    const members = await loadMembers(collection);
    panel.innerHTML = members.map(company => `<div class="company"><strong>${esc(company.name)}</strong><div class="monitors">${company.monitors.map(monitor => `<a download href="api/v1/${esc(monitor.path)}">${esc(monitor.id)} · ${esc(monitor.adapter)}</a>`).join('')}</div></div>`).join('');
    panel.hidden = false;
    button.textContent = 'Hide monitors';
  } catch (error) {
    panel.innerHTML = `<p>${esc(error.message)}</p>`;
    panel.hidden = false;
    button.textContent = 'Retry';
  } finally {
    button.disabled = false;
  }
}

api('catalog.json').then(async catalog => {
  if (catalog.catalog_version !== 3) throw Error('This catalog viewer requires catalog version 3.');
  state.catalog = catalog;
  const searchPages = await Promise.all(catalog.search_pages.map(reference => api(reference.path)));
  state.companies = searchPages.flatMap(page => page.companies);
  options('type', catalog.collections.flatMap(value => value.facets.collection_types || []));
  options('industry', catalog.collections.flatMap(value => value.facets.industries || []));
  options('role', catalog.collections.flatMap(value => value.facets.role_families || []));
  options('location', catalog.collections.flatMap(value => (value.facets.locations || []).map(locationKey)));
  ['q', 'type', 'industry', 'role', 'location'].forEach(id => $(id).addEventListener('input', render));
  render();
}).catch(error => $('status').textContent = error.message);
