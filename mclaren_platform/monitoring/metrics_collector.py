"""
Metrics Collection Engine for McLaren Platform
Integrates with existing platform components to collect and process metrics
"""

import time
import threading
import logging
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import psutil
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

@dataclass
class MetricData:
    """Data structure for storing metric information"""
    name: str
    value: Any
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class MetricsCollector:
    """
    Central metrics collection system for McLaren Platform
    Integrates with orchestrator, networking, and telemetry components
    """
    
    def __init__(self, collection_interval: float = 5.0):
        self.collection_interval = collection_interval
        self.running = False
        self.collectors: Dict[str, Callable] = {}
        self.metrics_storage: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.collection_thread: Optional[threading.Thread] = None
        self.callbacks: List[Callable[[str, MetricData], None]] = []
        
        # Initialize default collectors
        self._register_default_collectors()
        
        logger.info("Metrics collector initialized")
    
    def _register_default_collectors(self):
        """Register default system and platform metric collectors"""
        
        # System metrics
        self.register_collector('system.cpu', self._collect_cpu_metrics)
        self.register_collector('system.memory', self._collect_memory_metrics)
        self.register_collector('system.disk', self._collect_disk_metrics)
        self.register_collector('system.network', self._collect_network_metrics)
        
        # Platform metrics
        self.register_collector('platform.health', self._collect_platform_health)
        self.register_collector('platform.connections', self._collect_connection_metrics)
        self.register_collector('platform.performance', self._collect_performance_metrics)
    
    def register_collector(self, name: str, collector_func: Callable[[], List[MetricData]]):
        """Register a metric collector function"""
        self.collectors[name] = collector_func
        logger.info(f"Registered metric collector: {name}")
    
    def register_callback(self, callback: Callable[[str, MetricData], None]):
        """Register a callback to be called when metrics are collected"""
        self.callbacks.append(callback)
    
    def start_collection(self):
        """Start the metrics collection process"""
        if self.running:
            logger.warning("Metrics collection already running")
            return
        
        self.running = True
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        logger.info("Metrics collection started")
    
    def stop_collection(self):
        """Stop the metrics collection process"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=10)
        logger.info("Metrics collection stopped")
    
    def _collection_loop(self):
        """Main collection loop running in background thread"""
        logger.info("Starting metrics collection loop")
        
        while self.running:
            try:
                collection_start = time.time()
                
                # Run all registered collectors
                for collector_name, collector_func in self.collectors.items():
                    try:
                        metrics = collector_func()
                        if metrics:
                            for metric in metrics:
                                self._store_metric(collector_name, metric)
                                
                                # Call registered callbacks
                                for callback in self.callbacks:
                                    try:
                                        callback(collector_name, metric)
                                    except Exception as e:
                                        logger.error(f"Error in metric callback: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error in collector {collector_name}: {e}")
                
                # Calculate collection time and sleep accordingly
                collection_time = time.time() - collection_start
                sleep_time = max(0, self.collection_interval - collection_time)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Collection took {collection_time:.2f}s, longer than interval {self.collection_interval}s")
            
            except Exception as e:
                logger.error(f"Error in collection loop: {e}")
                time.sleep(1)  # Prevent tight error loops
    
    def _store_metric(self, collector_name: str, metric: MetricData):
        """Store metric data in internal storage"""
        storage_key = f"{collector_name}.{metric.name}"
        self.metrics_storage[storage_key].append(metric)
    
    def get_metrics(self, name_pattern: str = None, since: datetime = None) -> Dict[str, List[MetricData]]:
        """Retrieve stored metrics, optionally filtered by pattern and time"""
        result = {}
        
        for metric_name, metric_data in self.metrics_storage.items():
            # Apply name pattern filter
            if name_pattern and name_pattern not in metric_name:
                continue
            
            # Apply time filter
            if since:
                filtered_data = [m for m in metric_data if m.timestamp >= since]
            else:
                filtered_data = list(metric_data)
            
            if filtered_data:
                result[metric_name] = filtered_data
        
        return result
    
    def get_latest_metrics(self, name_pattern: str = None) -> Dict[str, MetricData]:
        """Get the most recent value for each metric"""
        result = {}
        
        for metric_name, metric_data in self.metrics_storage.items():
            if name_pattern and name_pattern not in metric_name:
                continue
            
            if metric_data:
                result[metric_name] = metric_data[-1]
        
        return result
    
    def _collect_cpu_metrics(self) -> List[MetricData]:
        """Collect CPU-related metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Overall CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(MetricData(
                name='usage_percent',
                value=cpu_percent,
                timestamp=current_time,
                labels={'component': 'cpu'}
            ))
            
            # Per-CPU usage
            cpu_percents = psutil.cpu_percent(percpu=True)
            for i, cpu_pct in enumerate(cpu_percents):
                metrics.append(MetricData(
                    name='usage_percent_per_cpu',
                    value=cpu_pct,
                    timestamp=current_time,
                    labels={'component': 'cpu', 'cpu_id': str(i)}
                ))
            
            # Load averages (Linux/macOS)
            try:
                load_avg = psutil.getloadavg()
                for i, period in enumerate(['1min', '5min', '15min']):
                    metrics.append(MetricData(
                        name='load_average',
                        value=load_avg[i],
                        timestamp=current_time,
                        labels={'component': 'cpu', 'period': period}
                    ))
            except AttributeError:
                pass  # Not available on Windows
            
        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {e}")
        
        return metrics
    
    def _collect_memory_metrics(self) -> List[MetricData]:
        """Collect memory-related metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Virtual memory
            memory = psutil.virtual_memory()
            memory_metrics = {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'free': memory.free,
                'percent': memory.percent
            }
            
            for metric_name, value in memory_metrics.items():
                metrics.append(MetricData(
                    name=f'virtual_{metric_name}',
                    value=value,
                    timestamp=current_time,
                    labels={'component': 'memory', 'type': 'virtual'}
                ))
            
            # Swap memory
            swap = psutil.swap_memory()
            swap_metrics = {
                'total': swap.total,
                'used': swap.used,
                'free': swap.free,
                'percent': swap.percent
            }
            
            for metric_name, value in swap_metrics.items():
                metrics.append(MetricData(
                    name=f'swap_{metric_name}',
                    value=value,
                    timestamp=current_time,
                    labels={'component': 'memory', 'type': 'swap'}
                ))
                
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {e}")
        
        return metrics
    
    def _collect_disk_metrics(self) -> List[MetricData]:
        """Collect disk I/O and usage metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Disk I/O counters
            disk_io = psutil.disk_io_counters()
            if disk_io:
                io_metrics = {
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count,
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_time': disk_io.read_time,
                    'write_time': disk_io.write_time
                }
                
                for metric_name, value in io_metrics.items():
                    metrics.append(MetricData(
                        name=f'io_{metric_name}',
                        value=value,
                        timestamp=current_time,
                        labels={'component': 'disk', 'type': 'io'}
                    ))
            
            # Disk usage for key mount points
            key_paths = ['/', '/home', '/tmp']  # Add more as needed
            for path in key_paths:
                try:
                    usage = psutil.disk_usage(path)
                    for metric_name, value in [('total', usage.total), ('used', usage.used), ('free', usage.free)]:
                        metrics.append(MetricData(
                            name=f'usage_{metric_name}',
                            value=value,
                            timestamp=current_time,
                            labels={'component': 'disk', 'type': 'usage', 'path': path}
                        ))
                except (OSError, FileNotFoundError):
                    continue  # Path doesn't exist on this system
                    
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {e}")
        
        return metrics
    
    def _collect_network_metrics(self) -> List[MetricData]:
        """Collect network interface metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Per-interface statistics
            interfaces = psutil.net_io_counters(pernic=True)
            for interface, stats in interfaces.items():
                interface_metrics = {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv,
                    'packets_sent': stats.packets_sent,
                    'packets_recv': stats.packets_recv,
                    'errin': stats.errin,
                    'errout': stats.errout,
                    'dropin': stats.dropin,
                    'dropout': stats.dropout
                }
                
                for metric_name, value in interface_metrics.items():
                    metrics.append(MetricData(
                        name=metric_name,
                        value=value,
                        timestamp=current_time,
                        labels={'component': 'network', 'interface': interface}
                    ))
            
            # Network connections
            connections = psutil.net_connections()
            connection_counts = defaultdict(int)
            for conn in connections:
                connection_counts[conn.status] += 1
            
            for status, count in connection_counts.items():
                metrics.append(MetricData(
                    name='connections',
                    value=count,
                    timestamp=current_time,
                    labels={'component': 'network', 'status': status}
                ))
                
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
        
        return metrics
    
    def _collect_platform_health(self) -> List[MetricData]:
        """Collect McLaren platform health metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Mock platform health score (replace with actual health checks)
            health_score = 95 + (time.time() % 10)  # Simulated health
            metrics.append(MetricData(
                name='health_score',
                value=health_score,
                timestamp=current_time,
                labels={'component': 'platform'}
            ))
            
            # Circuit breaker status (mock - replace with actual status)
            circuit_breakers = ['network', 'storage', 'compute', 'telemetry']
            for breaker in circuit_breakers:
                metrics.append(MetricData(
                    name='circuit_breaker_status',
                    value=1,  # 1 = healthy, 0 = open
                    timestamp=current_time,
                    labels={'component': 'platform', 'breaker': breaker}
                ))
                
        except Exception as e:
            logger.error(f"Error collecting platform health metrics: {e}")
        
        return metrics
    
    def _collect_connection_metrics(self) -> List[MetricData]:
        """Collect platform connection metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Active connections count
            active_connections = len(psutil.net_connections())
            metrics.append(MetricData(
                name='active_count',
                value=active_connections,
                timestamp=current_time,
                labels={'component': 'connections'}
            ))
            
            # Mock aggregation engine metrics
            interfaces = ['wlp2s0f0', 'docker0']  # From your platform logs
            for interface in interfaces:
                metrics.append(MetricData(
                    name='interface_status',
                    value=1,  # 1 = active, 0 = inactive
                    timestamp=current_time,
                    labels={'component': 'connections', 'interface': interface}
                ))
                
        except Exception as e:
            logger.error(f"Error collecting connection metrics: {e}")
        
        return metrics
    
    def _collect_performance_metrics(self) -> List[MetricData]:
        """Collect platform performance metrics"""
        metrics = []
        current_time = datetime.now()
        
        try:
            # Mock performance metrics (replace with actual measurements)
            performance_metrics = {
                'message_processing_time': 0.05,  # seconds
                'aggregation_latency': 0.02,      # seconds
                'throughput': 1000,               # messages/second
                'queue_depth': 10                 # messages in queue
            }
            
            for metric_name, value in performance_metrics.items():
                metrics.append(MetricData(
                    name=metric_name,
                    value=value,
                    timestamp=current_time,
                    labels={'component': 'performance'}
                ))
                
        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
        
        return metrics
    
    def export_metrics(self, format_type: str = 'json') -> str:
        """Export metrics in specified format"""
        latest_metrics = self.get_latest_metrics()
        
        if format_type == 'json':
            exportable = {}
            for metric_name, metric_data in latest_metrics.items():
                exportable[metric_name] = {
                    'value': metric_data.value,
                    'timestamp': metric_data.timestamp.isoformat(),
                    'labels': metric_data.labels,
                    'metadata': metric_data.metadata
                }
            return json.dumps(exportable, indent=2)
        
        elif format_type == 'prometheus':
            # Basic Prometheus format export
            lines = []
            for metric_name, metric_data in latest_metrics.items():
                sanitized_name = metric_name.replace('.', '_').replace('-', '_')
                labels_str = ','.join([f'{k}="{v}"' for k, v in metric_data.labels.items()])
                if labels_str:
                    line = f'{sanitized_name}{{{labels_str}}} {metric_data.value}'
                else:
                    line = f'{sanitized_name} {metric_data.value}'
                lines.append(line)
            return '\n'.join(lines)
        
        else:
            raise ValueError(f"Unsupported format: {format_type}")

# Global metrics collector instance
_global_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector instance"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector

def start_metrics_collection(collection_interval: float = 5.0) -> MetricsCollector:
    """Start metrics collection with the global collector"""
    collector = get_metrics_collector()
    collector.collection_interval = collection_interval
    collector.start_collection()
    return collector