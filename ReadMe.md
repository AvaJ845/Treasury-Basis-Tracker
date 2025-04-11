# US Treasury Basis Trade Tracker

This Streamlit application tracks US Treasury data with a focus on the hedge fund basis trade and its implications for mortgage rates. It provides real-time monitoring of market stress indicators and predicts potential impacts on mortgage rates.

## Features

- **Live Treasury Yield Tracking**: Monitor 2-year, 10-year, and 30-year Treasury yields
- **Basis Trade Analysis**: Track swap spreads and detect potential hedge fund unwinds
- **Leverage Monitoring**: Estimate current leverage levels in basis trades
- **Mortgage Rate Impact**: Forecast mortgage rate changes based on Treasury movements
- **Market Stress Dashboard**: Real-time indicators of potential market stress
- **Interactive Visualizations**: Detailed charts and metrics for analysis

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd treasury-basis-trade-tracker
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your API keys:
   - Get a free API key from FRED (Federal Reserve Economic Data): https://fred.stlouisfed.org/docs/api/api_key.html
   - (Optional) Get API keys from Alpha Vantage and Polygon for enhanced data access

4. Add your API keys to the application:
   - Either edit the app.py file directly to update the API keys at the top
   - Or use the custom API key section in the sidebar when running the app

## Usage

1. Run the Streamlit application:
   ```
   streamlit run app.py
   ```

2. Access the application in your web browser (typically at http://localhost:8501)

3. Configure the application using the sidebar:
   - Select the data timeframe (1 month to 2 years)
   - Set auto-refresh options
   - Adjust stress detection thresholds
   - Configure custom API keys if needed

4. Explore the different tabs:
   - **Treasury Yields**: View current and historical yield curves
   - **Basis Trade Analysis**: Monitor the basis trade and potential risks
   - **Mortgage Impact**: See how Treasury movements affect mortgage rates
   - **Market Stress**: Track indicators of potential market stress

## Understanding the Basis Trade

The Treasury basis trade is a popular hedge fund strategy that involves:

1. **Going long cash Treasuries**: Buying actual Treasury bonds
2. **Shorting Treasury futures**: Taking a short position in Treasury futures contracts
3. **Using leverage**: Financing the cash position through repo markets, often at 10:1 or higher leverage

The trade aims to profit from the small price differentials between cash Treasury prices and futures prices. When market stress occurs, highly leveraged funds may be forced to unwind positions quickly, creating market volatility that impacts mortgage rates.

## Data Sources

- **Treasury Yields**: Federal Reserve Economic Data (FRED)
- **Mortgage Rates**: Federal Reserve Economic Data (FRED)
- **Treasury Futures**: Yahoo Finance
- **Swap Rates**: Federal Reserve Economic Data (FRED)

## Requirements

- Python 3.8+
- Streamlit 1.31.0+
- See requirements.txt for full list of dependencies

## License

[MIT License](LICENSE)
