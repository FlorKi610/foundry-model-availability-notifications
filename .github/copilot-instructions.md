# Foundry Model Availability Notifications

> Project memory and instructions for GitHub Copilot CLI and compatible AI agents.
> This file is the single source of truth for project context, conventions, and architecture.

## Project Overview

Automated monitoring system that tracks Azure AI Foundry model availability across regions every 6 hours. Detects changes, generates diff views, creates GitHub issues, and publishes a live dashboard.

**Key outputs:**
- `LATEST_CHANGES.md` — Diff-only view showing what changed since the last scan
- GitHub Issues — Formatted notifications with impact classification
- MkDocs Dashboard — Live site at `https://FlorKi610.github.io/foundry-model-availability-notifications/`
- REST API + CLI — Programmatic access to model availability data

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend | Node.js + Express.js | >= 18 |
| Scripting | Python | 3.11 |
| CI/CD | GitHub Actions | Scheduled (cron `0 */6 * * *`) |
| Docs | MkDocs + Material | Latest |
| Storage | JSON files (no database) | — |
| Frontend | Vanilla JS (SPA) | — |
| Package Mgmt | npm + pip | — |

## Architecture & Data Flow

```
Azure AI Docs (GitHub)
    ↓ every 6 hours (GitHub Actions)
.region-watch/diff_regions.py
    ↓ fetches model matrix markdown tables, parses availability
    ↓ compares against previous snapshot
regions_snapshot.json (updated)
    ↓ if changes detected
    ├→ .region-watch/history/diff-*.json   (historical record)
    ├→ region_diff.json                     (raw diff payload)
    ├→ region_diff_europe.json              (EU-scoped view: by_model + by_region)
    ├→ region_diff_worldwide.json           (worldwide view)
    ├→ region_diff_*_flat.json              (BI-ready flat rows)
    ├→ region_diff_*_summary.md             (stats)
    ├→ LATEST_CHANGES.md                    (diff-only human-readable view)
    ├→ REGION_AVAILABILITY.md               (full model listing)
    ├→ GitHub Issue                          (notification with diff-focused body)
    └→ MkDocs site                          (deployed to GitHub Pages)
```

## Key Files & Directories

```
├── .github/
│   ├── copilot-instructions.md        ← YOU ARE HERE
│   ├── instructions/                  ← Granular AI agent skills
│   │   ├── senior-engineer.instructions.md
│   │   ├── ui-ux-architect.instructions.md
│   │   └── workflow-orchestrator.instructions.md
│   ├── workflows/
│   │   ├── region-watch.yml           ← Main 6-hour workflow (watch + issue + commit)
│   │   ├── deploy-docs.yml            ← MkDocs → GitHub Pages
│   │   ├── diff-notifier.yml          ← Manual demo issue creation
│   │   └── security.yml               ← Gitleaks + dependency audit
│   └── scripts/
│       └── send_diff_email.py         ← Optional email notifications
│
├── .region-watch/
│   ├── diff_regions.py                ← Core: fetches + diffs model availability (38 KB)
│   ├── render_markdown.py             ← Generates REGION_AVAILABILITY.md
│   ├── regions_snapshot.json          ← Current state of ALL models (source of truth)
│   ├── retirement_data.json           ← Model retirement tracking
│   └── history/                       ← Historical diff-*.json files
│
├── lib/
│   └── modelAvailability.js           ← Core service: snapshot loading, filtering, comparison
│
├── server.js                          ← Express API server (97 lines)
├── bin/foundry-models.js              ← CLI entry point
├── generate_docs.py                   ← MkDocs page generator
├── skills/foundry-model-availability/ ← Copilot skill package
│
├── region_diff.json                   ← Latest raw diff payload
├── region_diff_europe.json            ← Europe-scoped availability + changes
├── region_diff_worldwide.json         ← Worldwide availability + changes
├── LATEST_CHANGES.md                  ← Diff-only view (what changed this scan)
└── REGION_AVAILABILITY.md             ← Full model availability listing
```

## Data Formats

### Snapshot (`regions_snapshot.json`)
```json
{
  "ModelName": {
    "all": ["Region1", "Region2"],
    "skus": {
      "sku-key": {
        "label": "Display Name",
        "regions": ["Region1"]
      }
    }
  }
}
```

### Diff (`region_diff.json` → `changes`)
```json
{
  "ModelName": {
    "all": { "added": ["Region"], "removed": [] },
    "skus": {
      "sku-key": { "label": "Name", "added": ["Region"], "removed": [] }
    },
    "model_removed": false
  }
}
```

### Impact Classification
| Icon | Type | Meaning |
|------|------|---------|
| 🆕 | `new` | Brand new model in Europe |
| 📈 | `expanded` | Model added to more regions |
| 🔀 | `mixed` | Both additions and removals |
| 📉 | `reduced` | Model lost regions |
| ⛔ | `retired` | Model fully removed |

