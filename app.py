"""Commercial KPI dashboard for a fictional medical imaging analytics company.

Every number on this page comes from the semantic layer (semantic/metrics.yml),
filtered by the selected user's row-level security. Data is synthetic.
Run:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))

from mca.access import load_users  # noqa: E402
from mca.quality import run_checks  # noqa: E402
from mca.semantic import SemanticModel, TimeRange  # noqa: E402
from mca.warehouse import connect  # noqa: E402

NAVY = "#1F3864"
st.set_page_config(page_title="Medtech Commercial Analytics", layout="wide")


@st.cache_resource
def load():
    con = connect()
    return con, SemanticModel(con), load_users(con)


con, model, users = load()

# ---------- Sidebar: who is viewing, and filters ----------
st.sidebar.header("View as")
user_id = st.sidebar.selectbox(
    "User (demonstrates row-level security)", list(users),
    format_func=lambda uid: f"{users[uid].name} ({users[uid].role})")
user = users[user_id]
rls = model.policy.row_filter(user)
rls_text = f"Row filter: {rls.dimension} = {rls.value}" if rls else "Row filter: none (admin)"
st.sidebar.caption(rls_text)

st.sidebar.header("Filters")
products = st.sidebar.multiselect(
    "Product", ["Coronary Flow Analysis", "Stenosis Mapping", "Plaque Quantification"])
account_types = st.sidebar.multiselect(
    "Account type", ["Hospital", "Imaging Center", "Cardiology Practice"])
year = st.sidebar.selectbox("Bookings year", [2026, 2025, 2024])
filters = {"product": products, "account_type": account_types}
year_range = TimeRange("close_date", f"{year}-01-01", f"{year}-12-31")


def q(cube, measures, **kw):
    return model.query(cube, measures, user, filters=filters, **kw)


st.title("Medtech Commercial Analytics")
st.caption("Synthetic Salesforce-style data. All metrics are defined once in the semantic layer.")

tab_perf, tab_pipe, tab_usage, tab_dq, tab_defs = st.tabs(
    ["Commercial performance", "Pipeline", "Customer usage", "Data quality", "Metric definitions"])

# ---------- Commercial performance ----------
with tab_perf:
    k = q("opportunities", ["closed_won_amount", "closed_won_count", "win_rate", "avg_deal_size"],
          time_range=year_range).iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Bookings {year}", f"${(k.closed_won_amount or 0):,.0f}")
    c2.metric("Deals won", f"{int(k.closed_won_count or 0):,}")
    c3.metric("Win rate", f"{(k.win_rate or 0):.0%}")
    c4.metric("Avg deal size", f"${(k.avg_deal_size or 0):,.0f}")

    monthly = q("opportunities", ["closed_won_amount"], dimensions=["close_month"],
                time_range=year_range)
    st.plotly_chart(px.bar(monthly, x="close_month", y="closed_won_amount",
                           title="Bookings by month", color_discrete_sequence=[NAVY],
                           labels={"close_month": "", "closed_won_amount": "Bookings ($)"}),
                    width="stretch")
    by_region = q("opportunities", ["closed_won_amount", "win_rate"],
                  dimensions=["region", "product"], time_range=year_range)
    st.plotly_chart(px.bar(by_region, x="region", y="closed_won_amount", color="product",
                           barmode="group", title="Bookings by region and product",
                           labels={"closed_won_amount": "Bookings ($)", "region": ""}),
                    width="stretch")

# ---------- Pipeline ----------
with tab_pipe:
    p = q("opportunities", ["open_pipeline", "open_opportunity_count"]).iloc[0]
    c1, c2 = st.columns(2)
    c1.metric("Open pipeline", f"${(p.open_pipeline or 0):,.0f}")
    c2.metric("Open opportunities", f"{int(p.open_opportunity_count or 0):,}")
    stages = ["Prospecting", "Qualification", "Evaluation", "Proposal", "Negotiation"]
    by_stage = q("opportunities", ["open_pipeline", "open_opportunity_count"],
                 dimensions=["stage"])
    by_stage = by_stage[by_stage.stage.isin(stages)]
    by_stage = by_stage.set_index("stage").reindex(stages).reset_index()
    st.plotly_chart(px.bar(by_stage, x="stage", y="open_pipeline", title="Open pipeline by stage",
                           color_discrete_sequence=[NAVY],
                           labels={"stage": "", "open_pipeline": "Pipeline ($)"}),
                    width="stretch")
    top = q("opportunities", ["open_pipeline"], dimensions=["account_name", "region"])
    st.subheader("Top accounts by open pipeline")
    st.dataframe(top.dropna().sort_values("open_pipeline", ascending=False).head(15),
                 hide_index=True, width="stretch")

# ---------- Customer usage ----------
with tab_usage:
    usage_filters = {"product": products, "account_type": account_types}
    u = model.query("orders", ["analyses", "active_accounts", "analyses_per_account"], user,
                    filters=usage_filters, dimensions=["month"])
    if u.empty:
        st.info("No usage for this selection.")
    else:
        last = u.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("Analyses (latest month)", f"{int(last.analyses):,}")
        c2.metric("Active accounts", f"{int(last.active_accounts):,}")
        c3.metric("Analyses per account", f"{last.analyses_per_account:.1f}")
        by_prod = model.query("orders", ["analyses"], user, filters=usage_filters,
                              dimensions=["month", "product"])
        st.plotly_chart(px.line(by_prod, x="month", y="analyses", color="product",
                                title="Monthly analyses by product",
                                labels={"month": "", "analyses": "Analyses"}),
                        width="stretch")

# ---------- Data quality ----------
with tab_dq:
    st.caption("Checks run against the raw CRM extracts. Errors fail CI; warnings are reported.")
    results = run_checks(con)
    st.dataframe(
        [{"Check": r.check.description, "Severity": r.check.severity,
          "Status": "Pass" if r.passed else "Fail", "Rows flagged": r.failed_rows}
         for r in results], hide_index=True, width="stretch")

# ---------- Metric definitions ----------
with tab_defs:
    st.caption("Pulled directly from semantic/metrics.yml, so the definitions shown here are "
               "the same ones the dashboard computes.")
    st.dataframe(model.catalog(), hide_index=True, width="stretch")
