# UK Cost of Living Watch

Compare UK household living costs between any two years since 1990 using official data only.
Live site: https://scarab0793.github.io/Cost-of-Living-Watch-UK/

## What it does
- Two-year household comparison: pay, Income Tax and employee NI (real HMRC rules per tax year), average house price by region, mortgage cost, food basket, energy, petrol, hours of work per purchase.
- Trend explorer, tax, housing, food, energy, transport and government-finance charts.
- Data catalogue with publisher, source URL, unit, coverage, adjustment and limitations for every dataset; explicit gap registry (`data/gaps.json`).

## Data sources (all fetched by `update.py`, no AI, no estimates)
ONS (CPI/CPIH/RPI, RPI average prices, AWE earnings, public finances), HMRC (income tax and NI tables), HM Land Registry (UK HPI), Bank of England (Bank Rate, mortgage rates, historical earnings and early mortgage rates), DESNZ (domestic energy bills), World Bank (context), GOV.UK feeds.

## Integrity rules
Each series is checked against the title the publisher returns; shrinking or implausible downloads are rejected and the last good file is kept. Results go to `data/status.json` and `data/changes.json`.

## Not yet covered (see the site's Data & gaps section)
Rent levels, Council Tax, median earnings, vehicle categories and running costs, rate histories for VAT/fuel duty/VED/Corporation Tax, company financial results, MIRAS before 2000.

## Development
```
pip install -r requirements.txt
python update.py          # refresh data (add --static to re-extract archive datasets)
node tests/test_calc.js   # calculation and data-integrity tests
python -m http.server     # then open http://localhost:8000
```
The previous single-page version is kept in `legacy/index-v2.html`. Earlier pipeline bug fixed: the former `ons_earnings_*` series pointed at a construction-sector index mislabelled as whole-economy pay; they were removed and replaced by ONS AWE series KAB9/KAI7.
