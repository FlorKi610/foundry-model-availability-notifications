#!/usr/bin/env node

const path = require('path');
const { createModelAvailabilityService } = require('../lib/modelAvailability');

const service = createModelAvailabilityService(path.resolve(__dirname, '..'));

function printUsage() {
  console.log(`foundry-models

Usage:
  foundry-models summary [--scope europe|worldwide] [--json] [--markdown]
  foundry-models compare [--limit N] [--json]
  foundry-models model <name-or-slug> [--json]
  foundry-models list [--search text] [--region name] [--sku name] [--regional-only] [--limit N] [--json]

Examples:
  foundry-models summary --scope europe
  foundry-models compare --limit 10
  foundry-models model gpt-5.4
  foundry-models list --region "Sweden Central" --limit 15
`);
}

function parseArgs(rawArgs) {
  const options = {};
  const positionals = [];

  for (let index = 0; index < rawArgs.length; index += 1) {
    const token = rawArgs[index];

    if (!token.startsWith('--')) {
      positionals.push(token);
      continue;
    }

    const [keyPart, inlineValue] = token.slice(2).split('=', 2);
    const key = keyPart.trim();

    if (inlineValue !== undefined) {
      options[key] = inlineValue;
      continue;
    }

    const nextToken = rawArgs[index + 1];
    if (!nextToken || nextToken.startsWith('--')) {
      options[key] = true;
      continue;
    }

    options[key] = nextToken;
    index += 1;
  }

  return { options, positionals };
}

function printJson(payload) {
  console.log(JSON.stringify(payload, null, 2));
}

function limitItems(items, rawLimit) {
  const limit = rawLimit ? Number.parseInt(String(rawLimit), 10) : null;
  if (!limit || Number.isNaN(limit) || limit < 1) {
    return items;
  }

  return items.slice(0, limit);
}

function formatSummary(scope, payload) {
  const lines = [
    `Scope: ${scope}`,
    `Generated: ${payload.timestamp}`,
    `Update source: ${payload.updates?.source || 'n/a'}${payload.updates?.timestamp ? ` (${payload.updates.timestamp})` : ''}`,
    `Tracked regions: ${payload.summary.regionsTracked}`,
    `Models in scope: ${payload.summary.modelsTracked}`,
    `Regions with availability: ${payload.summary.regionsWithAvailability}`,
    `Models with updates: ${payload.summary.modelsWithUpdates}`,
    `Regions with updates: ${payload.summary.regionsWithUpdates}`,
    `Flat rows: ${payload.summary.flatRows}`,
  ];

  const topModels = limitItems(payload.highlights.models, 10).map((model) => {
    const added = model.updates?.added_regions?.length || 0;
    const removed = model.updates?.removed_regions?.length || 0;
    return `  - ${model.model}: ${model.region_count} current regions, +${added} / -${removed}`;
  });

  if (topModels.length) {
    lines.push('Top model updates:');
    lines.push(...topModels);
  }

  return lines.join('\n');
}

function formatCompare(payload, rawLimit) {
  const entries = limitItems(payload.entries, rawLimit);
  const lines = [
    `Latest refresh: ${payload.latestRefresh?.timestamp || 'n/a'}`,
    `Refresh source: ${payload.compareSource?.source || 'n/a'}`,
    `Changed models: ${payload.compareSource?.summary?.changedModels || 0}`,
    `Added regions: ${payload.compareSource?.summary?.addedRegions || 0}`,
    `Removed regions: ${payload.compareSource?.summary?.removedRegions || 0}`,
  ];

  if (entries.length) {
    lines.push('Changes:');
    for (const entry of entries) {
      const delta = [];
      if (entry.added.length) {
        delta.push(`+${entry.added.length}`);
      }
      if (entry.removed.length) {
        delta.push(`-${entry.removed.length}`);
      }
      lines.push(`  - ${entry.name} [${entry.status}] ${delta.join(' ') || 'no regional delta'} (${entry.new.regionCount} current regions)`);
    }
  }

  return lines.join('\n');
}

function formatModel(model) {
  const lines = [
    `Model: ${model.name}`,
    `Slug: ${model.id}`,
    `Regions: ${model.regionCount}`,
    `Global SKU: ${model.hasGlobalSku ? 'yes' : 'no'}`,
    `Summary: ${model.summary}`,
  ];

  if (model.regions.length) {
    lines.push(`Available regions: ${model.regions.join(', ')}`);
  }

  if (model.skus.length) {
    lines.push('SKUs:');
    for (const sku of model.skus) {
      lines.push(`  - ${sku.label}: ${sku.regions.join(', ')}`);
    }
  }

  return lines.join('\n');
}

function formatList(payload, rawLimit) {
  const models = limitItems(payload.models, rawLimit);
  const lines = [
    `Updated: ${payload.updatedAt}`,
    `Matching models: ${payload.count}`,
  ];

  if (models.length) {
    lines.push('Matches:');
    for (const model of models) {
      lines.push(`  - ${model.name} (${model.regionCount} regions)`);
    }
  }

  return lines.join('\n');
}

function fail(message) {
  console.error(message);
  process.exitCode = 1;
}

function main() {
  const [command, ...rest] = process.argv.slice(2);
  const { options, positionals } = parseArgs(rest);

  if (!command || command === 'help' || command === '--help') {
    printUsage();
    return;
  }

  if (command === 'summary') {
    const scope = service.normalizeScope(options.scope);
    const payload = service.loadScopeSummaryPayload(scope);

    if (options.markdown) {
      console.log(payload.markdown);
      return;
    }

    if (options.json) {
      printJson(payload);
      return;
    }

    console.log(formatSummary(scope, payload));
    return;
  }

  if (command === 'compare') {
    const payload = service.loadComparePayload();
    if (options.json) {
      printJson(payload);
      return;
    }

    console.log(formatCompare(payload, options.limit));
    return;
  }

  if (command === 'model') {
    const query = positionals.join(' ').trim();
    if (!query) {
      fail('Missing model name or slug. Example: foundry-models model gpt-5.4');
      return;
    }

    const model = service.findModel(query);
    if (!model) {
      fail(`Model not found: ${query}`);
      return;
    }

    if (options.json) {
      printJson(model);
      return;
    }

    console.log(formatModel(model));
    return;
  }

  if (command === 'list') {
    const payload = service.listModels({
      search: options.search,
      region: options.region,
      sku: options.sku,
      regionalOnly: Boolean(options['regional-only']),
    });

    if (options.json) {
      printJson(payload);
      return;
    }

    console.log(formatList(payload, options.limit));
    return;
  }

  fail(`Unknown command: ${command}`);
}

main();