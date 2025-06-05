import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import warnings
import requests

# Suppress pandas warnings
warnings.filterwarnings('ignore')

# Initialize the Dash app with better theme
external_stylesheets = [dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME]
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
app.title = 'Crypto Dashboard'

# Define the tickers for the cryptocurrencies
TICKERS = {
    'BTC-USD': 'Bitcoin',
    'ETH-USD': 'Ethereum',
    'BNB-USD': 'BNB',
    'SOL-USD': 'Solana',
    'XRP-USD': 'XRP',
    'DOGE-USD': 'Dogecoin',
    'ADA-USD': 'Cardano',
    'DOT-USD': 'Polkadot',
    'AVAX-USD': 'Avalanche',
    'LINK-USD': 'Chainlink'
}

# Period mapping for yfinance
PERIOD_MAP = {
    '24h': '1d',
    '1w': '7d',
    '1m': '1mo', 
    '6m': '6mo',
    '1y': '1y',
    '3y': '3y',
    'max': 'max'
}

def safe_float_extract(value):
    """Safely extract float value from pandas Series/scalar"""
    try:
        if hasattr(value, 'iloc'):
            value = value.iloc[0] if len(value) > 0 else 0
        if hasattr(value, 'item'):
            return float(value.item())
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return 0.0

def get_historical_data(symbol, period, max_retries=2):
    """Fetch historical data with retry logic"""
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            # Use 5-minute intervals for 24-hour data
            if period == '1d':
                df = ticker.history(period=period, interval='5m')
            else:
                df = ticker.history(period=period)
            if not df.empty and 'Close' in df.columns:
                return df
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {symbol}: {e}")
            if attempt < max_retries - 1:
                time.sleep(0.5)
    
    print(f"Failed to fetch data for {symbol} after {max_retries} attempts")
    return pd.DataFrame()

def get_current_price(symbol):
    """Get current price using Alpha Vantage API with yfinance fallback"""
    # Alpha Vantage API key
    api_key = 'YOUR_ALPHA_VANTAGE_API_KEY'
    
    # Extract crypto symbol (remove -USD suffix)
    crypto_symbol = symbol.replace('-USD', '')
    
    # Try Alpha Vantage first
    try:
        url = f'https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={crypto_symbol}&to_currency=USD&apikey={api_key}'
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'Realtime Currency Exchange Rate' in data:
            price = float(data['Realtime Currency Exchange Rate']['5. Exchange Rate'])
            timestamp = data['Realtime Currency Exchange Rate']['6. Last Refreshed']
            return price, f"Alpha Vantage - {timestamp}"
            
    except Exception as e:
        print(f"Alpha Vantage error for {symbol}: {e}")
    
    # Fallback to yfinance
    try:
        ticker = yf.Ticker(symbol)
        
        # Try to get current price from info
        info = ticker.info
        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
        
        if current_price:
            return float(current_price), f"yFinance - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Final fallback to recent historical data
        df = ticker.history(period="1d", interval="5m")
        if not df.empty and 'Close' in df.columns:
            price = safe_float_extract(df['Close'].dropna().iloc[-1:])
            timestamp = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
            return price, f"yFinance Historical - {timestamp}"
            
    except Exception as e:
        print(f"yFinance fallback error for {symbol}: {e}")
    
    return None, "Data unavailable"

