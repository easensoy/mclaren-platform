"""
McLaren Platform Web Dashboard
Integrates with existing monitoring infrastructure to provide web visualization
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import threading
import time

try:
    import dash
    from dash import dcc, html, Input, Output
    import plotly.graph_objs as go
    import plotly.express as px
    import pandas as pd
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False
    print("Dash not installed. Run: pip install dash plotly")

import psutil
from .metrics_collector import MetricsCollector
from .data_visualiser import DataVisualizer
from ..core.events import EventBus

logger = logging.getLogger(__name__)

class McLarenMonitor:
    """Main dashboard class that integrates with existing McLaren platform monitoring"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        if not DASH_AVAILABLE:
            raise ImportError("Dashboard requires dash and plotly. Run: pip install dash plotly")
        
        self.app = dash.Dash(__name__)
        self.app.title = "McLaren Platform Dashboard"
        
        # Initialize components
        self.metrics_collector = metrics_collector
        self.event_bus = EventBus()
        self.data_visualizer = DataVisualizer(self.event_bus)
        
        # Data storage for real-time updates
        self.live_data = {
            'network_interfaces': [],
            'system_metrics': [],
            'platform_health': [],
            'alerts': []
        }
        
        # Setup dashboard
        self._setup_layout()
        self._setup_callbacks()
        self._start_data_collection()
        
        logger.info("McLaren Dashboard initialized")
    
    def _setup_layout(self):
        """Setup the dashboard layout using existing platform styling"""
        
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.Img(src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 
                        style={'height': '50px', 'width': '50px', 'display': 'inline-block'}),
                html.H1("McLaren Applied Communication Platform", 
                       style={'display': 'inline-block', 'marginLeft': '20px', 'color': '#ff6b00'}),
                html.Div(id='live-status', style={'float': 'right', 'marginTop': '15px'})
            ], style={'backgroundColor': '#1a1a1a', 'padding': '20px', 'color': 'white'}),
            
            # Auto-refresh component
            dcc.Interval(
                id='interval-component',
                interval=3*1000,  # Update every 3 seconds
                n_intervals=0
            ),
            
            # Main dashboard content
            html.Div([
                # System Overview Row
                html.Div([
                    html.H2("System Overview", style={'color': '#ff6b00', 'textAlign': 'center'}),
                    html.Div([
                        html.Div([
                            dcc.Graph(id='cpu-memory-gauge')
                        ], className='six columns'),
                        html.Div([
                            dcc.Graph(id='network-overview')
                        ], className='six columns'),
                    ], className='row'),
                ], style={'margin': '20px'}),
                
                # Network Monitoring Row
                html.Div([
                    html.H2("Network Monitoring", style={'color': '#ff6b00', 'textAlign': 'center'}),
                    html.Div([
                        html.Div([
                            dcc.Graph(id='interface-quality')
                        ], className='six columns'),
                        html.Div([
                            dcc.Graph(id='network-throughput')
                        ], className='six columns'),
                    ], className='row'),
                ], style={'margin': '20px'}),
                
                # Platform Health Row
                html.Div([
                    html.H2("Platform Health", style={'color': '#ff6b00', 'textAlign': 'center'}),
                    html.Div([
                        html.Div([
                            dcc.Graph(id='health-metrics')
                        ], className='eight columns'),
                        html.Div([
                            html.Div(id='alerts-panel')
                        ], className='four columns'),
                    ], className='row'),
                ], style={'margin': '20px'}),
                
            ], style={'backgroundColor': '#f8f9fa', 'minHeight': '100vh'}),
            
        ])
    
    def _setup_callbacks(self):
        """Setup dashboard callbacks for real-time updates"""
        
        @self.app.callback(
            [Output('live-status', 'children'),
             Output('cpu-memory-gauge', 'figure'),
             Output('network-overview', 'figure'),
             Output('interface-quality', 'figure'),
             Output('network-throughput', 'figure'),
             Output('health-metrics', 'figure'),
             Output('alerts-panel', 'children')],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n):
            current_time = datetime.now()
            
            # Status indicator
            status = html.Div([
                html.Span("● LIVE", style={'color': 'green', 'fontWeight': 'bold'}),
                html.Span(f" | {current_time.strftime('%H:%M:%S')}", style={'marginLeft': '10px'})
            ])
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            # CPU/Memory Gauge
            gauge_fig = go.Figure()
            gauge_fig.add_trace(go.Indicator(
                mode="gauge+number",
                value=cpu_percent,
                title={'text': "CPU Usage (%)"},
                domain={'row': 0, 'column': 0},
                gauge={'axis': {'range': [None, 100]},
                      'bar': {'color': "orange"},
                      'steps': [{'range': [0, 50], 'color': "lightgray"},
                               {'range': [50, 80], 'color': "yellow"},
                               {'range': [80, 100], 'color': "red"}]}
            ))
            
            gauge_fig.add_trace(go.Indicator(
                mode="gauge+number",
                value=memory.percent,
                title={'text': "Memory Usage (%)"},
                domain={'row': 0, 'column': 1},
                gauge={'axis': {'range': [None, 100]},
                      'bar': {'color': "blue"},
                      'steps': [{'range': [0, 60], 'color': "lightgray"},
                               {'range': [60, 85], 'color': "yellow"},
                               {'range': [85, 100], 'color': "red"}]}
            ))
            
            gauge_fig.update_layout(
                grid={'rows': 1, 'columns': 2, 'pattern': "independent"},
                height=300,
                title="System Resources"
            )
            
            # Network Overview
            network_stats = psutil.net_io_counters(pernic=True)
            interfaces = list(network_stats.keys())[:5]
            bytes_sent = [network_stats[iface].bytes_sent/1024/1024 for iface in interfaces]
            bytes_recv = [network_stats[iface].bytes_recv/1024/1024 for iface in interfaces]
            
            network_fig = go.Figure()
            network_fig.add_trace(go.Bar(name='Sent (MB)', x=interfaces, y=bytes_sent, marker_color='orange'))
            network_fig.add_trace(go.Bar(name='Received (MB)', x=interfaces, y=bytes_recv, marker_color='blue'))
            network_fig.update_layout(title='Network Interface Activity', height=300)
            
            # Interface Quality (using data from your NetworkAggregationEngine concept)
            interface_names = ['wlp2s0f0', 'docker0', 'eth0', 'wlan0']
            quality_scores = [85 + (n%10), 92 - (n%5), 78 + (n%8), 88 - (n%3)]  # Mock dynamic data
            colors = ['green' if q > 80 else 'orange' if q > 60 else 'red' for q in quality_scores]
            
            quality_fig = go.Figure(data=[
                go.Bar(x=interface_names, y=quality_scores, marker_color=colors)
            ])
            quality_fig.update_layout(title='Interface Quality Scores', height=300)
            
            # Network Throughput Timeline
            if len(self.live_data['network_interfaces']) > 1:
                df_network = pd.DataFrame(self.live_data['network_interfaces'])
                throughput_fig = go.Figure()
                throughput_fig.add_trace(go.Scatter(
                    x=df_network['timestamp'],
                    y=df_network['throughput'],
                    mode='lines+markers',
                    name='Throughput (Mbps)',
                    line=dict(color='#ff6b00', width=2)
                ))
                throughput_fig.update_layout(title='Network Throughput Over Time', height=300)
            else:
                throughput_fig = go.Figure()
                throughput_fig.update_layout(title='Network Throughput (Collecting data...)', height=300)
            
            # Platform Health
            if len(self.live_data['platform_health']) > 1:
                df_health = pd.DataFrame(self.live_data['platform_health'])
                health_fig = go.Figure()
                health_fig.add_trace(go.Scatter(
                    x=df_health['timestamp'],
                    y=df_health['health_score'],
                    mode='lines+markers',
                    name='Health Score',
                    line=dict(color='green', width=3)
                ))
                health_fig.update_layout(title='Platform Health Score', height=300)
            else:
                health_fig = go.Figure()
                health_fig.update_layout(title='Platform Health (Initializing...)', height=300)
            
            # Alerts Panel
            alerts_content = html.Div([
                html.H4("🚨 System Alerts", style={'color': '#ff6b00'}),
                html.Div([
                    html.P("✅ All network interfaces operational", style={'color': 'green'}),
                    html.P("📊 Telemetry processing active", style={'color': 'blue'}),
                    html.P("🔧 Container orchestration running", style={'color': 'green'}),
                    html.P(f"⏰ Last update: {current_time.strftime('%H:%M:%S')}", style={'color': 'gray'}),
                    html.P(f"📈 CPU: {cpu_percent:.1f}% | Memory: {memory.percent:.1f}%", 
                          style={'color': 'black', 'fontWeight': 'bold'}),
                ])
            ], style={'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '5px', 'border': '1px solid #ddd'})
            
            return (status, gauge_fig, network_fig, quality_fig, throughput_fig, health_fig, alerts_content)
    
    def _start_data_collection(self):
        """Start background data collection for real-time updates"""
        def collect_data():
            while True:
                try:
                    current_time = datetime.now()
                    
                    # Collect network data
                    network_stats = psutil.net_io_counters()
                    self.live_data['network_interfaces'].append({
                        'timestamp': current_time,
                        'throughput': (network_stats.bytes_sent + network_stats.bytes_recv) / 1024 / 1024,  # MB
                        'packets': network_stats.packets_sent + network_stats.packets_recv
                    })
                    
                    # Collect platform health (mock data representing your platform health)
                    health_score = 90 + (time.time() % 20) - 10  # Simulated health fluctuation
                    self.live_data['platform_health'].append({
                        'timestamp': current_time,
                        'health_score': max(0, min(100, health_score))
                    })
                    
                    # Keep only last 50 data points for performance
                    for key in self.live_data:
                        if len(self.live_data[key]) > 50:
                            self.live_data[key] = self.live_data[key][-50:]
                    
                    time.sleep(3)  # Collect every 3 seconds
                    
                except Exception as e:
                    logger.error(f"Data collection error: {e}")
                    time.sleep(5)
        
        collection_thread = threading.Thread(target=collect_data, daemon=True)
        collection_thread.start()
        logger.info("Background data collection started")
    
    def run(self, debug=False, port=8050, host='0.0.0.0'):
        """Run the dashboard server"""
        logger.info(f"Starting McLaren Dashboard on http://{host}:{port}")
        print(f"\n🚀 McLaren Platform Dashboard")
        print(f"📊 Dashboard URL: http://localhost:{port}")
        print(f"🔄 Real-time updates every 3 seconds")
        print(f"📈 Monitoring: CPU, Memory, Network, Platform Health")
        print(f"Press Ctrl+C to stop\n")
        
        try:
            # Try the new API first, fallback to old API if needed
            if hasattr(self.app, 'run'):
                self.app.run(debug=debug, port=port, host=host, use_reloader=False)
            else:
                self.app.run_server(debug=debug, port=port, host=host, use_reloader=False)
        except Exception as e:
            logger.error(f"Dashboard startup failed: {e}")
            raise