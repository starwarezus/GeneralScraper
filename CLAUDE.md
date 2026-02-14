# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GeneralScraper is a Python clothing/product image scraper that searches Google and 20+ retail sites, downloads product images, and generates reports. It supports CLI, GUI (tkinter), and batch (CSV/JSON) interfaces.

## Setup & Running

```bash
# Install dependencies
pip install -r requirements.txt

# CLI usage
python clothing_image_scraper.py --brand "Nike" --style "Air Max"

# Batch processing
python csv_scraper.py items.csv
python json_scraper.py items.json

# GUI
python gui_scraper.py
```

Windows batch scripts (`START.bat`, `SETUP.bat`, etc.) provide menu-driven access to these commands.

## Architecture

All interfaces feed into the core `ClothingImageScraper` class in `clothing_image_scraper.py`:

```
GUI (gui_scraper.py) ──┐
CLI (argparse)     ────┼──▶ ClothingImageScraper ──▶ pics/ (images)
CSV (csv_scraper.py) ──┤    - Google Shopping/Images    scraper.log
JSON (json_scraper.py)─┘    - 20+ retailer scrapers     scraper_SUCCESS_ONLY.log
```

### Key Files

- **`clothing_image_scraper.py`** — Core engine. Contains `ClothingImageScraper` class with search, extraction, and download logic. Retailer-specific extractors follow the pattern `_extract_[retailer]_images(soup, url)`.
- **`csv_scraper.py`** — `CSVBatchScraper` class. Reads items from CSV, processes each through the core scraper, generates Excel reports via `generate_excel_report()`.
- **`json_scraper.py`** — `JSONBatchScraper` class. Same pattern as CSV but reads JSON input.
- **`gui_scraper.py`** — `ScraperGUI` class. Tkinter UI that wraps the core scraper with threaded execution.

### Search Strategy Priority

1. Google Shopping (most reliable aggregator)
2. Google Images
3. Direct retailer scraping (site-specific extractors)

### Anti-Detection

Requests use rotating user agents (6 variants), enhanced browser headers, Google referrer, session cookies, automatic retries on 403/timeout, and configurable delays between requests.

### Item Data Model

```python
{
    'brand': str,       # Recommended
    'model': str,       # Optional
    'style': str,       # Optional
    'color': str,       # Optional
    'barcode': str,     # Optional
    'url': str,         # Direct product URL, optional
    'max_images': int,  # Default 5
    'notes': str        # Ignored by scraper
}
```

### Logging

Dual-log system: `scraper.log` captures all messages, `scraper_SUCCESS_ONLY.log` captures only successful downloads with source metadata.

## Conventions

- Retailer-specific extractors are added as `_extract_[name]_images(soup, url)` methods on `ClothingImageScraper`
- Filenames are sanitized by replacing `<>:"/\|?*` and spaces with underscores
- Image deduplication uses `_create_image_signature(url)`
- Processing is sequential (no parallelization) with polite delays between requests

<!-- BACKLOG.MD MCP GUIDELINES START -->

<CRITICAL_INSTRUCTION>

## BACKLOG WORKFLOW INSTRUCTIONS

This project uses Backlog.md MCP for all task and project management activities.

**CRITICAL GUIDANCE**

- If your client supports MCP resources, read `backlog://workflow/overview` to understand when and how to use Backlog for this project.
- If your client only supports tools or the above request fails, call `backlog.get_workflow_overview()` tool to load the tool-oriented overview (it lists the matching guide tools).

- **First time working here?** Read the overview resource IMMEDIATELY to learn the workflow
- **Already familiar?** You should have the overview cached ("## Backlog.md Overview (MCP)")
- **When to read it**: BEFORE creating tasks, or when you're unsure whether to track work

These guides cover:
- Decision framework for when to create tasks
- Search-first workflow to avoid duplicates
- Links to detailed guides for task creation, execution, and finalization
- MCP tools reference

You MUST read the overview resource to understand the complete workflow. The information is NOT summarized here.

</CRITICAL_INSTRUCTION>

<!-- BACKLOG.MD MCP GUIDELINES END -->
