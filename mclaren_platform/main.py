import asyncio
import signal
import sys
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from .platform.orchestrator import PlatformOrchestrator
from .core.models import TelemetryData
from datetime import datetime

try:
    from .monitoring.dashboard import McLarenMonitor
    from .monitoring.prometheus_metrics import start_prometheus_server
    from .monitoring.metrics_collector import start_metrics_collection
    MONITORING_AVAILABLE = True
except ImportError as e:
    print(f"Monitoring components not available: {e}")
    print("Run: pip install dash plotly to enable web dashboard")
    MONITORING_AVAILABLE = False

class McLarenPlatformLauncher:
    
    def __init__(self):
        self.platform: Optional[PlatformOrchestrator] = None
        self.shutdown_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)
        self.monitoring_components = {}
    
    def setup_signal_handlers(self):
        if sys.platform != 'win32':
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, self.signal_handler)
    
    def signal_handler(self):
        self.logger.info("Shutdown signal received")
        self.shutdown_event.set()
    
    def start_monitoring_services(self):
        if not MONITORING_AVAILABLE:
            self.logger.warning("Monitoring services not available - continuing without web dashboard")
            return
        
        try:
            def start_prometheus():
                try:
                    prometheus_server = start_prometheus_server(port=8000)
                    self.logger.info("✅ Prometheus metrics server started on port 8000")
                    while True:
                        time.sleep(1)
                except Exception as e:
                    self.logger.error(f"❌ Failed to start Prometheus server: {e}")
            
            prometheus_thread = threading.Thread(target=start_prometheus, daemon=True)
            prometheus_thread.start()
            
            metrics_collector = start_metrics_collection(collection_interval=5.0)
            self.monitoring_components['metrics_collector'] = metrics_collector
            
            def start_dashboard():
                try:
                    dashboard = McLarenMonitor(metrics_collector=metrics_collector)
                    self.monitoring_components['dashboard'] = dashboard
                    self.logger.info("✅ Dashboard started on port 8050")
                    dashboard.run(debug=False, port=8050, host='0.0.0.0')
                except Exception as e:
                    self.logger.error(f"❌ Dashboard startup failed: {e}")
                    self.logger.info("Platform will continue without web dashboard")
            
            dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
            dashboard_thread.start()
            
            time.sleep(2)
            
            print("\n" + "="*60)
            print("McLaren Platform Monitoring Services Active")
            print("="*60)
            print("📊 Web Dashboard: http://localhost:8050")
            print("📈 Metrics API: http://localhost:8000/metrics") 
            print("🔄 Real-time updates every 3-5 seconds")
            print("="*60 + "\n")
            
            self.logger.info("All monitoring services started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring services: {e}")
    
    async def run(self, config_path: Optional[str] = None):
        try:
            print("Starting McLaren Applied Communication Platform...")
            
            self.start_monitoring_services()
            
            self.platform = PlatformOrchestrator(config_path)
            
            self.setup_signal_handlers()
            
            await self.platform.initialize()
            
            platform_task = asyncio.create_task(self.platform.start())
            
            telemetry_task = asyncio.create_task(self.simulate_telemetry_data())
            
            print("\n" + "🚀 Platform Startup Complete")
            print("📊 Access the web dashboard to monitor platform performance")
            print("⏹️  Press Ctrl+C to shutdown all services\n")
            
            await self.shutdown_event.wait()
            
            self.logger.info("Initiating graceful shutdown...")
            
            telemetry_task.cancel()
            
            await self.platform.stop()
            
            try:
                await asyncio.wait_for(platform_task, timeout=30.0)
            except asyncio.TimeoutError:
                self.logger.warning("Platform shutdown timed out")
                platform_task.cancel()
            
            self.logger.info("Platform shutdown completed successfully")
            
        except Exception as e:
            self.logger.error(f"Platform execution failed: {e}")
            raise
    
    async def simulate_telemetry_data(self):
        train_id = "TRAIN_001"
        base_location = (51.5074, -0.1278)
        
        while True:
            try:
                current_time = asyncio.get_event_loop().time()
                
                telemetry = TelemetryData(
                    timestamp=datetime.now(),
                    train_id=train_id,
                    location=base_location,
                    speed_kmh=85.0 + (current_time % 50),
                    network_metrics={
                        'bandwidth_mbps': 450 + (current_time % 100),
                        'latency_ms': 30 + (current_time % 20),
                        'packet_loss_percent': 0.1 + (current_time % 2)
                    },
                    system_health={
                        'cpu_percent': 40 + (current_time % 30),
                        'memory_percent': 60 + (current_time % 20),
                        'disk_percent': 25 + (current_time % 10)
                    },
                    passenger_count=150
                )
                
                if self.platform:
                    await self.platform.process_telemetry_data(telemetry)
                
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Telemetry simulation error: {e}")
                await asyncio.sleep(5)

async def main():
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Initializing McLaren Applied Communication Platform")
    
    config_path = None
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
        if not Path(config_path).exists():
            logger.error(f"Configuration path does not exist: {config_path}")
            sys.exit(1)
    
    launcher = McLarenPlatformLauncher()
    
    try:
        await launcher.run(config_path)
    except KeyboardInterrupt:
        logger.info("Platform shutdown initiated by user")
    except Exception as e:
        logger.error(f"Platform execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPlatform shutdown completed")
    except Exception as e:
        print(f"Critical platform failure: {e}")
        sys.exit(1)