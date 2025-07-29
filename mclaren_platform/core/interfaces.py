from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from datetime import datetime
from enum import Enum

class NetworkType(Enum):
    WIFI_6 = "wifi6"
    LTE_5G = "5g_lte"
    STARLINK = "starlink"
    GNSS = "gnss"
    ETHERNET = "ethernet"

class ConnectionStatus(Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"
    RECOVERING = "recovering"

class SecurityLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class INetworkProvider(ABC):
    """Interface for network connectivity providers."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the network provider."""
        pass
    
    @abstractmethod
    async def get_interfaces(self) -> List['NetworkInterface']:
        """Get available network interfaces."""
        pass
    
    @abstractmethod
    async def test_performance(self, interface_name: str) -> Tuple[float, float, float]:
        """Test network performance: bandwidth, latency, packet_loss."""
        pass
    
    @abstractmethod
    async def configure_interface(self, interface_name: str, config: Dict[str, Any]) -> bool:
        """Configure network interface with specific parameters."""
        pass

class IContainerOrchestrator(ABC):
    """Interface for container orchestration systems."""
    
    @abstractmethod
    async def deploy_workload(self, spec: 'WorkloadSpec') -> 'DeploymentResult':
        """Deploy a containerized workload."""
        pass
    
    @abstractmethod
    async def update_workload(self, name: str, new_spec: 'WorkloadSpec') -> 'UpdateResult':
        """Update an existing workload."""
        pass
    
    @abstractmethod
    async def get_workload_status(self, name: str) -> 'WorkloadStatus':
        """Get comprehensive status of a workload."""
        pass
    
    @abstractmethod
    async def scale_workload(self, name: str, replicas: int) -> bool:
        """Scale workload to specified number of replicas."""
        pass

class ITelemetryProcessor(ABC):
    """Interface for telemetry data processing."""
    
    @abstractmethod
    async def process_stream(self, data_stream: AsyncGenerator['TelemetryData', None]) -> None:
        """Process continuous telemetry data stream."""
        pass
    
    @abstractmethod
    async def get_analytics(self, query: 'AnalyticsQuery') -> 'AnalyticsResult':
        """Get analytics based on query parameters."""
        pass
    
    @abstractmethod
    async def register_alert(self, alert_rule: 'AlertRule') -> str:
        """Register alert rule and return rule ID."""
        pass

class ISecurityProvider(ABC):
    """Interface for security and compliance services."""
    
    @abstractmethod
    async def scan_vulnerabilities(self, scan_request: 'ScanRequest') -> 'ScanResult':
        """Perform security vulnerability scan."""
        pass
    
    @abstractmethod
    async def check_compliance(self, framework: str) -> 'ComplianceResult':
        """Check compliance against specific framework."""
        pass
    
    @abstractmethod
    async def encrypt_data(self, data: bytes, context: Dict[str, str]) -> bytes:
        """Encrypt sensitive data with context."""
        pass
    
    @abstractmethod
    async def audit_event(self, event: 'SecurityEvent') -> None:
        """Log security event for audit trail."""
        pass

class IFaultToleranceProvider(ABC):
    """Interface for fault tolerance and recovery services."""
    
    @abstractmethod
    async def register_circuit_breaker(self, config: 'CircuitBreakerConfig') -> 'CircuitBreaker':
        """Register new circuit breaker with configuration."""
        pass
    
    @abstractmethod
    async def execute_with_protection(self, func, circuit_breaker_name: str, *args, **kwargs):
        """Execute function with fault tolerance protection."""
        pass
    
    @abstractmethod
    async def trigger_recovery(self, component: str, failure_type: str) -> 'RecoveryResult':
        """Trigger recovery procedure for failed component."""
        pass

class IEventBus(ABC):
    """Interface for event communication system."""
    
    @abstractmethod
    async def publish(self, event: 'Event') -> None:
        """Publish event to subscribers."""
        pass
    
    @abstractmethod
    def subscribe(self, event_type: str, handler) -> str:
        """Subscribe to event type and return subscription ID."""
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from event type."""
        pass
