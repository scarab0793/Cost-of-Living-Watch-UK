"""Catalogue of automatically refreshed datasets.

Each entry is verified against the title published by the source itself
(`expect`, a case-insensitive regex). If a source ever returns a different
series under the same ID, the refresh is rejected instead of silently
storing the wrong data.
"""

ONS = "Office for National Statistics"
BOE = "Bank of England"
HMLR = "HM Land Registry / ONS / Registers of Scotland / LPS NI (UK House Price Index)"

RPI_AP = ("RPI average price series (published by ONS in dataset MM23). Annual figure as published by ONS. "
          "Prices are for a specified item and pack size, not a market-wide census.")
RPI_AP_LIMIT = ("Product specification and pack sizes change over time; the series may be discontinued. "
                "RPI is not a National Statistic; average-price quotes are indicative.")

CATALOGUE = []


def add(**kw):
    kw.setdefault("geography", "United Kingdom")
    kw.setdefault("adjusted", "Original (not seasonally adjusted unless stated in title)")
    kw.setdefault("scale", 1.0)
    kw.setdefault("min_obs", 5)
    kw.setdefault("limitations", "")
    CATALOGUE.append(kw)


# ---- Prices and inflation -------------------------------------------------
add(id="cpi_index", group="prices", label="CPI all items index (2015=100)", kind="ons", cdid="D7BT", dataset="mm23",
    expect=r"CPI INDEX 00: ALL ITEMS 2015=100", unit="index 2015=100", publisher=ONS,
    method="Consumer Prices Index, annual figure as published by ONS.",
    limitations="Index from 1988. CPI excludes owner-occupier housing costs.")
add(id="cpih_index", group="prices", label="CPIH all items index (2015=100)", kind="ons", cdid="L522", dataset="mm23",
    expect=r"CPIH INDEX 00: ALL ITEMS 2015=100", unit="index 2015=100", publisher=ONS,
    method="CPI including owner occupiers' housing costs.", limitations="Index from 1988.")
add(id="rpi_index", group="prices", label="RPI all items index (Jan 1987=100)", kind="ons", cdid="CHAW", dataset="mm23",
    expect=r"RPI All Items Index", unit="index Jan 1987=100", publisher=ONS,
    method="Retail Prices Index. Not a National Statistic; used here for long-run comparison only.",
    limitations="RPI overstates inflation relative to CPI in many years (formula effect).")
add(id="cpi_rate", group="prices", label="CPI annual inflation rate", kind="ons", cdid="D7G7", dataset="mm23",
    expect=r"CPI ANNUAL RATE 00", unit="%", publisher=ONS, method="12-month rate; annual average.")
add(id="cpi_electricity_gas", group="energy", label="CPI: electricity, gas and other fuels index (2015=100)", kind="ons",
    cdid="D7CH", dataset="mm23", expect=r"CPI INDEX 04\.5", unit="index 2015=100", publisher=ONS,
    method="Price index for household electricity, gas and other fuels (not a bill in £).",
    limitations="An index, not a £ bill. Use with a base-year bill to estimate cost changes.")
add(id="cpi_rail_fares", group="transport", label="CPI: passenger transport by railway index (2015=100)", kind="ons",
    cdid="D7EF", dataset="mm23", expect=r"CPI INDEX 07\.3\.1", unit="index 2015=100", publisher=ONS,
    method="Rail fares price index.", limitations="Index, not £ fares.")
add(id="cpi_new_cars", group="transport", label="CPI: new cars index (2015=100)", kind="ons", cdid="D7E8", dataset="mm23",
    expect=r"CPI INDEX 07\.1\.1A", unit="index 2015=100", publisher=ONS,
    method="Quality-adjusted new car price index.",
    limitations="Quality-adjusted index, not average transaction prices in £.")
add(id="cpi_motor_insurance", group="transport", label="CPI: motor vehicle insurance index (2015=100)", kind="ons",
    cdid="L7JE", dataset="mm23", expect=r"CPI INDEX 12\.5\.4\.1", unit="index 2015=100", publisher=ONS,
    method="Motor insurance premium price index.", limitations="Index, not £ premiums; may start after 1990.")

