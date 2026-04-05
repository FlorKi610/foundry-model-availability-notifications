# 🔔 Power Automate: Tägliche Teams-Benachrichtigung

## Flow-Beschreibung
Dieser Flow postet eine Adaptive Card in einen Teams-Channel, wenn sich die Model-Verfügbarkeit in Europa ändert.

## Setup in Power Automate

### Trigger: Recurrence
- **Frequency:** Day
- **Interval:** 1
- **At:** 07:00 (1h nach dem GitHub Actions Scan)

### Schritt 1: HTTP Request — Hole Summary
```
Method: GET
URI: https://raw.githubusercontent.com/FlorKi610/foundry-model-availability-notifications/main/region_diff_europe_summary.md
```

### Schritt 2: HTTP Request — Hole SKU Flat
```
Method: GET
URI: https://raw.githubusercontent.com/FlorKi610/foundry-model-availability-notifications/main/region_diff_europe_sku_flat.json
```

### Schritt 3: Parse JSON
Schema:
```json
{
  "type": "object",
  "properties": {
    "timestamp": { "type": "string" },
    "count": { "type": "integer" },
    "rows": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "model": { "type": "string" },
          "region": { "type": "string" },
          "sku": { "type": "string" },
          "sku_label": { "type": "string" },
          "is_available": { "type": "boolean" },
          "change_status": { "type": "string" },
          "sku_change_status": { "type": "string" },
          "model_removed": { "type": "boolean" }
        }
      }
    }
  }
}
```

### Schritt 4: Filter Array — Nur Änderungen
Filter: `change_status` is not equal to `unchanged`

### Schritt 5: Condition — Hat Änderungen?
If `length(body('Filter_Array'))` is greater than `0`

### Schritt 6 (If Yes): Post Adaptive Card in Teams Channel

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {
      "type": "TextBlock",
      "text": "🔄 Azure AI Model Availability Update",
      "weight": "Bolder",
      "size": "Large"
    },
    {
      "type": "TextBlock",
      "text": "Stand: @{body('Parse_JSON')?['timestamp']}",
      "isSubtle": true,
      "spacing": "None"
    },
    {
      "type": "ColumnSet",
      "columns": [
        {
          "type": "Column",
          "width": "auto",
          "items": [
            {
              "type": "TextBlock",
              "text": "🆕 Neu",
              "weight": "Bolder",
              "color": "Good"
            },
            {
              "type": "TextBlock",
              "text": "@{length(filter(body('Filter_Array'), item()?['change_status'], 'added'))} Einträge"
            }
          ]
        },
        {
          "type": "Column",
          "width": "auto",
          "items": [
            {
              "type": "TextBlock",
              "text": "⛔ Entfernt",
              "weight": "Bolder",
              "color": "Attention"
            },
            {
              "type": "TextBlock",
              "text": "@{length(filter(body('Filter_Array'), item()?['change_status'], 'removed'))} Einträge"
            }
          ]
        }
      ]
    },
    {
      "type": "TextBlock",
      "text": "**Top-Änderungen für deutsche Kunden:**",
      "wrap": true,
      "spacing": "Medium"
    },
    {
      "type": "FactSet",
      "facts": [
        {
          "title": "Germany West Central",
          "value": "Siehe Details im Dashboard →"
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "Action.OpenUrl",
      "title": "📊 Dashboard öffnen",
      "url": "https://FlorKi610.github.io/foundry-model-availability-notifications/"
    },
    {
      "type": "Action.OpenUrl",
      "title": "📋 GitHub Issues",
      "url": "https://github.com/FlorKi610/foundry-model-availability-notifications/issues?q=label:region-watch"
    },
    {
      "type": "Action.OpenUrl",
      "title": "🤖 Agent fragen",
      "url": "https://teams.microsoft.com"
    }
  ]
}
```

## Alternative: Incoming Webhook (einfacher)

Falls Power Automate zu komplex ist, kann auch der bestehende `TEAMS_WEBHOOK` Environment Variable in der GitHub Action genutzt werden:

1. Erstelle einen Incoming Webhook im Teams Channel
2. Kopiere die Webhook-URL
3. Setze sie als GitHub Secret `TEAMS_WEBHOOK` im Repository
4. Die GitHub Action sendet automatisch Benachrichtigungen bei Änderungen

```bash
# In GitHub Repo Settings → Secrets → Actions:
TEAMS_WEBHOOK=https://outlook.office.com/webhook/...
```
