const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const port = process.env.PORT || 3000;
const snapshotPath = path.join(__dirname, '.region-watch', 'regions_snapshot.json');
const regionDiffPath = path.join(__dirname, 'region_diff.json');
const regionDiffEuropePath = path.join(__dirname, 'region_diff_europe.json');
const regionDiffEuropeFlatPath = path.join(__dirname, 'region_diff_europe_flat.json');
const regionDiffEuropeSummaryPath = path.join(__dirname, 'region_diff_europe_summary.md');
const regionDiffWorldwidePath = path.join(__dirname, 'region_diff_worldwide.json');
const regionDiffWorldwideFlatPath = path.join(__dirname, 'region_diff_worldwide_flat.json');
const regionDiffWorldwideSummaryPath = path.join(__dirname, 'region_diff_worldwide_summary.md');
const historyDirPath = path.join(__dirname, '.region-watch', 'history');

function slugifyModel(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function dedupeSorted(values) {
  return [...new Set(values || [])].sort();
}

function normalizeModel(name, payload) {
  const skuEntries = Object.entries(payload.skus || {}).map(([skuKey, skuValue]) => ({
    key: skuKey,
    label: skuValue.label || skuKey,
    regions: dedupeSorted(skuValue.regions || []),
  }));

  const allRegions = new Set(payload.all || []);
  for (const sku of skuEntries) {
    for (const region of sku.regions) {
      allRegions.add(region);
    }
  }

  const globalSkus = skuEntries.filter((sku) => /global/i.test(sku.label)).map((sku) => sku.label);
  const regionalSkus = skuEntries.filter((sku) => !/global/i.test(sku.label)).map((sku) => sku.label);

  return {
    id: slugifyModel(name),
    name,
    regions: dedupeSorted([...allRegions]),
    regionCount: allRegions.size,
    skus: skuEntries,
    skuLabels: skuEntries.map((sku) => sku.label).sort(),
    hasGlobalSku: globalSkus.length > 0,
    globalSkus,
    regionalSkus,
    summary: `${allRegions.size} regions across ${skuEntries.length || 1} deployment type${skuEntries.length === 1 ? '' : 's'}`,
  };
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

function loadSnapshot() {
  const data = readJson(snapshotPath);
  const stats = fs.statSync(snapshotPath);

  const models = Object.entries(data).map(([name, payload]) => normalizeModel(name, payload));

  const regionOptions = [...new Set(models.flatMap((model) => model.regions))].sort();
  const skuOptions = [...new Set(models.flatMap((model) => model.skuLabels))].sort();

  models.sort((left, right) => left.name.localeCompare(right.name));

  return {
    updatedAt: stats.mtime.toISOString(),
    models,
    regions: regionOptions,
    skus: skuOptions,
  };
}

function buildStatusSummary(changes) {
  const values = Object.values(changes || {});
  const addedRegions = values.reduce((sum, change) => sum + (change.all?.added?.length || 0), 0);
  const removedRegions = values.reduce((sum, change) => sum + (change.all?.removed?.length || 0), 0);
  const modelAdds = values.filter((change) => !change.model_removed && !(change.all?.removed?.length) && (change.all?.added?.length || 0) > 0).length;
  const modelRemovals = values.filter((change) => change.model_removed).length;

  return {
    changedModels: values.length,
    addedRegions,
    removedRegions,
    modelAdds,
    modelRemovals,
  };
}

function loadCurrentRefresh() {
  const payload = readJson(regionDiffPath);
  const summary = buildStatusSummary(payload.changes || {});
  return {
    timestamp: payload.timestamp,
    hasChanges: summary.changedModels > 0,
    summary,
    changes: payload.changes || {},
    current: payload.current || {},
    source: 'latest-refresh',
  };
}

function loadLatestHistoryDiff() {
  const files = fs.readdirSync(historyDirPath)
    .filter((file) => file.endsWith('.json'))
    .sort();

  if (!files.length) {
    return null;
  }

  const latestFile = files[files.length - 1];
  const payload = readJson(path.join(historyDirPath, latestFile));
  const summary = buildStatusSummary(payload.changes || {});

  return {
    timestamp: payload.timestamp,
    hasChanges: summary.changedModels > 0,
    summary,
    changes: payload.changes || {},
    source: latestFile,
  };
}

function reconstructPreviousModel(modelName, change, currentModelsByName) {
  const currentModel = currentModelsByName.get(modelName);

  if (change.model_removed) {
    const oldSkus = Object.entries(change.skus || {}).map(([skuKey, skuChange]) => ({
      key: skuKey,
      label: skuChange.label || skuKey,
      regions: dedupeSorted(skuChange.removed || []),
    }));

    return normalizeModel(modelName, {
      all: dedupeSorted(change.all?.removed || []),
      skus: Object.fromEntries(oldSkus.map((sku) => [sku.key, { label: sku.label, regions: sku.regions }]))
    });
  }

  if (!currentModel) {
    return normalizeModel(modelName, { all: [], skus: {} });
  }

  const oldAll = dedupeSorted([
    ...currentModel.regions.filter((region) => !(change.all?.added || []).includes(region)),
    ...(change.all?.removed || []),
  ]);

  const oldSkuMap = new Map();

  for (const sku of currentModel.skus) {
    const skuChange = (change.skus || {})[sku.key];
    const oldRegions = skuChange
      ? dedupeSorted([
        ...sku.regions.filter((region) => !(skuChange.added || []).includes(region)),
        ...(skuChange.removed || []),
      ])
      : sku.regions;

    if (oldRegions.length) {
      oldSkuMap.set(sku.key, { label: sku.label, regions: oldRegions });
    }
  }

  for (const [skuKey, skuChange] of Object.entries(change.skus || {})) {
    if (!oldSkuMap.has(skuKey) && (skuChange.removed || []).length) {
      oldSkuMap.set(skuKey, { label: skuChange.label || skuKey, regions: dedupeSorted(skuChange.removed || []) });
    }
  }

  return normalizeModel(modelName, {
    all: oldAll,
    skus: Object.fromEntries(oldSkuMap.entries()),
  });
}

function buildCompareEntry(modelName, change, currentModelsByName) {
  const oldModel = reconstructPreviousModel(modelName, change, currentModelsByName);
  const newModel = currentModelsByName.get(modelName) || normalizeModel(modelName, { all: [], skus: {} });
  const added = dedupeSorted(change.all?.added || []);
  const removed = dedupeSorted(change.all?.removed || []);

  let status = 'changed';
  if (change.model_removed) {
    status = 'removed';
  } else if (!oldModel.regionCount && newModel.regionCount) {
    status = 'new-model';
  } else if (added.length && !removed.length) {
    status = 'expanded';
  } else if (!added.length && removed.length) {
    status = 'reduced';
  }

  const skuChanges = Object.entries(change.skus || {}).map(([skuKey, skuChange]) => ({
    key: skuKey,
    label: skuChange.label || skuKey,
    added: dedupeSorted(skuChange.added || []),
    removed: dedupeSorted(skuChange.removed || []),
    skuRemoved: Boolean(skuChange.sku_removed),
  }));

  return {
    id: slugifyModel(modelName),
    name: modelName,
    status,
    old: oldModel,
    new: newModel,
    added,
    removed,
    skuChanges,
  };
}

function loadComparePayload() {
  const currentRefresh = loadCurrentRefresh();
  const snapshot = loadSnapshot();
  const currentModelsByName = new Map(snapshot.models.map((model) => [model.name, model]));
  const sourcePayload = currentRefresh.hasChanges ? currentRefresh : loadLatestHistoryDiff();

  const entries = Object.entries(sourcePayload?.changes || {})
    .map(([modelName, change]) => buildCompareEntry(modelName, change, currentModelsByName))
    .sort((left, right) => {
      const statusOrder = ['new-model', 'expanded', 'changed', 'reduced', 'removed'];
      return statusOrder.indexOf(left.status) - statusOrder.indexOf(right.status) || left.name.localeCompare(right.name);
    });

  return {
    latestRefresh: currentRefresh,
    compareSource: sourcePayload
      ? {
        timestamp: sourcePayload.timestamp,
        source: sourcePayload.source,
        hasChanges: sourcePayload.hasChanges,
        summary: sourcePayload.summary,
      }
      : null,
    count: entries.length,
    entries,
  };
}

function loadEuropePayload() {
  return readJson(regionDiffEuropePath);
}

function loadEuropeFlatPayload() {
  return readJson(regionDiffEuropeFlatPath);
}

function loadEuropeSummaryPayload() {
  return loadScopedSummaryPayload(loadEuropePayload(), loadEuropeFlatPayload(), regionDiffEuropeSummaryPath);
}

function loadWorldwidePayload() {
  return readJson(regionDiffWorldwidePath);
}

function loadWorldwideFlatPayload() {
  return readJson(regionDiffWorldwideFlatPath);
}

function loadWorldwideSummaryPayload() {
  return loadScopedSummaryPayload(loadWorldwidePayload(), loadWorldwideFlatPayload(), regionDiffWorldwideSummaryPath);
}

function loadScopedSummaryPayload(scopedPayload, flatPayload, markdownPath) {
  const summaryMarkdown = fs.readFileSync(markdownPath, 'utf8');
  const scoped = scopedPayload;
  const flat = flatPayload;

  const byModel = scoped.views?.by_model || [];
  const byRegion = scoped.views?.by_region || [];
  const modelsWithUpdates = byModel.filter((item) =>
    item.updates?.added_regions?.length
    || item.updates?.removed_regions?.length
    || item.updates?.sku_updates?.length
    || item.updates?.model_removed
  );
  const regionsWithUpdates = byRegion.filter((item) =>
    item.updates?.added_models?.length
    || item.updates?.removed_models?.length
  );

  return {
    timestamp: scoped.timestamp,
    updates: scoped.updates,
    filter: scoped.filter,
    summary: {
      modelsTracked: byModel.length,
      regionsTracked: scoped.filter?.regions?.length || 0,
      regionsWithAvailability: byRegion.length,
      modelsWithUpdates: modelsWithUpdates.length,
      regionsWithUpdates: regionsWithUpdates.length,
      flatRows: flat.count || 0,
    },
    highlights: {
      regions: regionsWithUpdates,
      models: modelsWithUpdates,
    },
    markdown: summaryMarkdown,
  };
}

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/meta', (_req, res) => {
  const snapshot = loadSnapshot();
  res.json({
    updatedAt: snapshot.updatedAt,
    regions: snapshot.regions,
    skus: snapshot.skus,
    totalModels: snapshot.models.length,
  });
});

