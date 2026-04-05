#!/usr/bin/env python3
import json, os, re, sys, requests
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

# Model matrix directories to check for availability data
MODEL_MATRIX_DIRS = [
    "articles/foundry/openai/includes/model-matrix",  # OpenAI models (gpt, dall-e, whisper, etc.)
    "articles/foundry/foundry-models/includes/model-matrix",  # Foundry models (deepseek, llama, grok, etc.)
]

# Serverless/MaaS (Models-as-a-Service) files with transposed table format
# These files have models in rows and regions in text columns
MAAS_FILES = [
    "articles/foundry/includes/region-availability-maas.md",  # Serverless API models (Anthropic, Cohere, Phi, Mistral, etc.)
]

def get_model_matrix_directories() -> list[str]:
    """Get list of model matrix directories to check, including any from environment."""
    dirs = list(MODEL_MATRIX_DIRS)
    # Allow adding additional directories via environment variable
    extra_dirs = os.getenv("MODEL_MATRIX_EXTRA_DIRS", "")
    if extra_dirs:
        for directory in extra_dirs.split(","):
            directory = directory.strip()
            if directory and directory not in dirs:
                dirs.append(directory)
    return dirs

def get_model_matrix_api_url(directory: str) -> str:
    """Generate GitHub API URL for a model matrix directory.
    
    Args:
        directory: Relative path within azure-ai-docs repository
        
    Returns:
        Full GitHub API URL for the directory contents
        
    Note:
        Directory is expected to be a relative path like 'articles/foundry/...'
        and should not contain path traversal sequences.
    """
    # Basic validation to prevent path traversal
    if ".." in directory or directory.startswith("/"):
        raise ValueError(f"Invalid directory path: {directory}")
    return f"https://api.github.com/repos/MicrosoftDocs/azure-ai-docs/contents/{directory}?ref=main"

# Azure region codes -> display names
REGION_MAP = {
    "eastus": "East US", "eastus2": "East US 2", "westus": "West US", "westus2": "West US 2", "westus3": "West US 3",
    "centralus": "Central US", "northcentralus": "North Central US", "southcentralus": "South Central US",
    "westcentralus": "West Central US", "brazilsouth": "Brazil South", "brazilsoutheast": "Brazil Southeast",
    "canadacentral": "Canada Central", "canadaeast": "Canada East",
    "northeurope": "North Europe", "westeurope": "West Europe", "uksouth": "UK South", "ukwest": "UK West",
    "francecentral": "France Central", "francesouth": "France South",
    "germanynorth": "Germany North", "germanywestcentral": "Germany West Central",
    "switzerlandnorth": "Switzerland North", "switzerlandwest": "Switzerland West",
    "norwayeast": "Norway East", "norwaywest": "Norway West", "swedencentral": "Sweden Central", "swedensouth": "Sweden South",
    "spaincentral": "Spain Central", "italynorth": "Italy North", "polandcentral": "Poland Central",
    "netherlandswest": "Netherlands West", "finlandcentral": "Finland Central",
    "uaenorth": "UAE North", "uaecentral": "UAE Central", "qatarcentral": "Qatar Central",
    "saudiarabiacentral": "Saudi Arabia Central",
    "southafricanorth": "South Africa North", "southafricawest": "South Africa West",
    "eastasia": "East Asia", "southeastasia": "Southeast Asia",
    "japaneast": "Japan East", "japanwest": "Japan West", "koreacentral": "Korea Central", "koreasouth": "Korea South",
    "australiaeast": "Australia East", "australiasoutheast": "Australia Southeast",
    "australiacentral": "Australia Central", "australiacentral2": "Australia Central 2",
    "indiacentral": "India Central", "indiasouth": "India South", "westindia": "West India",
    "centralindia": "Central India", "southindia": "South India",
    "jioindiawest": "Jio India West", "jioindiacentral": "Jio India Central"
}

def normalize_model_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())

def normalize_region_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())

REGION_LOOKUP = {normalize_region_key(k): v for k, v in REGION_MAP.items()}

SKU_LABEL_OVERRIDES = {
    "standard-models": "Standard (all)",
    "standard-global": "Standard global deployments",
    "standard-gpt-4": "Standard GPT-4",
    "standard-gpt-35-turbo": "Standard GPT-3.5 Turbo",
    "standard-chat-completions": "Standard chat completions",
    "standard-completions": "Standard completions",
    "standard-embeddings": "Standard embeddings",
    "standard-audio": "Standard audio",
    "standard-image-generation": "Standard image generation",
    "provisioned-models": "Provisioned (PTU managed)",
    "provisioned-global": "Provisioned global",
    "datazone-standard": "Datazone standard",
    "datazone-provisioned-managed": "Datazone provisioned managed",
    "global-batch": "Global batch",
    "global-batch-datazone": "Global batch datazone",
    "quota": "Quota",
}

