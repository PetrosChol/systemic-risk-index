import pandas as pd
import yfinance as yf
from fredapi import Fred
import os
from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.decomposition import PCA
from datetime import datetime, timedelta

load_dotenv()


class IndexConstructor:
    """
    A class to construct a Systemic Risk Index (SRI) from various financial risk factors.
    """

    def __init__(self, risk_factors=["^VIX", "^MOVE", "BAMLC0A0CMEY"]) -> None:
        """
        Initializes the IndexConstructor.
        Args:
            risk_factors (list): A list of ticker symbols for risk factors.
                                 Yahoo Finance tickers should be used for VIX and MOVE.
        """
        self.risk_factors = risk_factors
        self.fred_api_key = os.environ.get("FRED_API_KEY")
        if not self.fred_api_key:
            raise ValueError("FRED_API_KEY not found in environment variables.")
        self.fred = Fred(api_key=self.fred_api_key)

        # Define which tickers are from Yahoo Finance
        self.yf_source_tickers = ["^VIX", "^MOVE"]

    def download_data(self) -> pd.DataFrame:
        """
        Downloads data for the specified risk factors from Yahoo Finance and FRED.
        Returns:
            pd.DataFrame: A DataFrame containing the time series data for all risk factors.
        """
        start_date = "2000-01-01"

        # Separate tickers based on their source
        yf_tickers = [
            ticker for ticker in self.risk_factors if ticker in self.yf_source_tickers
        ]
        fred_tickers = [
            ticker
            for ticker in self.risk_factors
            if ticker not in self.yf_source_tickers
        ]

        # Download data from Yahoo Finance using yfinance
        yf_data = pd.DataFrame()
        if yf_tickers:
            try:
                yf_download_result = yf.download(
                    yf_tickers, start=start_date, auto_adjust=False
                )
                if yf_download_result is not None and "Close" in yf_download_result:
                    yf_data = yf_download_result["Close"]
                    if isinstance(yf_data, pd.Series):
                        yf_data = yf_data.to_frame(name=yf_tickers[0])
                    yf_data.rename(
                        columns={"^VIX": "VIX", "^MOVE": "MOVE"}, inplace=True
                    )
                else:
                    print(
                        "Warning: yfinance download returned None or missing 'Close' column."
                    )
                    yf_data = pd.DataFrame()
            except Exception as e:
                print(
                    f"Could not download data from Yahoo Finance using 'yfinance': {e}"
                )

        # Download data from FRED using fredapi
        fred_data = pd.DataFrame()
        for ticker in fred_tickers:
            fred_data[ticker] = self.fred.get_series(ticker, start_date)

        # Combine the datasets
        combined_data = pd.concat([yf_data, fred_data], axis=1, join="outer")
        combined_data.index.name = "Date"
        return combined_data

    def preprocess_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocesses the raw data by resampling to weekly frequency and handling missing values.
        Args:
            data (pd.DataFrame): The raw data DataFrame.
        Returns:
            pd.DataFrame: The preprocessed DataFrame.
        """
        data_ffilled = data.ffill()
        weekly_data = data_ffilled.resample("W-FRI").last()
        weekly_data.ffill(inplace=True)
        weekly_data.dropna(inplace=True)
        return weekly_data

    def save_data(self, file_path: str) -> None:
        """
        Downloads, preprocesses, and saves the risk factor data to a CSV file.
        Args:
            file_path (str): The relative path to save the CSV file.
        """
        print("Downloading and preprocessing data...")
        raw_data = self.download_data()

        if raw_data.empty:
            print("Failed to download data. Aborting save.")
            return

        preprocessed_data = self.preprocess_data(raw_data)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        preprocessed_data.to_csv(file_path)
        print(f"Data saved successfully to {file_path}")

    def construct_sri(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Constructs the Systemic Risk Index (SRI) using PCA.
        Args:
            data (pd.DataFrame): The preprocessed data of risk factors.
        Returns:
            pd.DataFrame: The data DataFrame with an added "SRI" column.
        """
        factor_columns = [
            col for col in ["VIX", "MOVE", "BAMLC0A0CMEY"] if col in data.columns
        ]
        risk_factors_data = data[factor_columns].copy()

        # Check if the DataFrame is empty before proceeding
        if risk_factors_data.empty:
            print("Warning: Input data for SRI construction is empty after filtering.")
            print("This might be due to missing data for VIX, MOVE, or BAMLC0A0CMEY.")
            print("Skipping SRI calculation.")
            # Add an empty SRI column so the rest of the app doesn't break
            data["SRI"] = None
            return data

        scaler = StandardScaler()
        scaled_factors = scaler.fit_transform(risk_factors_data)

        pca = PCA(n_components=1)
        principal_component = pca.fit_transform(scaled_factors)

        sri_raw = pd.Series(
            principal_component.flatten(), index=risk_factors_data.index, name="SRI_raw"
        )

        loadings = pd.Series(pca.components_[0], index=risk_factors_data.columns)
        if "VIX" in loadings and loadings["VIX"] < 0:
            sri_raw *= -1

        min_max_scaler = MinMaxScaler(feature_range=(0, 100))
        sri_scaled = min_max_scaler.fit_transform(sri_raw.to_numpy().reshape(-1, 1))

        data["SRI"] = sri_scaled
        return data

    def get_final_dataframe(self) -> pd.DataFrame:
        """
        Reads the preprocessed data, constructs the SRI, and returns the final DataFrame.
        """
        file_path = os.path.join("data", "risk_factors.csv")

        try:
            data = pd.read_csv(
                file_path,
                index_col=0,
                parse_dates=True,
            )
        except FileNotFoundError:
            print(f"File not found at {file_path}. Please run save_data() first.")
            return pd.DataFrame()

        # Construct SRI on the entire dataset to get historical scaling
        sri_data = self.construct_sri(data)

        return sri_data
