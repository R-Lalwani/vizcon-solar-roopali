#!/usr/bin/env python
# coding: utf-8



import pandas as pd
import plotly.express as px




#### HELPER FUNCTIONS

def canon(df: pd.DataFrame) -> pd.DataFrame:
    """lower_snake_case the column NAMES (values untouched)."""
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

irena=pd.read_csv('IRENA_Region_Country_data.csv', encoding='latin-1')
print(irena.shape)

lcoe_projections=pd.read_csv('LCOE.csv', encoding='latin-1')
print(lcoe_projections.columns)
lcoe_projections=lcoe_projections[['ï»¿Year', 'Metric', 'Solar photovoltaic', 'Onshore wind', 'Hydropower']]


# In[28]:


## proper column names
irena=canon(irena)

# keep only these columns
irena=irena[['region', 'flag', 'technology', 'data_type', 'year', 'electricity_statistics']]

## separate the capacity and generation data
irena_generation=irena[irena.data_type=='Electricity Generation (GWh)']
irena_capacity=irena[irena.data_type=='Electricity Installed Capacity (MW)']

print(irena_generation.shape)
print(irena_capacity.shape)
## Capacity has more records, makes sense, as there could be no generation despite of having capacity



## rename statistics to generation_gwh, then create another column in twh
irena_generation.columns=['region', 'flag', 'technology', 'data_type', 'year','generation_gwh']
irena_generation['generation_twh']=irena_generation['generation_gwh']/1000

## get the total energy (TRW+TNRW) for each region-flag-year
# filter only total renewable & total non-renewable
irena_generation_total_energy = irena_generation[irena_generation["technology"].isin(["Total renewable", "Total non-renewable"])].copy()

# group by year and technology → global totals
irena_generation_total_energy = (
    irena_generation_total_energy.groupby(["region", "flag", "year"], as_index=False)[["generation_gwh", "generation_twh"]]
             .sum()
)

irena_generation_total_energy.columns=['region', 'flag', 'year', 'generation_gwh_total_energy', 'generation_twh_total_energy']


## create a dataset for % share
generation_data=pd.merge(irena_generation, irena_generation_total_energy, on=['region', 'flag', 'year'], how='left')
del irena_generation, irena_generation_total_energy

generation_data['pct_of_total_energy']=generation_data['generation_gwh']*100.0/generation_data['generation_gwh_total_energy']



# In[78]:


## Share of Solar, Hydro and Wind in Total Renewable

# Step 1: Identify "Total renewable energy" values per region/year/flag
totals = (
    generation_data[generation_data["technology"] == "Total renewable"]
    .set_index(["region", "flag", "year"])["generation_gwh"]
)

# Step 2: Map these totals back to the main df
generation_data["total_renewables"] = generation_data.set_index(["region", "flag", "year"]).index.map(totals)

# Step 3: Calculate percentage share
generation_data["share_of_total_renewables"] = (
    generation_data["generation_gwh"] / generation_data["total_renewables"] * 100
)

# Optional: filter only component technologies (exclude the total row itself)
renewable_share = generation_data[(generation_data["technology"] != "Total renewable energy") & (generation_data['region']=='World')]
renewable_share = renewable_share[renewable_share["technology"].isin(['Solar energy', 'Wind energy','Hydropower (excl. Pumped Storage)'])].copy()
renewable_share=renewable_share[['region', 'flag', 'technology', 'year', 'share_of_total_renewables']]

renewable_share.loc[(renewable_share["year"] >= 2024), "share_of_total_renewables"] *= 100

### projections
lcoe_projections.columns=['year', 'metric', 'Solar energy', 'Wind energy', 'Hydropower (excl. Pumped Storage)']
projections=lcoe_projections[lcoe_projections['metric']=='Projections']
projections['region']='World'
projections['flag']='Region'


# Melt wide → long
projections = projections.melt(
    id_vars=['region', 'flag', "year"],   # keep identifiers
    value_vars=['Solar energy', 'Wind energy', 'Hydropower (excl. Pumped Storage)'],
    var_name="technology",
    value_name="share_of_total_renewables"
)
projections=projections[['region', 'flag', 'technology', 'year', 'share_of_total_renewables']]
renewable_share = pd.concat([renewable_share, projections], ignore_index=True)

