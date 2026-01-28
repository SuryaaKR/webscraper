# webscraper

Scrapes directory-style websites (infinite scroll or pagination) and exports leads to Excel.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configure

Copy `config.example.yaml` and update the selectors to match the directory site.

```bash
cp config.example.yaml config.yaml
```

Fields captured per lead:
- company_name
- address
- email
- website
- phone
- country
- field (optional industry category)

Pagination options:
- Click the next button with `pagination.next_button_selector`
- Or generate URLs using `pagination.url_template` with `{page}` placeholder

## Run

```bash
python scraper.py --config config.yaml
```

The output Excel file is written to the `output_file` path in the config.
