import asyncio
import logging
from typing import Dict, Any, Callable, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
from core.models import Event
from core.events import EventBus

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    timeout_seconds: int = 60
    half_open_max_calls: int = 3
    success_threshold: int = 1

class CircuitBreakerOpenException(Exception):
    pass

class CircuitBreaker:
    
    def __init__(self, name: str, config: CircuitBreakerConfig, event_bus: Optional[EventBus] = None):
        self.name = name
        self.config = config
        self.event_bus = event_bus
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time = datetime.now()
        
        self._logger = logging.getLogger(__name__)
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
            else:
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} is open")
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpenException(f"Circuit breaker {self.name} half-open call limit exceeded")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
            
        except Exception as e:
            await self._on_failure(e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return False
        
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.timeout_seconds
    
    def _transition_to_half_open(self) -> None:
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        self._logger.info(f"Circuit breaker {self.name} transitioned to half-open")
    
    async def _on_success(self) -> None:
        self.last_success_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            self.success_count += 1
            
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0
    
    async def _on_failure(self, exception: Exception) -> None:
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        
        if self.event_bus:
            await self.event_bus.publish(Event(
                event_type='circuit_breaker_failure',
                data={
                    'circuit_breaker': self.name,
                    'failure_count': self.failure_count,
                    'state': self.state.value,
                    'error': str(exception)
                }
            ))
    
    def _transition_to_closed(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0
        
        self._logger.info(f"Circuit breaker {self.name} closed after successful recovery")
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(Event(
                event_type='circuit_breaker_closed',
                data={'circuit_breaker': self.name}
            )))
    
    def _transition_to_open(self) -> None:
        self.state = CircuitState.OPEN
        self.success_count = 0
        self.half_open_calls = 0
        
        self._logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
        
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(Event(
                event_type='circuit_breaker_opened',
                data={
                    'circuit_breaker': self.name,
                    'failure_count': self.failure_count
                }
            )))
    
    def get_status(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.config.failure_threshold,
            'timeout_seconds': self.config.timeout_seconds,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None,
            'last_success_time': self.last_success_time.isoformat(),
            'half_open_calls': self.half_open_calls if self.state == CircuitState.HALF_OPEN else 0
        }