##### STREAMLIT CODE ###

import streamlit as st

st.set_page_config(page_title="Energy Transition — Renewables Story", layout="wide")

# -------------------------------------------------------------------
# 0) LOAD YOUR PREPARED TABLES (no uploads). Replace these lines with
#    your actual import or inline prep code that creates the 3 dfs:
#    generation_data, renewable_share, lcoe_projections
# -------------------------------------------------------------------
# Example: read from disk (comment out if you already build them inline)
# generation_data = pd.read_parquet("processed/generation_data.parquet")
# renewable_share = pd.read_parquet("processed/renewable_share.parquet")
# lcoe_projections        = pd.read_parquet("processed/lcoe_costs.parquet")

# -------------------------------------------------------------------
# 1) FILTERS / CONSTANTS
# -------------------------------------------------------------------
REGIONS = sorted(generation_data[generation_data.flag=='Region']["region"].dropna().unique().tolist())
YEARS   = sorted(generation_data["year"].dropna().unique().tolist())

st.sidebar.header("Filters")
region = st.sidebar.selectbox("Region", options=(["World"] + [r for r in REGIONS if r != "World"]), index=0)
yr_min, yr_max = st.sidebar.select_slider("Year range", options=YEARS, value=(min(YEARS), max(YEARS)))

# Infographic constants (no sidebar controls)
DEPLETION_NOTE = "Conventional fossil fuel reserves are finite; supply risks escalate as reserves deplete by ~2060."
GHG_KPI        = "~1.2°C warming"
GHG_SUB        = "vs pre-industrial global average (IPCC synthesis)"

# -------------------------------------------------------------------
# 2) HELPERS SPECIFIC TO YOUR LABELS
# -------------------------------------------------------------------
FOSSIL_TECHS = {"Coal", "Oil", "Natural gas", "Fossil fuels", "Fossil fuel"}
NUCLEAR_TECHS = {"Nuclear energy", "Nuclear"}
SOLAR_TECHS = {"Solar energy", "Solar photovoltaic"}
WIND_TECHS = {"Wind energy", "Onshore wind", "Offshore wind"}
HYDRO_TECHS = {"Hydropower (excl. Pumped Storage)", "Hydropower"}

def _bucket(row_tech: str) -> str | None:
    t = (row_tech or "").strip()
    if t in FOSSIL_TECHS: return "Fossil fuels"
    if t in NUCLEAR_TECHS: return "Nuclear"
    if t in SOLAR_TECHS: return "Solar"
    if t in WIND_TECHS: return "Wind"
    if t in HYDRO_TECHS: return "Hydro"
    return None

# Scoped data
scope = generation_data[
    (generation_data["region"] == region) &
    (generation_data["year"].between(yr_min, yr_max))
].copy()

# -------------------------------------------------------------------
# 3) TOP ROW — Renewables share line (left) AND infographics stacked (right)
# -------------------------------------------------------------------
st.title("Energy Transition — Why Renewables Are Rising")

colL, colR = st.columns([2,1], gap="large")

with colL:
    gd = scope.copy()
    gd = gd[gd['technology']=='Total renewable']

    st.subheader(f"Renewables Share of Total Energy — {region}")
    fig_share = px.line(
        gd, x="year", y="pct_of_total_energy",
        markers=True, title=None,
        labels={"pct_of_total_energy":"share (%) to total energy"}
    )
    fig_share.update_layout(yaxis_title="%")
    st.plotly_chart(fig_share, use_container_width=True)

    st.markdown(
        """
        *Observations*
        - Renewables’ share rises steadily in the selected period.
        - Inflection points often align with cost declines and policy shifts.
        - The gap with non-renewables narrows as solar & wind scale rapidly.
        """
    )

with colR:
    st.subheader("Why this shift?")
    # stacked, not side-by-side
    st.metric("Finite fuels", "Depletion risk ~2060", help=DEPLETION_NOTE)
    st.write("")  # small spacer
    st.metric("Climate signal", GHG_KPI, help=GHG_SUB)
    st.caption("These structural drivers accelerate the shift to renewables.")