### SKU Categories
| Icon | Category | Examples |
|------|----------|---------|
| 🏢 | Regional | Standard, Provisioned (PTU managed) |
| 🌐 | Global | Global Standard, Provisioned global |
| 📊 | Datazone | Datazone standard, Datazone provisioned managed |
| 🔄 | Batch | Global batch, Global batch datazone |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/meta` | Metadata (timestamps, regions, SKUs, model count) |
| GET | `/api/models` | List models (query: `search`, `region`, `sku`, `regionalOnly`) |
| GET | `/api/models/:id` | Single model by slug |
| GET | `/api/compare/latest` | Latest changes (old vs new state) |
| GET | `/api/europe/latest` | Europe JSON view (by_model + by_region) |
| GET | `/api/worldwide/latest` | Worldwide JSON view |
| GET | `/api/europe/summary` | Europe summary (JSON or `?format=markdown`) |

## Conventions & Patterns

### Code Style
- **ES6 Modules**: `"type": "module"` in package.json, use `import`/`export`
- **Files**: `kebab-case` (e.g., `model-availability.js`)
- **Classes**: `PascalCase` (e.g., `DataStore`)
- **Functions**: `camelCase` (e.g., `loadSnapshot()`)
- **Constants**: `UPPER_SNAKE` (e.g., `MAX_BODY`)

### Model Slugs
Models are slugified for URL-safe IDs: `GPT-4o` → `gpt-4o`, `Llama-3.3-70B-Instruct` → `llama-3-3-70b-instruct`

### Error Handling
- Python scripts: `try/except` with `Warning:` prefix to stderr
- Node.js API: Express error middleware returning `{ error, code, details }`
- GitHub Actions: Fallback logic (e.g., issue creation retries without assignees)

### Workflow Conventions
- Issue label: `region-watch`
- Commit author: `region-bot <bot@users.noreply.github.com>`
- Issues only created when actual changes detected (not SKU-only metadata)
- Issue body is diff-focused: only changed models/regions shown
- SKU tables show Changes column (added/removed) not full region listings
- `LATEST_CHANGES.md` generated every run (shows "No changes" if nothing changed)

### Python (diff_regions.py)
- Fetches model matrix files from `MicrosoftDocs/azure-ai-docs` via GitHub API
- Parses markdown tables (✅ = available)
- Uses `GITHUB_TOKEN` env var for rate limit boost
- Writes multiple output artifacts (JSON, markdown, flat rows)

## Development Workflow

### Running Locally
```bash
# Install dependencies
npm install
pip install -r requirements.txt

# Run the model availability check
python .region-watch/diff_regions.py > region_diff.json

# Start the web server
npm start  # → http://localhost:3000

# Use the CLI
node bin/foundry-models.js summary --scope europe
node bin/foundry-models.js compare --limit 10
```

### Testing Changes to the Workflow
1. Modify `.github/workflows/region-watch.yml`
2. Validate YAML: `python -c "import yaml; yaml.safe_load(open('.github/workflows/region-watch.yml'))"`
3. Run `diff_regions.py` locally to generate test data
4. Commit and push, then trigger with `gh workflow run region-watch.yml`
5. Check results: `gh run list --workflow=region-watch.yml --limit 1`

### Adding New Data Sources
See `ADDING_NEW_MODELS.md` for instructions on adding new model matrix files to the scraper.

## Skills Reference

This project uses granular instruction files in `.github/instructions/`:

| Skill | File | Use For |
|-------|------|---------|
| Senior Engineer | `senior-engineer.instructions.md` | Code implementation, refactoring, debugging, architecture |
| UI/UX Architect | `ui-ux-architect.instructions.md` | Visual design, layout, accessibility, dashboard styling |
| Workflow Orchestrator | `workflow-orchestrator.instructions.md` | Complex tasks, planning, multi-step operations |

Additionally, the `skills/foundry-model-availability/SKILL.md` provides a Copilot skill for querying model availability data interactively.

## Lessons & Decisions

- **Diff-only issue body**: Issue SKU tables show only added/removed regions per SKU, not full region listings. This keeps issues focused and readable.
- **LATEST_CHANGES.md**: Generated every workflow run. Shows `+`/`-` diff syntax per model. "No changes detected" when nothing changed.
- **Europe as default scope**: All user-facing summaries default to Europe unless worldwide is explicitly requested.
- **No database**: Pure JSON file storage. The `regions_snapshot.json` is the single source of truth for current state.
- **History retention**: Every detected change is stored as `diff-{timestamp}.json` in `.region-watch/history/` for audit trail.
- **Atomic workflow**: The GitHub Actions workflow does fetch → diff → generate → commit → issue in one job to ensure consistency.
