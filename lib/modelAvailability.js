const fs = require('fs');
const path = require('path');

function createModelAvailabilityService(baseDir) {
  const rootDir = path.resolve(baseDir || process.cwd());
  const snapshotPath = path.join(rootDir, '.region-watch', 'regions_snapshot.json');
  const regionDiffPath = path.join(rootDir, 'region_diff.json');
  const regionDiffEuropePath = path.join(rootDir, 'region_diff_europe.json');
  const regionDiffEuropeFlatPath = path.join(rootDir, 'region_diff_europe_flat.json');
  const regionDiffEuropeSummaryPath = path.join(rootDir, 'region_diff_europe_summary.md');
  const regionDiffWorldwidePath = path.join(rootDir, 'region_diff_worldwide.json');
  const regionDiffWorldwideFlatPath = path.join(rootDir, 'region_diff_worldwide_flat.json');
  const regionDiffWorldwideSummaryPath = path.join(rootDir, 'region_diff_worldwide_summary.md');
  const historyDirPath = path.join(rootDir, '.region-watch', 'history');

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

  function listModels(options = {}) {
    const snapshot = loadSnapshot();
    const normalizedSearch = String(options.search || '').trim().toLowerCase();
    const normalizedRegion = String(options.region || '').trim().toLowerCase();
    const normalizedSku = String(options.sku || '').trim().toLowerCase();
    const requireRegionalOnly = Boolean(options.regionalOnly);

    const models = snapshot.models.filter((model) => {
      if (normalizedSearch && !model.name.toLowerCase().includes(normalizedSearch) && model.id !== normalizedSearch) {
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

    return {
      updatedAt: snapshot.updatedAt,
      count: models.length,
      models,
    };
  }

  function getModelById(id) {
    const snapshot = loadSnapshot();
    return snapshot.models.find((model) => model.id === id) || null;
  }

  function findModel(query) {
    const normalizedQuery = String(query || '').trim().toLowerCase();
    if (!normalizedQuery) {
      return null;
    }

    const snapshot = loadSnapshot();
    return snapshot.models.find((model) => model.id === normalizedQuery || model.name.toLowerCase() === normalizedQuery)
      || snapshot.models.find((model) => model.name.toLowerCase().includes(normalizedQuery))
      || null;
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
        skus: Object.fromEntries(oldSkus.map((sku) => [sku.key, { label: sku.label, regions: sku.regions }])),
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

  function loadWorldwidePayload() {
    return readJson(regionDiffWorldwidePath);
  }

  function loadWorldwideFlatPayload() {
    return readJson(regionDiffWorldwideFlatPath);
  }

  function loadScopedSummaryPayload(scopedPayload, flatPayload, markdownPath) {
    const summaryMarkdown = fs.readFileSync(markdownPath, 'utf8');
    const byModel = scopedPayload.views?.by_model || [];
    const byRegion = scopedPayload.views?.by_region || [];
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
      timestamp: scopedPayload.timestamp,
      updates: scopedPayload.updates,
      filter: scopedPayload.filter,
      summary: {
        modelsTracked: byModel.length,
        regionsTracked: scopedPayload.filter?.regions?.length || 0,
        regionsWithAvailability: byRegion.length,
        modelsWithUpdates: modelsWithUpdates.length,
        regionsWithUpdates: regionsWithUpdates.length,
        flatRows: flatPayload.count || 0,
      },
      highlights: {
        regions: regionsWithUpdates,
        models: modelsWithUpdates,
      },
      markdown: summaryMarkdown,
    };
  }

  function loadEuropeSummaryPayload() {
    return loadScopedSummaryPayload(loadEuropePayload(), loadEuropeFlatPayload(), regionDiffEuropeSummaryPath);
  }

  function loadWorldwideSummaryPayload() {
    return loadScopedSummaryPayload(loadWorldwidePayload(), loadWorldwideFlatPayload(), regionDiffWorldwideSummaryPath);
  }

  function normalizeScope(scope) {
    return String(scope || 'europe').trim().toLowerCase() === 'worldwide' ? 'worldwide' : 'europe';
  }

  function loadScopePayload(scope) {
    return normalizeScope(scope) === 'worldwide' ? loadWorldwidePayload() : loadEuropePayload();
  }

  function loadScopeSummaryPayload(scope) {
    return normalizeScope(scope) === 'worldwide' ? loadWorldwideSummaryPayload() : loadEuropeSummaryPayload();
  }

  return {
    rootDir,
    slugifyModel,
    dedupeSorted,
    normalizeModel,
    loadSnapshot,
    listModels,
    getModelById,
    findModel,
    loadCurrentRefresh,
    loadLatestHistoryDiff,
    loadComparePayload,
    loadEuropePayload,
    loadEuropeFlatPayload,
    loadEuropeSummaryPayload,
    loadWorldwidePayload,
    loadWorldwideFlatPayload,
    loadWorldwideSummaryPayload,
    normalizeScope,
    loadScopePayload,
    loadScopeSummaryPayload,
  };
}

module.exports = {
  createModelAvailabilityService,
};