# ---- Earnings ---------------------------------------------------------------
add(id="awe_total_pay", group="earnings", label="Average weekly earnings, whole economy, total pay (£/week)", kind="ons",
    cdid="KAB9", dataset="emp", expect=r"AWE: Whole Economy Level.*Total Pay Excluding Arrears", unit="GBP/week",
    publisher=ONS, adjusted="Seasonally adjusted",
    method="Monthly Average Weekly Earnings survey, annual average of published annual figure.",
    limitations="Starts 2000. Excludes arrears. Earnings of employees, not household income.")
add(id="awe_regular_pay", group="earnings", label="Average weekly earnings, whole economy, regular pay (£/week)", kind="ons",
    cdid="KAI7", dataset="emp", expect=r"AWE: Whole Economy Level.*Regular Pay Excluding Arrears", unit="GBP/week",
    publisher=ONS, adjusted="Seasonally adjusted", method="As above, regular pay (excludes bonuses).",
    limitations="Starts 2000.")

# ---- Food and fuel prices (RPI average prices, pence -> GBP) ---------------------
for _id, cdid, label, expect, unit in [
    ("price_milk", "CZNT", "Milk, pasteurised, per pint", r"Milk: Pasteurised, per pint", "GBP/pint"),
    ("price_bread_white_sliced", "CZOH", "Bread, white sliced loaf, 800g", r"Bread: white loaf, sliced, 800g", "GBP/800g loaf"),
    ("price_eggs_size4", "CZNU", "Eggs, size 4 (55-60g), dozen", r"Eggs: size 4", "GBP/dozen"),
    ("price_butter", "CZOB", "Butter, home produced, 250g", r"Butter: Home produced", "GBP/250g"),
    ("price_cheese", "CZNW", "Cheddar-type cheese, per kg", r"Cheese: cheddar type", "GBP/kg"),
    ("price_beef_mince", "CZPI", "Beef mince (best), per kg", r"best beef mince", "GBP/kg"),
    ("price_chicken", "CZOM", "Chicken, roasting, fresh/chilled, per kg", r"Chicken: roasting", "GBP/kg"),
    ("price_pork_loin", "CZOX", "Pork loin (with bone), per kg", r"Pork: home-killed, loin", "GBP/kg"),
    ("price_potatoes_new", "CZNK", "Potatoes, new loose, per kg", r"Potatoes, new loose", "GBP/kg"),
    ("price_potatoes_old", "VKYY", "Potatoes, old white, per kg", r"Potatoes, old white", "GBP/kg"),
    ("price_sugar", "CZNN", "Sugar, granulated, per kg", r"Sugar: Granulated", "GBP/kg"),
    ("price_tea_bags", "CZNQ", "Tea bags, per 250g", r"Tea bags", "GBP/250g"),
    ("price_coffee_instant", "CZNP", "Coffee, instant, per 100g", r"Coffee: pure, instant", "GBP/100g"),
    ("price_bananas", "CZMV", "Bananas, per kg", r"Bananas", "GBP/kg"),
    ("price_apples_dessert", "CZMY", "Apples, dessert, per kg", r"Apples, dessert", "GBP/kg"),
    ("price_carrots", "CZNE", "Carrots, per kg", r"Carrots", "GBP/kg"),
    ("price_tomatoes", "CZNJ", "Tomatoes, per kg", r"Tomatoes", "GBP/kg"),
]:
    add(id=_id, group="food", label=label, kind="ons", cdid=cdid, dataset="mm23", expect=expect, unit=unit,
        scale=0.01, publisher=ONS, method=RPI_AP, limitations=RPI_AP_LIMIT)

add(id="price_petrol", group="transport", label="Unleaded petrol, pence per litre -> £/litre", kind="ons", cdid="CZMK",
    dataset="mm23", expect=r"Unleaded petrol", unit="GBP/litre", scale=0.01, publisher=ONS, method=RPI_AP,
    limitations="Leaded petrol was the norm before 2000; the series is ULS/unleaded from 1990.")
