import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import netifaces
from ..core.interfaces import INetworkProvider, NetworkType, ConnectionStatus
from ..core.models import NetworkInterface, Event
from ..core.events import EventBus

class NetworkAggregationEngine(INetworkProvider):
    """Advanced network aggregation engine managing multiple connection types."""
    
    def __init__(self, config: Dict[str, Any], event_bus: EventBus):
        self._config = config
        self._event_bus = event_bus
        self._interfaces: Dict[str, NetworkInterface] = {}
        self._performance_history: Dict[str, List[float]] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)
        
        # Subscribe to relevant events
        self._event_bus.subscribe('network_interface_failed', self._handle_interface_failure)
        self._event_bus.subscribe('recovery_requested', self._handle_recovery_request)
    
    async def initialize(self) -> None:
        """Initialize network aggregation engine and start monitoring."""
        try:
            await self._discover_interfaces()
            await self._start_performance_monitoring()
            
            self._logger.info(f"Network aggregation engine initialized with {len(self._interfaces)} interfaces")
            
            await self._event_bus.publish(Event(
                event_type='network_engine_initialized',
                data={
                    'interface_count': len(self._interfaces),
                    'active_interfaces': len([i for i in self._interfaces.values() if i.status == ConnectionStatus.ACTIVE])
                }
            ))
            
        except Exception as e:
            self._logger.error(f"Network engine initialization failed: {e}")
            raise
    
    async def get_interfaces(self) -> List[NetworkInterface]:
        """Get all discovered network interfaces."""
        return list(self._interfaces.values())
    
    async def test_performance(self, interface_name: str) -> Tuple[float, float, float]:
        """Test performance of specific interface."""
        if interface_name not in self._interfaces:
            raise ValueError(f"Interface {interface_name} not found")
        
        try:
            performance_result = await self._measure_interface_performance(interface_name)
            
            # Update interface metrics
            interface = self._interfaces[interface_name]
            interface.bandwidth_mbps = performance_result[0]
            interface.latency_ms = performance_result[1]
            interface.packet_loss_percent = performance_result[2]
            interface.last_updated = datetime.now()
            interface.quality_score = self._calculate_quality_score(interface)
            
            return performance_result
            
        except Exception as e:
            self._logger.error(f"Performance test failed for {interface_name}: {e}")
            raise
    
    async def configure_interface(self, interface_name: str, config: Dict[str, Any]) -> bool:
        """Configure network interface with specific parameters."""
        try:
            if interface_name not in self._interfaces:
                return False
            
            interface = self._interfaces[interface_name]
            
            # Apply configuration based on interface type
            if interface.type == NetworkType.WIFI_6:
                success = await self._configure_wifi_interface(interface_name, config)
            elif interface.type == NetworkType.LTE_5G:
                success = await self._configure_lte_interface(interface_name, config)
            elif interface.type == NetworkType.STARLINK:
                success = await self._configure_starlink_interface(interface_name, config)
            else:
                success = await self._configure_ethernet_interface(interface_name, config)
            
            if success:
                interface.metadata.update(config)
                await self._event_bus.publish(Event(
                    event_type='interface_configured',
                    data={'interface_name': interface_name, 'config': config}
                ))
            
            return success
            
        except Exception as e:
            self._logger.error(f"Interface configuration failed for {interface_name}: {e}")
            return False
    
    async def select_optimal_interface(self, requirements: Dict[str, Any] = None) -> Optional[NetworkInterface]:
        """Select optimal interface based on current performance and requirements."""
        active_interfaces = [
            iface for iface in self._interfaces.values() 
            if iface.status == ConnectionStatus.ACTIVE
        ]
        
        if not active_interfaces:
            return None
        
        requirements = requirements or {}
        scored_interfaces = []
        
        for interface in active_interfaces:
            score = await self._calculate_interface_score(interface, requirements)
            scored_interfaces.append((interface, score))
        
        scored_interfaces.sort(key=lambda x: x[1], reverse=True)
        return scored_interfaces[0][0] if scored_interfaces else None
    
    async def _discover_interfaces(self) -> None:
        """Discover and configure all available network interfaces."""
        try:
            system_interfaces = netifaces.interfaces()
            
            for interface_name in system_interfaces:
                try:
                    await self._configure_discovered_interface(interface_name)
                except Exception as e:
                    self._logger.warning(f"Failed to configure interface {interface_name}: {e}")
                    
        except Exception as e:
            self._logger.error(f"Interface discovery failed: {e}")
            raise
    
    async def _configure_discovered_interface(self, interface_name: str) -> None:
        """Configure a discovered network interface."""
        addresses = netifaces.ifaddresses(interface_name)
        
        if netifaces.AF_INET not in addresses:
            return  # Skip interfaces without IPv4
        
        ip_info = addresses[netifaces.AF_INET][0]
        ip_address = ip_info['addr']
        
        # Skip localhost and invalid interfaces
        if ip_address.startswith('127.') or ip_address == '0.0.0.0':
            return
        
        network_type = self._identify_network_type(interface_name, ip_address)
        bandwidth, latency, packet_loss = await self._measure_interface_performance(interface_name)
        
        interface = NetworkInterface(
            name=interface_name,
            type=network_type,
            ip_address=ip_address,
            bandwidth_mbps=bandwidth,
            latency_ms=latency,
            packet_loss_percent=packet_loss,
            status=ConnectionStatus.ACTIVE,
            last_updated=datetime.now()
        )
        
        interface.quality_score = self._calculate_quality_score(interface)
        self._interfaces[interface_name] = interface
        self._performance_history[interface_name] = [interface.quality_score]
        
        self._logger.info(f"Configured interface {interface_name}: {network_type.value}")
    
    def _identify_network_type(self, interface_name: str, ip_address: str) -> NetworkType:
        """Identify network type based on interface characteristics."""
        name_lower = interface_name.lower()
        
        if any(keyword in name_lower for keyword in ['wlan', 'wifi', 'wireless']):
            return NetworkType.WIFI_6
        elif any(keyword in name_lower for keyword in ['cellular', 'lte', '5g', 'mobile']):
            return NetworkType.LTE_5G
        elif 'starlink' in name_lower or ip_address.startswith('100.'):
            return NetworkType.STARLINK
        elif any(keyword in name_lower for keyword in ['eth', 'enet']):
            return NetworkType.ETHERNET
        else:
            return NetworkType.ETHERNET
    
    async def _measure_interface_performance(self, interface_name: str) -> Tuple[float, float, float]:
        """Measure comprehensive performance metrics for interface."""
        try:
            # Simulate performance measurement (in production, use actual network testing)
            bandwidth = await self._measure_bandwidth(interface_name)
            latency = await self._measure_latency(interface_name)
            packet_loss = await self._measure_packet_loss(interface_name)
            
            return bandwidth, latency, packet_loss
            
        except Exception as e:
            self._logger.warning(f"Performance measurement failed for {interface_name}: {e}")
            return 100.0, 100.0, 5.0  # Conservative defaults
    
    async def _measure_bandwidth(self, interface_name: str) -> float:
        """Measure interface bandwidth in Mbps."""
        # Simplified bandwidth measurement
        # In production, this would use actual speed testing
        return 500.0
    
    async def _measure_latency(self, interface_name: str) -> float:
        """Measure interface latency in milliseconds."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '3', '-W', '5', '8.8.8.8',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                output = stdout.decode()
                for line in output.split('\n'):
                    if 'avg' in line and '/' in line:
                        parts = line.split('/')
                        if len(parts) >= 4:
                            return float(parts[-2])
            
            return 50.0  # Default latency
            
        except Exception:
            return 100.0
    
    async def _measure_packet_loss(self, interface_name: str) -> float:
        """Measure packet loss percentage."""
        try:
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '10', '-W', '5', '8.8.8.8',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            
            if proc.returncode == 0:
                output = stdout.decode()
                for line in output.split('\n'):
                    if 'packet loss' in line:
                        parts = line.split()
                        for part in parts:
                            if '%' in part:
                                return float(part.replace('%', ''))
            
            return 0.0
            
        except Exception:
            return 2.0
    
    def _calculate_quality_score(self, interface: NetworkInterface) -> float:
        """Calculate overall quality score for interface."""
        bandwidth_score = min(interface.bandwidth_mbps / 1000.0, 1.0) * 40
        latency_score = max(0, (200 - interface.latency_ms) / 200) * 30
        loss_score = max(0, (10 - interface.packet_loss_percent) / 10) * 30
        
        return bandwidth_score + latency_score + loss_score
    
    async def _calculate_interface_score(self, interface: NetworkInterface, requirements: Dict[str, Any]) -> float:
        """Calculate interface score based on specific requirements."""
        base_score = interface.quality_score
        
        # Apply requirement-based scoring
        min_bandwidth = requirements.get('min_bandwidth_mbps', 0)
        max_latency = requirements.get('max_latency_ms', 1000)
        preferred_type = requirements.get('preferred_type')
        
        # Bandwidth requirement penalty
        if interface.bandwidth_mbps < min_bandwidth:
            base_score *= 0.5
        
        # Latency requirement penalty
        if interface.latency_ms > max_latency:
            base_score *= 0.7
        
        # Type preference bonus
        if preferred_type and interface.type.value == preferred_type:
            base_score *= 1.2
        
        # Historical performance consideration
        if interface.name in self._performance_history:
            history = self._performance_history[interface.name]
            if len(history) > 1:
                trend = sum(history[-5:]) / len(history[-5:]) if len(history) >= 5 else sum(history) / len(history)
                trend_factor = trend / 100.0  # Normalize
                base_score *= (0.8 + 0.4 * trend_factor)
        
        return base_score
    
    async def _start_performance_monitoring(self) -> None:
        """Start continuous performance monitoring."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
        
        self._monitoring_task = asyncio.create_task(self._performance_monitoring_loop())
    
    async def _performance_monitoring_loop(self) -> None:
        """Continuous performance monitoring loop."""
        while True:
            try:
                interval = self._config.get('scan_interval_seconds', 60)
                
                for interface_name, interface in self._interfaces.items():
                    try:
                        bandwidth, latency, packet_loss = await self._measure_interface_performance(interface_name)
                        
                        # Update interface metrics
                        interface.bandwidth_mbps = bandwidth
                        interface.latency_ms = latency
                        interface.packet_loss_percent = packet_loss
                        interface.last_updated = datetime.now()
                        interface.quality_score = self._calculate_quality_score(interface)
                        
                        # Update performance history
                        if interface_name not in self._performance_history:
                            self._performance_history[interface_name] = []
                        
                        self._performance_history[interface_name].append(interface.quality_score)
                        
                        # Keep only last 100 measurements
                        if len(self._performance_history[interface_name]) > 100:
                            self._performance_history[interface_name] = self._performance_history[interface_name][-100:]
                        
                        # Check for performance degradation
                        await self._check_performance_degradation(interface)
                        
                    except Exception as e:
                        self._logger.error(f"Performance monitoring failed for {interface_name}: {e}")
                        interface.status = ConnectionStatus.FAILED
                        
                        await self._event_bus.publish(Event(
                            event_type='interface_monitoring_failed',
                            data={'interface_name': interface_name, 'error': str(e)}
                        ))
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Performance monitoring loop error: {e}")
                await asyncio.sleep(60)
    
    async def _check_performance_degradation(self, interface: NetworkInterface) -> None:
        """Check if interface performance has degraded significantly."""
        quality_threshold = self._config.get('quality_threshold', 30)
        
        if interface.quality_score < quality_threshold and interface.status == ConnectionStatus.ACTIVE:
            interface.status = ConnectionStatus.DEGRADED
            
            await self._event_bus.publish(Event(
                event_type='interface_degraded',
                data={
                    'interface_name': interface.name,
                    'quality_score': interface.quality_score,
                    'threshold': quality_threshold
                }
            ))
    
    async def _configure_wifi_interface(self, interface_name: str, config: Dict[str, Any]) -> bool:
        """Configure WiFi 6 specific parameters."""
        # WiFi 6 specific configuration logic
        return True
    
    async def _configure_lte_interface(self, interface_name: str, config: Dict[str, Any]) -> bool:
        """Configure 5G LTE specific parameters."""
        # 5G LTE specific configuration logic
        return True
    
    async def _configure_starlink_interface(self, interface_name: str, config: Dict[str, Any]) -> bool:
        """Configure Starlink specific parameters."""
        # Starlink specific configuration logic
        return True
    
    async def _configure_ethernet_interface(self, interface_name: str, config: Dict[str, Any]) -> bool:
        """Configure Ethernet specific parameters."""
        # Ethernet specific configuration logic
        return True
    
    async def _handle_interface_failure(self, event: Event) -> None:
        """Handle interface failure events."""
        interface_name = event.data.get('interface_name')
        if interface_name in self._interfaces:
            self._interfaces[interface_name].status = ConnectionStatus.FAILED
            self._logger.warning(f"Interface {interface_name} marked as failed")
    
    async def _handle_recovery_request(self, event: Event) -> None:
        """Handle recovery request events."""
        component = event.data.get('component')
        if component == 'network':
            await self._attempt_interface_recovery()
    
    async def _attempt_interface_recovery(self) -> None:
        """Attempt to recover failed interfaces."""
        failed_interfaces = [
            name for name, interface in self._interfaces.items()
            if interface.status == ConnectionStatus.FAILED
        ]
        
        for interface_name in failed_interfaces:
            try:
                # Attempt to test interface
                bandwidth, latency, packet_loss = await self._measure_interface_performance(interface_name)
                
                if bandwidth > 0:  # Interface appears to be working
                    interface = self._interfaces[interface_name]
                    interface.bandwidth_mbps = bandwidth
                    interface.latency_ms = latency
                    interface.packet_loss_percent = packet_loss
                    interface.status = ConnectionStatus.ACTIVE
                    interface.quality_score = self._calculate_quality_score(interface)
                    
                    await self._event_bus.publish(Event(
                        event_type='interface_recovered',
                        data={'interface_name': interface_name}
                    ))
                    
            except Exception as e:
                self._logger.error(f"Interface recovery failed for {interface_name}: {e}")