def github_headers(accept: str) -> dict:
    headers = {"Accept": accept}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def parse_env_list(name: str, normalizer=None) -> set:
    raw = os.getenv(name, "")
    items = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if normalizer:
            token = normalizer(token)
        items.add(token)
    return items

def sku_slug(filename: str) -> str:
    return os.path.splitext(filename)[0].lower()

def sku_label(slug: str) -> str:
    if slug in SKU_LABEL_OVERRIDES:
        return SKU_LABEL_OVERRIDES[slug]
    words = re.split(r"[-_]+", slug)
    return " ".join(word.capitalize() for word in words if word)

def list_markdown_files() -> list:
    """List markdown files from all configured model matrix directories."""
    include_files = parse_env_list("MODEL_MATRIX_INCLUDE_FILES", lambda v: v.lower())
    exclude_files = parse_env_list("MODEL_MATRIX_EXCLUDE_FILES", lambda v: v.lower())
    
    all_files = []
    for directory in get_model_matrix_directories():
        try:
            api_url = get_model_matrix_api_url(directory)
            listing = requests.get(api_url, headers=github_headers("application/vnd.github+json"), timeout=30)
            listing.raise_for_status()
            
            for item in listing.json():
                if item.get("type") != "file":
                    continue
                name = item.get("name", "")
                if not name.endswith(".md"):
                    continue
                lowered = name.lower()
                if include_files and lowered not in include_files:
                    continue
                if lowered in exclude_files:
                    continue
                slug = sku_slug(name)
                all_files.append({
                    "name": name,
                    "slug": slug,
                    "label": sku_label(slug),
                    "url": item.get("download_url"),
                    "source_dir": directory,
                })
        except requests.exceptions.HTTPError as e:
            # If a directory doesn't exist or is inaccessible, log and continue
            status_code = e.response.status_code if e.response else "unknown"
            if status_code == 404:
                print(f"Warning: Directory not found: {directory}", file=sys.stderr)
            elif status_code == 403:
                print(f"Warning: Access forbidden to directory {directory} (check GitHub token permissions)", file=sys.stderr)
            else:
                print(f"Warning: Could not access directory {directory} (HTTP {status_code}): {e}", file=sys.stderr)
            continue
        except ValueError as e:
            # Invalid directory path
            print(f"Warning: Invalid directory path {directory}: {e}", file=sys.stderr)
            continue
        except Exception as e:
            print(f"Warning: Error processing directory {directory}: {e}", file=sys.stderr)
            continue
    
    return all_files

def fetch_markdown(url: str) -> str:
    resp = requests.get(url, headers=github_headers("application/vnd.github.v3.raw"), timeout=30)
    resp.raise_for_status()
    return resp.text

def split_cells(row: str, allow_no_leading_pipe: bool = False) -> list:
    row = row.strip()
    if not row:
        return []
    if not row.startswith("|"):
        if not allow_no_leading_pipe:
            return []
        # For MaaS format, some data rows don't start with |
        # but still end with | and have | separators
        if "|" not in row:
            return []
        # Add leading | for consistent parsing
        row = "|" + row
    return [c.strip() for c in row.strip().strip("|").split("|")]

def parse_model_names(cell: str) -> list:
    cell = re.sub(r"\*\*|\*", "", cell).strip()
    if not cell:
        return []
    models = []
    seen = set()
    for segment in re.split(r"<br\s*/?>|\n|;", cell):
        segment = segment.strip()
        if not segment:
            continue
        base = segment.split(",")[0].split("/")[0].strip(" -")
        base = re.sub(r"\s+", " ", base)
        if not base or base.lower() in {"region", "model"}:
            continue
        key = normalize_model_name(base)
        if not key or key in seen:
            continue
        seen.add(key)
        models.append(base)
    return models

def is_available_cell(cell: str) -> bool:
    if not cell:
        return False
    if "✅" in cell or "✔" in cell:
        return True
    return cell.strip().lower() in {"yes", "y", "true"}

def format_region_name(cell: str) -> Optional[str]:
    cell = re.sub(r"<br\s*/?>", " ", cell)
    cell = " ".join(cell.split())
    if not cell:
        return None
    key = normalize_region_key(cell)
    return REGION_LOOKUP.get(key, cell)


def parse_regions_from_text(text: str) -> list[str]:
    """Parse region names from a text cell that may contain multiple regions separated by <br>."""
    if not text or text.lower() in {"not available", "not applicable", "n/a", "-"}:
        return []
    
    regions = []
    # Split by <br>, newlines, and other common separators
    for segment in re.split(r"<br\s*/?>|\n", text):
        segment = segment.strip()
        if not segment or segment.lower() in {"not available", "not applicable", "n/a", "-"}:
            continue
        # Skip links like [Microsoft Managed Countries/Regions](...) - these are not actual regions
        if segment.startswith("[") or "/partner-center/" in segment:
            continue
        region = format_region_name(segment)
        if region and region not in regions:
            regions.append(region)
    return regions


