---
name: foundry-model-availability
description: "Use for Azure AI Foundry model availability questions based on this repository's snapshot and diff artifacts. WHEN: model availability by region, compare Europe vs worldwide, latest availability changes, region coverage, summarize model rollout changes, generate a markdown digest, or answer which models are available in a region."
license: MIT
metadata:
  author: GitHub Copilot
  version: "1.0.0"
---

# Foundry Model Availability

This skill is designed to be installed as a user skill under `.agents/skills/foundry-model-availability` and then reused across sessions.

## Use This Skill When

- The user asks which models are available in a region.
- The user asks what changed recently in Europe or worldwide.
- The user asks for a markdown or JSON summary of the latest diff.
- The user wants a model lookup by name or slug.
- The user wants to surface this repository through a local CLI workflow.

## Preferred Inputs

If the current workspace is this repository, use the generated repository artifacts first:

- `.region-watch/regions_snapshot.json` for current model availability.
- `region_diff.json` for the latest raw compare payload.
- `region_diff_europe.json` and `region_diff_worldwide.json` for scope-specific views.
- `region_diff_europe_summary.md` and `region_diff_worldwide_summary.md` for digest-ready markdown.

If the workspace does not contain those files, ask the user for the repository path or tell them this skill expects a checkout of the `foundry-model-availability-notifications` project.

## Preferred Interface

Prefer the local CLI wrapper when available in the current workspace:

```bash
node bin/foundry-models.js summary --scope europe
node bin/foundry-models.js compare --limit 10
node bin/foundry-models.js model gpt-5.4
node bin/foundry-models.js list --region "Sweden Central"
```

If the user has GitHub CLI configured with an alias, the same workflow becomes:

```bash
gh foundry-models summary --scope europe
gh foundry-models compare --limit 10
gh foundry-models model gpt-5.4
```

## Response Guidance

- Use `Europe` as the default scope unless the user asks for worldwide coverage.
- For change summaries, mention the update source timestamp and whether the answer came from the latest refresh or the most recent historical diff.
- For model lookup, include the total region count and the available regions.
- If generated artifacts are missing or stale, tell the user to refresh them with `.region-watch/diff_regions.py`.
- Prefer concise answers that cite the exact scope used.

## Installation

From the repository root on Windows PowerShell:

```powershell
.\install-skill.ps1
```

To install the skill and also register the GitHub CLI alias:

```powershell
.\install-skill.ps1 -RegisterGhAlias
```