add(id="price_diesel", group="transport", label="Diesel, per litre (Derv before Feb 2000)", kind="ons", cdid="CZML",
    dataset="mm23", expect=r"diesel", unit="GBP/litre", scale=0.01, publisher=ONS, method=RPI_AP,
    limitations=RPI_AP_LIMIT)

# ---- Housing ------------------------------------------------------------------
for _slug, _name in [("united-kingdom", "United Kingdom"), ("england", "England"), ("wales", "Wales"),
                     ("scotland", "Scotland"), ("northern-ireland", "Northern Ireland"),
                     ("north-east", "North East"), ("north-west", "North West"),
                     ("yorkshire-and-the-humber", "Yorkshire and The Humber"), ("east-midlands", "East Midlands"),
                     ("west-midlands", "West Midlands"), ("east-of-england", "East of England"),
                     ("london", "London"), ("south-east", "South East"), ("south-west", "South West")]:
    add(id=f"house_price_{_slug}", group="housing", label=f"Average house price, {_name} (£)", kind="hpi", region=_slug,
        expect=r"UK HPI average price", unit="GBP", publisher=HMLR, geography=_name, min_obs=20,
        adjusted="Original, not seasonally adjusted",
        method="Mean of monthly UK HPI average prices (mix-adjusted, based on registered sales). Full year = all 12 months.",
        limitations="Latest year is partial until December is published. Averages include all property types.")

# ---- Interest rates --------------------------------------------------------------
add(id="bank_rate", group="housing", label="Bank Rate (annual mean of daily, %)", kind="boe", code="IUDBEDR",
    expect=r"IUDBEDR", unit="%", publisher=BOE, min_obs=20,
    method="Official Bank Rate; mean of month averages.", limitations="Policy rate, not a consumer rate.")
add(id="mortgage_svr", group="housing", label="Standard variable mortgage rate, households (%)", kind="boe", code="IUMTLMV",
    expect=r"IUMTLMV", unit="%", publisher=BOE, min_obs=20,
    method="Average of month-end quoted rates (all lenders, sterling).",
    limitations="Starts 1995 in this series; 1990-1994 not covered here.")
add(id="mortgage_2y_fixed_75ltv", group="housing", label="2-year fixed mortgage rate, 75% LTV (%)", kind="boe",
    code="IUMBV34", expect=r"IUMBV34", unit="%", publisher=BOE, min_obs=20,
    method="Quoted rate, mean of month-end values.", limitations="Starts 1995.")

# ---- Government finances (calendar-year, GBP million) ---------------------------------
for _id, cdid, ds, label, expect in [
    ("rcpt_vat", "NZGF", "pusf", "VAT receipts (central government, £m)", r"VAT"),
    ("rcpt_fuel_duty", "CUDG", "pusf", "Fuel duty receipts (£m)", r"Fuel duty"),
    ("rcpt_paye_income_tax", "MS6W", "pusf", "PAYE income tax receipts (£m)", r"PAYE income tax"),
    ("rcpt_social_contributions", "AIIH", "pusf", "Compulsory social contributions incl. National Insurance (£m)", r"Compulsory social contributions"),
    ("rcpt_council_tax", "NMHM", "pusf", "Council tax receipts, local government (£m)", r"Council tax"),
    ("rcpt_stamp_duty_shares", "BKST", "pusf", "Stamp duty on shares (£m) — NOT property SDLT", r"Stamp duty \(shares\)"),
    ("tme", "KAU3", "pusf", "Public sector total managed expenditure (£m)", r"Total managed expenditure"),
    ("psnd_pct_gdp", "HF6X", "pusf", "Public sector net debt ex banks (% of GDP)", r"Net Debt \(excluding public sector banks\) as a % of GDP"),
    ("gdp_nominal", "YBHA", "qna", "GDP at market prices, current prices (£m)", r"Gross Domestic Product at market prices: Current price"),
]:
    add(id=_id, group="government", label=label, kind="ons", cdid=cdid, dataset=ds, expect=expect,
        unit="% of GDP" if "pct" in _id else "GBP million", publisher=ONS, adjusted="Current prices, not inflation-adjusted",
        method="ONS public sector finances / national accounts, annual figure as published.",
        limitations="Component series; do not add together (categories overlap: e.g. NICs sit inside social contributions).")