def create_price_chart(df, period, crypto_name):
    """Create minimalist plotly chart for price data"""
    if df.empty or 'Close' not in df.columns:
        return go.Figure(), 0.0, 'gray'
    
    close_prices = df['Close'].dropna()
    if close_prices.empty:
        return go.Figure(), 0.0, 'gray'
    
    # Calculate price change
    first_price = safe_float_extract(close_prices.iloc[:1])
    last_price = safe_float_extract(close_prices.iloc[-1:])
    
    if first_price == 0:
        percent_change = 0.0
        color = '#6c757d'
    else:
        percent_change = ((last_price - first_price) / first_price) * 100
        color = '#2563eb' if percent_change >= 0 else '#ef4444'
    
    # Calculate Y-axis range for better visualization
    min_price = close_prices.min()
    max_price = close_prices.max()
    price_range = max_price - min_price
    
    # Add padding to Y-axis (5% on each side)
    padding = price_range * 0.05 if price_range > 0 else max_price * 0.05
    y_min = max(0, min_price - padding)
    y_max = max_price + padding
    
    # Create minimal chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df.index,
        y=close_prices,
        mode='lines',
        name='Price',
        line=dict(color=color, width=2),
        hovertemplate='<b>%{x}</b><br>Price: <b>$%{y:,.2f}</b><extra></extra>'
    ))
    
    fig.update_layout(
        title={
            'text': f'{crypto_name} • {period.upper()} ({percent_change:+.2f}%)',
            'x': 0.02,
            'xanchor': 'left',
            'font': {'size': 16, 'color': '#1f2937', 'family': 'Inter, sans-serif'}
        },
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=400,
        font={'family': 'Inter, sans-serif', 'color': '#6b7280'},
        xaxis=dict(
            showgrid=False,
            showline=False,
            showticklabels=True,
            tickfont={'size': 11, 'color': '#9ca3af'}
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f3f4f6',
            gridwidth=1,
            showline=False,
            tickformat='$,.0f',
            tickfont={'size': 11, 'color': '#9ca3af'},
            range=[y_min, y_max]
        ),
        margin=dict(l=60, r=20, t=60, b=40),
        hovermode='x unified',
        showlegend=False
    )
    
    return fig, percent_change, color

# Consolidated styling
STYLES = {
    'header': {
        'background': 'white', 'color': '#1f2937', 'padding': '3rem 0 2rem 0',
        'margin-bottom': '2rem', 'border-bottom': '1px solid #e5e7eb'
    },
    'card': {
        'border-radius': '8px', 'border': '1px solid #e5e7eb',
        'background': 'white', 'padding': '0'
    },
    'price_card': {
        'background': '#1f2937', 'color': 'white',
        'border-radius': '8px', 'border': 'none'
    },
    'button_inactive': {
        'background': 'white', 'border': '1px solid #e5e7eb',
        'color': '#6b7280', 'font-weight': '400'
    },
    'button_active': {
        'background': '#1f2937', 'border': '1px solid #1f2937',
        'color': 'white', 'font-weight': '500'
    },
    'metric_label': {'color': '#6b7280', 'font-size': '12px', 'margin-bottom': '2px'},
    'metric_value': {'color': '#1f2937', 'font-weight': '500'},
    'metric_na': {'color': '#9ca3af'}
}

# Minimal UI Components
def create_header():
    return html.Div([
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H1("Crypto Dashboard", 
                               className="h2 fw-normal mb-2",
                               style={'color': '#1f2937', 'font-weight': '400'}),
                        html.P("Real-time cryptocurrency data",
                               className="text-muted mb-0",
                               style={'font-size': '16px'})
                    ], className="text-center")
                ])
            ])
        ])
    ], style=STYLES['header'])

def create_price_card():
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.H6(id="crypto-name", className="text-center mb-2",
                       style={'color': 'rgba(255,255,255,0.8)', 'font-weight': '400'}),
                html.H2(id="current-price", className="text-center mb-2", 
                        style={'font-size': '2rem', 'font-weight': '600', 'color': 'white'}),
                html.P(id="last-updated", className="text-center mb-0", 
                       style={'color': 'rgba(255,255,255,0.6)', 'font-size': '12px'})
            ], style={'padding': '1rem'})
        ], style={'padding': '0'})
    ], style=STYLES['price_card'], className="mb-4")

