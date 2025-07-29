from typing import Dict, List, Optional, Any, Tuple, Union, AsyncGenerator

def __init__(self, config_path: Optional[str] = None):
    self.config_path = config_path or os.getenv('MCLAREN_CONFIG', 'config/default.yaml')