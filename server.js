const express = require('express');
const path = require('path');
const { createModelAvailabilityService } = require('./lib/modelAvailability');

const app = express();
const port = process.env.PORT || 3000;
const service = createModelAvailabilityService(__dirname);

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/meta', (_req, res) => {
  const snapshot = service.loadSnapshot();
  res.json({
    updatedAt: snapshot.updatedAt,
    regions: snapshot.regions,
    skus: snapshot.skus,
    totalModels: snapshot.models.length,
  });
});

app.get('/api/models', (req, res) => {
  const payload = service.listModels({
    search: req.query.search,
    region: req.query.region,
    sku: req.query.sku,
    regionalOnly: String(req.query.regionalOnly || 'false').toLowerCase() === 'true',
  });

  res.json(payload);
});

app.get('/api/models/:id', (req, res) => {
  const snapshot = service.loadSnapshot();
  const model = service.getModelById(req.params.id);

  if (!model) {
    res.status(404).json({ message: 'Model not found.' });
    return;
  }

  res.json({ updatedAt: snapshot.updatedAt, model });
});

app.get('/api/compare/latest', (_req, res) => {
  const compare = service.loadComparePayload();
  res.json(compare);
});

app.get('/api/views/primary', (_req, res) => {
  res.json({
    primaryScope: 'Europe',
    availableScopes: ['Europe', 'Worldwide'],
    primary: service.loadEuropePayload(),
  });
});

app.get('/api/europe/latest', (_req, res) => {
  res.json(service.loadEuropePayload());
});

app.get('/api/europe/flat', (_req, res) => {
  res.json(service.loadEuropeFlatPayload());
});

app.get('/api/europe/summary', (req, res) => {
  const payload = service.loadEuropeSummaryPayload();

  if (String(req.query.format || '').toLowerCase() === 'markdown') {
    res.type('text/markdown').send(payload.markdown);
    return;
  }

  res.json(payload);
});

app.get('/api/worldwide/latest', (_req, res) => {
  res.json(service.loadWorldwidePayload());
});

app.get('/api/worldwide/flat', (_req, res) => {
  res.json(service.loadWorldwideFlatPayload());
});

app.get('/api/worldwide/summary', (req, res) => {
  const payload = service.loadWorldwideSummaryPayload();

  if (String(req.query.format || '').toLowerCase() === 'markdown') {
    res.type('text/markdown').send(payload.markdown);
    return;
  }

  res.json(payload);
});

app.listen(port, () => {
  console.log(`Model browser running at http://localhost:${port}`);
});