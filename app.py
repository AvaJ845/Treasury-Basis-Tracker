# Treasury Basis Trade Tracker
# This Streamlit app tracks US Treasury data, focusing on the hedge fund basis trade
# and its implications for mortgage rates with leveraged positions monitoring

import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime
import altair as alt
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import time
import json
import yfinance as yf
from fredapi import Fred

# App configuration
st.set_page_config(
    page_title="Treasury Basis Trade Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API keys (from input at the top of the file)
FRED_API_KEY = "a81e9c33d8dbac1cc1309e51527e0d53"
ALPHA_VANTAGE_API_KEY = "E3R1QOXBCPW9924S"
POLYGON_API_KEY = "9rP1CLlxuoRWPvkEiOMxxIwNyffjUEb4"

# Initialize the FRED API client
fred = Fred(api_key=FRED_API_KEY)

# CSS styling for the app
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 20px;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #2C5282;
        margin-top: 30px;
        margin-bottom: 10px;
    }
    .alert-box {
        padding: 10px 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .alert-danger {
        background-color: #FECACA;
        border: 1px solid #F87171;
        color: #B91C1C;
    }
    .alert-warning {
        background-color: #FEF3C7;
        border: 1px solid #FBBF24;
        color: #92400E;
    }
    .alert-info {
        background-color: #DBEAFE;
        border: 1px solid #60A5FA;
        color: #1E40AF;
    }
    .alert-success {
        background-color: #D1FAE5;
        border: 1px solid #34D399;
        color: #065F46;
    }
    .leverage-high {
        color: #B91C1C;
        font-weight: bold;
    }
    .leverage-medium {
        color: #B45309;
        font-weight: bold;
    }
    .leverage-normal {
        color: #065F46;
        font-weight: bold;
    }
    .data-container {
        background-color: #F3F4F6;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.12);
        text-align: center;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #4B5563;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def load_fred_series(series_id, start_date=None, end_date=None):
    """Load data from FRED for the given series_id."""
    try:
        if not start_date:
            start_date = datetime.datetime.now() - datetime.timedelta(days=365)
        if not end_date:
            end_date = datetime.datetime.now()
            
        data = fred.get_series(series_id, start_date, end_date)
        return data
    except Exception as e:
        st.error(f"Error loading FRED data for {series_id}: {e}")
        return pd.Series()

def calculate_yield_curve_spread(series1, series2):
    """Calculate the spread between two yield series."""
    if series1.empty or series2.empty:
        return pd.Series()
    
    # Reindex to match dates
    df = pd.DataFrame({'Series1': series1, 'Series2': series2})
    df = df.dropna()
    df['Spread'] = df['Series1'] - df['Series2']
    return df['Spread']

def calculate_rolling_volatility(series, window=20):
    """Calculate rolling volatility of a series."""
    if series.empty:
        return pd.Series()
    
    return series.rolling(window=window).std() * np.sqrt(252)  # Annualized

def detect_basis_trade_stress(swap_spreads, threshold=0.10):
    """Detect potential basis trade unwinding events based on sudden spread changes."""
    if swap_spreads.empty or len(swap_spreads) < 2:
        return pd.DataFrame()
    
    daily_changes = swap_spreads.diff().abs()
    stress_events = daily_changes[daily_changes > threshold].dropna()
    
    # Create a DataFrame with the details
    if not stress_events.empty:
        stress_df = pd.DataFrame({
            'Date': stress_events.index,
            'Spread_Change': stress_events.values,
            'Previous_Spread': swap_spreads.shift(1).loc[stress_events.index],
            'Current_Spread': swap_spreads.loc[stress_events.index]
        })
        stress_df['Direction'] = stress_df.apply(
            lambda x: 'Widening' if x['Current_Spread'] > x['Previous_Spread'] else 'Tightening', 
            axis=1
        )
        return stress_df
    return pd.DataFrame()

def calculate_basis_trade_leverage(repo_rate, futures_margin_rate=0.03):
    """
    Estimate the potential leverage in basis trades based on repo rates and futures margin requirements.
    Higher leverage indicates more risk in unwinding events.
    """
    # Cash component: If repo rate is 4%, then leverage is 25x (1/0.04)
    cash_leverage = 1 / repo_rate if repo_rate > 0 else 0
    
    # Futures component: If margin rate is 3%, then leverage is 33.3x (1/0.03)
    futures_leverage = 1 / futures_margin_rate if futures_margin_rate > 0 else 0
    
    # Total effective leverage in the basis trade combines both components
    # This is a simplified model - actual leverage depends on specific implementation
    effective_leverage = (cash_leverage + futures_leverage) / 2
    
    return effective_leverage

def get_leverage_status(leverage):
    """Return the status and color class based on leverage levels."""
    if leverage > 30:
        return "EXTREMELY HIGH", "leverage-high"
    elif leverage > 20:
        return "HIGH", "leverage-high"
    elif leverage > 15:
        return "ELEVATED", "leverage-medium"
    else:
        return "NORMAL", "leverage-normal"

def predict_mortgage_impact(treasury_yield_change):
    """
    Predict the potential impact on mortgage rates based on Treasury yield changes.
    Historically, mortgage rates move with Treasury yields but with a spread.
    """
    # Simplified model: Mortgage rates typically move with 10Y Treasury but with a higher magnitude
    mortgage_change_estimate = treasury_yield_change * 1.2
    
    # Qualitative assessment
    if abs(treasury_yield_change) < 0.05:
        impact = "MINIMAL"
        direction = "STABLE"
    else:
        impact = "SIGNIFICANT" if abs(treasury_yield_change) > 0.15 else "MODERATE"
        direction = "HIGHER" if treasury_yield_change > 0 else "LOWER"
    
    return mortgage_change_estimate, impact, direction

def format_with_arrow(value):
    """Format a value with an up or down arrow."""
    if value > 0:
        return f"↑ {value:.3f}"
    elif value < 0:
        return f"↓ {value:.3f}"
    else:
        return f"{value:.3f}"

# Data loading functions
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_treasury_data():
    """Load key treasury data series from FRED."""
    # Define series IDs for various treasury metrics
    series_ids = {
        'DGS2': '2-Year Treasury Yield',
        'DGS5': '5-Year Treasury Yield',
        'DGS10': '10-Year Treasury Yield',
        'DGS30': '30-Year Treasury Yield',
        'MORTGAGE30US': '30-Year Fixed Rate Mortgage',
        'BAMLH0A0HYM2': 'ICE BofA US High Yield Index',  # Corporate bond yields
        'WSWP10': '10-Year Swap Rate',  # For calculating swap spread
        'WFII10': '10-Year Inflation-Indexed Treasury Yield',  # Real yield
        'T10Y2Y': '10-Year Minus 2-Year Treasury Yield Spread',  # Yield curve
        'DAAA': 'Moody\'s Seasoned Aaa Corporate Bond Yield'  # Credit spreads
    }
    
    # Start date for data fetching (1 year ago)
    start_date = datetime.datetime.now() - datetime.timedelta(days=365)
    
    # Load all series
    data_dict = {}
    for series_id, series_name in series_ids.items():
        data_dict[series_id] = load_fred_series(series_id, start_date)
    
    # Combine into a DataFrame
    df = pd.DataFrame(data_dict)
    df.index.name = 'Date'
    
    # Calculate additional metrics
    if 'DGS10' in df.columns and 'WSWP10' in df.columns:
        df['Swap_Spread'] = df['WSWP10'] - df['DGS10']
    
    if 'DGS10' in df.columns and 'MORTGAGE30US' in df.columns:
        df['Mortgage_Treasury_Spread'] = df['MORTGAGE30US'] - df['DGS10']
    
    if 'DGS10' in df.columns and 'DAAA' in df.columns:
        df['Credit_Spread'] = df['DAAA'] - df['DGS10']
    
    # Calculate volatility for key metrics
    for col in ['DGS10', 'DGS2', 'Swap_Spread', 'Mortgage_Treasury_Spread']:
        if col in df.columns:
            df[f'{col}_Vol'] = calculate_rolling_volatility(df[col])
    
    return df, series_ids

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_repo_rates():
    """Get recent repo rates from FRED."""
    try:
        # DTBCR3M is the 3-month Treasury bill: Secondary market rate
        # This is used as a proxy for repo rates
        repo_data = load_fred_series('DTBCR3M', 
                                  datetime.datetime.now() - datetime.timedelta(days=30))
        return repo_data
    except Exception as e:
        st.error(f"Error loading repo rate data: {e}")
        return pd.Series([0.04])  # Default fallback value

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_futures_data():
    """Get Treasury futures data using Yahoo Finance."""
    try:
        # Treasury futures tickers
        tickers = ["ZB=F", "ZN=F", "ZF=F", "ZT=F"]  # 30Y, 10Y, 5Y, 2Y Treasury futures
        
        # Fetch data for the past 30 days
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=30)
        
        futures_data = {}
        for ticker in tickers:
            data = yf.download(ticker, start=start_date, end=end_date)
            futures_data[ticker] = data['Close']
        
        return pd.DataFrame(futures_data)
    except Exception as e:
        st.error(f"Error loading futures data: {e}")
        return pd.DataFrame()

def calculate_basis_trade_metrics():
    """Calculate key metrics related to the basis trade."""
    # Load data
    treasury_data, _ = load_treasury_data()
    repo_rates = get_repo_rates()
    futures_data = get_futures_data()
    
    # Latest values
    latest_data = {
        '10Y_Treasury': treasury_data['DGS10'].iloc[-1] if 'DGS10' in treasury_data else None,
        '2Y_Treasury': treasury_data['DGS2'].iloc[-1] if 'DGS2' in treasury_data else None,
        'Swap_Spread': treasury_data['Swap_Spread'].iloc[-1] if 'Swap_Spread' in treasury_data else None,
        'Mortgage_Spread': treasury_data['Mortgage_Treasury_Spread'].iloc[-1] if 'Mortgage_Treasury_Spread' in treasury_data else None,
        'Yield_Curve': treasury_data['T10Y2Y'].iloc[-1] if 'T10Y2Y' in treasury_data else None,
        'Repo_Rate': repo_rates.iloc[-1] if not repo_rates.empty else 0.04
    }
    
    # Calculate changes
    if len(treasury_data) > 1:
        latest_data['10Y_Change_1d'] = treasury_data['DGS10'].diff().iloc[-1] if 'DGS10' in treasury_data else 0
        latest_data['10Y_Change_5d'] = treasury_data['DGS10'].diff(5).iloc[-1] if 'DGS10' in treasury_data else 0
        latest_data['Swap_Spread_Change_1d'] = treasury_data['Swap_Spread'].diff().iloc[-1] if 'Swap_Spread' in treasury_data else 0
    else:
        latest_data['10Y_Change_1d'] = 0
        latest_data['10Y_Change_5d'] = 0
        latest_data['Swap_Spread_Change_1d'] = 0
    
    # Detect basis trade stress
    if 'Swap_Spread' in treasury_data:
        swap_spreads = treasury_data['Swap_Spread'].dropna()
        stress_events = detect_basis_trade_stress(swap_spreads)
        latest_data['Recent_Stress_Events'] = stress_events
    else:
        latest_data['Recent_Stress_Events'] = pd.DataFrame()
    
    # Calculate basis trade leverage (using repo rate as proxy)
    if latest_data['Repo_Rate']:
        latest_data['Basis_Trade_Leverage'] = calculate_basis_trade_leverage(latest_data['Repo_Rate'] / 100)
    else:
        latest_data['Basis_Trade_Leverage'] = 0
    
    # Predict mortgage impact
    mortgage_change, impact, direction = predict_mortgage_impact(latest_data['10Y_Change_5d'])
    latest_data['Mortgage_Change_Estimate'] = mortgage_change
    latest_data['Mortgage_Impact'] = impact
    latest_data['Mortgage_Direction'] = direction
    
    return latest_data

# Main app layout
def main():
    st.markdown('<h1 class="main-header">US Treasury Basis Trade Tracker</h1>', unsafe_allow_html=True)
    
    # Load data
    with st.spinner("Loading Treasury data..."):
        treasury_data, series_names = load_treasury_data()
        basis_metrics = calculate_basis_trade_metrics()
    
    # Dashboard layout with 3 columns for key metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown('<p class="metric-label">10-Year Treasury Yield</p>', unsafe_allow_html=True)
        if basis_metrics['10Y_Treasury'] is not None:
            st.markdown(f'<p class="metric-value">{basis_metrics["10Y_Treasury"]:.3f}%</p>', unsafe_allow_html=True)
            st.markdown(f'1d Change: {format_with_arrow(basis_metrics["10Y_Change_1d"])}%', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown('<p class="metric-label">Basis Trade Leverage Estimate</p>', unsafe_allow_html=True)
        leverage = basis_metrics['Basis_Trade_Leverage']
        status, css_class = get_leverage_status(leverage)
        st.markdown(f'<p class="metric-value">{leverage:.1f}x</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="{css_class}">Status: {status}</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown('<p class="metric-label">Mortgage Rate Impact</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="metric-value">{basis_metrics["Mortgage_Direction"]}</p>', unsafe_allow_html=True)
        st.markdown(f'Estimated change: {format_with_arrow(basis_metrics["Mortgage_Change_Estimate"])}%', unsafe_allow_html=True)
        st.markdown(f'Impact: {basis_metrics["Mortgage_Impact"]}', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Alert box for basis trade stress
    if not basis_metrics['Recent_Stress_Events'].empty:
        recent_event = basis_metrics['Recent_Stress_Events'].iloc[0]
        st.markdown(
            f"""
            <div class="alert-box alert-danger">
                <strong>⚠️ Basis Trade Stress Detected!</strong><br>
                Date: {recent_event['Date'].strftime('%Y-%m-%d')}<br>
                Spread Change: {recent_event['Spread_Change']:.3f} ({recent_event['Direction']})<br>
                This indicates potential hedge fund unwinding of Treasury positions.
            </div>
            """, 
            unsafe_allow_html=True
        )
    
    # Yield Curve Status
    if basis_metrics['Yield_Curve'] is not None:
        if basis_metrics['Yield_Curve'] < 0:
            st.markdown(
                f"""
                <div class="alert-box alert-warning">
                    <strong>🔄 Inverted Yield Curve</strong><br>
                    10Y-2Y Spread: {basis_metrics['Yield_Curve']:.3f}%<br>
                    The yield curve inversion may signal economic concern and can affect basis trade positioning.
                </div>
                """, 
                unsafe_allow_html=True
            )
    
    # Tabs for detailed analysis
    tab1, tab2, tab3, tab4 = st.tabs(["Treasury Yields", "Basis Trade Analysis", "Mortgage Impact", "Market Stress"])
    
    with tab1:
        st.markdown('<h2 class="sub-header">Treasury Yield Curves</h2>', unsafe_allow_html=True)
        
        # Plot Treasury yields
        fig = go.Figure()
        
        for col in ['DGS2', 'DGS5', 'DGS10', 'DGS30']:
            if col in treasury_data.columns:
                fig.add_trace(go.Scatter(
                    x=treasury_data.index,
                    y=treasury_data[col],
                    mode='lines',
                    name=series_names.get(col, col)
                ))
        
        fig.update_layout(
            title="US Treasury Yields (Last 12 Months)",
            xaxis_title="Date",
            yaxis_title="Yield (%)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show yield curve inversion
        if 'T10Y2Y' in treasury_data.columns:
            fig_inversion = go.Figure()
            
            fig_inversion.add_trace(go.Scatter(
                x=treasury_data.index,
                y=treasury_data['T10Y2Y'],
                mode='lines',
                name='10Y-2Y Spread',
                line=dict(color='royalblue')
            ))
            
            # Add a horizontal line at y=0
            fig_inversion.add_shape(
                type="line",
                x0=treasury_data.index.min(),
                y0=0,
                x1=treasury_data.index.max(),
                y1=0,
                line=dict(color="red", width=1, dash="dash"),
            )
            
            fig_inversion.update_layout(
                title="10Y-2Y Treasury Spread (Yield Curve Inversion Indicator)",
                xaxis_title="Date",
                yaxis_title="Spread (%)",
                hovermode="x unified",
                height=400
            )
            
            st.plotly_chart(fig_inversion, use_container_width=True)
    
    with tab2:
        st.markdown('<h2 class="sub-header">Basis Trade Analysis</h2>', unsafe_allow_html=True)
        
        # Explain the basis trade
        with st.expander("What is the Treasury Basis Trade?"):
            st.write("""
            The Treasury basis trade is a popular hedge fund strategy that involves:
            
            1. **Going long cash Treasuries**: Buying actual Treasury bonds
            2. **Shorting Treasury futures**: Taking a short position in Treasury futures contracts
            3. **Using leverage**: Financing the cash position through repo markets, often at 10:1 or higher leverage
            
            The trade aims to profit from the small price differentials (the "basis") between cash Treasury prices and futures prices.
            When this spread widens or narrows unexpectedly, it can force highly leveraged funds to unwind positions quickly,
            creating market stress and volatility.
            """)
        
        # Plot swap spread as basis trade indicator
        if 'Swap_Spread' in treasury_data.columns:
            fig_swap = go.Figure()
            
            fig_swap.add_trace(go.Scatter(
                x=treasury_data.index,
                y=treasury_data['Swap_Spread'],
                mode='lines',
                name='10Y Swap Spread',
                line=dict(color='green')
            ))
            
            fig_swap.update_layout(
                title="10-Year Swap Spread (Basis Trade Stress Indicator)",
                xaxis_title="Date",
                yaxis_title="Spread (%)",
                hovermode="x unified",
                height=400
            )
            
            st.plotly_chart(fig_swap, use_container_width=True)
            
            # Show volatility of swap spread
            if 'Swap_Spread_Vol' in treasury_data.columns:
                fig_vol = go.Figure()
                
                fig_vol.add_trace(go.Scatter(
                    x=treasury_data.index,
                    y=treasury_data['Swap_Spread_Vol'],
                    mode='lines',
                    name='Swap Spread Volatility',
                    line=dict(color='orange')
                ))
                
                fig_vol.update_layout(
                    title="Swap Spread Volatility (Annualized)",
                    xaxis_title="Date",
                    yaxis_title="Volatility",
                    hovermode="x unified",
                    height=300
                )
                
                st.plotly_chart(fig_vol, use_container_width=True)
        
        # Show leverage analysis
        st.markdown('<h3>Basis Trade Leverage Analysis</h3>', unsafe_allow_html=True)
        
        repo_rate = basis_metrics['Repo_Rate']
        leverage = basis_metrics['Basis_Trade_Leverage']
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="Current Repo Rate (%)",
                value=f"{repo_rate:.3f}%"
            )
        
        with col2:
            status, _ = get_leverage_status(leverage)
            st.metric(
                label="Estimated Basis Trade Leverage",
                value=f"{leverage:.1f}x",
                delta=f"Status: {status}"
            )
        
        # Show leverage risk chart
        leverage_data = pd.DataFrame({
            'Repo_Rate': np.arange(0.01, 0.1, 0.005),
            'Leverage': [calculate_basis_trade_leverage(r) for r in np.arange(0.01, 0.1, 0.005)]
        })
        
        fig_leverage = px.line(
            leverage_data,
            x='Repo_Rate',
            y='Leverage',
            title="Basis Trade Leverage vs. Repo Rate"
        )
        
        # Add current position
        fig_leverage.add_trace(
            go.Scatter(
                x=[repo_rate/100],
                y=[leverage],
                mode='markers',
                marker=dict(size=12, color='red'),
                name='Current Position'
            )
        )
        
        # Add risk zones
        fig_leverage.add_shape(
            type="rect",
            x0=0.01, y0=30,
            x1=0.1, y1=100,
            fillcolor="red",
            opacity=0.2,
            line_width=0,
            layer="below"
        )
        
        fig_leverage.add_shape(
            type="rect",
            x0=0.01, y0=20,
            x1=0.1, y1=30,
            fillcolor="orange",
            opacity=0.2,
            line_width=0,
            layer="below"
        )
        
        fig_leverage.add_shape(
            type="rect",
            x0=0.01, y0=0,
            x1=0.1, y1=20,
            fillcolor="green",
            opacity=0.2,
            line_width=0,
            layer="below"
        )
        
        fig_leverage.update_layout(
            xaxis_title="Repo Rate",
            yaxis_title="Leverage Multiple",
            height=400
        )
        
        st.plotly_chart(fig_leverage, use_container_width=True)
    
    with tab3:
        st.markdown('<h2 class="sub-header">Mortgage Rate Impact</h2>', unsafe_allow_html=True)
        
        # Plot mortgage rates vs 10Y Treasury
        fig_mortgage = go.Figure()
        
        if 'DGS10' in treasury_data.columns:
            fig_mortgage.add_trace(go.Scatter(
                x=treasury_data.index,
                y=treasury_data['DGS10'],
                mode='lines',
                name='10Y Treasury Yield',
                line=dict(color='blue')
            ))
        
        if 'MORTGAGE30US' in treasury_data.columns:
            fig_mortgage.add_trace(go.Scatter(
                x=treasury_data.index,
                y=treasury_data['MORTGAGE30US'],
                mode='lines',
                name='30Y Fixed Mortgage Rate',
                line=dict(color='red')
            ))
        
        fig_mortgage.update_layout(
            title="30-Year Mortgage Rate vs. 10-Year Treasury Yield",
            xaxis_title="Date",
            yaxis_title="Rate (%)",
            hovermode="x unified",
            height=500
        )
        
        st.plotly_chart(fig_mortgage, use_container_width=True)
        
        # Plot mortgage-treasury spread
        if 'Mortgage_Treasury_Spread' in treasury_data.columns:
            fig_spread = go.Figure()
            
            fig_spread.add_trace(go.Scatter(
                x=treasury_data.index,
                y=treasury_data['Mortgage_Treasury_Spread'],
                mode='lines',
                name='Mortgage-Treasury Spread',
                line=dict(color='purple')
            ))
            
            fig_spread.update_layout(
                title="Mortgage-Treasury Spread (Indicators of Mortgage Market Stress)",
                xaxis_title="Date",
                yaxis_title="Spread (%)",
                hovermode="x unified",
                height=400
            )
            
            st.plotly_chart(fig_spread, use_container_width=True)
        
        # Mortgage impact analysis
        st.markdown('<h3>Mortgage Rate Impact Analysis</h3>', unsafe_allow_html=True)
        
        mortgage_change = basis_metrics['Mortgage_Change_Estimate']
        impact = basis_metrics['Mortgage_Impact']
        direction = basis_metrics['Mortgage_Direction']
        
        # Create alert box based on impact
        alert_class = "alert-info"
        if impact == "SIGNIFICANT" and direction == "HIGHER":
            alert_class = "alert-danger"
        elif impact == "SIGNIFICANT" and direction == "LOWER":
            alert_class = "alert-success"
        elif impact == "MODERATE" and direction == "HIGHER":
            alert_class = "alert-warning"
        
        st.markdown(
            f"""
            <div class="alert-box {alert_class}">
                <strong>Mortgage Rate Forecast:</strong><br>
                Based on recent Treasury yield changes, mortgage rates are likely to move <strong>{direction}</strong>.<br>
                Estimated change: {format_with_arrow(mortgage_change)}%<br>
                Impact level: {impact}
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # Show the relationship between Treasury yields and mortgage rates
        with st.expander("How do Treasury yields affect mortgage rates?"):
            st.write("""
            Mortgage rates are closely tied to the 10-year Treasury yield, but with a spread:
            
            1. **Direct relationship**: When 10-year Treasury yields rise, mortgage rates typically follow
            2. **Spread variation**: The difference between mortgage rates and Treasury yields (the spread) can vary based on:
               - Credit conditions
               - Liquidity in the mortgage-backe
