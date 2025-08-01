import sys
import time
import threading
import logging
from pathlib import Path
import platform as python_platform

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mclaren_platform.monitoring.dashboard import McLarenMonitor
    from mclaren_platform.monitoring.prometheus_metrics import start_prometheus_server
    from mclaren_platform.monitoring.metrics_collector import start_metrics_collection
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the McLaren_Platform directory")
    print("and that all dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def start_prometheus_monitoring(port=8000):
    try:
        logger.info(f"Starting Prometheus metrics server on port {port}")
        prometheus_server = start_prometheus_server(port=port)
        logger.info(f"Prometheus metrics available at http://localhost:{port}/metrics")
        return prometheus_server
    except Exception as e:
        logger.error(f"Failed to start Prometheus server: {e}")
        return None

def start_dashboard_monitoring(port=8050):
    try:
        logger.info(f"Starting McLaren Dashboard on port {port}")
        
        metrics_collector = start_metrics_collection(collection_interval=5.0)
        
        dashboard = McLarenMonitor(metrics_collector=metrics_collector)
        dashboard.run(debug=False, port=port, host='0.0.0.0')
        
    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        raise

def main():
    print("=" * 60)
    print("McLaren Applied Communication Platform - Monitoring Suite")
    print("=" * 60)
    
    prometheus_thread = threading.Thread(
        target=start_prometheus_monitoring,
        args=(8000,),
        daemon=True
    )
    prometheus_thread.start()
    
    time.sleep(2)
    
    print("\n📊 Monitoring Services Starting...")
    print("📈 Prometheus Metrics: http://localhost:8000/metrics")
    print("🖥️  Live Dashboard: http://localhost:8050")
    print("\n🔍 Monitoring the following:")
    print("   • Network interface statistics")
    print("   • System performance (CPU, Memory, Disk)")
    print("   • Platform health and connectivity")
    print("   • Circuit breaker status")
    print("   • Communication metrics")
    
    print("\n🚀 Starting dashboard server...")
    print("Press Ctrl+C to stop all services")
    
    try:
        start_dashboard_monitoring(port=8050)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down monitoring services...")
        logger.info("Monitoring services stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()