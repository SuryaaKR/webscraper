#!/usr/bin/env python3
import argparse
import time
from pathlib import Path

import pandas as pd
import yaml
from playwright.sync_api import sync_playwright


DEFAULT_COLUMNS = [
    "company_name",
    "address",
    "email",
    "website",
    "phone",
    "country",
    "field",
]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned if cleaned else None


def extract_value(element, field_config: dict | str):
    if isinstance(field_config, str):
        target = element.query_selector(field_config)
        if not target:
            return None
        return normalize_text(target.inner_text())

    selector = field_config.get("selector")
    attr = field_config.get("attr")
    if not selector:
        return None
    target = element.query_selector(selector)
    if not target:
        return None
    if attr:
        value = target.get_attribute(attr)
        if value and attr == "href" and value.startswith("mailto:"):
            value = value.replace("mailto:", "", 1)
        return normalize_text(value)
    return normalize_text(target.inner_text())


def extract_items(page, config: dict) -> list[dict]:
    items = []
    item_selector = config["extraction"]["item_selector"]
    fields = config["extraction"]["fields"]
    elements = page.query_selector_all(item_selector)
    for element in elements:
        record = {}
        for field_name, field_config in fields.items():
            record[field_name] = extract_value(element, field_config)
        items.append(record)
    return items


def scroll_page(page, scroll_config: dict):
    max_scrolls = scroll_config.get("max_scrolls", 50)
    pause_ms = scroll_config.get("pause_ms", 1200)
    stop_after_unchanged = scroll_config.get("stop_after_unchanged", 3)
    unchanged = 0
    previous_height = 0

    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        current_height = page.evaluate("document.body.scrollHeight")
        if current_height == previous_height:
            unchanged += 1
        else:
            unchanged = 0
        previous_height = current_height
        if unchanged >= stop_after_unchanged:
            break


def paginate(page, pagination_config: dict, extract_callback):
    max_pages = pagination_config.get("max_pages", 50)
    next_selector = pagination_config.get("next_button_selector")
    results = []

    for _ in range(max_pages):
        results.extend(extract_callback())
        if not next_selector:
            break
        next_button = page.query_selector(next_selector)
        if not next_button:
            break
        next_button.click()
        page.wait_for_timeout(pagination_config.get("pause_ms", 1500))
    return results


def paginate_by_url(page, pagination_config: dict, extract_callback):
    url_template = pagination_config.get("url_template")
    if not url_template:
        return []
    start_page = pagination_config.get("start_page", 1)
    max_pages = pagination_config.get("max_pages", 50)
    pause_ms = pagination_config.get("pause_ms", 1500)
    results = []
    for page_number in range(start_page, start_page + max_pages):
        page.goto(url_template.format(page=page_number), wait_until="networkidle")
        results.extend(extract_callback())
        page.wait_for_timeout(pause_ms)
    return results


def ensure_columns(records: list[dict], columns: list[str]) -> list[dict]:
    normalized = []
    for record in records:
        normalized.append({col: record.get(col) for col in columns})
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape lead data from directory sites with infinite scroll or pagination."
    )
    parser.add_argument("--config", required=True, help="Path to YAML config file.")
    args = parser.parse_args()

    config_path = Path(args.config)
    config = load_config(config_path)

    output_file = Path(config.get("output_file", "output.xlsx"))
    output_file.parent.mkdir(parents=True, exist_ok=True)

    columns = config.get("columns", DEFAULT_COLUMNS)
    all_records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not config.get("headful", False))
        context = browser.new_context()
        page = context.new_page()

        for url in config.get("start_urls", []):
            page.goto(url, wait_until="networkidle")
            mode = config.get("mode", "infinite_scroll")
            if mode == "infinite_scroll":
                scroll_page(page, config.get("scroll", {}))
                records = extract_items(page, config)
            elif mode == "pagination":
                pagination_config = config.get("pagination", {})
                if pagination_config.get("url_template"):
                    records = paginate_by_url(
                        page,
                        pagination_config,
                        lambda: extract_items(page, config),
                    )
                else:
                    records = paginate(
                        page,
                        pagination_config,
                        lambda: extract_items(page, config),
                    )
            else:
                raise ValueError(f"Unknown mode: {mode}")

            all_records.extend(records)
            time.sleep(config.get("between_urls_pause_s", 1))

        browser.close()

    all_records = ensure_columns(all_records, columns)
    df = pd.DataFrame(all_records)
    df.to_excel(output_file, index=False)


if __name__ == "__main__":
    main()
