import streamlit as st
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import os

# Ensure the 'data' directory exists
os.makedirs("data", exist_ok=True)

from models import MODEL_PROVIDERS
from summary_gen import RiskSummaryGenerator
from index_construction import IndexConstructor

st.set_page_config(layout="wide", page_title="Systemic Risk Analysis", page_icon="📈")


# --- DATA LOADING (with caching for efficiency) ---
@st.cache_data
def load_sri_data():
    """
    Loads the risk factors data and computes the SRI over the FULL history.
    Returns None if the source data file does not exist.
    """
    try:
        constructor = IndexConstructor()
        # The get_final_dataframe should now return the entire historical data
        sri_df = constructor.get_final_dataframe()
        return sri_df
    except FileNotFoundError:
        return None


# --- SIDEBAR ---
st.sidebar.title("🧮 Systemic Risk Analysis")
st.sidebar.markdown("This app analyzes systemic risk using large language models.")
st.sidebar.markdown("---")

st.sidebar.header("Model Selection")
available_models = [
    model for provider_models in MODEL_PROVIDERS.values() for model in provider_models
]
model_name = st.sidebar.selectbox(
    "Select a model for summary generation:", options=available_models, index=0
)

with st.sidebar as sidebar:
    st.sidebar.header("Data Actions")
    if st.sidebar.button("Download Fresh Risk Data"):
        with st.spinner("Downloading and preprocessing risk factors..."):
            try:
                constructor = IndexConstructor()
                constructor.save_data("data/risk_factors.csv")
                st.sidebar.success("Data downloaded successfully!")
                st.cache_data.clear()
            except Exception as e:
                st.sidebar.error(f"An error occurred: {e}")

st.sidebar.markdown("---")
st.sidebar.info(
    "First, download the data. Then, generate the summary on the main page."
)


# --- MAIN PAGE ---
st.title("📊 Economic Outlook & Systemic Risk")

# Load the FULL historical data first
full_sri_data = load_sri_data()

# Check if data exists before proceeding
if full_sri_data is not None and not full_sri_data.empty:

    # Create a 90-week slice for display purposes. All charts will use this slice.
    sri_data_display = full_sri_data.tail(90)

    st.header("Generate Risk Summary")
    if st.button(f"Generate Summary with {model_name}"):
        with st.spinner(
            f"Generating summary with {model_name}... This may take a moment."
        ):
            try:
                # The generator can still use the display slice for its context
                generator = RiskSummaryGenerator(model_name=model_name)
                # We pass the display data to the generator
                summary = generator.generate_summary(input_data=sri_data_display)
                st.markdown(summary)
            except Exception as e:
                st.error(f"Failed to generate summary: {e.args[0]}")

    st.markdown("---")
    st.header("📉 Systemic Risk Index (SRI)")
    st.markdown(
        "*Note: The Systemic Risk Index (SRI) is a measure of systemic risk in the financial system, scaled from 0 to 100.*"
    )

    # Use the 90-week display DataFrame for the chart
    fig_sri = px.line(
        sri_data_display,
        x=sri_data_display.index,
        y="SRI",
        labels={"Date": "Date", "SRI": "SRI Value (0-100)"},
    )
    fig_sri.update_layout(xaxis_title="Date", yaxis_title="SRI Value")
    st.plotly_chart(fig_sri, use_container_width=True)

    fig_factors = make_subplots(
        rows=1,
        cols=3,
        shared_xaxes=True,
        subplot_titles=(
            "Equity Market Volatility (VIX)",
            "Bond Market Volatility (MOVE)",
            "Corporate Bond Yields (ICE BofA)",
        ),
    )

    # Consistently use the 'sri_data_display' slice for ALL subplots
    fig_factors.add_trace(
        go.Scatter(x=sri_data_display.index, y=sri_data_display["VIX"], name="VIX"),
        row=1,
        col=1,
    )
    fig_factors.add_trace(
        go.Scatter(x=sri_data_display.index, y=sri_data_display["MOVE"], name="MOVE"),
        row=1,
        col=2,
    )
    fig_factors.add_trace(
        go.Scatter(
            x=sri_data_display.index,
            y=sri_data_display["BAMLC0A0CMEY"],
            name="Corp Yield",
        ),
        row=1,
        col=3,
    )

    fig_factors.update_layout(height=400, showlegend=False)

    st.plotly_chart(fig_factors, use_container_width=True)

else:
    st.warning(
        "Data not found. Please click the 'Download Fresh Risk Data' button in the sidebar to begin."
    )
