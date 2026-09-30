"""Generate synthetic, Salesforce-style commercial data for a fictional
medical imaging analytics company.

All data is SYNTHETIC. No real customers, people, or company data are used.

Objects mirror common Salesforce objects and field names:
  users.csv          ~ User          (Id, Name, Region, Role)
  accounts.csv       ~ Account       (Id, Name, Type, Region, BillingState, OwnerId, CreatedDate)
  opportunities.csv  ~ Opportunity   (Id, AccountId, Name, StageName, Product,
                                    Amount, CreatedDate, CloseDate, IsClosed, IsWon)
  orders.csv         ~ monthly analysis volume per account and product
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
OUT = Path(__file__).parent / "raw"
START, END = date(2024, 1, 1), date(2026, 9, 30)

REGIONS = {
    "West": ["CA", "OR", "WA", "AZ", "CO"],
    "Central": ["TX", "IL", "MN", "OH", "MO"],
    "East": ["NY", "MA", "PA", "FL", "GA"],
}
ACCOUNT_TYPES = ["Hospital", "Imaging Center", "Cardiology Practice"]
PRODUCTS = {  # product -> typical deal size (USD)
    "Coronary Flow Analysis": 60_000,
    "Stenosis Mapping": 35_000,
    "Plaque Quantification": 45_000,
}
OPEN_STAGES = ["Prospecting", "Qualification", "Evaluation", "Proposal", "Negotiation"]
NAME_A = ["Summit", "Riverside", "Lakeview", "Bayside", "Pioneer", "Cedar", "Harbor",
          "Mesa", "Northgate", "Valley", "Granite", "Maple", "Coastal", "Prairie", "Union"]
NAME_B = {"Hospital": "Medical Center", "Imaging Center": "Imaging",
          "Cardiology Practice": "Heart Associates"}


def rand_date(rng: np.random.Generator, lo: date, hi: date) -> date:
    return lo + timedelta(days=int(rng.integers(0, (hi - lo).days + 1)))


def build(seed: int = SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    # Users: one manager + three reps per region, plus an admin
    users = [{"Id": "U000", "Name": "Analytics Admin", "Region": "All", "Role": "admin"}]
    uid = 1
    for region in REGIONS:
        users.append({"Id": f"U{uid:03d}", "Name": f"{region} Sales Manager",
                      "Region": region, "Role": "regional_manager"})
        uid += 1
        for i in range(1, 4):
            users.append({"Id": f"U{uid:03d}", "Name": f"{region} Rep {i}",
                          "Region": region, "Role": "rep"})
            uid += 1
    users_df = pd.DataFrame(users)
    reps = users_df[users_df.Role == "rep"]

    # Accounts
    accounts = []
    for i in range(1, 301):
        region = rng.choice(list(REGIONS))
        atype = rng.choice(ACCOUNT_TYPES, p=[0.4, 0.35, 0.25])
        owner = rng.choice(reps[reps.Region == region].Id.to_numpy())
        accounts.append({
            "Id": f"A{i:04d}",
            "Name": f"{rng.choice(NAME_A)} {NAME_B[atype]} {i}",
            "Type": atype,
            "Region": region,
            # ~2% missing BillingState: a realistic warning-level data defect
            "BillingState": None if rng.random() < 0.02 else rng.choice(REGIONS[region]),
            "OwnerId": owner,
            "CreatedDate": rand_date(rng, START, date(2025, 12, 31)),
        })
    acc_df = pd.DataFrame(accounts)

    # Opportunities
    opps = []
    for i in range(1, 1201):
        acc = acc_df.iloc[int(rng.integers(0, len(acc_df)))]
        product = rng.choice(list(PRODUCTS))
        created = rand_date(rng, max(acc.CreatedDate, START), END - timedelta(days=10))
        close = created + timedelta(days=int(rng.integers(30, 181)))
        if close <= END:
            won = rng.random() < 0.38
            stage, is_closed = ("Closed Won" if won else "Closed Lost"), True
        else:
            stage, is_closed, won = rng.choice(OPEN_STAGES), False, False
        amount = round(float(rng.normal(PRODUCTS[product], PRODUCTS[product] * 0.25)), -2)
        opps.append({
            "Id": f"O{i:05d}", "AccountId": acc.Id,
            "Name": f"{acc.Name} - {product}", "StageName": stage, "Product": product,
            "Amount": max(amount, 5_000.0), "CreatedDate": created, "CloseDate": close,
            "IsClosed": is_closed, "IsWon": won,
        })
    opp_df = pd.DataFrame(opps)

    # Monthly analysis volume for accounts with a won deal, starting the month after close
    orders = []
    won = opp_df[opp_df.IsWon]
    months = pd.date_range(START, END, freq="MS").date
    for _, o in won.iterrows():
        base = rng.integers(5, 60)
        for m in months:
            if m > o.CloseDate:
                vol = max(0, int(rng.normal(base, base * 0.2)))
                orders.append({"AccountId": o.AccountId, "Product": o.Product,
                               "Month": m, "AnalysesOrdered": vol})
    ord_df = (pd.DataFrame(orders)
              .groupby(["AccountId", "Product", "Month"], as_index=False).sum())

    return {"users": users_df, "accounts": acc_df,
            "opportunities": opp_df, "orders": ord_df}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in build().items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"wrote {name}.csv ({len(df):,} rows)")


if __name__ == "__main__":
    main()
