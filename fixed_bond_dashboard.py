import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import requests
import json
import time
from fredapi import Fred
import warnings
warnings.filterwarnings('ignore')

# Page configuration for mobile-friendly display
st.set_page_config(
    page_title="Bond Arbitrage Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark theme CSS
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: white;
    }
    
    .main-header {
        font-size: 2.5rem;
        color: #00D4AA;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    
    .section-header {
        font-size: 1.5rem;
        color: #FAFAFA;
        margin: 1rem 0;
        padding: 0.5rem;
        background: linear-gradient(90deg, #1f2937, #374151);
        border-radius: 8px;
        border-left: 4px solid #00D4AA;
    }
    
    .metric-container {
        background: #1f2937;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #374151;
        margin: 0.5rem 0;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #00D4AA;
    }
    
    .metric-change-positive {
        color: #10B981;
        font-size: 0.9rem;
    }
    
    .metric-change-negative {
        color: #EF4444;
        font-size: 0.9rem;
    }
    
    .alert-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        font-weight: bold;
    }
    
    .alert-high {
        background-color: #DC2626;
        border: 1px solid #EF4444;
    }
    
    .alert-medium {
        background-color: #D97706;
        border: 1px solid #F59E0B;
    }
    
    .alert-low {
        background-color: #059669;
        border: 1px solid #10B981;
    }
    
    .stSelectbox > div > div {
        background-color: #1f2937;
        color: white;
    }
    
    .stButton > button {
        background-color: #00D4AA;
        color: #0E1117;
        border: none;
        font-weight: bold;
    }
    
    /* Mobile responsiveness */
    @media (max-width: 768px) {
        .main-header {
            font-size: 2rem;
        }
        .section-header {
            font-size: 1.2rem;
        }
        .metric-value {
            font-size: 1.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for data caching
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'cached_data' not in st.session_state:
    st.session_state.cached_data = {}

class BondArbitrageMonitor:
    def __init__(self):
        self.fred_api_key = "YOUR_FRED_API_KEY"  # Replace with actual API key
        # For demo purposes, we'll simulate data
        
    def simulate_treasury_data(self):
        """Simulate treasury market data for demo"""
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        
        # Primary-Secondary spread simulation
        primary_secondary_spread = np.random.normal(3.5, 1.2, 30)
        primary_secondary_spread = np.maximum(primary_secondary_spread, 0.5)
        
        # WI spreads simulation
        wi_spread = np.random.normal(2.8, 0.8, 30)
        wi_spread = np.maximum(wi_spread, 0.2)
        
        # Basis data simulation
        basis_spread = np.random.normal(0.15, 0.05, 30)
        
        # Repo rates simulation
        repo_rates = np.random.normal(5.2, 0.1, 30)
        
        return pd.DataFrame({
            'date': dates,
            'primary_secondary_spread': primary_secondary_spread,
            'wi_spread': wi_spread,
            'basis_spread': basis_spread,
            'repo_rate': repo_rates,
            '2s10s_spread': np.random.normal(85, 15, 30),
            '5s30s_spread': np.random.normal(45, 10, 30)
        })
    
    def get_market_data(self):
        """Get real market data from various sources"""
        try:
            # Get Treasury ETF data as proxy
            tlt = yf.download('TLT', period='30d', interval='1d')
            ief = yf.download('IEF', period='30d', interval='1d')
            shy = yf.download('SHY', period='30d', interval='1d')
            
            # Calculate yields (inverse relationship with bond prices)
            tlt_yield_change = -tlt['Close'].pct_change() * 100
            ief_yield_change = -ief['Close'].pct_change() * 100
            
            # VIX data
            vix = yf.download('^VIX', period='30d', interval='1d')
            
            # Ensure we get scalar values by using .iloc[-1] and converting to float
            return {
                'tlt_yield_change': float(tlt_yield_change.iloc[-1]) if len(tlt_yield_change) > 0 else 0.0,
                'ief_yield_change': float(ief_yield_change.iloc[-1]) if len(ief_yield_change) > 0 else 0.0,
                'vix': float(vix['Close'].iloc[-1]) if len(vix) > 0 else 18.5,
                'vix_change': float(vix['Close'].pct_change().iloc[-1]) if len(vix) > 0 else 0.02
            }
        except Exception as e:
            # Return default values if there's any error
            st.warning(f"Could not fetch real market data, using simulated data. Error: {str(e)}")
            return {
                'tlt_yield_change': np.random.normal(0, 0.5),
                'ief_yield_change': np.random.normal(0, 0.3),
                'vix': 18.5,
                'vix_change': 0.02
            }
    
    def calculate_z_score(self, current_value, historical_data, window=20):
        """Calculate Z-score for spread analysis"""
        historical_mean = historical_data.rolling(window).mean().iloc[-1]
        historical_std = historical_data.rolling(window).std().iloc[-1]
        if historical_std == 0:
            return 0, historical_mean, historical_std
        z_score = (current_value - historical_mean) / historical_std
        return z_score, historical_mean, historical_std

def create_gauge_chart(value, title, min_val=0, max_val=100, threshold_low=30, threshold_high=70):
    """Create a gauge chart for key metrics"""
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = value,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'color': 'white', 'size': 16}},
        delta = {'reference': (threshold_low + threshold_high) / 2},
        gauge = {
            'axis': {'range': [None, max_val], 'tickcolor': 'white'},
            'bar': {'color': "#00D4AA"},
            'steps': [
                {'range': [min_val, threshold_low], 'color': "#059669"},
                {'range': [threshold_low, threshold_high], 'color': "#D97706"},
                {'range': [threshold_high, max_val], 'color': "#DC2626"}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "white", 'family': "Arial"},
        height=250
    )
    
    return fig

def create_trend_chart(df, y_col, title, color="#00D4AA"):
    """Create trend line chart"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df[y_col],
        mode='lines+markers',
        name=title,
        line=dict(color=color, width=3),
        marker=dict(size=6, color=color)
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(color='white', size=16)),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        xaxis=dict(gridcolor='#374151', showgrid=True),
        yaxis=dict(gridcolor='#374151', showgrid=True),
        height=300,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    return fig

def display_metric_card(title, current_value, previous_value, unit="bps", is_percentage=False):
    """Display metric card with trend"""
    change = current_value - previous_value
    change_pct = (change / previous_value * 100) if previous_value != 0 else 0
    
    change_color = "metric-change-positive" if change >= 0 else "metric-change-negative"
    change_symbol = "▲" if change >= 0 else "▼"
    
    if is_percentage:
        value_display = f"{current_value:.2f}%"
        change_display = f"{change:+.2f}%"
    else:
        value_display = f"{current_value:.1f}{unit}"
        change_display = f"{change:+.1f}{unit}"
    
    st.markdown(f"""
    <div class="metric-container">
        <div style="font-size: 0.9rem; margin-bottom: 0.5rem;">{title}</div>
        <div class="metric-value">{value_display}</div>
        <div class="{change_color}">
            {change_symbol} {change_display} ({change_pct:+.1f}%)
        </div>
    </div>
    """, unsafe_allow_html=True)

# Main Dashboard
def main():
    st.markdown('<div class="main-header">🏦 Bond Arbitrage Monitor</div>', unsafe_allow_html=True)
    
    # Strategy Guide Link
    st.markdown("""
    <div style='text-align: center; margin-bottom: 1rem;'>
        <a href="https://claude.ai/public/artifacts/15bdbb30-e563-4f7b-b2fe-3e3eb00d9c13" 
           target="_blank" 
           style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                  color: white; 
                  padding: 8px 16px; 
                  border-radius: 20px; 
                  text-decoration: none; 
                  font-weight: bold;
                  font-size: 0.9rem;
                  box-shadow: 0 4px 15px rgba(0,0,0,0.2);'>
            📚 Bond Arbitrage Strategy Guide
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    # Auto-refresh mechanism
    placeholder = st.empty()
    
    # Refresh button and auto-refresh toggle
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button("🔄 Refresh Data", key="refresh"):
            st.session_state.cached_data = {}
            st.rerun()
    
    with col2:
        auto_refresh = st.checkbox("Auto Refresh (30s)", value=True)
    
    with col3:
        st.write(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")
    
    # Initialize data monitor
    monitor = BondArbitrageMonitor()
    
    # Get data
    treasury_data = monitor.simulate_treasury_data()
    market_data = monitor.get_market_data()
    
    current_data = treasury_data.iloc[-1]
    previous_data = treasury_data.iloc[-2]
    
    # Alert System
    st.markdown('<div class="section-header">🚨 Trading Alerts</div>', unsafe_allow_html=True)
    
    alerts = []
    
    # Calculate Z-scores for alerts
    ps_zscore, _, _ = monitor.calculate_z_score(current_data['primary_secondary_spread'], 
                                              treasury_data['primary_secondary_spread'])
    wi_zscore, _, _ = monitor.calculate_z_score(current_data['wi_spread'], 
                                              treasury_data['wi_spread'])
    
    if abs(ps_zscore) > 1.5:
        alert_type = "alert-high" if abs(ps_zscore) > 2.0 else "alert-medium"
        direction = "SHORT SPREAD" if ps_zscore > 0 else "LONG SPREAD"
        alerts.append((f"🔥 PRIMARY-SECONDARY: {direction} | Z-score: {ps_zscore:.2f}", alert_type))
    
    if abs(wi_zscore) > 1.2:
        alert_type = "alert-high" if abs(wi_zscore) > 1.8 else "alert-medium"
        direction = "SELL WI" if wi_zscore > 0 else "BUY WI"
        alerts.append((f"⚡ WI ARBITRAGE: {direction} | Z-score: {wi_zscore:.2f}", alert_type))
    
    # Fixed: Use scalar comparison instead of Series comparison
    if market_data['vix'] > 25:
        alerts.append((f"⚠️ HIGH VOLATILITY: VIX {market_data['vix']:.1f} | Reduce Position Size", "alert-medium"))
    
    if not alerts:
        alerts.append(("✅ No High Priority Alerts", "alert-low"))
    
    for alert_text, alert_class in alerts:
        st.markdown(f'<div class="{alert_class} alert-box">{alert_text}</div>', unsafe_allow_html=True)
    
    # Key Metrics Overview
    st.markdown('<div class="section-header">📊 Key Metrics Overview</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        display_metric_card("Primary-Secondary Spread", 
                          current_data['primary_secondary_spread'],
                          previous_data['primary_secondary_spread'])
    
    with col2:
        display_metric_card("WI Spread", 
                          current_data['wi_spread'],
                          previous_data['wi_spread'])
    
    with col3:
        display_metric_card("Cash-Futures Basis", 
                          current_data['basis_spread'] * 100,
                          previous_data['basis_spread'] * 100)
    
    with col4:
        display_metric_card("Repo Rate", 
                          current_data['repo_rate'],
                          previous_data['repo_rate'], 
                          unit="%", 
                          is_percentage=True)
    
    # Z-Score Analysis
    st.markdown('<div class="section-header">📈 Z-Score Analysis (20-Day Window)</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        ps_gauge = create_gauge_chart(
            abs(ps_zscore),
            "Primary-Secondary Z-Score",
            min_val=0,
            max_val=3,
            threshold_low=1.0,
            threshold_high=2.0
        )
        st.plotly_chart(ps_gauge, use_container_width=True)
    
    with col2:
        wi_gauge = create_gauge_chart(
            abs(wi_zscore),
            "WI Spread Z-Score", 
            min_val=0,
            max_val=3,
            threshold_low=0.8,
            threshold_high=1.5
        )
        st.plotly_chart(wi_gauge, use_container_width=True)
    
    # Trend Charts
    st.markdown('<div class="section-header">📉 Historical Trends (30 Days)</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        ps_chart = create_trend_chart(treasury_data, 'primary_secondary_spread', 
                                    'Primary-Secondary Spread (bps)', '#00D4AA')
        st.plotly_chart(ps_chart, use_container_width=True)
        
        basis_chart = create_trend_chart(treasury_data, 'basis_spread', 
                                       'Cash-Futures Basis (%)', '#F59E0B')
        st.plotly_chart(basis_chart, use_container_width=True)
    
    with col2:
        wi_chart = create_trend_chart(treasury_data, 'wi_spread', 
                                    'WI Spread (bps)', '#EF4444')
        st.plotly_chart(wi_chart, use_container_width=True)
        
        curve_chart = create_trend_chart(treasury_data, '2s10s_spread', 
                                       '2s10s Curve (bps)', '#8B5CF6')
        st.plotly_chart(curve_chart, use_container_width=True)
    
    # Market Environment
    st.markdown('<div class="section-header">🌐 Market Environment</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="VIX Level",
            value=f"{market_data['vix']:.1f}",
            delta=f"{market_data['vix_change']:+.1%}"
        )
    
    with col2:
        volatility_regime = "HIGH" if market_data['vix'] > 25 else "NORMAL" if market_data['vix'] > 15 else "LOW"
        st.metric(
            label="Volatility Regime",
            value=volatility_regime
        )
    
    with col3:
        risk_appetite = "RISK-OFF" if market_data['vix'] > 25 else "NEUTRAL" if market_data['vix'] > 20 else "RISK-ON"
        st.metric(
            label="Risk Sentiment",
            value=risk_appetite
        )
    
    # Trading Opportunities
    st.markdown('<div class="section-header">💡 Active Opportunities</div>', unsafe_allow_html=True)
    
    opportunities = []
    
    if abs(ps_zscore) > 1.5:
        direction = "Short Primary-Secondary Spread" if ps_zscore > 0 else "Long Primary-Secondary Spread"
        target_profit = f"{abs(ps_zscore * 1.5):.1f}bps"
        opportunities.append([direction, f"Z-score: {ps_zscore:.2f}", target_profit, "High"])
    
    if abs(wi_zscore) > 1.2:
        direction = "Sell WI, Buy Secondary" if wi_zscore > 0 else "Buy WI, Sell Secondary"
        target_profit = f"{abs(wi_zscore * 1.2):.1f}bps"
        opportunities.append([direction, f"Z-score: {wi_zscore:.2f}", target_profit, "Medium"])
    
    basis_opportunity = abs(current_data['basis_spread'] - 0.15)
    if basis_opportunity > 0.05:
        direction = "Long Basis Trade" if current_data['basis_spread'] < 0.15 else "Short Basis Trade"
        target_profit = f"{basis_opportunity * 100:.1f}bps"
        opportunities.append([direction, f"Deviation: {basis_opportunity:.3f}", target_profit, "Medium"])
    
    if opportunities:
        opportunity_df = pd.DataFrame(opportunities, 
                                    columns=['Strategy', 'Signal Strength', 'Target Profit', 'Priority'])
        st.dataframe(opportunity_df, use_container_width=True)
    else:
        st.info("📊 No high-probability opportunities detected at current market levels.")
    
    # Performance Tracking
    st.markdown('<div class="section-header">📋 Today\'s Performance Summary</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Spread Volatility", f"{treasury_data['primary_secondary_spread'].std():.1f}bps")
    
    with col2:
        st.metric("Market Efficiency", f"{100 - abs(ps_zscore) * 20:.0f}%")
    
    with col3:
        correlation = np.corrcoef(treasury_data['primary_secondary_spread'], 
                                treasury_data['wi_spread'])[0,1]
        st.metric("Cross-Strategy Correlation", f"{correlation:.2f}")
    
    # Footer with mobile optimization note
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #6B7280; font-size: 0.8rem;'>
        📱 Optimized for mobile viewing | 🔄 Auto-refreshes every 30 seconds<br>
        💡 Swipe left/right to navigate on mobile devices
    </div>
    """, unsafe_allow_html=True)
    
    # Auto refresh functionality
    if auto_refresh:
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
