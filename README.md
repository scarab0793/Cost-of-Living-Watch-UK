# UK Living Cost Index

Live static dashboard and calculators for UK household living costs, 1990 to present.

## Deployment

GitHub Pages: Settings > Pages > Build and deployment > Deploy from a branch > main > /(root).

## Automation

GitHub Actions runs at 06:17, 12:17, 18:17 UTC and fetches official GOV.UK Atom feeds. It commits only when new verified stories exist. Run manually from Actions > Refresh official news > Run workflow.

## Current functionality

- Household monthly and annual budget calculator
- Mortgage repayment calculator
- Fuel tank cost calculator
- Illustrative inflation scenario calculator
- Dedicated housing, food, energy, transport, tax, company profit and news sections

## Data quality

Historical 1990–2026 official series and corporate financial statements are **not yet integrated**. No fabricated historical prices or profits. The current inflation calculator uses user-supplied scenario assumptions, not historical inflation observations.

Primary sources linked in the interface: ONS, GOV.UK, HMRC, OBR, Ofgem, Companies House.

## Tech

Static HTML/CSS/JavaScript, Python standard library, GitHub Actions, no AI credits or server required.