app.get('/api/models', (req, res) => {
  const { search = '', region = '', sku = '', regionalOnly = 'false' } = req.query;
  const snapshot = loadSnapshot();

  const normalizedSearch = String(search).trim().toLowerCase();
  const normalizedRegion = String(region).trim().toLowerCase();
  const normalizedSku = String(sku).trim().toLowerCase();
  const requireRegionalOnly = String(regionalOnly).toLowerCase() === 'true';

  const filtered = snapshot.models.filter((model) => {
    if (normalizedSearch && !model.name.toLowerCase().includes(normalizedSearch)) {
      return false;
    }

    if (normalizedRegion && !model.regions.some((entry) => entry.toLowerCase() === normalizedRegion)) {
      return false;
    }

    if (normalizedSku && !model.skuLabels.some((entry) => entry.toLowerCase() === normalizedSku)) {
      return false;
    }

    if (requireRegionalOnly && model.regionalSkus.length === 0) {
      return false;
    }

    return true;
  });

  res.json({
    updatedAt: snapshot.updatedAt,
    count: filtered.length,
    models: filtered,
  });
});

app.get('/api/models/:id', (req, res) => {
  const snapshot = loadSnapshot();
  const model = snapshot.models.find((entry) => entry.id === req.params.id);

  if (!model) {
    res.status(404).json({ message: 'Model not found.' });
    return;
  }

  res.json({ updatedAt: snapshot.updatedAt, model });
});

