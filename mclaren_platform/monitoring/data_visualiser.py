import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List, Optional
import asyncio
from core.events import EventBus

class DataVisualizer:
    
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._logger = logging.getLogger(__name__)
        self._telemetry_data = []
        self._network_data = []
        
        plt.style.use('seaborn-v0_8-darkgrid')
        sns.set_palette("husl")
    
    async def generate_platform_dashboard(self, output_dir: str = "logs"):
        await self._generate_sample_data()
        
        fig = plt.figure(figsize=(20, 16))
        fig.suptitle('McLaren Applied Communication Platform - Live Dashboard', 
                    fontsize=20, fontweight='bold', y=0.98)
        
        gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)
        
        ax1 = fig.add_subplot(gs[0, :2])
        self._plot_train_telemetry(ax1)
        
        ax2 = fig.add_subplot(gs[0, 2])
        self._plot_network_performance(ax2)
        
        ax3 = fig.add_subplot(gs[1, 0])
        self._plot_system_resources(ax3)
        
        ax4 = fig.add_subplot(gs[1, 1])
        self._plot_container_status(ax4)
        
        ax5 = fig.add_subplot(gs[1, 2])
        self._plot_alert_summary(ax5)
        
        ax6 = fig.add_subplot(gs[2, :2])
        self._plot_interface_quality_timeline(ax6)
        
        ax7 = fig.add_subplot(gs[2, 2])
        self._plot_throughput_analysis(ax7)
        
        ax8 = fig.add_subplot(gs[3, :])
        self._plot_predictive_analytics(ax8)
        
        plt.savefig(f'{output_dir}/mclaren_platform_dashboard.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        await self._generate_telemetry_report(output_dir)
        await self._generate_network_analysis_report(output_dir)
        
        self._logger.info(f"Dashboard and reports generated in {output_dir}/")
    
    async def _generate_sample_data(self):
        base_time = datetime.now() - timedelta(hours=2)
        
        for i in range(240):
            timestamp = base_time + timedelta(seconds=i * 30)
            
            speed_variation = 20 * np.sin(i * 0.05) + np.random.normal(0, 5)
            base_speed = 85 + speed_variation
            
            telemetry = {
                'timestamp': timestamp,
                'train_id': 'TRAIN_001',
                'speed_kmh': max(0, base_speed),
                'location_lat': 51.5074 + (i * 0.001),
                'location_lon': -0.1278 + (i * 0.0005),
                'passenger_count': 150 + np.random.randint(-20, 30),
                'network_quality': 70 + 20 * np.sin(i * 0.1) + np.random.normal(0, 5),
                'system_cpu': 30 + 20 * np.sin(i * 0.08) + np.random.normal(0, 3),
                'system_memory': 60 + 10 * np.sin(i * 0.06) + np.random.normal(0, 2),
                'bandwidth_mbps': 400 + 100 * np.sin(i * 0.07) + np.random.normal(0, 20),
                'latency_ms': 45 + 15 * np.sin(i * 0.09) + np.random.normal(0, 5)
            }
            self._telemetry_data.append(telemetry)
        
        interfaces = ['wlp2s0f0', 'docker0', 'eth0']
        for interface in interfaces:
            for i in range(120):
                timestamp = base_time + timedelta(seconds=i * 30)
                
                network_point = {
                    'timestamp': timestamp,
                    'interface': interface,
                    'quality_score': 60 + 30 * np.sin(i * 0.1) + np.random.normal(0, 5),
                    'bandwidth_mbps': 300 + 150 * np.sin(i * 0.08) + np.random.normal(0, 25),
                    'latency_ms': 50 + 20 * np.sin(i * 0.12) + np.random.normal(0, 5),
                    'packet_loss': max(0, 1 + 2 * np.sin(i * 0.15) + np.random.normal(0, 0.5))
                }
                self._network_data.append(network_point)
    
    def _plot_train_telemetry(self, ax):
        df = pd.DataFrame(self._telemetry_data)
        
        ax.plot(df['timestamp'], df['speed_kmh'], color='blue', linewidth=2, label='Speed (km/h)')
        ax.set_xlabel('Time')
        ax.set_ylabel('Speed (km/h)', color='blue')
        ax.tick_params(axis='y', labelcolor='blue')
        
        ax2 = ax.twinx()
        ax2.plot(df['timestamp'], df['passenger_count'], color='red', linewidth=1, alpha=0.7, label='Passengers')
        ax2.set_ylabel('Passenger Count', color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        
        ax.set_title('Train Speed & Passenger Load Over Time', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_network_performance(self, ax):
        df = pd.DataFrame(self._telemetry_data)
        
        current_quality = df['network_quality'].iloc[-1]
        
        theta = np.linspace(0, np.pi, 100)
        r = 1
        
        if current_quality >= 80:
            color = 'green'
            status = 'Excellent'
        elif current_quality >= 60:
            color = 'orange'
            status = 'Good'
        else:
            color = 'red'
            status = 'Poor'
        
        ax.fill_between(theta, 0, r, alpha=0.3, color='lightgray')
        
        quality_angle = (current_quality / 100) * np.pi
        theta_fill = np.linspace(0, quality_angle, 50)
        ax.fill_between(theta_fill, 0, r, alpha=0.8, color=color)
        
        ax.text(np.pi/2, 0.5, f'{current_quality:.1f}%\n{status}', 
               ha='center', va='center', fontsize=12, fontweight='bold')
        
        ax.set_xlim(0, np.pi)
        ax.set_ylim(0, 1)
        ax.set_title('Current Network Quality', fontweight='bold')
        ax.axis('off')
    
    def _plot_system_resources(self, ax):
        df = pd.DataFrame(self._telemetry_data)
        
        cpu = df['system_cpu'].iloc[-1]
        memory = df['system_memory'].iloc[-1]
        
        resources = ['CPU', 'Memory']
        values = [cpu, memory]
        colors = ['lightcoral' if v > 80 else 'lightblue' for v in values]
        
        bars = ax.bar(resources, values, color=colors, alpha=0.8)
        
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                   f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylim(0, 100)
        ax.set_ylabel('Usage (%)')
        ax.set_title('System Resources', fontweight='bold')
        ax.grid(True, axis='y', alpha=0.3)
    
    def _plot_container_status(self, ax):
        container_status = {
            'Running': 8,
            'Stopped': 1,
            'Failed': 0,
            'Updating': 1
        }
        
        colors = ['lightgreen', 'lightgray', 'lightcoral', 'lightyellow']
        wedges, texts, autotexts = ax.pie(container_status.values(), 
                                         labels=container_status.keys(),
                                         colors=colors,
                                         autopct='%1.0f',
                                         startangle=90)
        
        ax.set_title('Container Status', fontweight='bold')
    
    def _plot_alert_summary(self, ax):
        alert_levels = ['Critical', 'Warning', 'Info']
        alert_counts = [0, 2, 5]
        colors = ['red', 'orange', 'lightblue']
        
        bars = ax.bar(alert_levels, alert_counts, color=colors, alpha=0.8)
        
        for bar, count in zip(bars, alert_counts):
            if count > 0:
                ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                       str(count), ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylabel('Count')
        ax.set_title('Active Alerts', fontweight='bold')
        ax.set_ylim(0, max(alert_counts) + 1 if alert_counts else 1)
    
    def _plot_interface_quality_timeline(self, ax):
        df = pd.DataFrame(self._network_data)
        
        for interface in df['interface'].unique():
            interface_data = df[df['interface'] == interface]
            ax.plot(interface_data['timestamp'], interface_data['quality_score'], 
                   label=interface, linewidth=2, marker='o', markersize=3)
        
        ax.set_xlabel('Time')
        ax.set_ylabel('Quality Score')
        ax.set_title('Network Interface Quality Timeline', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_throughput_analysis(self, ax):
        df = pd.DataFrame(self._telemetry_data)
        
        throughput_stats = {
            'Current': df['bandwidth_mbps'].iloc[-1],
            'Average': df['bandwidth_mbps'].mean(),
            'Peak': df['bandwidth_mbps'].max(),
            'Minimum': df['bandwidth_mbps'].min()
        }
        
        bars = ax.bar(throughput_stats.keys(), throughput_stats.values(), 
                     color=['lightblue', 'lightgreen', 'gold', 'lightcoral'], alpha=0.8)
        
        for bar, value in zip(bars, throughput_stats.values()):
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 5,
                   f'{value:.0f}', ha='center', va='bottom', fontweight='bold')
        
        ax.set_ylabel('Bandwidth (Mbps)')
        ax.set_title('Throughput Analysis', fontweight='bold')
        ax.tick_params(axis='x', rotation=45)
    
    def _plot_predictive_analytics(self, ax):
        df = pd.DataFrame(self._telemetry_data)
        
        time_data = pd.to_datetime(df['timestamp'])
        network_quality = df['network_quality'].values
        
        x_numeric = np.arange(len(network_quality))
        z = np.polyfit(x_numeric, network_quality, 2)
        p = np.poly1d(z)
        
        future_points = 50
        extended_x = np.arange(len(network_quality) + future_points)
        predicted_quality = p(extended_x)
        
        time_extended = pd.date_range(start=time_data.iloc[0], 
                                    periods=len(extended_x), freq='30s')
        
        ax.plot(time_data, network_quality, 'b-', linewidth=2, label='Historical Quality', alpha=0.8)
        
        future_time = time_extended[len(network_quality):]
        future_predicted = predicted_quality[len(network_quality):]
        ax.plot(future_time, future_predicted, 'r--', linewidth=2, label='Predicted Quality', alpha=0.8)
        
        confidence = 5
        ax.fill_between(future_time, 
                       future_predicted - confidence, 
                       future_predicted + confidence, 
                       alpha=0.3, color='red', label='Confidence Band')
        
        ax.set_xlabel('Time')
        ax.set_ylabel('Network Quality Score')
        ax.set_title('Predictive Network Quality Analytics', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=45)
        
        ax.axhline(y=30, color='orange', linestyle=':', alpha=0.7, label='Alert Threshold')
    
    async def _generate_telemetry_report(self, output_dir: str):
        df = pd.DataFrame(self._telemetry_data)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('McLaren Platform - Detailed Telemetry Analysis', fontsize=16, fontweight='bold')
        
        axes[0, 0].hist(df['speed_kmh'], bins=30, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0, 0].axvline(df['speed_kmh'].mean(), color='red', linestyle='--', 
                          label=f'Mean: {df["speed_kmh"].mean():.1f} km/h')
        axes[0, 0].set_xlabel('Speed (km/h)')
        axes[0, 0].set_ylabel('Frequency')
        axes[0, 0].set_title('Speed Distribution')
        axes[0, 0].legend()
        
        axes[0, 1].scatter(df['speed_kmh'], df['network_quality'], alpha=0.6, color='green')
        z = np.polyfit(df['speed_kmh'], df['network_quality'], 1)
        p = np.poly1d(z)
        axes[0, 1].plot(df['speed_kmh'], p(df['speed_kmh']), "r--", alpha=0.8)
        axes[0, 1].set_xlabel('Speed (km/h)')
        axes[0, 1].set_ylabel('Network Quality')
        axes[0, 1].set_title('Speed vs Network Quality Correlation')
        
        axes[1, 0].plot(df['timestamp'], df['system_cpu'], label='CPU %', linewidth=2)
        axes[1, 0].plot(df['timestamp'], df['system_memory'], label='Memory %', linewidth=2)
        axes[1, 0].set_xlabel('Time')
        axes[1, 0].set_ylabel('Usage (%)')
        axes[1, 0].set_title('System Performance Timeline')
        axes[1, 0].legend()
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        axes[1, 1].plot(df['timestamp'], df['passenger_count'], color='purple', linewidth=2)
        axes[1, 1].fill_between(df['timestamp'], df['passenger_count'], alpha=0.3, color='purple')
        axes[1, 1].set_xlabel('Time')
        axes[1, 1].set_ylabel('Passenger Count')
        axes[1, 1].set_title('Passenger Load Over Time')
        axes[1, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/telemetry_detailed_report.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    async def _generate_network_analysis_report(self, output_dir: str):
        df = pd.DataFrame(self._network_data)
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('McLaren Platform - Network Performance Analysis', fontsize=16, fontweight='bold')
        
        df_pivot = df.pivot_table(values='bandwidth_mbps', index='timestamp', columns='interface')
        df_pivot.plot(ax=axes[0, 0], linewidth=2)
        axes[0, 0].set_title('Bandwidth by Interface')
        axes[0, 0].set_ylabel('Bandwidth (Mbps)')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        for interface in df['interface'].unique():
            interface_data = df[df['interface'] == interface]
            axes[0, 1].hist(interface_data['latency_ms'], alpha=0.6, label=interface, bins=20)
        axes[0, 1].set_xlabel('Latency (ms)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title('Latency Distribution by Interface')
        axes[0, 1].legend()
        
        df_quality = df.pivot_table(values='quality_score', index='interface', 
                                   columns=df['timestamp'].dt.hour, aggfunc='mean')
        sns.heatmap(df_quality, ax=axes[1, 0], cmap='RdYlGn', center=50, 
                   cbar_kws={'label': 'Quality Score'})
        axes[1, 0].set_title('Quality Score Heatmap (by Hour)')
        axes[1, 0].set_xlabel('Hour of Day')
        
        for interface in df['interface'].unique():
            interface_data = df[df['interface'] == interface]
            axes[1, 1].plot(interface_data['timestamp'], interface_data['packet_loss'], 
                           label=interface, linewidth=2)
        axes[1, 1].set_xlabel('Time')
        axes[1, 1].set_ylabel('Packet Loss (%)')
        axes[1, 1].set_title('Packet Loss Trends')
        axes[1, 1].legend()
        axes[1, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/network_detailed_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()