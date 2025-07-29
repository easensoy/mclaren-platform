import asyncio
import signal
import sys
import logging
from pathlib import Path

from .platform.orchestrator import PlatformOrchestrator
from .core.models import TelemetryData
from datetime import datetime
from typing import Optional

class McLarenPlatformLauncher:
    """Main launcher for the McLaren Applied Communication Platform."""
    
    def __init__(self):
        self.platform: Optional[PlatformOrchestrator] = None
        self.shutdown_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        if sys.platform != 'win32':
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self.signal_handler)
    
    def signal_handler(self):
        """Handle shutdown signals."""
        self.logger.info("Shutdown signal received")
        self.shutdown_event.set()
    
    async def run(self, config_path: Optional[str] = None):
        """Run the complete McLaren platform."""
        try:
            # Initialize platform
            self.platform = PlatformOrchestrator(config_path)
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Initialize and start platform
            await self.platform.initialize()
            
            # Start platform in background
            platform_task = asyncio.create_task(self.platform.start())
            
            # Simulate telemetry data (in production, this would come from real sensors)
            telemetry_task = asyncio.create_task(self.simulate_telemetry_data())
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Graceful shutdown
            self.logger.info("Initiating graceful shutdown...")
            
            # Cancel tasks
            telemetry_task.cancel()
            
            # Stop platform
            await self.platform.stop()
            
            # Wait for platform task to complete
            try:
                await asyncio.wait_for(platform_task, timeout=30.0)
            except asyncio.TimeoutError:
                self.logger.warning("Platform shutdown timed out")
                platform_task.cancel()
            
            self.logger.info("Platform shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Platform execution failed: {e}")
            raise
    
    async def simulate_telemetry_data(self):
        """Simulate telemetry data for demonstration purposes."""
        train_id = "TRAIN_001"
        base_location = (51.5074, -0.1278)  # London coordinates
        
        while True:
            try:
                # Create sample telemetry data
                telemetry = TelemetryData(
                    timestamp=datetime.now(),
                    train_id=train_id,
                    location=base_location,
                    speed_kmh=85.0 + (asyncio.get_event_loop().time() % 50),  # Varying speed
                    network_metrics={
                        'bandwidth_mbps': 450 + (asyncio.get_event_loop().time() % 100),
                        'latency_ms': 30 + (asyncio.get_event_loop().time() % 20),
                        'packet_loss_percent': 0.1 + (asyncio.get_event_loop().time() % 2)
                    },
                    system_health={
                        'cpu_percent': 40 + (asyncio.get_event_loop().time() % 30),
                        'memory_percent': 60 + (asyncio.get_event_loop().time() % 20),
                        'disk_percent': 25 + (asyncio.get_event_loop().time() % 10)
                    },
                    passenger_count=150
                )
                
                # Process telemetry through platform
                if self.platform:
                    await self.platform.process_telemetry_data(telemetry)
                
                await asyncio.sleep(5)  # Send telemetry every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Telemetry simulation error: {e}")
                await asyncio.sleep(5)

async def main():
    """Main entry point for the McLaren platform."""
    
    # Setup basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting McLaren Applied Communication Platform...")
    
    # Determine config path
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        if not Path(config_path).exists():
            logger.error(f"Config path does not exist: {config_path}")
            sys.exit(1)
    
    # Create and run platform launcher
    launcher = McLarenPlatformLauncher()
    
    try:
        await launcher.run(config_path)
    except KeyboardInterrupt:
        logger.info("Platform stopped by user")
    except Exception as e:
        logger.error(f"Platform failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPlatform interrupted by user")
    except Exception as e:
        print(f"Platform execution failed: {e}")
        sys.exit(1)