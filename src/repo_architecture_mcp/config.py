"""Configuration management for the Repository Architecture MCP Server."""

import json
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
import logging

from .models import AnalysisConfig
from .errors import ConfigurationError

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and validation."""
    
    DEFAULT_CONFIG_PATHS = [
        "repo-architecture-mcp.json",
        "repo-architecture-mcp.yaml",
        "repo-architecture-mcp.yml",
        "~/.config/repo-architecture-mcp/config.json",
        "~/.config/repo-architecture-mcp/config.yaml",
        "~/.repo-architecture-mcp.json",
        "~/.repo-architecture-mcp.yaml"
    ]
    
    def __init__(self):
        self._config: Optional[AnalysisConfig] = None
        self._config_path: Optional[Path] = None
    
    def load_config(self, config_path: Optional[Union[str, Path]] = None) -> AnalysisConfig:
        """Load configuration from file or use defaults.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            Loaded configuration
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        if config_path:
            # Load from specified path
            config_file = Path(config_path).expanduser()
            if not config_file.exists():
                raise ConfigurationError(f"Configuration file not found: {config_file}")
            
            config_data = self._load_config_file(config_file)
            self._config_path = config_file
        else:
            # Try default paths
            config_data = {}
            for default_path in self.DEFAULT_CONFIG_PATHS:
                config_file = Path(default_path).expanduser()
                if config_file.exists():
                    logger.info(f"Loading configuration from: {config_file}")
                    config_data = self._load_config_file(config_file)
                    self._config_path = config_file
                    break
            else:
                logger.info("No configuration file found, using defaults")
        
        # Merge with environment variables
        config_data = self._merge_env_vars(config_data)
        
        # Create and validate configuration
        try:
            self._config = AnalysisConfig.from_dict(config_data)
            self._validate_config(self._config)
            return self._config
        except Exception as e:
            raise ConfigurationError(f"Invalid configuration: {e}")
    
    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from a file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Configuration data
            
        Raises:
            ConfigurationError: If file cannot be loaded or parsed
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.suffix.lower() == '.json':
                    return json.load(f)
                elif config_path.suffix.lower() in ['.yaml', '.yml']:
                    return yaml.safe_load(f) or {}
                else:
                    raise ConfigurationError(f"Unsupported configuration file format: {config_path.suffix}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading configuration file: {e}")
    
    def _merge_env_vars(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Merge environment variables into configuration.
        
        Args:
            config_data: Base configuration data
            
        Returns:
            Configuration with environment variables merged
        """
        env_mapping = {
            'GITHUB_TOKEN': 'github_token',
            'REPO_ARCH_MAX_WORKERS': 'max_workers',
            'REPO_ARCH_MEMORY_LIMIT': 'memory_limit_mb',
            'REPO_ARCH_CACHE_TTL': 'cache_ttl_hours',
            'REPO_ARCH_OUTPUT_DIR': 'output_directory',
            'REPO_ARCH_OUTPUT_FORMAT': 'output_format',
            'REPO_ARCH_MAX_DEPTH': 'max_depth',
            'REPO_ARCH_MAX_NODES': 'max_nodes',
            'REPO_ARCH_PARALLEL': 'parallel_processing',
            'REPO_ARCH_CACHE_ENABLED': 'cache_enabled',
        }
        
        for env_var, config_key in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                # Convert string values to appropriate types
                if config_key in ['max_workers', 'memory_limit_mb', 'cache_ttl_hours', 'max_depth', 'max_nodes']:
                    try:
                        config_data[config_key] = int(env_value)
                    except ValueError:
                        logger.warning(f"Invalid integer value for {env_var}: {env_value}")
                elif config_key in ['parallel_processing', 'cache_enabled']:
                    config_data[config_key] = env_value.lower() in ['true', '1', 'yes', 'on']
                else:
                    config_data[config_key] = env_value
        
        return config_data
    
    def _validate_config(self, config: AnalysisConfig) -> None:
        """Validate configuration values.
        
        Args:
            config: Configuration to validate
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        if config.max_depth < 1:
            raise ConfigurationError("max_depth must be at least 1")
        
        if config.max_file_size_mb < 1:
            raise ConfigurationError("max_file_size_mb must be at least 1")
        
        if config.max_workers < 1:
            raise ConfigurationError("max_workers must be at least 1")
        
        if config.memory_limit_mb < 100:
            raise ConfigurationError("memory_limit_mb must be at least 100")
        
        if config.cache_ttl_hours < 1:
            raise ConfigurationError("cache_ttl_hours must be at least 1")
        
        if config.max_nodes < 10:
            raise ConfigurationError("max_nodes must be at least 10")
        
        valid_layouts = ['hierarchical', 'circular', 'force-directed']
        if config.diagram_layout not in valid_layouts:
            raise ConfigurationError(f"diagram_layout must be one of: {valid_layouts}")
        
        valid_formats = ['mermaid', 'plantuml', 'svg', 'png']
        if config.output_format not in valid_formats:
            raise ConfigurationError(f"output_format must be one of: {valid_formats}")
        
        if config.output_directory:
            output_path = Path(config.output_directory).expanduser()
            if not output_path.parent.exists():
                raise ConfigurationError(f"Output directory parent does not exist: {output_path.parent}")
    
    def save_config(self, config: AnalysisConfig, config_path: Optional[Union[str, Path]] = None) -> None:
        """Save configuration to file.
        
        Args:
            config: Configuration to save
            config_path: Optional path to save to (uses loaded path if not specified)
            
        Raises:
            ConfigurationError: If configuration cannot be saved
        """
        if config_path:
            save_path = Path(config_path).expanduser()
        elif self._config_path:
            save_path = self._config_path
        else:
            save_path = Path("repo-architecture-mcp.json").expanduser()
        
        try:
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save configuration
            with open(save_path, 'w', encoding='utf-8') as f:
                if save_path.suffix.lower() == '.json':
                    json.dump(config.to_dict(), f, indent=2, default=str)
                elif save_path.suffix.lower() in ['.yaml', '.yml']:
                    yaml.dump(config.to_dict(), f, default_flow_style=False)
                else:
                    # Default to JSON
                    json.dump(config.to_dict(), f, indent=2)
            
            logger.info(f"Configuration saved to: {save_path}")
            
        except Exception as e:
            raise ConfigurationError(f"Error saving configuration: {e}")
    
    def get_config(self) -> Optional[AnalysisConfig]:
        """Get the currently loaded configuration."""
        return self._config
    
    def get_config_path(self) -> Optional[Path]:
        """Get the path of the currently loaded configuration file."""
        return self._config_path


def create_sample_config(output_path: Union[str, Path]) -> None:
    """Create a sample configuration file.
    
    Args:
        output_path: Path where to create the sample configuration
    """
    config = AnalysisConfig()
    manager = ConfigManager()
    
    try:
        manager.save_config(config, output_path)
        print(f"Sample configuration created at: {output_path}")
    except ConfigurationError as e:
        print(f"Error creating sample configuration: {e}")