def parse_maas_table(table: str) -> dict:
    """Parse a MaaS-style table where models are in rows and regions are listed as text in columns.
    
    Expected format:
    | Model | Offer Availability Region | Hub/Project Region for Deployment | Hub/Project Region for Fine tuning |
    |-------|---------------------------|-----------------------------------|-----------------------------------|
    | ModelName | ... | East US <br> West US | ... |
    
    Note: Some MaaS tables have data rows that don't start with '|'.
    """
    rows = [line for line in table.strip().splitlines() if line.strip()]
    if len(rows) < 3:
        return {}
    
    header_cells = split_cells(rows[0])
    if not header_cells:
        return {}
    
    # Find the column index for deployment regions (usually "Hub/Project Region for Deployment")
    deployment_col = -1
    finetuning_col = -1
    for idx, cell in enumerate(header_cells):
        cell_lower = cell.lower()
        if "deployment" in cell_lower and "region" in cell_lower:
            deployment_col = idx
        elif "fine" in cell_lower and "tuning" in cell_lower and "region" in cell_lower:
            finetuning_col = idx
    
    # If we can't find deployment column, this isn't a MaaS table
    if deployment_col < 0:
        return {}
    
    model_regions = defaultdict(set)
    
    for row in rows[2:]:  # skip header and separator row
        # Use allow_no_leading_pipe=True for MaaS tables
        cells = split_cells(row, allow_no_leading_pipe=True)
        if not cells or len(cells) <= deployment_col:
            continue
        
        # First cell contains model name(s)
        models = parse_model_names(cells[0])
        if not models:
            continue
        
        # Get regions from deployment column
        deployment_regions = parse_regions_from_text(cells[deployment_col])
        
        # Optionally get fine-tuning regions if available
        finetuning_regions = []
        if finetuning_col >= 0 and len(cells) > finetuning_col:
            finetuning_regions = parse_regions_from_text(cells[finetuning_col])
        
        # Combine all regions
        all_regions = set(deployment_regions) | set(finetuning_regions)
        
        for model in models:
            model_regions[model].update(all_regions)
    
    return model_regions

def parse_table(table: str) -> dict:
    rows = [line for line in table.strip().splitlines() if line.strip()]
    if len(rows) < 3:
        return {}

    header_cells = split_cells(rows[0])
    if not header_cells:
        return {}

    header_models = [parse_model_names(cell) for cell in header_cells]
    model_regions = defaultdict(set)

    for row in rows[2:]:  # skip separator row
        cells = split_cells(row)
        if not cells:
            continue
        region = format_region_name(cells[0])
        if not region:
            continue
        for idx, models in enumerate(header_models):
            if idx >= len(cells) or not models:
                continue
            if is_available_cell(cells[idx]):
                for model in models:
                    model_regions[model].add(region)

    return model_regions

def extract_models_from_markdown(markdown: str) -> dict:
    combined = defaultdict(set)
    for table in re.findall(r"(?:^\|.*\n)+", markdown, re.MULTILINE):
        data = parse_table(table)
        for model, regions in data.items():
            combined[model].update(regions)
    return combined


def extract_models_from_maas_markdown(markdown: str) -> dict:
    """Extract models from MaaS-style markdown with transposed tables.
    
    MaaS tables may have data rows that don't start with '|', so we use
    a more flexible regex pattern.
    """
    combined = defaultdict(set)
    # Match tables: header line starting with |, separator line, then data lines
    # Data lines may or may not start with |
    table_pattern = r"(\|[^\n]+\|\s*\n\|[-|\s]+\|\s*\n(?:[^\n]*\|\s*\n)*)"
    for table in re.findall(table_pattern, markdown, re.MULTILINE):
        data = parse_maas_table(table)
        for model, regions in data.items():
            combined[model].update(regions)
    return combined


def get_maas_file_url(file_path: str) -> str:
    """Generate raw GitHub URL for a MaaS file."""
    return f"https://raw.githubusercontent.com/MicrosoftDocs/azure-ai-docs/main/{file_path}"


def fetch_maas_files() -> list[dict]:
    """Fetch and return info about MaaS files for processing."""
    files = []
    for file_path in MAAS_FILES:
        name = os.path.basename(file_path)
        slug = sku_slug(name)
        files.append({
            "name": name,
            "slug": slug,
            "label": sku_label(slug),
            "url": get_maas_file_url(file_path),
            "source_file": file_path,
            "is_maas": True,
        })
    return files