app.get('/api/compare/latest', (_req, res) => {
  const compare = loadComparePayload();
  res.json(compare);
});

app.get('/api/views/primary', (_req, res) => {
  res.json({
    primaryScope: 'Europe',
    availableScopes: ['Europe', 'Worldwide'],
    primary: loadEuropePayload(),
  });
});

app.get('/api/europe/latest', (_req, res) => {
  res.json(loadEuropePayload());
});

app.get('/api/europe/flat', (_req, res) => {
  res.json(loadEuropeFlatPayload());
});

app.get('/api/europe/summary', (req, res) => {
  const payload = loadEuropeSummaryPayload();

  if (String(req.query.format || '').toLowerCase() === 'markdown') {
    res.type('text/markdown').send(payload.markdown);
    return;
  }

  res.json(payload);
});

app.get('/api/worldwide/latest', (_req, res) => {
  res.json(loadWorldwidePayload());
});

app.get('/api/worldwide/flat', (_req, res) => {
  res.json(loadWorldwideFlatPayload());
});

app.get('/api/worldwide/summary', (req, res) => {
  const payload = loadWorldwideSummaryPayload();

  if (String(req.query.format || '').toLowerCase() === 'markdown') {
    res.type('text/markdown').send(payload.markdown);
    return;
  }

  res.json(payload);
});

app.listen(port, () => {
  console.log(`Model browser running at http://localhost:${port}`);
});