def create_metrics_card():
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([
                    html.H6("Metrics", className="mb-3", 
                           style={'color': '#1f2937', 'font-weight': '500'}),
                    dbc.Button("?", id="info-btn", size="sm", 
                              style={'background': '#f3f4f6', 'border': 'none', 'color': '#6b7280',
                                    'border-radius': '50%', 'width': '24px', 'height': '24px',
                                    'font-size': '12px'})
                ], className="d-flex justify-content-between align-items-center mb-3"),
                html.Div(id="metrics-content")
            ], style={'padding': '1.5rem'})
        ], style={'padding': '0'})
    ], style=STYLES['card'], className="mb-4")

def create_button_group():
    """Create time period button group"""
    buttons = []
    for period in PERIOD_MAP.keys():
        buttons.append(
            dbc.Button(
                period.upper(), 
                id=f"btn-{period}", 
                size="sm",
                style=STYLES['button_inactive']
            )
        )
    return dbc.ButtonGroup(buttons, className="d-flex justify-content-center mb-4")

def create_metric_item(label, value, is_last=False):
    """Helper function to create consistent metric items"""
    className = "mb-0" if is_last else "mb-3"
    value_style = STYLES['metric_value'] if value != "N/A" else STYLES['metric_na']
    
    return html.Div([
        html.Div(label, style=STYLES['metric_label']),
        html.Div(value, style=value_style)
    ], className=className)

def create_chart_card():
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Div([create_button_group()]),
                dcc.Graph(id='price-chart'),
                html.Div([
                    html.Div(id='price-indicator', className="text-center mt-2")
                ])
            ], style={'padding': '1.5rem'})
        ], style={'padding': '0'})
    ], style=STYLES['card'])

def create_crypto_selector():
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Label("Select Cryptocurrency", 
                          className="form-label mb-2",
                          style={'color': '#374151', 'font-weight': '500', 'font-size': '14px'}),
                dcc.Dropdown(
                    id='crypto-selector',
                    options=[{'label': f"{name}", 'value': symbol} 
                           for symbol, name in TICKERS.items()],
                    value='BTC-USD',
                    clearable=False,
                    style={'border': '1px solid #e5e7eb', 'border-radius': '6px'}
                )
            ], style={'padding': '1.5rem'})
        ], style={'padding': '0'})
    ], style=STYLES['card'], className="mb-4")

# Minimal modal
info_modal = dbc.Modal([
    dbc.ModalHeader("About Metrics", style={'border': 'none', 'padding': '1.5rem 1.5rem 0 1.5rem'}),
    dbc.ModalBody([
        html.Div([
            html.P([html.Strong("Day Range"), " — High and low prices in 24 hours"], 
                   className="mb-2", style={'font-size': '14px'}),
            html.P([html.Strong("52W Range"), " — High and low prices in past year"], 
                   className="mb-2", style={'font-size': '14px'}),
            html.P([html.Strong("Volume"), " — Trading volume in 24 hours"], 
                   className="mb-0", style={'font-size': '14px'})
        ])
    ], style={'padding': '0 1.5rem'}),
    dbc.ModalFooter([
        dbc.Button("Close", id="close-info", 
                  style={'background': '#1f2937', 'border': 'none', 'font-weight': '400'})
    ], style={'border': 'none', 'padding': '1rem 1.5rem 1.5rem 1.5rem'})
], id="info-modal", is_open=False, centered=True)

# Minimal main layout
app.layout = html.Div([
    create_header(),
    dbc.Container([
        dbc.Row([
            dbc.Col([create_crypto_selector()], width=12, lg=4, className="mx-auto")
        ], className="mb-4"),
        dcc.Store(id='selected-period', data='24h'),
        dbc.Row([
            dbc.Col([
                create_price_card(), create_metrics_card(), info_modal
            ], width=12, lg=4),
            dbc.Col([create_chart_card()], width=12, lg=8)
        ])
    ], fluid=True, style={'max-width': '1200px'})
], style={'background-color': '#fafafa', 'min-height': '100vh', 'font-family': 'Inter, sans-serif'})

