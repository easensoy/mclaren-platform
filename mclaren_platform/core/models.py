from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union, AsyncGenerator
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

@dataclass
class Event:
    event_type: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    correlation_id: Optional[str] = None

@dataclass
class NetworkInterface:
    name: str
    type: NetworkType
    ip_address: str
    bandwidth_mbps: float
    latency_ms: float
    packet_loss_percent: float
    status: ConnectionStatus
    last_updated: datetime
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class TelemetryData:
    timestamp: datetime
    train_id: str
    location: Tuple[float, float]
    speed_kmh: float
    network_metrics: Dict[str, Any]
    system_health: Dict[str, Any]
    passenger_count: int
    route_id: Optional[str] = None
    weather_conditions: Optional[Dict[str, Any]] = None

@dataclass
class WorkloadSpec:
    name: str
    image: str
    replicas: int = 1
    resources: Dict[str, str] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    ports: List[int] = field(default_factory=list)
    volumes: Dict[str, str] = field(default_factory=dict)
    restart_policy: str = "unless-stopped"

@dataclass
class DeploymentResult:
    success: bool
    workload_id: str
    message: str
    deployed_at: datetime
    endpoints: List[str] = field(default_factory=list)

@dataclass
class WorkloadStatus:
    name: str
    status: str
    replicas_running: int
    replicas_desired: int
    cpu_usage_percent: float
    memory_usage_mb: float
    network_io: Dict[str, int]
    uptime_seconds: float
    last_updated: datetime

@dataclass
class SecurityEvent:
    timestamp: datetime
    event_type: str
    severity: SecurityLevel
    source_ip: str
    description: str
    user_id: Optional[str] = None
    resolved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class UpdateResult:
    success: bool
    message: str
    rollback_performed: bool
    updated_at: datetime = field(default_factory=datetime.now)

@dataclass
class ScanRequest:
    targets: List[str]
    scan_type: str = "comprehensive"
    include_network: bool = True
    include_system: bool = True
    timeout_seconds: int = 300

@dataclass 
class ScanResult:
    scan_id: str
    targets_scanned: List[str]
    vulnerabilities: Dict[str, List[Dict[str, Any]]]
    scan_duration_seconds: float
    completed_at: datetime
    summary: Dict[str, int]

@dataclass
class ComplianceResult:
    framework: str
    overall_status: str
    checks_passed: int
    total_checks: int
    issues: List[Dict[str, Any]]
    last_checked: datetime
    next_check_due: datetime

@dataclass
class AlertRule:
    rule_id: str
    name: str
    condition: str
    threshold: Union[int, float]
    severity: str
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnalyticsQuery:
    train_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metrics: List[str] = field(default_factory=list)
    aggregation: str = "average"
    interval: str = "5m"

@dataclass
class AnalyticsResult:
    query_id: str
    data_points: List[Dict[str, Any]]
    summary: Dict[str, Any]
    generated_at: datetime

@dataclass
class RecoveryResult:
    component: str
    recovery_strategy: str
    success: bool
    message: str
    recovery_time_seconds: float
    attempted_at: datetime