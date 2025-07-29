"""
Prometheus metrics collection for McLaren Platform
Exports platform metrics in Prometheus format for external monitoring
"""

import time
import psutil
import threading
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class PrometheusMetrics:
    """Prometheus metrics exporter for McLaren Platform"""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.running = False
        self.collection_thread: Optional[threading.Thread] = None
        
        # Initialize Prometheus metrics
        self._init_metrics()
        
    def _init_metrics(self):
        """Initialize all Prometheus metrics"""
        
        # Network metrics
        self.network_bytes_sent = Counter(
            'mclaren_network_bytes_sent_total',
            'Total bytes sent over network',
            ['interface']
        )
        
        self.network_bytes_received = Counter(
            'mclaren_network_bytes_received_total',
            'Total bytes received over network',
            ['interface']
        )
        
        self.network_packets_sent = Counter(
            'mclaren_network_packets_sent_total',
            'Total packets sent over network',
            ['interface']
        )
        
        self.network_packets_received = Counter(
            'mclaren_network_packets_received_total',
            'Total packets received over network',
            ['interface']
        )
        
        # System metrics
        self.cpu_usage = Gauge(
            'mclaren_cpu_usage_percent',
            'CPU usage percentage'
        )
        
        self.memory_usage = Gauge(
            'mclaren_memory_usage_percent',
            'Memory usage percentage'
        )
        
        self.disk_io_read = Counter(
            'mclaren_disk_io_read_bytes_total',
            'Total disk bytes read'
        )
        
        self.disk_io_write = Counter(
            'mclaren_disk_io_write_bytes_total',
            'Total disk bytes written'
        )
        
        # Platform-specific metrics
        self.platform_health = Gauge(
            'mclaren_platform_health_score',
            'Overall platform health score (0-100)'
        )
        
        self.active_connections = Gauge(
            'mclaren_active_connections',
            'Number of active network connections'
        )
        
        self.circuit_breaker_status = Gauge(
            'mclaren_circuit_breaker_status',
            'Circuit breaker status',
            ['breaker_name']
        )
        
        self.message_processing_time = Histogram(
            'mclaren_message_processing_seconds',
            'Time taken to process messages',
            ['message_type']
        )
        
        self.aggregation_latency = Histogram(
            'mclaren_aggregation_latency_seconds',
            'Network aggregation latency',
            ['interface']
        )
        
        # Container metrics (when Docker is available)
        self.container_count = Gauge(
            'mclaren_container_count',
            'Number of running containers'
        )
        
        # Error metrics
        self.error_count = Counter(
            'mclaren_errors_total',
            'Total number of errors',
            ['error_type', 'component']
        )
        
        logger.info("Prometheus metrics initialized")
    
    def start_server(self):
        """Start Prometheus metrics HTTP server"""
        try:
            start_http_server(self.port)
            logger.info(f"Prometheus metrics server started on port {self.port}")
            
            # Start metrics collection
            self.running = True
            self.collection_thread = threading.Thread(target=self._collect_metrics_loop, daemon=True)
            self.collection_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")
            raise
    
    def stop_server(self):
        """Stop metrics collection"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        logger.info("Prometheus metrics collection stopped")
    
    def _collect_metrics_loop(self):
        """Background loop for collecting metrics"""
        logger.info("Starting metrics collection loop")
        
        # Store previous values for delta calculations
        prev_network_stats = {}
        prev_disk_stats = None
        
        while self.running:
            try:
                # Collect system metrics
                self._collect_system_metrics()
                
                # Collect network metrics
                current_network_stats = self._collect_network_metrics(prev_network_stats)
                prev_network_stats = current_network_stats
                
                # Collect disk I/O metrics
                prev_disk_stats = self._collect_disk_metrics(prev_disk_stats)
                
                # Collect platform-specific metrics
                self._collect_platform_metrics()
                
                time.sleep(10)  # Collect every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                self.error_count.labels(error_type='collection', component='prometheus').inc()
                time.sleep(5)  # Wait before retrying
    
    def _collect_system_metrics(self):
        """Collect system performance metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_usage.set(memory.percent)
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            self.error_count.labels(error_type='system_metrics', component='prometheus').inc()
    
    def _collect_network_metrics(self, prev_stats: Dict) -> Dict:
        """Collect network interface metrics"""
        try:
            current_stats = {}
            
            # Per-interface statistics
            interfaces = psutil.net_io_counters(pernic=True)
            for interface, stats in interfaces.items():
                current_stats[interface] = {
                    'bytes_sent': stats.bytes_sent,
                    'bytes_recv': stats.bytes_recv,
                    'packets_sent': stats.packets_sent,
                    'packets_recv': stats.packets_recv
                }
                
                # Calculate deltas if we have previous data
                if interface in prev_stats:
                    prev = prev_stats[interface]
                    
                    bytes_sent_delta = stats.bytes_sent - prev['bytes_sent']
                    bytes_recv_delta = stats.bytes_recv - prev['bytes_recv']
                    packets_sent_delta = stats.packets_sent - prev['packets_sent']
                    packets_recv_delta = stats.packets_recv - prev['packets_recv']
                    
                    # Only increment if positive (handles counter resets)
                    if bytes_sent_delta >= 0:
                        self.network_bytes_sent.labels(interface=interface)._value._value += bytes_sent_delta
                    if bytes_recv_delta >= 0:
                        self.network_bytes_received.labels(interface=interface)._value._value += bytes_recv_delta
                    if packets_sent_delta >= 0:
                        self.network_packets_sent.labels(interface=interface)._value._value += packets_sent_delta
                    if packets_recv_delta >= 0:
                        self.network_packets_received.labels(interface=interface)._value._value += packets_recv_delta
            
            return current_stats
            
        except Exception as e:
            logger.error(f"Error collecting network metrics: {e}")
            self.error_count.labels(error_type='network_metrics', component='prometheus').inc()
            return {}
    
    def _collect_disk_metrics(self, prev_stats):
        """Collect disk I/O metrics"""
        try:
            current_stats = psutil.disk_io_counters()
            if current_stats and prev_stats:
                read_delta = current_stats.read_bytes - prev_stats.read_bytes
                write_delta = current_stats.write_bytes - prev_stats.write_bytes
                
                if read_delta >= 0:
                    self.disk_io_read._value._value += read_delta
                if write_delta >= 0:
                    self.disk_io_write._value._value += write_delta
            
            return current_stats
            
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {e}")
            self.error_count.labels(error_type='disk_metrics', component='prometheus').inc()
            return prev_stats
    
    def _collect_platform_metrics(self):
        """Collect McLaren platform-specific metrics"""
        try:
            # Active network connections
            connections = len(psutil.net_connections())
            self.active_connections.set(connections)
            
            # Mock platform health (replace with actual platform health check)
            health_score = 95 + (time.time() % 10)  # Simulated health
            self.platform_health.set(health_score)
            
            # Mock circuit breaker status (replace with actual circuit breaker states)
            circuit_breakers = ['network', 'storage', 'compute', 'telemetry']
            for breaker in circuit_breakers:
                # Simulate healthy circuit breakers
                self.circuit_breaker_status.labels(breaker_name=breaker).set(1)
            
        except Exception as e:
            logger.error(f"Error collecting platform metrics: {e}")
            self.error_count.labels(error_type='platform_metrics', component='prometheus').inc()
    
    def record_message_processing_time(self, message_type: str, processing_time: float):
        """Record time taken to process a message"""
        self.message_processing_time.labels(message_type=message_type).observe(processing_time)
    
    def record_aggregation_latency(self, interface: str, latency: float):
        """Record network aggregation latency"""
        self.aggregation_latency.labels(interface=interface).observe(latency)
    
    def increment_error(self, error_type: str, component: str):
        """Increment error counter"""
        self.error_count.labels(error_type=error_type, component=component).inc()
    
    def update_container_count(self, count: int):
        """Update container count metric"""
        self.container_count.set(count)
    
    def update_circuit_breaker_status(self, breaker_name: str, status: int):
        """Update circuit breaker status (1=healthy, 0=open)"""
        self.circuit_breaker_status.labels(breaker_name=breaker_name).set(status)

# Global instance for easy access
prometheus_metrics = PrometheusMetrics()

def start_prometheus_server(port: int = 8000):
    """Start Prometheus metrics server"""
    prometheus_metrics.port = port
    prometheus_metrics.start_server()
    return prometheus_metrics

def get_prometheus_metrics() -> PrometheusMetrics:
    """Get the global Prometheus metrics instance"""
    return prometheus_metrics