# -------------------------------------------------------------------
# 4) SECOND ROW — ONLY Energy Mix (stacked area)
# -------------------------------------------------------------------
st.subheader("Energy Mix — Share of Total Energy (Stacked)")

m = scope.copy()
m["bucket"] = m["technology"].apply(_bucket)
m = m[m["bucket"].notna()]

by_bucket = (m.groupby(["year","bucket"], as_index=False)
               .agg(gen_twh=("generation_twh","sum"),
                    total_twh=("generation_twh_total_energy","max")))
by_bucket["share_pct"] = by_bucket["gen_twh"] * 100 / by_bucket["total_twh"]

pivot = by_bucket.pivot(index="year", columns="bucket", values="share_pct").fillna(0).reset_index()
stack_cols = [c for c in ["Fossil fuels","Nuclear","Solar","Wind","Hydro"] if c in pivot.columns]

fig_stack = px.area(
    pivot, x="year", y=stack_cols,
    title=None, labels={c:c for c in stack_cols}
)
fig_stack.update_layout(yaxis_title="% of total energy", legend_title_text="")
st.plotly_chart(fig_stack, use_container_width=True)

# -------------------------------------------------------------------
# 5) THIRD ROW — 2023 Renewables Pie (left) AND History+Forecast (right)
# -------------------------------------------------------------------
colB, colC = st.columns([1,2], gap="large")

with colB:
    st.subheader("Renewables Split — 2023")
    year_pie = 2023 if 2023 in renewable_share["year"].unique() else max(renewable_share["year"])
    rscope = renewable_share[
        (renewable_share["region"] == region) &
        (renewable_share["year"] == year_pie)
    ]
    PIE_TECHS = {"Solar energy","Wind energy", "Hydropower (excl. Pumped Storage)"}

    
    rpie = rscope[rscope["technology"].isin(PIE_TECHS)].copy()

    if rpie.empty:
        st.info("No renewable split for the chosen filters/year.")
    else:
        fig_pie = px.pie(
            rpie, names="technology", values="share_of_total_renewables"
        )
        # Remove the legend
        fig_pie.update_layout(showlegend=False)

        
        st.plotly_chart(fig_pie, use_container_width=True)

with colC:
    st.subheader("Renewables Split — History & Forecast")
    rline = renewable_share[
        (renewable_share["region"] == region) &
        (renewable_share["technology"].isin(PIE_TECHS))
    ].copy()

    rline.loc[(rline["year"] >= 2024), "share_of_total_renewables"] *= 100


    print(renewable_share[renewable_share.year>2024].head())


    fig_rline = px.line(
        rline, x="year", y="share_of_total_renewables",
        color="technology", markers=True,
        title=None, labels={"share_of_total_renewables":"% of renewables"}
    )

    fig_rline.update_layout(legend=dict(
        orientation="v",  # Vertical orientation (optional, but common for left legends)
        yanchor="top",    # Anchor the legend to the top of its bounding box
        y=1,              # Position the legend's top at the top of the plot area (paper coordinates)
        xanchor="right",  # Anchor the legend to the right of its bounding box
        x=-0.3            # Position the legend's right edge at -0.3 (left of plot area)
    ))
    st.plotly_chart(fig_rline, use_container_width=True)
    #st.caption("Projections included if you appended them to renewable_share (e.g., 2029 solar overtakes hydro).")

# -------------------------------------------------------------------
# 6) LCOE — Cost comparison (unchanged)
# -------------------------------------------------------------------
st.subheader("LCOE — Cost Comparison (USD ($)/MWh)")

wide_cols = [c for c in lcoe_projections.columns if any(k in c.lower() for k in ["solar","wind","hydro"])]

lcoe_long = lcoe_projections[lcoe_projections.year<=2023].melt(id_vars=[c for c in lcoe_projections.columns if c not in wide_cols],
                                 value_vars=wide_cols,
                                 var_name="technology", value_name="lcoe_usd_mwh")

lcoe_long["technology"] = lcoe_long["technology"].str.replace("_"," ").str.title()
fig_lcoe = px.line(
    lcoe_long, x="year", y="lcoe_usd_mwh", color="technology",
    markers=True, labels={"lcoe_usd_mwh":"$/MWh"}, title=None
)
st.plotly_chart(fig_lcoe, use_container_width=True)