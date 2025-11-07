import streamlit as st
import pandas as pd
import plotly.express as px
import os
import io
from data_quality_checker import DataQualityChecker

st.set_page_config(page_title="Data Quality Dashboard", layout="wide")

# ---------------------------------------------------------
# App Header
# ---------------------------------------------------------
st.title("🧮 Data Quality Analysis Dashboard")
st.markdown(
    "Upload your dataset to automatically check for missing values, outliers, type issues, cardinality, "
    "and more. The dashboard also explains each metric to help understand data quality."
)

# ---------------------------------------------------------
# File Upload or Sample Selection
# ---------------------------------------------------------
sample_folder = "dirty_data_samples"
sample_files = [f for f in os.listdir(sample_folder) if f.endswith((".csv", ".xlsx", ".parquet"))]

st.markdown(
    "You can either upload your own file or select a sample dataset from the dropdown below."
)

uploaded_file = st.file_uploader("📂 Upload a data file", type=["csv", "xlsx", "parquet"])
selected_sample = None
if not uploaded_file and sample_files:
    selected_sample = st.selectbox("Or choose a sample dataset", sample_files)

# ---------------------------------------------------------
# Load the dataset into a DataFrame
# ---------------------------------------------------------
df = None
file_name = None

try:
    if uploaded_file:
        file_name = uploaded_file.name
        if file_name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif file_name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        elif file_name.endswith(".parquet"):
            df = pd.read_parquet(uploaded_file)
    elif selected_sample:
        file_name = selected_sample
        sample_path = os.path.join(sample_folder, selected_sample)
        if selected_sample.endswith(".csv"):
            df = pd.read_csv(sample_path)
        elif selected_sample.endswith(".xlsx"):
            df = pd.read_excel(sample_path)
        elif selected_sample.endswith(".parquet"):
            df = pd.read_parquet(sample_path)
except Exception as e:
    st.error(f"❌ Error loading file: {e}")

# ---------------------------------------------------------
# Run Analysis if a DataFrame is loaded
# ---------------------------------------------------------
if df is not None:
    with st.spinner("🔍 Analyzing dataset..."):
        checker = DataQualityChecker(df=df, file_name=file_name)
        report = checker.run_all_checks()
        text_report = checker.generate_text_report()

    # ------------------------- Basic Info -------------------------
    basic_info = report.get("basic_info", {})
    st.success(f"✅ File analyzed successfully: **{basic_info.get('file_name', file_name)}**")
    st.write(f"**Rows:** {basic_info.get('total_rows', len(df)):,}  |  **Columns:** {basic_info.get('total_columns', len(df.columns))}")
    st.caption(f"Generated on: {basic_info.get('load_timestamp', '')}")
    st.info("This section shows basic file information and dataset dimensions.")

    # ------------------------- Text Summary -------------------------
    with st.expander("🧾 Full Text Report"):
        st.text(text_report)
        st.caption("The full text report summarizes missing values, duplicates, and overall data quality metrics.")

    # ------------------------- Missing Values -------------------------
    st.subheader("🔍 Missing Values Overview")
    missing_df = pd.DataFrame({
        "Column": report["missing_values"]["missing_by_column"].keys(),
        "Missing Count": report["missing_values"]["missing_by_column"].values(),
        "Missing %": report["missing_values"]["missing_percentage_by_column"].values()
    })
    missing_df["Missing %"] = pd.to_numeric(missing_df["Missing %"], errors="coerce").fillna(0).round(2)
    st.dataframe(missing_df, width='stretch')

    if not missing_df.empty:
        fig_missing = px.bar(
            missing_df,
            x="Column",
            y="Missing %",
            title="Missing Percentage by Column",
            text="Missing %",
            color="Missing %",
            color_continuous_scale="Reds",
            height=500
        )
        fig_missing.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig_missing.update_layout(xaxis_tickangle=-45, yaxis_tickformat=".2f", margin=dict(t=120, b=100, l=60, r=40))
        st.plotly_chart(fig_missing, width='stretch')

    # ------------------------- Outlier Visualization -------------------------
    st.subheader("📊 Numeric Outliers")
    outlier_df = pd.DataFrame(report["outliers"]).T.reset_index().rename(columns={"index": "Column"})
    if not outlier_df.empty:
        outlier_df["outlier_percentage"] = pd.to_numeric(outlier_df["outlier_percentage"], errors="coerce").fillna(0).round(2)
        st.dataframe(outlier_df, width='stretch')
        fig_outliers = px.bar(
            outlier_df,
            x="Column",
            y="outlier_percentage",
            title="Outlier Percentage by Column",
            text="outlier_percentage",
            color="outlier_percentage",
            color_continuous_scale="Blues",
            height=500
        )
        fig_outliers.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig_outliers.update_layout(xaxis_tickangle=-45, yaxis_tickformat=".2f", margin=dict(t=120, b=100, l=60, r=40))
        st.plotly_chart(fig_outliers, width='stretch')
    else:
        st.info("No numeric outliers detected.")

    # ------------------------- Sample Value Inspection -------------------------
    st.subheader("🔠 Column Data Type & Sample Value Inspection")
    samples = report.get("sample_inspection", {})
    sample_df = pd.DataFrame([
        {
            "Column": col,
            "Detected Type": info["detected_type"],
            "Sample Values": ", ".join(map(str, info["sample_values"])),
            "Notes": info["notes"] or ""
        }
        for col, info in samples.items()
    ])
    st.dataframe(sample_df, width='stretch')

    # ------------------------- Cardinality -------------------------
    st.subheader("🔢 Categorical Column Cardinality")
    cardinality = report.get("cardinality", {})
    if cardinality:
        card_df = pd.DataFrame(cardinality).T.reset_index().rename(columns={"index": "Column"})
        card_df["cardinality_percentage"] = pd.to_numeric(card_df["cardinality_percentage"], errors="coerce").fillna(0).round(2)
        card_df["unique_values"] = pd.to_numeric(card_df["unique_values"], errors="coerce").fillna(0).astype(int)
        st.dataframe(card_df, width='stretch')
        fig_cardinality = px.bar(
            card_df,
            x="Column",
            y="cardinality_percentage",
            title="Cardinality Percentage by Column",
            text="cardinality_percentage",
            color="cardinality_percentage",
            color_continuous_scale="Purples",
            height=500
        )
        fig_cardinality.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig_cardinality.update_layout(xaxis_tickangle=-45, yaxis_tickformat=".2f", margin=dict(t=120, b=100, l=60, r=40))
        st.plotly_chart(fig_cardinality, width='stretch')
    else:
        st.info("No categorical columns found.")

    # ------------------------- Download Report -------------------------
    st.subheader("💾 Download Full Report")

    # Generate PDF (text + summary only, no charts)
    pdf_bytes = checker.get_pdf_bytes()
    st.download_button(
        label="📥 Download PDF Report",
        data=pdf_bytes,
        file_name="data_quality_report.pdf",
        mime="application/pdf"
    )

    txt_bytes = io.BytesIO(text_report.encode("utf-8"))
    st.download_button(
        label="📥 Download TXT Report",
        data=txt_bytes,
        file_name="data_quality_report.txt",
        mime="text/plain"
    )

else:
    st.info("📁 Please upload a CSV, Excel, or Parquet file, or select a sample dataset to begin analysis.")
