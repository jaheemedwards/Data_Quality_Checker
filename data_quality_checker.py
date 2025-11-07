import pandas as pd
import numpy as np
from datetime import datetime
import logging
from fpdf import FPDF
import io
import plotly.express as px

class DataQualityChecker:
    def __init__(self, file_path=None, df=None, file_name=None):
        """
        Initialize the DataQualityChecker.

        Parameters:
        - file_path: path to CSV, Excel, or Parquet file
        - df: pandas DataFrame (optional)
        - file_name: name to use for reports if df is provided
        """
        self.file_path = file_path
        self.df = df
        self.file_name = file_name if file_name else (file_path.split("/")[-1] if file_path else "DataFrame")
        self.quality_report = {}

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        logging.info(f"Initialized DataQualityChecker for: {self.file_name}")

    # ---------------------------------------------------------
    # Load data
    # ---------------------------------------------------------
    def load_data(self):
        """Load dataset from file if no DataFrame provided"""
        if self.df is not None:
            self.quality_report["basic_info"] = {
                "file_name": self.file_name,
                "total_rows": len(self.df),
                "total_columns": len(self.df.columns),
                "load_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            logging.info("Using provided DataFrame.")
            return True

        if not self.file_path:
            logging.error("No file path or DataFrame provided.")
            return False

        try:
            if self.file_path.endswith(".csv"):
                self.df = pd.read_csv(self.file_path)
            elif self.file_path.endswith(".xlsx"):
                self.df = pd.read_excel(self.file_path)
            elif self.file_path.endswith(".parquet"):
                self.df = pd.read_parquet(self.file_path)
            else:
                raise ValueError("Unsupported file format. Use CSV, XLSX, or PARQUET.")

            self.quality_report["basic_info"] = {
                "file_name": self.file_path.split("/")[-1],
                "total_rows": len(self.df),
                "total_columns": len(self.df.columns),
                "load_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            logging.info("Data loaded successfully from file.")
            return True

        except Exception as e:
            logging.error(f"Error loading file: {e}")
            print(f"❌ Error loading file: {e}")
            return False

    # ---------------------------------------------------------
    # Missing values
    # ---------------------------------------------------------
    def check_missing_values(self):
        missing_data = self.df.isnull().sum()
        missing_percentage = (missing_data / len(self.df)) * 100
        self.quality_report["missing_values"] = {
            "total_missing": int(missing_data.sum()),
            "missing_by_column": missing_data.to_dict(),
            "missing_percentage_by_column": missing_percentage.to_dict(),
            "columns_with_missing": missing_data[missing_data > 0].index.tolist(),
        }
        logging.info("Checked missing values.")

    # ---------------------------------------------------------
    # Data types
    # ---------------------------------------------------------
    def check_data_types(self):
        dtypes = self.df.dtypes.astype(str).to_dict()
        self.quality_report["data_types"] = {
            "column_types": dtypes,
            "numeric_columns": self.df.select_dtypes(include=[np.number]).columns.tolist(),
            "categorical_columns": self.df.select_dtypes(include=["object"]).columns.tolist(),
            "datetime_columns": self.df.select_dtypes(include=["datetime64"]).columns.tolist(),
        }
        logging.info("Checked data types.")

    # ---------------------------------------------------------
    # Duplicates
    # ---------------------------------------------------------
    def check_duplicates(self):
        duplicate_rows = self.df.duplicated().sum()
        self.quality_report["duplicates"] = {
            "total_duplicate_rows": int(duplicate_rows),
            "duplicate_percentage": float((duplicate_rows / len(self.df)) * 100),
        }
        logging.info("Checked duplicates.")

    # ---------------------------------------------------------
    # Outliers
    # ---------------------------------------------------------
    def check_numeric_outliers(self, method="IQR"):
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        outliers = {}

        for col in numeric_cols:
            if self.df[col].dropna().empty:
                continue
            Q1 = self.df[col].quantile(0.25)
            Q3 = self.df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            outlier_count = ((self.df[col] < lower_bound) | (self.df[col] > upper_bound)).sum()
            outliers[col] = {
                "outlier_count": int(outlier_count),
                "outlier_percentage": float((outlier_count / len(self.df)) * 100),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
            }

        self.quality_report["outliers"] = outliers
        logging.info("Checked numeric outliers.")

    # ---------------------------------------------------------
    # Column samples
    # ---------------------------------------------------------
    def inspect_column_samples(self, sample_size=3):
        sample_data = {}
        for col in self.df.columns:
            dtype = str(self.df[col].dtype)
            samples = self.df[col].dropna().astype(str).unique()[:sample_size].tolist()
            if len(samples) == 0:
                samples = ["<no non-null values>"]

            # Detect numeric-like object columns
            flag = ""
            if dtype == "object":
                numeric_like = sum(s.replace(".", "", 1).isdigit() for s in samples)
                if len(samples) > 0 and (numeric_like / len(samples)) > 0.6:
                    flag = "⚠️ POSSIBLE NUMERIC STORED AS STRING"

            sample_data[col] = {"detected_type": dtype, "sample_values": samples, "notes": flag}

        self.quality_report["sample_inspection"] = sample_data
        logging.info("Inspected column samples.")

    # ---------------------------------------------------------
    # Cardinality
    # ---------------------------------------------------------
    def check_cardinality(self):
        categorical_cols = self.df.select_dtypes(include=["object"]).columns
        cardinality = {}
        for col in categorical_cols:
            unique_count = self.df[col].nunique(dropna=True)
            cardinality[col] = {
                "unique_values": int(unique_count),
                "cardinality_percentage": float((unique_count / len(self.df)) * 100),
                "high_cardinality": bool(unique_count > (len(self.df) * 0.5)),
            }
        self.quality_report["cardinality"] = cardinality
        logging.info("Checked cardinality.")

    # ---------------------------------------------------------
    # Summary statistics
    # ---------------------------------------------------------
    def generate_summary_statistics(self):
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        self.quality_report["summary_statistics"] = {
            "describe": self.df[numeric_cols].describe().to_dict(),
            "skewness": self.df[numeric_cols].skew().to_dict(),
            "kurtosis": self.df[numeric_cols].kurtosis().to_dict(),
        }
        logging.info("Generated summary statistics.")

    # ---------------------------------------------------------
    # Run all checks
    # ---------------------------------------------------------
    def run_all_checks(self):
        if not self.load_data():
            return None
        self.check_missing_values()
        self.check_data_types()
        self.check_duplicates()
        self.check_numeric_outliers()
        self.check_cardinality()
        self.generate_summary_statistics()
        self.inspect_column_samples()
        logging.info("All checks completed.")
        return self.quality_report

    # ---------------------------------------------------------
    # Text report
    # ---------------------------------------------------------
    def generate_text_report(self):
        if not self.quality_report:
            self.run_all_checks()

        basic = self.quality_report["basic_info"]
        missing = self.quality_report["missing_values"]
        dupes = self.quality_report["duplicates"]
        samples = self.quality_report.get("sample_inspection", {})

        report = []
        report.append("=" * 60)
        report.append("DATA QUALITY REPORT")
        report.append("=" * 60)
        report.append(f"File: {basic['file_name']}")
        report.append(f"Rows: {basic['total_rows']:,}")
        report.append(f"Columns: {basic['total_columns']}")
        report.append(f"Generated: {basic['load_timestamp']}\n")
        report.append(f"Total Missing: {missing['total_missing']:,}")
        report.append(f"Columns with Missing: {len(missing['columns_with_missing'])}")
        report.append(f"Duplicate Rows: {dupes['total_duplicate_rows']:,} ({dupes['duplicate_percentage']:.1f}%)")
        report.append("=" * 60)
        report.append("\nCOLUMN SAMPLE VALUES")
        report.append("-" * 60)

        for col, info in samples.items():
            report.append(f"{col} ({info['detected_type']}): {info['sample_values']}")
            if info["notes"]:
                report.append(f"  ⚠️ {info['notes']}")
            report.append("")

        return "\n".join(report)

    # ---------------------------------------------------------
    # Get PDF bytes (text + charts + summary stats)
    # ---------------------------------------------------------
    def get_pdf_bytes(self):
        """Generate PDF report with text and summary statistics only."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Courier", size=10)

        # ------------------ Text report ------------------
        text_report = self.generate_text_report()
        for line in text_report.split("\n"):
            pdf.multi_cell(0, 5, line)

        # ------------------ Summary statistics ------------------
        summary = self.quality_report.get("summary_statistics", {}).get("describe", {})
        if summary:
            pdf.add_page()
            pdf.set_font("Courier", 'B', 12)
            pdf.cell(0, 10, "Numeric Summary Statistics", ln=True, align="C")
            pdf.set_font("Courier", size=10)
            pdf.ln(5)

            df_summary = pd.DataFrame(summary).reset_index().rename(columns={"index": "Metric"}).round(2)
            col_width = 25
            row_height = 6
            for i, row in df_summary.iterrows():
                for col in df_summary.columns:
                    pdf.cell(col_width, row_height, txt=str(row[col])[:12], border=1)
                pdf.ln(row_height)

        # ------------------ Return as BytesIO ------------------
        pdf_bytes = pdf.output(dest='S').encode('latin1')  # Return PDF as bytes
        return io.BytesIO(pdf_bytes)
