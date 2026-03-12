const elements = {
  stats: document.getElementById('stats'),
  currentViewButton: document.getElementById('currentViewButton'),
  compareViewButton: document.getElementById('compareViewButton'),
  currentView: document.getElementById('currentView'),
  compareView: document.getElementById('compareView'),
  searchInput: document.getElementById('searchInput'),
  regionSelect: document.getElementById('regionSelect'),
  skuSelect: document.getElementById('skuSelect'),
  regionalOnlyCheckbox: document.getElementById('regionalOnlyCheckbox'),
  clearFiltersButton: document.getElementById('clearFiltersButton'),
  resultCount: document.getElementById('resultCount'),
  modelList: document.getElementById('modelList'),
  modelDetail: document.getElementById('modelDetail'),
  compareSummary: document.getElementById('compareSummary'),
  compareList: document.getElementById('compareList'),
};

const state = {
  activeModelId: null,
  currentModels: [],
  meta: null,
  compare: null,
  activeView: 'current',
};

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderStats(meta) {
  const updated = new Date(meta.updatedAt).toLocaleString();
  elements.stats.innerHTML = [
    `<div class="stat"><strong>${meta.totalModels}</strong> tracked models</div>`,
    `<div class="stat"><strong>${meta.regions.length}</strong> regions</div>`,
    `<div class="stat"><strong>${Math.round(meta.totalModels / meta.regions.length)}</strong> avg. models per region signal</div>`,
    `<div class="stat">Snapshot updated <strong>${updated}</strong></div>`,
  ].join('');
}

function setView(view) {
  state.activeView = view;
  const currentActive = view === 'current';
  elements.currentViewButton.classList.toggle('is-active', currentActive);
  elements.compareViewButton.classList.toggle('is-active', !currentActive);
  elements.currentView.classList.toggle('is-active', currentActive);
  elements.compareView.classList.toggle('is-active', !currentActive);
}

