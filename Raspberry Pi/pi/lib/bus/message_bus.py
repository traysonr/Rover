"""
Simple In-Process Message Bus
Pub/sub for inter-service communication within Pi
"""

import asyncio
from typing import Callable, Dict, List, Any
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Lightweight in-process message bus using asyncio queues.
    For Phase 1 - all services run in same process.
    """
    
    def __init__(self, queue_size: int = 100):
        self.queue_size = queue_size
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._stats: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
    
    async def subscribe(self, topic: str) -> asyncio.Queue:
        """
        Subscribe to a topic.
        Returns a queue that will receive messages for that topic.
        """
        queue = asyncio.Queue(maxsize=self.queue_size)
        async with self._lock:
            self._subscribers[topic].append(queue)
        logger.debug(f"Subscribed to topic: {topic}")
        return queue
    
    async def unsubscribe(self, topic: str, queue: asyncio.Queue):
        """Unsubscribe from a topic"""
        async with self._lock:
            if topic in self._subscribers:
                try:
                    self._subscribers[topic].remove(queue)
                    logger.debug(f"Unsubscribed from topic: {topic}")
                except ValueError:
                    pass
    
    async def publish(self, topic: str, message: Any):
        """
        Publish a message to a topic.
        Non-blocking - drops messages if subscribers are full.
        """
        async with self._lock:
            subscribers = self._subscribers.get(topic, [])
            if not subscribers:
                return
            
            self._stats[f"pub_{topic}"] += 1
            
            # Send to all subscribers
            for queue in subscribers:
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    logger.warning(f"Subscriber queue full for topic: {topic}")
                    self._stats[f"drop_{topic}"] += 1
    
    def get_stats(self) -> Dict[str, int]:
        """Get bus statistics"""
        return dict(self._stats)
    
    def get_topics(self) -> List[str]:
        """Get list of active topics"""
        return list(self._subscribers.keys())


# Global singleton instance
_bus_instance: MessageBus = None


def get_message_bus() -> MessageBus:
    """Get global message bus instance"""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = MessageBus()
    return _bus_instance

