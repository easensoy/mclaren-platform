import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..core.config import ConfigurationManager
from ..core.events import EventBus, Event
from ..core.models import TelemetryData
from ..networking.aggregation_engine import NetworkAggregationEngine
from ..edge.container_manager import ContainerManager
from ..fault_tolerance.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

class PlatformOrchestrator:
    """
    Main orchestrator for the McLaren Applied Communication Platform.
    Coordinates all subsystems and manages platform lifecycle.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # Core services
        self._config = ConfigurationManager()
        self._event_bus = EventBus()
        self._logger = self._setup_logging()
        
        # Subsystem components
        self._network_engine: Optional[NetworkAggregationEngine] = None
        self._container_manager: Optional[ContainerManager] = None
        
        # Circuit breakers for fault tolerance
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Platform state
        self._initialized = False
        self._running = False
        self._start_time: Optional[datetime] = None
        self._background_tasks: List[asyncio.Task] = []
        
        # Setup platform event handlers
        self._setup_event_handlers()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup centralized logging configuration."""
        log_level = self._config.get('logging.level', 'INFO')
        log_file = self._config.get('logging.file', 'mclaren_platform.log')
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        return logging.getLogger(__name__)
    
    def _setup_event_handlers(self) -> None:
        """Setup platform-level event handlers for coordination."""
        self._event_bus.subscribe('component_failure', self._handle_component_failure)
        self._event_bus.subscribe('critical_alert', self._handle_critical_alert)
        self._event_bus.subscribe('platform_shutdown_requested', self._handle_shutdown_request)
        self._event_bus.subscribe('telemetry_data_received', self._handle_telemetry_data)
        self._event_bus.subscribe('network_degraded', self._handle_network_degradation)
        self._event_bus.subscribe('workload_unhealthy', self._handle_workload_health_issue)
    
    async def initialize(self) -> None:
        """Initialize all platform components in proper dependency order."""
        if self._initialized:
            self._logger.warning("Platform already initialized")
            return
        
        try:
            self._logger.info("Initializing McLaren Communication Platform...")
            
            # Initialize fault tolerance first
            await self._initialize_circuit_breakers()
            
            # Initialize core subsystems
            await self._initialize_network_engine()
            await self._initialize_container_manager()
            
            self._initialized = True
            self._logger.info("Platform initialization completed successfully")
            
            await self._event_bus.publish(Event(
                event_type='platform_initialized',
                data={
                    'timestamp': datetime.now().isoformat(),
                    'components': ['network', 'containers', 'fault_tolerance'],
                    'circuit_breakers': len(self._circuit_breakers)
                }
            ))
            
        except Exception as e:
            self._logger.error(f"Platform initialization failed: {e}")
            await self._cleanup_partial_initialization()
            raise
    
    async def start(self) -> None:
        """Start platform operations and background monitoring."""
        if not self._initialized:
            raise RuntimeError("Platform must be initialized before starting")
        
        if self._running:
            self._logger.warning("Platform already running")
            return
        
        try:
            self._logger.info("Starting platform operations...")
            self._start_time = datetime.now()
            self._running = True
            
            # Start background monitoring tasks
            self._background_tasks = [
                asyncio.create_task(self._health_monitoring_loop()),
                asyncio.create_task(self._performance_monitoring_loop()),
                asyncio.create_task(self._coordination_loop())
            ]
            
            await self._event_bus.publish(Event(
                event_type='platform_started',
                data={
                    'timestamp': self._start_time.isoformat(),
                    'background_tasks': len(self._background_tasks)
                }
            ))
            
            self._logger.info("Platform operations started successfully")
            
            # Wait for background tasks (they run indefinitely)
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
        except Exception as e:
            self._logger.error(f"Platform startup failed: {e}")
            self._running = False
            raise
    
    async def stop(self) -> None:
        """Stop platform operations gracefully."""
        if not self._running:
            self._logger.warning("Platform is not running")
            return
        
        try:
            self._logger.info("Stopping platform operations...")
            self._running = False
            
            # Cancel background tasks
            for task in self._background_tasks:
                task.cancel()
            
            # Wait for tasks to complete cancellation
            if self._background_tasks:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
            
            await self._event_bus.publish(Event(
                event_type='platform_stopped',
                data={'timestamp': datetime.now().isoformat()}
            ))
            
            self._logger.info("Platform stopped successfully")
            
        except Exception as e:
            self._logger.error(f"Platform shutdown error: {e}")
    
    async def get_platform_status(self) -> Dict[str, Any]:
        """Get comprehensive platform status and health information."""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'initialized': self._initialized,
                'running': self._running,
                'uptime_seconds': 0,
                'components': {},
                'circuit_breakers': {},
                'health': 'unknown',
                'performance_metrics': {}
            }
            
            if self._start_time:
                status['uptime_seconds'] = (datetime.now() - self._start_time).total_seconds()
            
            # Collect component statuses
            if self._network_engine:
                interfaces = await self._network_engine.get_interfaces()
                status['components']['network'] = {
                    'total_interfaces': len(interfaces),
                    'active_interfaces': len([i for i in interfaces if i.status.value == 'active']),
                    'degraded_interfaces': len([i for i in interfaces if i.status.value == 'degraded']),
                    'average_quality': sum(i.quality_score for i in interfaces) / len(interfaces) if interfaces else 0
                }
            
            if self._container_manager:
                workload_count = len(self._container_manager._workload_registry)
                status['components']['containers'] = {
                    'managed_workloads': workload_count,
                    'total_containers': sum(
                        len(info['container_ids']) 
                        for info in self._container_manager._workload_registry.values()
                    )
                }
            
            # Collect circuit breaker statuses
            for name, cb in self._circuit_breakers.items():
                status['circuit_breakers'][name] = cb.get_status()
            
            # Calculate overall health
            status['health'] = self._calculate_overall_health(status)
            
            return status
            
        except Exception as e:
            self._logger.error(f"Status collection failed: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'health': 'error'
            }
    
    async def process_telemetry_data(self, telemetry_data: TelemetryData) -> None:
        """Process incoming telemetry data through the platform."""
        try:
            await self._event_bus.publish(Event(
                event_type='telemetry_data_received',
                data={
                    'train_id': telemetry_data.train_id,
                    'timestamp': telemetry_data.timestamp.isoformat(),
                    'speed_kmh': telemetry_data.speed_kmh,
                    'passenger_count': telemetry_data.passenger_count
                }
            ))
            
        except Exception as e:
            self._logger.error(f"Telemetry processing failed: {e}")
    
    async def _initialize_circuit_breakers(self) -> None:
        """Initialize circuit breakers for all critical components."""
        circuit_breaker_configs = self._config.get_section('circuit_breakers')
        
        default_config = CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=60,
            half_open_max_calls=3
        )
        
        components = ['network', 'containers', 'telemetry', 'security']
        
        for component in components:
            config = circuit_breaker_configs.get(component, {})
            
            cb_config = CircuitBreakerConfig(
                failure_threshold=config.get('failure_threshold', default_config.failure_threshold),
                timeout_seconds=config.get('timeout_seconds', default_config.timeout_seconds),
                half_open_max_calls=config.get('half_open_max_calls', default_config.half_open_max_calls)
            )
            
            self._circuit_breakers[component] = CircuitBreaker(
                name=component,
                config=cb_config,
                event_bus=self._event_bus
            )
        
        self._logger.info(f"Initialized {len(self._circuit_breakers)} circuit breakers")
    
    async def _initialize_network_engine(self) -> None:
        """Initialize network aggregation engine with circuit breaker protection."""
        network_config = self._config.get_section('network')
        self._network_engine = NetworkAggregationEngine(network_config, self._event_bus)
        
        await self._circuit_breakers['network'].execute(
            self._network_engine.initialize
        )
    
    async def _initialize_container_manager(self) -> None:
        """Initialize container management with circuit breaker protection."""
        container_config = self._config.get_section('containers')
        self._container_manager = ContainerManager(container_config, self._event_bus)
        
        await self._circuit_breakers['containers'].execute(
            self._container_manager.initialize
        )
    
    async def _cleanup_partial_initialization(self) -> None:
        """Clean up after partial initialization failure."""
        self._logger.info("Cleaning up partial initialization...")
        
        # Stop any running background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        
        self._initialized = False
        self._running = False
    
    async def _health_monitoring_loop(self) -> None:
        """Continuous health monitoring of all platform components."""
        while self._running:
            try:
                interval = self._config.get('monitoring.health_check_interval', 30)
                
                # Check network engine health
                if self._network_engine:
                    await self._check_network_health()
                
                # Check container manager health
                if self._container_manager:
                    await self._check_container_health()
                
                # Check circuit breaker states
                await self._check_circuit_breaker_health()
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(30)
    
    async def _performance_monitoring_loop(self) -> None:
        """Continuous performance monitoring and optimization."""
        while self._running:
            try:
                interval = self._config.get('monitoring.performance_check_interval', 60)
                
                # Collect performance metrics
                metrics = await self._collect_performance_metrics()
                
                # Publish performance data
                await self._event_bus.publish(Event(
                    event_type='performance_metrics_collected',
                    data=metrics
                ))
                
                # Check for performance degradation
                await self._analyze_performance_trends(metrics)
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Performance monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _coordination_loop(self) -> None:
        """Coordination loop for cross-component optimization."""
        while self._running:
            try:
                interval = self._config.get('coordination.optimization_interval', 120)
                
                # Coordinate network and container optimization
                await self._optimize_resource_allocation()
                
                # Balance load across network interfaces
                await self._optimize_network_load_balancing()
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Coordination loop error: {e}")
                await asyncio.sleep(120)
    
    async def _check_network_health(self) -> None:
        """Check network engine health and trigger alerts if needed."""
        try:
            interfaces = await self._network_engine.get_interfaces()
            
            active_count = len([i for i in interfaces if i.status.value == 'active'])
            total_count = len(interfaces)
            
            if total_count > 0 and active_count / total_count < 0.5:
                await self._event_bus.publish(Event(
                    event_type='network_health_critical',
                    data={
                        'active_interfaces': active_count,
                        'total_interfaces': total_count,
                        'health_ratio': active_count / total_count
                    }
                ))
                
        except Exception as e:
            self._logger.error(f"Network health check failed: {e}")
    
    async def _check_container_health(self) -> None:
        """Check container manager health and workload status."""
        try:
            workload_registry = self._container_manager._workload_registry
            
            for workload_name in workload_registry.keys():
                try:
                    status = await self._container_manager.get_workload_status(workload_name)
                    
                    if status.replicas_running < status.replicas_desired:
                        await self._event_bus.publish(Event(
                            event_type='workload_health_degraded',
                            data={
                                'workload_name': workload_name,
                                'running_replicas': status.replicas_running,
                                'desired_replicas': status.replicas_desired
                            }
                        ))
                        
                except Exception as e:
                    self._logger.error(f"Workload health check failed for {workload_name}: {e}")
                    
        except Exception as e:
            self._logger.error(f"Container health check failed: {e}")
    
    async def _check_circuit_breaker_health(self) -> None:
        """Check circuit breaker states and trigger alerts for open breakers."""
        open_breakers = [
            name for name, cb in self._circuit_breakers.items()
            if cb.state.value == 'open'
        ]
        
        if open_breakers:
            await self._event_bus.publish(Event(
                event_type='circuit_breakers_open',
                data={'open_breakers': open_breakers}
            ))
    
    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive performance metrics from all components."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'network': {},
            'containers': {},
            'platform': {
                'uptime_seconds': (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
                'active_tasks': len([t for t in self._background_tasks if not t.done()])
            }
        }
        
        # Network metrics
        if self._network_engine:
            interfaces = await self._network_engine.get_interfaces()
            if interfaces:
                metrics['network'] = {
                    'average_quality': sum(i.quality_score for i in interfaces) / len(interfaces),
                    'average_bandwidth': sum(i.bandwidth_mbps for i in interfaces) / len(interfaces),
                    'average_latency': sum(i.latency_ms for i in interfaces) / len(interfaces)
                }
        
        # Container metrics
        if self._container_manager:
            workload_registry = self._container_manager._workload_registry
            if workload_registry:
                total_cpu = 0
                total_memory = 0
                workload_count = 0
                
                for workload_name in workload_registry.keys():
                    try:
                        status = await self._container_manager.get_workload_status(workload_name)
                        total_cpu += status.cpu_usage_percent
                        total_memory += status.memory_usage_mb
                        workload_count += 1
                    except:
                        pass
                
                if workload_count > 0:
                    metrics['containers'] = {
                        'average_cpu_percent': total_cpu / workload_count,
                        'total_memory_mb': total_memory,
                        'workload_count': workload_count
                    }
        
        return metrics
    
    async def _analyze_performance_trends(self, metrics: Dict[str, Any]) -> None:
        """Analyze performance trends and trigger optimization if needed."""
        # Network performance analysis
        network_metrics = metrics.get('network', {})
        avg_quality = network_metrics.get('average_quality', 0)
        
        if avg_quality < 50:  # Quality threshold
            await self._event_bus.publish(Event(
                event_type='network_performance_degraded',
                data={'average_quality': avg_quality}
            ))
        
        # Container performance analysis
        container_metrics = metrics.get('containers', {})
        avg_cpu = container_metrics.get('average_cpu_percent', 0)
        
        if avg_cpu > 80:  # CPU threshold
            await self._event_bus.publish(Event(
                event_type='container_performance_degraded',
                data={'average_cpu_percent': avg_cpu}
            ))
    
    async def _optimize_resource_allocation(self) -> None:
        """Optimize resource allocation between network and container workloads."""
        try:
            # Get current resource utilization
            if self._network_engine and self._container_manager:
                interfaces = await self._network_engine.get_interfaces()
                high_quality_interfaces = [i for i in interfaces if i.quality_score > 70]
                
                # If we have high-quality network interfaces, scale up workloads
                if len(high_quality_interfaces) > 2:
                    await self._event_bus.publish(Event(
                        event_type='scale_up_opportunity',
                        data={'high_quality_interfaces': len(high_quality_interfaces)}
                    ))
                    
        except Exception as e:
            self._logger.error(f"Resource optimization failed: {e}")
    
    async def _optimize_network_load_balancing(self) -> None:
        """Optimize load balancing across available network interfaces."""
        try:
            if self._network_engine:
                interfaces = await self._network_engine.get_interfaces()
                active_interfaces = [i for i in interfaces if i.status.value == 'active']
                
                if len(active_interfaces) > 1:
                    # Find optimal interface for current conditions
                    optimal_interface = await self._network_engine.select_optimal_interface({
                        'min_bandwidth_mbps': 100,
                        'max_latency_ms': 100
                    })
                    
                    if optimal_interface:
                        await self._event_bus.publish(Event(
                            event_type='optimal_interface_selected',
                            data={
                                'interface_name': optimal_interface.name,
                                'quality_score': optimal_interface.quality_score
                            }
                        ))
                        
        except Exception as e:
            self._logger.error(f"Network load balancing optimization failed: {e}")
    
    def _calculate_overall_health(self, status: Dict[str, Any]) -> str:
        """Calculate overall platform health based on component status."""
        if not status['initialized'] or not status['running']:
            return 'stopped'
        
        # Check circuit breakers
        open_breakers = [
            name for name, cb_status in status['circuit_breakers'].items()
            if cb_status['state'] == 'open'
        ]
        
        if open_breakers:
            return 'critical'
        
        # Check component health
        network_health = status['components'].get('network', {})
        active_interfaces = network_health.get('active_interfaces', 0)
        total_interfaces = network_health.get('total_interfaces', 1)
        
        if total_interfaces > 0 and active_interfaces / total_interfaces < 0.5:
            return 'degraded'
        
        container_health = status['components'].get('containers', {})
        managed_workloads = container_health.get('managed_workloads', 0)
        
        if managed_workloads == 0:
            return 'degraded'
        
        return 'healthy'
    
    async def _handle_component_failure(self, event: Event) -> None:
        """Handle component failure events with recovery coordination."""
        component = event.data.get('component')
        error = event.data.get('error')
        
        self._logger.error(f"Component failure in {component}: {error}")
        
        # Coordinate recovery based on component type
        if component == 'network':
            await self._coordinate_network_recovery()
        elif component == 'containers':
            await self._coordinate_container_recovery()
        
        await self._event_bus.publish(Event(
            event_type='recovery_coordination_started',
            data={'failed_component': component}
        ))
    
    async def _handle_critical_alert(self, event: Event) -> None:
        """Handle critical system alerts requiring immediate attention."""
        alert_type = event.data.get('type')
        message = event.data.get('message')
        
        self._logger.critical(f"Critical alert: {alert_type} - {message}")
        
        # Implement critical alert handling logic
        # This could include emergency shutdown, notifications, etc.
    
    async def _handle_shutdown_request(self, event: Event) -> None:
        """Handle platform shutdown requests."""
        reason = event.data.get('reason', 'Unknown')
        self._logger.info(f"Shutdown requested: {reason}")
        
        # Initiate graceful shutdown
        await self.stop()
    
    async def _handle_telemetry_data(self, event: Event) -> None:
        """Handle incoming telemetry data and coordinate processing."""
        train_id = event.data.get('train_id')
        speed_kmh = event.data.get('speed_kmh')
        
        # Coordinate telemetry processing across components
        if speed_kmh > 200:  # High speed threshold
            await self._event_bus.publish(Event(
                event_type='high_speed_detected',
                data={
                    'train_id': train_id,
                    'speed_kmh': speed_kmh,
                    'requires_enhanced_monitoring': True
                }
            ))
    
    async def _handle_network_degradation(self, event: Event) -> None:
        """Handle network degradation by coordinating with container workloads."""
        degraded_interfaces = event.data.get('degraded_interfaces', [])
        
        self._logger.warning(f"Network degradation detected on interfaces: {degraded_interfaces}")
        
        # Reduce container workload if network performance is poor
        if len(degraded_interfaces) > 1:
            await self._event_bus.publish(Event(
                event_type='reduce_workload_recommended',
                data={'reason': 'network_degradation'}
            ))
    
    async def _handle_workload_health_issue(self, event: Event) -> None:
        """Handle workload health issues by coordinating recovery."""
        workload_name = event.data.get('workload_name')
        
        self._logger.warning(f"Workload health issue detected: {workload_name}")
        
        # Check if network issues are contributing to workload problems
        if self._network_engine:
            interfaces = await self._network_engine.get_interfaces()
            healthy_interfaces = [i for i in interfaces if i.status.value == 'active' and i.quality_score > 50]
            
            if len(healthy_interfaces) < 2:
                await self._event_bus.publish(Event(
                    event_type='workload_health_network_related',
                    data={
                        'workload_name': workload_name,
                        'healthy_interfaces': len(healthy_interfaces)
                    }
                ))
    
    async def _coordinate_network_recovery(self) -> None:
        """Coordinate network recovery procedures."""
        try:
            if self._network_engine:
                # Attempt to reinitialize network interfaces
                await self._circuit_breakers['network'].execute(
                    self._network_engine.initialize
                )
                
        except Exception as e:
            self._logger.error(f"Network recovery coordination failed: {e}")
    
    async def _coordinate_container_recovery(self) -> None:
        """Coordinate container recovery procedures."""
        try:
            if self._container_manager:
                # Restart failed workloads
                workload_registry = self._container_manager._workload_registry
                
                for workload_name in workload_registry.keys():
                    status = await self._container_manager.get_workload_status(workload_name)
                    
                    if status.replicas_running == 0:
                        spec = workload_registry[workload_name]['spec']
                        await self._container_manager.deploy_workload(spec)
                        
        except Exception as e:
            self._logger.error(f"Container recovery coordination failed: {e}")
    
    async def _generate_periodic_reports(self) -> None:
        """Generate periodic monitoring reports and visualizations."""
        while self._running:
            try:
                # Generate dashboard every 5 minutes
                await self._data_visualizer.generate_platform_dashboard()
                
                # Update Prometheus metrics
                await self._prometheus_metrics.update_system_metrics()
                
                if self._network_engine:
                    interfaces = await self._network_engine.get_interfaces()
                    self._prometheus_metrics.update_network_interface_metrics(interfaces)
                
                # Network analysis every 10 minutes
                await self._network_analyzer.start_packet_capture(duration=30)
                analysis = self._network_analyzer.analyze_traffic_patterns()
                
                if analysis and 'error' not in analysis:
                    self._network_analyzer.generate_traffic_visualizations()
                
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                self._logger.error(f"Periodic report generation failed: {e}")
                await asyncio.sleep(300)