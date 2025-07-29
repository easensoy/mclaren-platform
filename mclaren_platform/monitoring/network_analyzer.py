import asyncio
import subprocess
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from ..core.events import EventBus, Event

class NetworkAnalyzer:
    """Network traffic analysis using packet capture and statistical analysis."""
    
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._logger = logging.getLogger(__name__)
        self._capture_running = False
        self._packet_data = []
        
    async def start_packet_capture(self, interface: str = "any", duration: int = 60):
        """Start packet capture using tshark (Wireshark CLI)."""
        try:
            # Use tshark for packet capture
            cmd = [
                'tshark', '-i', interface, '-a', f'duration:{duration}',
                '-T', 'fields', '-e', 'frame.time_epoch', '-e', 'ip.src', 
                '-e', 'ip.dst', '-e', 'frame.len', '-e', 'ip.proto'
            ]
            
            self._capture_running = True
            self._logger.info(f"Starting packet capture on {interface} for {duration}s")
            
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                await self._process_packet_data(stdout.decode())
                await self._event_bus.publish(Event(
                    event_type='packet_capture_completed',
                    data={'interface': interface, 'packets_captured': len(self._packet_data)}
                ))
            else:
                self._logger.error(f"Packet capture failed: {stderr.decode()}")
                
        except FileNotFoundError:
            self._logger.warning("tshark not found, using mock data for demonstration")
            await self._generate_mock_packet_data()
        except Exception as e:
            self._logger.error(f"Packet capture error: {e}")
        finally:
            self._capture_running = False
    
    async def _process_packet_data(self, raw_data: str):
        """Process captured packet data into structured format."""
        self._packet_data = []
        
        for line in raw_data.strip().split('\n'):
            if line:
                fields = line.split('\t')
                if len(fields) >= 5:
                    try:
                        packet = {
                            'timestamp': float(fields[0]),
                            'src_ip': fields[1],
                            'dst_ip': fields[2],
                            'length': int(fields[3]) if fields[3] else 0,
                            'protocol': fields[4]
                        }
                        self._packet_data.append(packet)
                    except (ValueError, IndexError):
                        continue
    
    async def _generate_mock_packet_data(self):
        """Generate mock packet data for demonstration."""
        import random
        
        self._packet_data = []
        base_time = time.time()
        
        for i in range(1000):
            packet = {
                'timestamp': base_time + i * 0.1,
                'src_ip': f"192.168.1.{random.randint(1, 100)}",
                'dst_ip': f"10.0.0.{random.randint(1, 50)}",
                'length': random.randint(64, 1500),
                'protocol': random.choice(['6', '17', '1'])  # TCP, UDP, ICMP
            }
            self._packet_data.append(packet)
    
    def analyze_traffic_patterns(self) -> Dict[str, Any]:
        """Analyze network traffic patterns using pandas and numpy."""
        if not self._packet_data:
            return {'error': 'No packet data available'}
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(self._packet_data)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df['protocol_name'] = df['protocol'].map({'6': 'TCP', '17': 'UDP', '1': 'ICMP'})
        
        analysis = {
            'total_packets': len(df),
            'capture_duration': df['timestamp'].max() - df['timestamp'].min(),
            'average_packet_size': df['length'].mean(),
            'total_bytes': df['length'].sum(),
            'protocol_distribution': df['protocol_name'].value_counts().to_dict(),
            'top_source_ips': df['src_ip'].value_counts().head(10).to_dict(),
            'top_destination_ips': df['dst_ip'].value_counts().head(10).to_dict(),
            'packets_per_second': len(df) / (df['timestamp'].max() - df['timestamp'].min()),
            'bandwidth_usage': {
                'average_bps': df['length'].sum() * 8 / (df['timestamp'].max() - df['timestamp'].min()),  # bits per second
                'peak_bps': df.groupby(df['timestamp'].astype(int))['length'].sum().max() * 8,
                'average_packet_rate': len(df) / (df['timestamp'].max() - df['timestamp'].min())
            }
        }
        
        return analysis
    
    def generate_traffic_visualizations(self, output_dir: str = "logs"):
        """Generate network traffic visualizations."""
        if not self._packet_data:
            self._logger.warning("No packet data available for visualization")
            return
        
        df = pd.DataFrame(self._packet_data)
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        df['protocol_name'] = df['protocol'].map({'6': 'TCP', '17': 'UDP', '1': 'ICMP'})
        
        # Set up the plotting style
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('McLaren Platform - Network Traffic Analysis', fontsize=16, fontweight='bold')
        
        # 1. Protocol Distribution Pie Chart
        protocol_counts = df['protocol_name'].value_counts()
        axes[0, 0].pie(protocol_counts.values, labels=protocol_counts.index, autopct='%1.1f%%')
        axes[0, 0].set_title('Protocol Distribution')
        
        # 2. Packet Size Distribution
        axes[0, 1].hist(df['length'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0, 1].set_xlabel('Packet Size (bytes)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].set_title('Packet Size Distribution')
        axes[0, 1].axvline(df['length'].mean(), color='red', linestyle='--', label=f'Mean: {df["length"].mean():.0f}')
        axes[0, 1].legend()
        
        # 3. Traffic Over Time
        df_time_grouped = df.set_index('datetime').resample('1s')['length'].sum()
        axes[1, 0].plot(df_time_grouped.index, df_time_grouped.values, color='green', linewidth=2)
        axes[1, 0].set_xlabel('Time')
        axes[1, 0].set_ylabel('Bytes per Second')
        axes[1, 0].set_title('Network Traffic Over Time')
        axes[1, 0].tick_params(axis='x', rotation=45)
        
        # 4. Top Source IPs
        top_ips = df['src_ip'].value_counts().head(10)
        axes[1, 1].barh(range(len(top_ips)), top_ips.values, color='coral')
        axes[1, 1].set_yticks(range(len(top_ips)))
        axes[1, 1].set_yticklabels(top_ips.index)
        axes[1, 1].set_xlabel('Packet Count')
        axes[1, 1].set_title('Top 10 Source IP Addresses')
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/network_traffic_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        # Generate additional latency analysis chart
        self._generate_latency_analysis(df, output_dir)
        
        self._logger.info(f"Network visualizations saved to {output_dir}/")
    
    def _generate_latency_analysis(self, df: pd.DataFrame, output_dir: str):
        """Generate latency analysis visualization."""
        # Simulate latency data based on packet timing
        df_sorted = df.sort_values('timestamp')
        df_sorted['inter_arrival_time'] = df_sorted['timestamp'].diff() * 1000  # Convert to ms
        
        plt.figure(figsize=(12, 8))
        
        # Create subplot for latency analysis
        fig, axes = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle('McLaren Platform - Network Latency Analysis', fontsize=16, fontweight='bold')
        
        # Inter-arrival time distribution
        axes[0].hist(df_sorted['inter_arrival_time'].dropna(), bins=50, alpha=0.7, color='lightblue', edgecolor='black')
        axes[0].set_xlabel('Inter-arrival Time (ms)')
        axes[0].set_ylabel('Frequency')
        axes[0].set_title('Packet Inter-arrival Time Distribution')
        axes[0].axvline(df_sorted['inter_arrival_time'].mean(), color='red', linestyle='--', 
                       label=f'Mean: {df_sorted["inter_arrival_time"].mean():.2f} ms')
        axes[0].legend()
        
        # Latency over time (simulated)
        latency_over_time = df_sorted.set_index('datetime')['inter_arrival_time'].rolling('10s').mean()
        axes[1].plot(latency_over_time.index, latency_over_time.values, color='purple', linewidth=2)
        axes[1].set_xlabel('Time')
        axes[1].set_ylabel('Average Latency (ms)')
        axes[1].set_title('Network Latency Trends (10s Rolling Average)')
        axes[1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/network_latency_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()