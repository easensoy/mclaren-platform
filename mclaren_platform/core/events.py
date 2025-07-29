import asyncio
import logging
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime
import uuid
from .interfaces import IEventBus
from .models import Event

class EventBus(IEventBus):
    """Event bus implementation for decoupled component communication."""
    
    def __init__(self):
        self._subscribers: Dict[str, Dict[str, Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._logger = logging.getLogger(__name__)
    
    async def publish(self, event: Event) -> None:
        """Publish event to all registered subscribers."""
        try:
            # Add to event history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]
            
            # Notify subscribers
            if event.event_type in self._subscribers:
                tasks = []
                for subscription_id, handler in self._subscribers[event.event_type].items():
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            tasks.append(asyncio.create_task(handler(event)))
                        else:
                            handler(event)
                    except Exception as e:
                        self._logger.error(f"Event handler error for {subscription_id}: {e}")
                
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            
            self._logger.debug(f"Published event: {event.event_type}")
            
        except Exception as e:
            self._logger.error(f"Event publishing failed: {e}")
    
    def subscribe(self, event_type: str, handler: Callable) -> str:
        """Subscribe to event type and return subscription ID."""
        subscription_id = str(uuid.uuid4())
        
        if event_type not in self._subscribers:
            self._subscribers[event_type] = {}
        
        self._subscribers[event_type][subscription_id] = handler
        self._logger.debug(f"Subscribed {subscription_id} to {event_type}")
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> None:
        """Remove subscription by ID."""
        for event_type, subscribers in self._subscribers.items():
            if subscription_id in subscribers:
                del subscribers[subscription_id]
                self._logger.debug(f"Unsubscribed {subscription_id} from {event_type}")
                break
    
    def get_event_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """Get recent event history, optionally filtered by type."""
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]