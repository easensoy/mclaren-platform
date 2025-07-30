import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

class ConfigurationManager:
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self._config: Dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        try:
            default_config_path = self.config_dir / "default.yaml"
            if default_config_path.exists():
                with open(default_config_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            
            environment = os.getenv('MCLAREN_ENV', 'development')
            env_config_path = self.config_dir / f"{environment}.yaml"
            
            if env_config_path.exists():
                with open(env_config_path, 'r') as f:
                    env_config = yaml.safe_load(f) or {}
                    self._merge_configs(self._config, env_config)
            
            self._apply_env_overrides()
            
            self._logger.info(f"Configuration loaded for environment: {environment}")
            
        except Exception as e:
            self._logger.error(f"Configuration loading failed: {e}")
            raise
    
    def _merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_configs(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self) -> None:
        env_mappings = {
            'REDIS_URL': ['redis', 'url'],
            'LOG_LEVEL': ['logging', 'level'],
            'DATABASE_URL': ['database', 'url'],
            'SECRET_KEY': ['security', 'secret_key'],
            'NETWORK_SCAN_INTERVAL': ['network', 'scan_interval_seconds'],
            'CONTAINER_REGISTRY': ['containers', 'registry_url']
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                self._set_nested_value(config_path, value)
    
    def _set_nested_value(self, path: List[str], value: str) -> None:
        current = self._config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        if path[-1].endswith(('_seconds', '_interval', '_timeout')):
            try:
                value = int(value)
            except ValueError:
                pass
        
        current[path[-1]] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        try:
            keys = key.split('.')
            value = self._config
            
            for k in keys:
                value = value[k]
            
            return value
        except KeyError:
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        return self._config.get(section, {})
    
    def reload(self) -> None:
        self._load_configuration()