def build_current_snapshot(files: list) -> dict:
    combined = defaultdict(lambda: defaultdict(set))
    
    # Process regular model matrix files
    for entry in files:
        if not entry.get("url"):
            continue
        markdown = fetch_markdown(entry["url"])
        data = extract_models_from_markdown(markdown)
        sku = entry.get("slug")
        for model, regions in data.items():
            combined[model][sku].update(regions)
    
    # Process MaaS files (transposed table format)
    for entry in fetch_maas_files():
        try:
            markdown = fetch_markdown(entry["url"])
            data = extract_models_from_maas_markdown(markdown)
            sku = entry.get("slug")
            for model, regions in data.items():
                combined[model][sku].update(regions)
        except Exception as e:
            print(f"Warning: Error processing MaaS file {entry.get('name', 'unknown')}: {e}", file=sys.stderr)

    result = {}
    for model in sorted(combined.keys(), key=str.lower):
        sku_map = combined[model]
        all_regions = set()
        formatted_skus = {}
        for sku_key in sorted(sku_map.keys()):
            regions = sorted(sku_map[sku_key])
            all_regions.update(regions)
            formatted_skus[sku_key] = {
                "label": sku_label(sku_key),
                "regions": regions,
            }
        result[model] = {
            "all": sorted(all_regions),
            "skus": formatted_skus,
        }
    return result

def _history_filename(now: datetime) -> str:
    base = now.strftime("%Y%m%dT%H%M%S")
    millis = int(now.microsecond / 1000)
    return f"diff-{base}{millis:03d}Z.json"

