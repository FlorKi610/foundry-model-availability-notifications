# 🤖 Teams Agent Setup Guide

## Übersicht

Dieser Ordner enthält einen **Microsoft 365 Copilot Declarative Agent**, der deutschen Account Teams hilft, die Verfügbarkeit von Azure AI Modellen in Europa abzufragen — mit voller SKU-Granularität.

## Dateien

| Datei | Beschreibung |
|-------|-------------|
| `manifest.json` | Teams App Manifest (für Teams Developer Portal) |
| `declarativeAgent.json` | Agent-Definition mit Capabilities und Conversation Starters |
| `instructions.md` | System-Prompt mit SKU-Erklärungen und Antwort-Formaten |
| `color.png` | App-Icon 192×192 (muss noch erstellt werden) |
| `outline.png` | App-Icon 32×32 transparent (muss noch erstellt werden) |

## Setup-Optionen

### Option A: Copilot Studio (Empfohlen — kein Code nötig)

1. Gehe zu [Copilot Studio](https://copilotstudio.microsoft.com)
2. Erstelle einen neuen **Declarative Agent**
3. Kopiere den Inhalt von `instructions.md` in das **Instructions**-Feld
4. Unter **Knowledge** → **Add knowledge** → **Public website/data**:
   ```
   https://raw.githubusercontent.com/FlorKi610/foundry-model-availability-notifications/main/region_diff_europe_sku_flat.json
   ```
5. Füge die Conversation Starters aus `declarativeAgent.json` hinzu
6. Klicke **Publish** → **Microsoft Teams**

### Option B: Teams Developer Portal

1. Gehe zu [Teams Developer Portal](https://dev.teams.microsoft.com)
2. Erstelle eine neue App
3. Lade `manifest.json` hoch
4. Erstelle 2 Icons (192×192 und 32×32) und lade sie als `color.png` / `outline.png` hoch
5. Ersetze `{{APP_ID}}` in manifest.json durch die generierte App-ID
6. Unter **Copilot agents** → lade `declarativeAgent.json` hoch
7. Publish to organization

### Option C: Teams Toolkit (VS Code)

```bash
# Installiere Teams Toolkit Extension in VS Code
# Öffne diesen Ordner als Projekt
# F5 zum Testen im Teams Developer Tenant
```

## Datenquelle

Der Agent nutzt diese automatisch aktualisierten Dateien:

| Datei | URL | Inhalt |
|-------|-----|--------|
| SKU Flat (Europa) | `region_diff_europe_sku_flat.json` | 1 Zeile = 1 Model+Region+SKU |
| Summary (Europa) | `region_diff_europe_summary.md` | Markdown-Zusammenfassung |
| SKU Flat (Weltweit) | `region_diff_worldwide_sku_flat.json` | Alle Regionen weltweit |

**Aktualisierung:** Täglich um 06:00 UTC via GitHub Actions.

## Beispiel-Interaktionen

### "Welche Modelle gibt es in Germany West Central?"

> 📍 **Germany West Central** — Stand: 17.03.2026
>
> | Modell | SKU-Variante | Status |
> |--------|-------------|--------|
> | gpt-4o | Standard (all) | ✅ |
> | gpt-4o | Provisioned (PTU managed) | ✅ |
> | gpt-4o | Datazone standard | ✅ |
> | gpt-5 | Standard global deployments | ✅ |
> | gpt-5.2 | Standard global deployments | 🆕 Neu |
> | DeepSeek-R1 | Global Standard | ✅ |
> | DeepSeek-R1 | Global Provisioned Managed | ✅ |

### "In welchen SKUs gibt es GPT-5.2 in Europa?"

> 🤖 **gpt-5.2** — verfügbar in 11 EU-Regionen
>
> **SKU:** Standard global deployments
>
> | Region | Verfügbar | Status |
> |--------|-----------|--------|
> | France Central | ✅ | 🆕 Neu |
> | Germany West Central | ✅ | 🆕 Neu |
> | Italy North | ✅ | 🆕 Neu |
> | Sweden Central | ✅ | 🆕 Neu |
> | ... | | |
>
> ⚠️ **Hinweis:** gpt-5.2 ist aktuell nur als *Standard global deployment* verfügbar. Provisioned (PTU) und Datazone-SKUs gibt es noch nicht.

### "Welche Modelle wurden kürzlich retired?"

> ⛔ **Retirements** (Stand: 10.03.2026)
>
> | Modell | Entfernt aus | SKU-Varianten betroffen |
> |--------|-------------|------------------------|
> | gpt-35-turbo | 8 EU-Regionen | Standard, Provisioned |
> | gpt-4 | 7 EU-Regionen | Standard, Provisioned |
> | gpt-4-32k | 7 EU-Regionen | Standard, Provisioned |
>
> 💡 **Empfehlung:** Kunden auf gpt-4o (Standard + Provisioned) oder gpt-5 (Standard global) migrieren.

### "Hat Germany West Central Datazone-Support?"

> ✅ **Germany West Central unterstützt Datazone-SKUs!**
>
> Modelle mit Datazone in Germany West Central:
> | Modell | Datazone standard | Datazone provisioned |
> |--------|------------------|---------------------|
> | gpt-4o | ✅ | ✅ |
> | gpt-4o-mini | ✅ | ✅ |
>
> 🔒 **Datazone** garantiert, dass Daten innerhalb der EU-Datenzone verarbeitet werden — ideal für DSGVO-sensitive Workloads.

## Troubleshooting

- **Agent antwortet nicht auf Modellfragen:** Prüfe ob die Knowledge Source URL erreichbar ist
- **Daten sind veraltet:** Prüfe ob die GitHub Action `region-watch` erfolgreich läuft
- **SKU-Daten fehlen:** Die SKU-Flat-Datei wird seit dem letzten Update generiert — einmal den Workflow manuell triggern
