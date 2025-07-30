import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator, List
from datetime import datetime, timedelta
import aioredis
import uuid
from core.interfaces import ITelemetryProcessor
from core.models import TelemetryData, Event, AlertRule, AnalyticsQuery, AnalyticsResult
from core.events import EventBus

class TelemetryProcessor(ITelemetryProcessor):
    
    def __init__(self, config: Dict[str, Any], event_bus: EventBus):
        self._config = config
        self._event_bus = event_bus
        self._redis_client: Optional[aioredis.Redis] = None
        self._processing_queue = asyncio.Queue()
        self._alert_rules: Dict[str, AlertRule] = {}
        self._analytics_cache: Dict[str, Any] = {}
        self._processing_task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)
        
        self._event_bus.subscribe('telemetry_alert_triggered', self._handle_alert)
        self._event_bus.subscribe('high_speed_detected', self._handle_high_speed_alert)
    
    async def initialize(self) -> None:
        try:
            redis_url = self._config.get('redis_url', 'redis://localhost:6379')
            self._redis_client = await aioredis.from_url(redis_url)
            await self._redis_client.ping()
            
            await self._setup_default_alert_rules()
            
            self._processing_task = asyncio.create_task(self._processing_loop())
            
            self._logger.info("Telemetry processor initialized successfully")
            
            await self._event_bus.publish(Event(
                event_type='telemetry_processor_initialized',
                data={'alert_rules': len(self._alert_rules)}
            ))
            
        except Exception as e:
            self._logger.error(f"Telemetry processor initialization failed: {e}")
            raise
    
    async def process_stream(self, data_stream: AsyncGenerator[TelemetryData, None]) -> None:
        try:
            async for telemetry_data in data_stream:
                await self._processing_queue.put(telemetry_data)
                
        except Exception as e:
            self._logger.error(f"Stream processing failed: {e}")
            raise
    
    async def get_analytics(self, query: AnalyticsQuery) -> AnalyticsResult:
        try:
            query_id = str(uuid.uuid4())
            
            cache_key = self._generate_cache_key(query)
            if cache_key in self._analytics_cache:
                cached_result = self._analytics_cache[cache_key]
                if (datetime.now() - cached_result['timestamp']).total_seconds() < 300:
                    return cached_result['result']
            
            data_points = await self._fetch_telemetry_data(query)
            summary = await self._calculate_analytics_summary(data_points, query)
            
            result = AnalyticsResult(
                query_id=query_id,
                data_points=data_points,
                summary=summary,
                generated_at=datetime.now()
            )
            
            self._analytics_cache[cache_key] = {
                'timestamp': datetime.now(),
                'result': result
            }
            
            return result
            
        except Exception as e:
            self._logger.error(f"Analytics generation failed: {e}")
            raise
    
    async def register_alert(self, alert_rule: AlertRule) -> str:
        try:
            self._alert_rules[alert_rule.rule_id] = alert_rule
            
            await self._event_bus.publish(Event(
                event_type='alert_rule_registered',
                data={
                    'rule_id': alert_rule.rule_id,
                    'name': alert_rule.name,
                    'condition': alert_rule.condition
                }
            ))
            
            self._logger.info(f"Alert rule registered: {alert_rule.name}")
            return alert_rule.rule_id
            
        except Exception as e:
            self._logger.error(f"Alert rule registration failed: {e}")
            raise
    
    async def _processing_loop(self) -> None:
        while True:
            try:
                telemetry_data = await asyncio.wait_for(
                    self._processing_queue.get(), 
                    timeout=1.0
                )
                
                await self._process_telemetry_data(telemetry_data)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Processing loop error: {e}")
                await asyncio.sleep(1)
    
    async def _process_telemetry_data(self, data: TelemetryData) -> None:
        try:
            await self._store_telemetry_data(data)
            
            await self._check_alert_rules(data)
            
            await self._update_real_time_analytics(data)
            
            await self._event_bus.publish(Event(
                event_type='telemetry_data_processed',
                data={
                    'train_id': data.train_id,
                    'timestamp': data.timestamp.isoformat(),
                    'speed_kmh': data.speed_kmh,
                    'location': data.location
                }
            ))
            
        except Exception as e:
            self._logger.error(f"Telemetry processing failed: {e}")
    
    async def _store_telemetry_data(self, data: TelemetryData) -> None:
        if not self._redis_client:
            return
        
        stream_key = f"telemetry:{data.train_id}"
        
        telemetry_record = {
            'timestamp': data.timestamp.isoformat(),
            'location_lat': data.location[0],
            'location_lon': data.location[1],
            'speed_kmh': data.speed_kmh,
            'network_metrics': json.dumps(data.network_metrics),
            'system_health': json.dumps(data.system_health),
            'passenger_count': data.passenger_count
        }
        
        if data.route_id:
            telemetry_record['route_id'] = data.route_id
        
        if data.weather_conditions:
            telemetry_record['weather_conditions'] = json.dumps(data.weather_conditions)
        
        await self._redis_client.xadd(stream_key, telemetry_record)
        
        max_length = self._config.get('buffer_size', 10000)
        await self._redis_client.xtrim(stream_key, maxlen=max_length, approximate=True)
        
        latest_key = f"telemetry:latest:{data.train_id}"
        await self._redis_client.setex(
            latest_key,
            3600,
            json.dumps({
                'timestamp': data.timestamp.isoformat(),
                'location': data.location,
                'speed_kmh': data.speed_kmh,
                'network_quality': self._calculate_network_quality(data.network_metrics),
                'system_efficiency': self._calculate_system_efficiency(data.system_health),
                'passenger_count': data.passenger_count
            })
        )
    
    async def _check_alert_rules(self, data: TelemetryData) -> None:
        for rule_id, rule in self._alert_rules.items():
            if not rule.enabled:
                continue
            
            try:
                if await self._evaluate_alert_condition(rule, data):
                    await self._trigger_alert(rule, data)
                    
            except Exception as e:
                self._logger.error(f"Alert rule evaluation failed for {rule_id}: {e}")
    
    async def _evaluate_alert_condition(self, rule: AlertRule, data: TelemetryData) -> bool:
        if rule.condition == 'speed_threshold':
            return data.speed_kmh > rule.threshold
        elif rule.condition == 'network_quality_low':
            network_quality = self._calculate_network_quality(data.network_metrics)
            return network_quality < rule.threshold
        elif rule.condition == 'system_efficiency_low':
            system_efficiency = self._calculate_system_efficiency(data.system_health)
            return system_efficiency < rule.threshold
        elif rule.condition == 'passenger_capacity_high':
            max_capacity = rule.metadata.get('max_capacity', 400)
            return data.passenger_count > (max_capacity * rule.threshold / 100)
        
        return False
    
    async def _trigger_alert(self, rule: AlertRule, data: TelemetryData) -> None:
        await self._event_bus.publish(Event(
            event_type='telemetry_alert_triggered',
            data={
                'rule_id': rule.rule_id,
                'rule_name': rule.name,
                'severity': rule.severity,
                'train_id': data.train_id,
                'condition': rule.condition,
                'threshold': rule.threshold,
                'actual_value': self._get_actual_value(rule, data),
                'timestamp': data.timestamp.isoformat()
            }
        ))
    
    def _get_actual_value(self, rule: AlertRule, data: TelemetryData) -> float:
        if rule.condition == 'speed_threshold':
            return data.speed_kmh
        elif rule.condition == 'network_quality_low':
            return self._calculate_network_quality(data.network_metrics)
        elif rule.condition == 'system_efficiency_low':
            return self._calculate_system_efficiency(data.system_health)
        elif rule.condition == 'passenger_capacity_high':
            return data.passenger_count
        
        return 0.0
    
    def _calculate_network_quality(self, network_metrics: Dict[str, Any]) -> float:
        try:
            bandwidth = network_metrics.get('bandwidth_mbps', 0)
            latency = network_metrics.get('latency_ms', 1000)
            packet_loss = network_metrics.get('packet_loss_percent', 100)
            
            bandwidth_score = min(bandwidth / 1000, 1.0) * 40
            latency_score = max(0, (200 - latency) / 200) * 30
            loss_score = max(0, (10 - packet_loss) / 10) * 30
            
            return bandwidth_score + latency_score + loss_score
        except Exception:
            return 0.0
    
    def _calculate_system_efficiency(self, system_health: Dict[str, Any]) -> float:
        try:
            cpu_usage = system_health.get('cpu_percent', 100)
            memory_usage = system_health.get('memory_percent', 100)
            disk_usage = system_health.get('disk_percent', 100)
            
            cpu_score = max(0, (100 - cpu_usage) / 100) * 40
            memory_score = max(0, (100 - memory_usage) / 100) * 30
            disk_score = max(0, (100 - disk_usage) / 100) * 30
            
            return cpu_score + memory_score + disk_score
        except Exception:
            return 0.0
    
    async def _update_real_time_analytics(self, data: TelemetryData) -> None:
        analytics_key = f"analytics:realtime:{data.train_id}"
        
        analytics_data = {
            'timestamp': data.timestamp.isoformat(),
            'current_speed': data.speed_kmh,
            'network_quality': self._calculate_network_quality(data.network_metrics),
            'system_efficiency': self._calculate_system_efficiency(data.system_health),
            'passenger_density': data.passenger_count / 400,
            'location': data.location
        }
        
        if self._redis_client:
            await self._redis_client.setex(
                analytics_key,
                1800,
                json.dumps(analytics_data)
            )
    
    async def _setup_default_alert_rules(self) -> None:
        default_rules = [
            AlertRule(
                rule_id="speed_high",
                name="High Speed Alert",
                condition="speed_threshold",
                threshold=self._config.get('alerts', {}).get('speed_threshold_kmh', 200),
                severity="warning"
            ),
            AlertRule(
                rule_id="network_quality_low",
                name="Low Network Quality Alert",
                condition="network_quality_low",
                threshold=self._config.get('alerts', {}).get('network_quality_threshold', 30),
                severity="warning"
            ),
            AlertRule(
                rule_id="system_efficiency_low",
                name="Low System Efficiency Alert",
                condition="system_efficiency_low",
                threshold=self._config.get('alerts', {}).get('system_efficiency_threshold', 40),
                severity="critical"
            )
        ]
        
        for rule in default_rules:
            self._alert_rules[rule.rule_id] = rule
    
    def _generate_cache_key(self, query: AnalyticsQuery) -> str:
        key_parts = [
            query.train_id or "all",
            query.start_time.isoformat() if query.start_time else "no_start",
            query.end_time.isoformat() if query.end_time else "no_end",
            "_".join(sorted(query.metrics)) if query.metrics else "all_metrics",
            query.aggregation,
            query.interval
        ]
        return ":".join(key_parts)
    
    async def _fetch_telemetry_data(self, query: AnalyticsQuery) -> List[Dict[str, Any]]:
        if not self._redis_client:
            return []
        
        data_points = []
        
        try:
            end_time = query.end_time or datetime.now()
            start_time = query.start_time or (end_time - timedelta(hours=1))
            
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)
            
            if query.train_id:
                stream_key = f"telemetry:{query.train_id}"
                stream_data = await self._redis_client.xrange(
                    stream_key,
                    min=start_ts,
                    max=end_ts,
                    count=1000
                )
                
                for entry_id, fields in stream_data:
                    data_point = self._parse_stream_entry(fields)
                    if query.metrics:
                        data_point = {k: v for k, v in data_point.items() if k in query.metrics}
                    data_points.append(data_point)
            
            return data_points
            
        except Exception as e:
            self._logger.error(f"Failed to fetch telemetry data: {e}")
            return []
    
    def _parse_stream_entry(self, fields: Dict[bytes, bytes]) -> Dict[str, Any]:
        try:
            data_point = {}
            
            for key, value in fields.items():
                key_str = key.decode('utf-8')
                value_str = value.decode('utf-8')
                
                if key_str in ['network_metrics', 'system_health', 'weather_conditions']:
                    try:
                        data_point[key_str] = json.loads(value_str)
                    except json.JSONDecodeError:
                        data_point[key_str] = {}
                elif key_str in ['location_lat', 'location_lon', 'speed_kmh']:
                    data_point[key_str] = float(value_str)
                elif key_str == 'passenger_count':
                    data_point[key_str] = int(value_str)
                else:
                    data_point[key_str] = value_str
            
            return data_point
            
        except Exception as e:
            self._logger.error(f"Failed to parse stream entry: {e}")
            return {}
    
    async def _calculate_analytics_summary(self, data_points: List[Dict[str, Any]], query: AnalyticsQuery) -> Dict[str, Any]:
        if not data_points:
            return {'error': 'No data points available'}
        
        summary = {
            'total_points': len(data_points),
            'time_range': {
                'start': query.start_time.isoformat() if query.start_time else None,
                'end': query.end_time.isoformat() if query.end_time else None
            },
            'metrics': {}
        }
        
        numeric_fields = ['speed_kmh', 'location_lat', 'location_lon', 'passenger_count']
        
        for field in numeric_fields:
            values = [point.get(field) for point in data_points if point.get(field) is not None]
            
            if values:
                summary['metrics'][field] = {
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                    'count': len(values)
                }
        
        return summary
    
    async def _handle_alert(self, event: Event) -> None:
        rule_name = event.data.get('rule_name')
        severity = event.data.get('severity')
        train_id = event.data.get('train_id')
        
        self._logger.warning(f"Alert triggered: {rule_name} for train {train_id} (severity: {severity})")
    
    async def _handle_high_speed_alert(self, event: Event) -> None:
        train_id = event.data.get('train_id')
        speed_kmh = event.data.get('speed_kmh')
        
        self._logger.info(f"High speed detected for train {train_id}: {speed_kmh} km/h")
        
        await self._event_bus.publish(Event(
            event_type='enhanced_monitoring_requested',
            data={
                'train_id': train_id,
                'reason': 'high_speed_detected',
                'monitoring_duration_minutes': 30
            }
        ))