def write_diff_history(changes: dict, timestamp: str, now: datetime) -> None:
    if not changes:
        return
    history_dir = ".region-watch/history"
    os.makedirs(history_dir, exist_ok=True)
    payload = {
        "timestamp": timestamp,
        "changes": changes,
    }
    filename = os.path.join(history_dir, _history_filename(now))
    with open(filename, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


EUROPEAN_REGIONS = [
    "Finland Central",
    "France Central",
    "France South",
    "Germany North",
    "Germany West Central",
    "Italy North",
    "Netherlands West",
    "North Europe",
    "Norway East",
    "Norway West",
    "Poland Central",
    "Spain Central",
    "Sweden Central",
    "Sweden South",
    "Switzerland North",
    "Switzerland West",
    "UK South",
    "UK West",
    "West Europe",
]


def build_region_updates(changes: dict, region_filter: set[str]) -> dict:
    region_updates = defaultdict(lambda: {"added_models": [], "removed_models": []})

    for model, change in changes.items():
        for region in change.get("all", {}).get("added", []):
            if region in region_filter:
                region_updates[region]["added_models"].append(model)
        for region in change.get("all", {}).get("removed", []):
            if region in region_filter:
                region_updates[region]["removed_models"].append(model)

    formatted = {}
    for region in sorted(region_updates.keys()):
        formatted[region] = {
            "added_models": sorted(region_updates[region]["added_models"], key=str.lower),
            "removed_models": sorted(region_updates[region]["removed_models"], key=str.lower),
        }
    return formatted


def build_model_view(current: dict, changes: dict, region_filter: set[str]) -> list[dict]:
    model_names = sorted(set(current.keys()) | set(changes.keys()), key=str.lower)
    items = []

    for model in model_names:
        current_info = _normalize_model_entry(current.get(model, {}))
        change = changes.get(model, {})

        available_regions = sorted(region for region in current_info["all"] if region in region_filter)
        added_regions = sorted(region for region in change.get("all", {}).get("added", []) if region in region_filter)
        removed_regions = sorted(region for region in change.get("all", {}).get("removed", []) if region in region_filter)

        sku_updates = []
        for sku_key, sku_change in sorted((change.get("skus") or {}).items()):
            sku_added = sorted(region for region in sku_change.get("added", []) if region in region_filter)
            sku_removed = sorted(region for region in sku_change.get("removed", []) if region in region_filter)
            if not sku_added and not sku_removed and not sku_change.get("sku_removed"):
                continue
            sku_updates.append({
                "sku": sku_key,
                "label": sku_change.get("label", sku_label(sku_key)),
                "added_regions": sku_added,
                "removed_regions": sku_removed,
                "sku_removed": bool(sku_change.get("sku_removed")),
            })

        filtered_skus = []
        for sku_key, sku_info in sorted(current_info["skus"].items()):
            sku_regions = sorted(region for region in sku_info.get("regions", []) if region in region_filter)
            if not sku_regions:
                continue
            filtered_skus.append({
                "sku": sku_key,
                "label": sku_info.get("label", sku_label(sku_key)),
                "regions": sku_regions,
            })

        if not available_regions and not added_regions and not removed_regions and not sku_updates:
            continue

        items.append({
            "model": model,
            "available_regions": available_regions,
            "region_count": len(available_regions),
            "updates": {
                "added_regions": added_regions,
                "removed_regions": removed_regions,
                "model_removed": bool(change.get("model_removed")),
                "sku_updates": sku_updates,
            },
            "skus": filtered_skus,
        })

    return items


def build_region_view(current: dict, changes: dict, region_filter: set[str]) -> list[dict]:
    region_models = defaultdict(list)

    for model, raw_info in current.items():
        info = _normalize_model_entry(raw_info)
        for region in info["all"]:
            if region in region_filter:
                region_models[region].append(model)

    region_updates = build_region_updates(changes, region_filter)
    regions = sorted(set(region_models.keys()) | set(region_updates.keys()))

    items = []
    for region in regions:
        updates = region_updates.get(region, {"added_models": [], "removed_models": []})
        items.append({
            "region": region,
            "available_models": sorted(region_models.get(region, []), key=str.lower),
            "model_count": len(region_models.get(region, [])),
            "updates": {
                "added_models": updates["added_models"],
                "removed_models": updates["removed_models"],
            },
        })

    return items


def load_latest_history_changes() -> tuple[dict, Optional[str], Optional[str]]:
    history_dir = ".region-watch/history"
    if not os.path.isdir(history_dir):
        return {}, None, None

    files = sorted(
        file_name for file_name in os.listdir(history_dir)
        if file_name.endswith(".json")
    )
    if not files:
        return {}, None, None

    latest_file = files[-1]
    latest_path = os.path.join(history_dir, latest_file)
    with open(latest_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return payload.get("changes", {}), payload.get("timestamp"), latest_file


def resolve_effective_changes(changes: dict, timestamp: str) -> tuple[dict, str, str]:
    effective_changes = changes
    update_source = "latest-refresh"
    update_timestamp = timestamp

    if not effective_changes:
        history_changes, history_timestamp, history_file = load_latest_history_changes()
        if history_changes:
            effective_changes = history_changes
            update_source = history_file or "history"
            update_timestamp = history_timestamp or timestamp

    return effective_changes, update_source, update_timestamp


def resolve_worldwide_regions(current: dict, changes: dict) -> list[str]:
    regions = set()

    for raw_info in current.values():
        info = _normalize_model_entry(raw_info)
        regions.update(info["all"])
        for sku_info in info["skus"].values():
            regions.update(sku_info.get("regions", []))

    for change in changes.values():
        regions.update(change.get("all", {}).get("added", []))
        regions.update(change.get("all", {}).get("removed", []))
        for sku_change in change.get("skus", {}).values():
            regions.update(sku_change.get("added", []))
            regions.update(sku_change.get("removed", []))

    return sorted(regions, key=str.lower)


def build_filtered_payload(current: dict, changes: dict, timestamp: str, scope: str, region_list: list[str]) -> dict:
    region_filter = set(region_list)
    effective_changes, update_source, update_timestamp = resolve_effective_changes(changes, timestamp)

    return {
        "timestamp": timestamp,
        "updates": {
            "source": update_source,
            "timestamp": update_timestamp,
        },
        "filter": {
            "scope": scope,
            "primary": scope == "Europe",
            "regions": region_list,
        },
        "views": {
            "by_model": build_model_view(current, effective_changes, region_filter),
            "by_region": build_region_view(current, effective_changes, region_filter),
        },
    }


def build_europe_payload(current: dict, changes: dict, timestamp: str) -> dict:
    return build_filtered_payload(current, changes, timestamp, "Europe", EUROPEAN_REGIONS)


def build_worldwide_payload(current: dict, changes: dict, timestamp: str) -> dict:
    worldwide_regions = resolve_worldwide_regions(current, changes)
    return build_filtered_payload(current, changes, timestamp, "Worldwide", worldwide_regions)


def build_flat_rows(payload: dict) -> list[dict]:
    rows = []
    timestamp = payload.get("timestamp")
    update_source = payload.get("updates", {}).get("source")
    update_timestamp = payload.get("updates", {}).get("timestamp")
    scope = payload.get("filter", {}).get("scope")

    for model_entry in payload.get("views", {}).get("by_model", []):
        available_regions = set(model_entry.get("available_regions", []))
        added_regions = set(model_entry.get("updates", {}).get("added_regions", []))
        removed_regions = set(model_entry.get("updates", {}).get("removed_regions", []))

        region_to_skus = defaultdict(list)
        for sku_entry in model_entry.get("skus", []):
            for region in sku_entry.get("regions", []):
                region_to_skus[region].append(sku_entry.get("label") or sku_entry.get("sku"))

        for region in sorted(available_regions):
            change_status = "unchanged"
            if region in added_regions:
                change_status = "added"

            rows.append({
                "timestamp": timestamp,
                "update_source": update_source,
                "update_timestamp": update_timestamp,
                "scope": scope,
                "model": model_entry.get("model"),
                "region": region,
                "is_available": True,
                "availability_status": "available",
                "change_status": change_status,
                "region_count": model_entry.get("region_count", 0),
                "sku_labels": sorted(region_to_skus.get(region, []), key=str.lower),
            })

        for region in sorted(removed_regions):
            if region in available_regions:
                continue

            rows.append({
                "timestamp": timestamp,
                "update_source": update_source,
                "update_timestamp": update_timestamp,
                "scope": scope,
                "model": model_entry.get("model"),
                "region": region,
                "is_available": False,
                "availability_status": "removed",
                "change_status": "removed",
                "region_count": model_entry.get("region_count", 0),
                "sku_labels": [],
            })

    rows.sort(key=lambda row: (row["model"].lower(), row["region"].lower(), row["availability_status"]))
    return rows


def build_sku_flat_rows(payload: dict) -> list[dict]:
    """Build SKU-exploded flat rows: one row per model+region+sku combination.

    This format is optimized for Teams agents and BI tools that need to query
    by individual SKU/deployment type rather than by SKU-label arrays.
    """
    rows = []
    timestamp = payload.get("timestamp")
    update_source = payload.get("updates", {}).get("source")
    update_timestamp = payload.get("updates", {}).get("timestamp")
    scope = payload.get("filter", {}).get("scope")

    for model_entry in payload.get("views", {}).get("by_model", []):
        model_name = model_entry.get("model")
        region_count = model_entry.get("region_count", 0)
        added_regions = set(model_entry.get("updates", {}).get("added_regions", []))
        removed_regions = set(model_entry.get("updates", {}).get("removed_regions", []))
        model_removed = model_entry.get("updates", {}).get("model_removed", False)
        sku_updates = {
            u["sku"]: u for u in model_entry.get("updates", {}).get("sku_updates", [])
        }

        for sku_entry in model_entry.get("skus", []):
            sku_key = sku_entry.get("sku", "")
            sku_label = sku_entry.get("label", sku_key)
            sku_update = sku_updates.get(sku_key, {})
            sku_added = set(sku_update.get("added_regions", []))
            sku_removed = set(sku_update.get("removed_regions", []))

            for region in sku_entry.get("regions", []):
                region_change = "unchanged"
                if region in added_regions:
                    region_change = "added"
                sku_change = "unchanged"
                if region in sku_added:
                    sku_change = "added"

                rows.append({
                    "timestamp": timestamp,
                    "update_source": update_source,
                    "update_timestamp": update_timestamp,
                    "scope": scope,
                    "model": model_name,
                    "region": region,
                    "sku": sku_key,
                    "sku_label": sku_label,
                    "is_available": True,
                    "change_status": region_change,
                    "sku_change_status": sku_change,
                    "model_removed": model_removed,
                    "region_count": region_count,
                })

        # Emit removed-region rows (no SKU info available after removal)
        for region in sorted(removed_regions):
            if region in {r for s in model_entry.get("skus", []) for r in s.get("regions", [])}:
                continue
            rows.append({
                "timestamp": timestamp,
                "update_source": update_source,
                "update_timestamp": update_timestamp,
                "scope": scope,
                "model": model_name,
                "region": region,
                "sku": "",
                "sku_label": "",
                "is_available": False,
                "change_status": "removed",
                "sku_change_status": "removed",
                "model_removed": model_removed,
                "region_count": region_count,
            })

    rows.sort(key=lambda r: (r["model"].lower(), r["sku"].lower(), r["region"].lower()))
    return rows


def build_summary_markdown(payload: dict) -> str:
    by_model = payload.get("views", {}).get("by_model", [])
    by_region = payload.get("views", {}).get("by_region", [])
    scope = payload.get("filter", {}).get("scope", "Filtered")

    models_with_updates = [
        item for item in by_model
        if item.get("updates", {}).get("added_regions")
        or item.get("updates", {}).get("removed_regions")
        or item.get("updates", {}).get("sku_updates")
        or item.get("updates", {}).get("model_removed")
    ]
    changed_regions = [
        item for item in by_region
        if item.get("updates", {}).get("added_models")
        or item.get("updates", {}).get("removed_models")
    ]

    total_added_regions = sum(len(item.get("updates", {}).get("added_regions", [])) for item in by_model)
    total_removed_regions = sum(len(item.get("updates", {}).get("removed_regions", [])) for item in by_model)
    total_added_models = sum(len(item.get("updates", {}).get("added_models", [])) for item in by_region)
    total_removed_models = sum(len(item.get("updates", {}).get("removed_models", [])) for item in by_region)

    lines = [
        f"# {scope} Model Availability Daily Summary",
        "",
        f"Generated: {payload.get('timestamp')}",
        f"Update source: {payload.get('updates', {}).get('source')} ({payload.get('updates', {}).get('timestamp')})",
        "",
        "## Snapshot",
        "",
        f"- Regions tracked: {len(payload.get('filter', {}).get('regions', []))}",
        f"- Models currently available in {scope}: {len(by_model)}",
        f"- Regions with current availability: {len(by_region)}",
        f"- Models with updates: {len(models_with_updates)}",
        f"- Added region placements: {total_added_regions}",
        f"- Removed region placements: {total_removed_regions}",
        f"- Added models by region: {total_added_models}",
        f"- Removed models by region: {total_removed_models}",
        "",
        "## Regional Changes",
        "",
        "| Region | Current Models | Added Models | Removed Models |",
        "| --- | ---: | ---: | ---: |",
    ]

    for region_entry in sorted(changed_regions, key=lambda item: item["region"].lower()):
        lines.append(
            f"| {region_entry['region']} | {region_entry['model_count']} | "
            f"{len(region_entry.get('updates', {}).get('added_models', []))} | "
            f"{len(region_entry.get('updates', {}).get('removed_models', []))} |"
        )

    if not changed_regions:
        lines.append("| No regional changes in the selected update source | 0 | 0 | 0 |")

    lines.extend([
        "",
        "## Model Changes",
        "",
        "| Model | Current Regions | Added Regions | Removed Regions |",
        "| --- | ---: | ---: | ---: |",
    ])

    for model_entry in sorted(models_with_updates, key=lambda item: item["model"].lower()):
        lines.append(
            f"| {model_entry['model']} | {model_entry['region_count']} | "
            f"{len(model_entry.get('updates', {}).get('added_regions', []))} | "
            f"{len(model_entry.get('updates', {}).get('removed_regions', []))} |"
        )

    if not models_with_updates:
        lines.append("| No model-level changes in the selected update source | 0 | 0 | 0 |")

    return "\n".join(lines) + "\n"


def write_filtered_views(current: dict, changes: dict, timestamp: str) -> None:
    payloads = [
        ("region_diff_europe", build_europe_payload(current, changes, timestamp)),
        ("region_diff_worldwide", build_worldwide_payload(current, changes, timestamp)),
    ]

    for base_name, payload in payloads:
        flat_payload = {
            "timestamp": payload.get("timestamp"),
            "updates": payload.get("updates", {}),
            "filter": payload.get("filter", {}),
            "count": 0,
            "rows": [],
        }
        flat_payload["rows"] = build_flat_rows(payload)
        flat_payload["count"] = len(flat_payload["rows"])
        summary_markdown = build_summary_markdown(payload)

        with open(f"{base_name}.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=False)

        with open(f"{base_name}_flat.json", "w", encoding="utf-8") as handle:
            json.dump(flat_payload, handle, indent=2, sort_keys=False)

        with open(f"{base_name}_summary.md", "w", encoding="utf-8") as handle:
            handle.write(summary_markdown)

        # SKU-exploded flat: one row per model+region+sku (for Teams agents / BI)
        sku_flat_payload = {
            "timestamp": payload.get("timestamp"),
            "updates": payload.get("updates", {}),
            "filter": payload.get("filter", {}),
            "count": 0,
            "rows": [],
        }
        sku_flat_payload["rows"] = build_sku_flat_rows(payload)
        sku_flat_payload["count"] = len(sku_flat_payload["rows"])

        with open(f"{base_name}_sku_flat.json", "w", encoding="utf-8") as handle:
            json.dump(sku_flat_payload, handle, indent=2, sort_keys=False)

def filter_models(data: dict) -> dict:
    """Filter models based on environment variables.
    
    By default (when no filters are set), returns all models.
    Only applies filtering when MODEL_MATRIX_INCLUDE_MODELS or MODEL_MATRIX_EXCLUDE_MODELS are set.
    """
    include_models = parse_env_list("MODEL_MATRIX_INCLUDE_MODELS", normalize_model_name)
    exclude_models = parse_env_list("MODEL_MATRIX_EXCLUDE_MODELS", normalize_model_name)

    # If no filters are set, return all models (default behavior for mkdocs pages)
    if not include_models and not exclude_models:
        return data

    filtered = {}
    for model, info in data.items():
        key = normalize_model_name(model)
        if include_models and key not in include_models:
            continue
        if key in exclude_models:
            continue
        filtered[model] = info
    return filtered

def load_snapshot(path: str) -> dict:
    return json.load(open(path, "r", encoding="utf-8")) if os.path.exists(path) else {}

def _normalize_model_entry(entry) -> dict:
    if isinstance(entry, dict):
        all_regions = entry.get("all", [])
        skus = entry.get("skus", {})
        normalized_skus = {}
        for sku_key, sku_value in skus.items():
            if isinstance(sku_value, dict):
                normalized_skus[sku_key] = {
                    "label": sku_value.get("label", sku_label(sku_key)),
                    "regions": sku_value.get("regions", []),
                }
            elif isinstance(sku_value, list):
                normalized_skus[sku_key] = {
                    "label": sku_label(sku_key),
                    "regions": sku_value,
                }
        return {
            "all": all_regions,
            "skus": normalized_skus,
        }
    if isinstance(entry, list):
        return {"all": entry, "skus": {}}
    return {"all": [], "skus": {}}

def diff(old: dict, new: dict) -> dict:
    changes = {}
    for model, info in new.items():
        new_info = _normalize_model_entry(info)
        old_info = _normalize_model_entry(old.get(model, {}))

        overall_added = sorted(set(new_info["all"]) - set(old_info["all"]))
        overall_removed = sorted(set(old_info["all"]) - set(new_info["all"]))

        sku_changes = {}
        for sku_key, sku_detail in new_info["skus"].items():
            old_sku_detail = old_info["skus"].get(sku_key, {"label": sku_detail["label"], "regions": []})
            added = sorted(set(sku_detail["regions"]) - set(old_sku_detail.get("regions", [])))
            removed = sorted(set(old_sku_detail.get("regions", [])) - set(sku_detail["regions"]))
            if added or removed or sku_key not in old_info["skus"]:
                sku_changes[sku_key] = {
                    "label": sku_detail["label"],
                    "added": added,
                    "removed": removed,
                }

        for sku_key, old_sku_detail in old_info["skus"].items():
            if sku_key not in new_info["skus"]:
                sku_changes[sku_key] = {
                    "label": old_sku_detail.get("label", sku_label(sku_key)),
                    "added": [],
                    "removed": sorted(old_sku_detail.get("regions", [])),
                    "sku_removed": True,
                }

        if overall_added or overall_removed or sku_changes:
            changes[model] = {
                "all": {"added": overall_added, "removed": overall_removed},
                "skus": sku_changes,
            }

    # Detect models removed entirely
    for model, old_info in old.items():
        if model not in new:
            normalized_old = _normalize_model_entry(old_info)
            changes[model] = {
                "all": {"added": [], "removed": normalized_old["all"]},
                "skus": {
                    sku: {
                        "label": detail.get("label", sku_label(sku)),
                        "added": [],
                        "removed": detail.get("regions", []),
                        "sku_removed": True,
                    }
                    for sku, detail in normalized_old["skus"].items()
                },
                "model_removed": True,
            }

    return changes

def main() -> int:
    files = list_markdown_files()
    current = filter_models(build_current_snapshot(files))
    snap_path = ".region-watch/regions_snapshot.json"
    baseline = load_snapshot(snap_path)

    if not baseline:
        baseline = current

    changes = diff(baseline, current)
    now = datetime.now(timezone.utc)
    timestamp_iso = now.isoformat()
    file_names = [entry["name"] for entry in files]
    output = {
        "timestamp": timestamp_iso,
        "changes": changes,
        "current": current,
        "files": file_names,
    }
    print(json.dumps(output, indent=2))

    write_diff_history(changes, timestamp_iso, now)
    write_filtered_views(current, changes, timestamp_iso)

    if os.getenv("TEAMS_WEBHOOK") and any(
        change["all"]["added"]
        or change["all"]["removed"]
        or any(sku_change.get("added") or sku_change.get("removed") or sku_change.get("sku_removed") for sku_change in change["skus"].values())
        or change.get("model_removed")
        for change in changes.values()
    ):
        lines = ["Model region changes detected:"]
        for model, change in changes.items():
            if change["all"]["added"]:
                lines.append(f"• {model}: added -> {', '.join(change['all']['added'])}")
            if change["all"]["removed"]:
                lines.append(f"• {model}: removed -> {', '.join(change['all']['removed'])}")
            for sku_key, sku_change in change["skus"].items():
                if sku_change.get("added"):
                    lines.append(
                        f"  - {sku_change['label']} ({sku_key}): added -> {', '.join(sku_change['added'])}"
                    )
                if sku_change.get("removed"):
                    lines.append(
                        f"  - {sku_change['label']} ({sku_key}): removed -> {', '.join(sku_change['removed'])}"
                    )
                if sku_change.get("sku_removed"):
                    lines.append(f"  - {sku_change['label']} ({sku_key}): sku removed")
            if change.get("model_removed"):
                lines.append("  - model removed")
        try:
            requests.post(os.getenv("TEAMS_WEBHOOK"), json={"text": "\n".join(lines)}, timeout=10)
        except Exception:
            pass

    os.makedirs(".region-watch", exist_ok=True)
    with open(snap_path, "w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=2, sort_keys=True)

    return 0

if __name__ == "__main__":
    sys.exit(main())