# Callbacks
@app.callback(
    [Output('crypto-name', 'children'),
     Output('current-price', 'children'),
     Output('last-updated', 'children')],
    [Input('crypto-selector', 'value')]
)
def update_current_price(selected_crypto):
    if not selected_crypto:
        return "Select Crypto", "N/A", ""
    
    crypto_name = TICKERS.get(selected_crypto, "Unknown")
    price, timestamp = get_current_price(selected_crypto)
    
    if price is None:
        return crypto_name, "Price Unavailable", timestamp
    
    return crypto_name, f"${price:,.2f}", f"Updated: {timestamp}"

@app.callback(
    [Output('price-chart', 'figure'), Output('price-indicator', 'children'), Output('selected-period', 'data')] +
    [Output(f'btn-{period}', 'style') for period in PERIOD_MAP.keys()],
    [Input('crypto-selector', 'value')] + [Input(f'btn-{period}', 'n_clicks') for period in PERIOD_MAP.keys()],
    [State('selected-period', 'data')]
)
def update_chart(selected_crypto, *args):
    current_period = args[-1] or '24h'
    
    ctx = callback_context
    if ctx.triggered and ctx.triggered[0]['prop_id'] != 'crypto-selector.value':
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        if button_id.startswith('btn-'):
            current_period = button_id.replace('btn-', '')
    
    # Generate button styles efficiently
    button_styles = [
        STYLES['button_active'] if period == current_period else STYLES['button_inactive']
        for period in PERIOD_MAP.keys()
    ]
    
    if not selected_crypto:
        return go.Figure(), "", current_period, *button_styles
    
    yf_period = PERIOD_MAP[current_period]
    df = get_historical_data(selected_crypto, yf_period)
    crypto_name = TICKERS.get(selected_crypto, "Unknown")
    
    fig, percent_change, color = create_price_chart(df, current_period, crypto_name)
    indicator_text = f"{percent_change:+.2f}%"
    indicator_style = {"color": color, "font-weight": "500", "font-size": "14px"}
    
    return fig, html.Span(indicator_text, style=indicator_style), current_period, *button_styles

@app.callback(
    Output('metrics-content', 'children'),
    [Input('crypto-selector', 'value')]
)
def update_metrics(selected_crypto):
    if not selected_crypto:
        return html.P("Select a cryptocurrency", className="text-muted", style={'font-size': '14px'})
    
    try:
        df_1d = get_historical_data(selected_crypto, '1d')
        df_1y = get_historical_data(selected_crypto, '1y')
        
        # Day Range
        if not df_1d.empty and 'High' in df_1d.columns and 'Low' in df_1d.columns:
            day_high = safe_float_extract(df_1d['High'].max())
            day_low = safe_float_extract(df_1d['Low'].min())
            day_range = f"${day_low:,.2f} - ${day_high:,.2f}"
        else:
            day_range = "N/A"
        
        # 52W Range
        if not df_1y.empty and 'High' in df_1y.columns and 'Low' in df_1y.columns:
            year_high = safe_float_extract(df_1y['High'].max())
            year_low = safe_float_extract(df_1y['Low'].min())
            year_range = f"${year_low:,.2f} - ${year_high:,.2f}"
        else:
            year_range = "N/A"
        
        # Volume
        if not df_1d.empty and 'Volume' in df_1d.columns:
            volume = f"{safe_float_extract(df_1d['Volume'].sum()):,.0f}"
        else:
            volume = "N/A"
        
        return [
            create_metric_item("Day Range", day_range),
            create_metric_item("52W Range", year_range),
            create_metric_item("Volume (24h)", volume, is_last=True)
        ]
        
    except Exception as e:
        print(f"Error updating metrics: {e}")
        return [html.Div("Error loading metrics", style={'color': '#ef4444', 'font-size': '14px'})]

@app.callback(
    Output("info-modal", "is_open"),
    [Input("info-btn", "n_clicks"), Input("close-info", "n_clicks")],
    [State("info-modal", "is_open")]
)
def toggle_info_modal(open_clicks, close_clicks, is_open):
    if open_clicks or close_clicks:
        return not is_open
    return is_open

# Run the application
if __name__ == '__main__':
    app.run(debug=True, port=8063)