function fillSelect(select, values, placeholder) {
  select.innerHTML = `<option value="">${placeholder}</option>`;
  for (const value of values) {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}

function tagMarkup(label, className = '') {
  const classes = ['tag', className].filter(Boolean).join(' ');
  return `<span class="${classes}">${escapeHtml(label)}</span>`;
}

function regionMarkup(regions) {
  return regions.map((region) => `<span class="region-chip">${escapeHtml(region)}</span>`).join('');
}

function regionListMarkup(regions) {
  if (!regions.length) {
    return tagMarkup('No regions listed');
  }

  return `<div class="region-row list-meta">${regionMarkup(regions)}</div>`;
}

function deltaChipMarkup(label, kind) {
  return `<span class="delta-chip ${kind}">${escapeHtml(label)}</span>`;
}

function coveragePercent(regionCount) {
  if (!state.meta || !state.meta.regions.length) {
    return 0;
  }
  return Math.round((regionCount / state.meta.regions.length) * 100);
}

function sortModels(models) {
  return [...models].sort((left, right) => {
    return right.regionCount - left.regionCount || left.name.localeCompare(right.name);
  });
}

function renderCompare() {
  const compare = state.compare;
  if (!compare) {
    elements.compareSummary.innerHTML = '<div class="empty-state">Kein Vergleich verfugbar.</div>';
    elements.compareList.innerHTML = '';
    return;
  }

  const latestRefreshLabel = compare.latestRefresh?.timestamp ? new Date(compare.latestRefresh.timestamp).toLocaleString() : 'Unknown';
  const sourceLabel = compare.compareSource?.timestamp ? new Date(compare.compareSource.timestamp).toLocaleString() : 'Unknown';
  const latestRefreshState = compare.latestRefresh?.hasChanges ? 'Beim letzten Refresh wurden Anderungen gefunden.' : 'Beim letzten Refresh gab es keine Anderungen.';
  const sourceHint = compare.latestRefresh?.hasChanges
    ? 'Die Old/New-Ansicht basiert auf dem letzten Refresh.'
    : 'Die Old/New-Ansicht zeigt die letzte echte Anderung, weil der letzte Refresh keine Deltas hatte.';

  elements.compareSummary.innerHTML = `
    <div class="compare-summary-grid">
      <div class="compare-summary-copy">
        <p class="eyebrow">Agent view</p>
        <h2>Old / New pro Refresh</h2>
        <p>${latestRefreshState}</p>
        <p>Letzter Refresh: <strong>${latestRefreshLabel}</strong><br />Vergleichsquelle: <strong>${sourceLabel}</strong><br />${sourceHint}</p>
      </div>
      <div class="metric-card"><div class="metric-value">${compare.count}</div><div class="metric-label">Geanderte Modelle</div></div>
      <div class="metric-card"><div class="metric-value">${compare.compareSource?.summary?.addedRegions || 0}</div><div class="metric-label">Neue Regionen</div></div>
      <div class="metric-card"><div class="metric-value">${compare.compareSource?.summary?.removedRegions || 0}</div><div class="metric-label">Entfernte Regionen</div></div>
      <div class="metric-card"><div class="metric-value">${compare.compareSource?.summary?.modelRemovals || 0}</div><div class="metric-label">Entfernte Modelle</div></div>
    </div>
  `;

  if (!compare.entries.length) {
    elements.compareList.innerHTML = '<div class="card empty-state">Keine Unterschiede verfugbar.</div>';
    return;
  }

  elements.compareList.innerHTML = compare.entries.map((entry) => {
    const deltas = [
      ...entry.added.map((region) => deltaChipMarkup(`+ ${region}`, 'added')),
      ...entry.removed.map((region) => deltaChipMarkup(`- ${region}`, 'removed')),
    ].join('');

    const skuChanges = entry.skuChanges.length
      ? `<div class="sku-change-list">${entry.skuChanges.map((sku) => `
        <article class="sku-change-card">
          <h4>${escapeHtml(sku.label)}</h4>
          <div class="delta-row">
            ${sku.added.map((region) => deltaChipMarkup(`+ ${region}`, 'added')).join('')}
            ${sku.removed.map((region) => deltaChipMarkup(`- ${region}`, 'removed')).join('')}
            ${sku.skuRemoved ? deltaChipMarkup('SKU entfernt', 'removed') : ''}
          </div>
        </article>
      `).join('')}</div>`
      : '';

    return `
      <article class="card compare-card">
        <div class="compare-card-header">
          <div>
            <p class="eyebrow">Changed model</p>
            <h2>${escapeHtml(entry.name)}</h2>
          </div>
          <span class="status-badge ${entry.status}">${escapeHtml(entry.status)}</span>
        </div>
        <div class="delta-row">${deltas || '<span class="compare-caption">Keine direkten Regions-Deltas im Gesamtmodell.</span>'}</div>
        <div class="compare-columns">
          <section class="compare-column">
            <h3>Old</h3>
            ${regionListMarkup(entry.old.regions)}
            <p class="compare-caption">${entry.old.regionCount} Regionen, ${entry.old.skus.length} Deployment-Typen</p>
          </section>
          <section class="compare-column">
            <h3>New</h3>
            ${regionListMarkup(entry.new.regions)}
            <p class="compare-caption">${entry.new.regionCount} Regionen, ${entry.new.skus.length} Deployment-Typen</p>
          </section>
        </div>
        ${skuChanges}
      </article>
    `;
  }).join('');
}

function syncUrl() {
  const params = new URLSearchParams();

  if (elements.searchInput.value.trim()) {
    params.set('search', elements.searchInput.value.trim());
  }
  if (elements.regionSelect.value) {
    params.set('region', elements.regionSelect.value);
  }
  if (elements.skuSelect.value) {
    params.set('sku', elements.skuSelect.value);
  }
  if (elements.regionalOnlyCheckbox.checked) {
    params.set('regionalOnly', 'true');
  }
  if (state.activeModelId) {
    params.set('model', state.activeModelId);
  }

  const query = params.toString();
  const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState({}, '', nextUrl);
}

function applyUrlState() {
  const params = new URLSearchParams(window.location.search);
  elements.searchInput.value = params.get('search') || '';
  elements.regionSelect.value = params.get('region') || '';
  elements.skuSelect.value = params.get('sku') || '';
  elements.regionalOnlyCheckbox.checked = params.get('regionalOnly') === 'true';
  state.activeModelId = params.get('model');
}

function renderDetail(model) {
  if (!model) {
    elements.modelDetail.className = 'detail-empty';
    elements.modelDetail.textContent = 'Select a model to see region coverage and deployment details.';
    return;
  }

  const globalTags = model.globalSkus.map((label) => tagMarkup(label, 'global')).join('');
  const regionalTags = model.regionalSkus.map((label) => tagMarkup(label, 'regional')).join('');
  const coverage = coveragePercent(model.regionCount);
  const skuCards = model.skus.map((sku) => `
    <article class="sku-card">
      <h3>${escapeHtml(sku.label)}</h3>
      <div class="coverage-stack">
        <div class="coverage-bar"><span style="width: ${coveragePercent(sku.regions.length)}%"></span></div>
        <div class="coverage-caption">${sku.regions.length} region${sku.regions.length === 1 ? '' : 's'} of ${state.meta.regions.length} tracked</div>
      </div>
      ${regionListMarkup(sku.regions)}
    </article>
  `).join('');

  elements.modelDetail.className = '';
  elements.modelDetail.innerHTML = `
    <div class="detail-block">
      <p class="eyebrow">Model details</p>
      <h2>${escapeHtml(model.name)}</h2>
      <p class="detail-meta">${model.summary}</p>
    </div>
    <div class="detail-block">
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-value">${model.regionCount}</div>
          <div class="metric-label">Available regions</div>
        </div>
        <div class="metric-card">
          <div class="metric-value">${model.skus.length}</div>
          <div class="metric-label">Deployment types</div>
        </div>
        <div class="metric-card">
          <div class="metric-value">${model.regionalSkus.length}</div>
          <div class="metric-label">Regional deployment types</div>
        </div>
        <div class="metric-card">
          <div class="metric-value">${model.globalSkus.length}</div>
          <div class="metric-label">Global deployment types</div>
        </div>
      </div>
    </div>
    <div class="detail-block">
      <h3>Coverage</h3>
      <div class="coverage-stack">
        <div class="coverage-bar"><span style="width: ${coverage}%"></span></div>
        <div class="coverage-caption">${coverage}% of the ${state.meta.regions.length} tracked regions include this model.</div>
      </div>
    </div>
    <div class="detail-block">
      <h3>Deployment types</h3>
      <div class="tag-row">${regionalTags || tagMarkup('No region-bound deployments recorded')}</div>
      ${globalTags ? `<div class="tag-row" style="margin-top: 10px;">${globalTags}</div>` : ''}
    </div>
    <div class="detail-block">
      <h3>All available regions</h3>
      ${regionListMarkup(model.regions)}
    </div>
    <div class="detail-block">
      <h3>Regions by deployment type</h3>
      <div class="sku-grid">${skuCards}</div>
    </div>
  `;
}

function renderList(models) {
  state.currentModels = models;
  elements.resultCount.textContent = `${models.length} result${models.length === 1 ? '' : 's'}`;

  if (!models.length) {
    state.activeModelId = null;
    elements.modelList.innerHTML = '<div class="empty-state">No models match the current filters. Clear one or more filters to widen the result set.</div>';
    renderDetail(null);
    syncUrl();
    return;
  }

  if (!models.some((model) => model.id === state.activeModelId)) {
    state.activeModelId = models[0].id;
  }

  elements.modelList.innerHTML = models.map((model) => {
    const activeClass = model.id === state.activeModelId ? 'is-active' : '';
    const coverage = coveragePercent(model.regionCount);
    const tags = [
      tagMarkup(`${model.regionCount} regions`, 'coverage'),
      model.regionalSkus.length ? tagMarkup('Has regional deployment', 'regional') : tagMarkup('Global-only', 'global'),
    ].join('');

    return `
      <button class="model-card ${activeClass}" data-model-id="${model.id}">
        <div class="model-card-header">
          <div class="model-card-title">
            <h3>${escapeHtml(model.name)}</h3>
            <p>${escapeHtml(model.summary)}</p>
          </div>
          ${tagMarkup(`${coverage}%`, 'coverage')}
        </div>
        <div class="coverage-stack">
          <div class="coverage-bar"><span style="width: ${coverage}%"></span></div>
          <div class="coverage-caption">Coverage across tracked regions</div>
        </div>
        <div class="tag-row">${tags}</div>
        ${regionListMarkup(model.regions)}
      </button>
    `;
  }).join('');

  const activeModel = models.find((model) => model.id === state.activeModelId) || models[0];
  renderDetail(activeModel);
  syncUrl();

  document.querySelectorAll('[data-model-id]').forEach((button) => {
    button.addEventListener('click', () => {
      state.activeModelId = button.dataset.modelId;
      renderList(state.currentModels);
    });
  });
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function buildQuery() {
  const params = new URLSearchParams();

  if (elements.searchInput.value.trim()) {
    params.set('search', elements.searchInput.value.trim());
  }
  if (elements.regionSelect.value) {
    params.set('region', elements.regionSelect.value);
  }
  if (elements.skuSelect.value) {
    params.set('sku', elements.skuSelect.value);
  }
  if (elements.regionalOnlyCheckbox.checked) {
    params.set('regionalOnly', 'true');
  }

  return params.toString();
}

async function refreshModels() {
  const query = buildQuery();
  const data = await fetchJson(`/api/models${query ? `?${query}` : ''}`);
  renderList(sortModels(data.models));
}

async function refreshCompare() {
  state.compare = await fetchJson('/api/compare/latest');
  renderCompare();
}

function clearFilters() {
  elements.searchInput.value = '';
  elements.regionSelect.value = '';
  elements.skuSelect.value = '';
  elements.regionalOnlyCheckbox.checked = false;
}

async function initialize() {
  try {
    const meta = await fetchJson('/api/meta');
    state.meta = meta;
    renderStats(meta);
    fillSelect(elements.regionSelect, meta.regions, 'All regions');
    fillSelect(elements.skuSelect, meta.skus, 'All deployment types');
    applyUrlState();

    const onFilterChange = () => refreshModels().catch(showError);
    elements.searchInput.addEventListener('input', onFilterChange);
    elements.regionSelect.addEventListener('change', onFilterChange);
    elements.skuSelect.addEventListener('change', onFilterChange);
    elements.regionalOnlyCheckbox.addEventListener('change', onFilterChange);
    elements.currentViewButton.addEventListener('click', () => setView('current'));
    elements.compareViewButton.addEventListener('click', () => setView('compare'));
    elements.clearFiltersButton.addEventListener('click', () => {
      clearFilters();
      refreshModels().catch(showError);
    });

    await refreshModels();
    await refreshCompare();
  } catch (error) {
    showError(error);
  }
}

function showError(error) {
  elements.modelList.innerHTML = `<div class="empty-state">${error.message}</div>`;
  renderDetail(null);
}

initialize();