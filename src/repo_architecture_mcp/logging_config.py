"""Logging configuration for the Repository Architecture MCP Server."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(Enum):
    """Available logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(Enum):
    """Available logging formats."""
    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"


class LoggingConfig:
    """Centralized logging configuration manager."""
    
    DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DETAILED_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s"
    JSON_FORMAT = '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "file": "%(filename)s", "line": %(lineno)d, "function": "%(funcName)s", "message": "%(message)s"}'
    
    def __init__(self):
        """Initialize logging configuration."""
        self._configured = False
        self._log_file: Optional[str] = None
        self._log_level = LogLevel.INFO
        self._log_format = LogFormat.SIMPLE
        self._handlers: Dict[str, logging.Handler] = {}
    
    def configure(
        self,
        level: LogLevel = LogLevel.INFO,
        format_type: LogFormat = LogFormat.SIMPLE,
        log_file: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        enable_console: bool = True,
        console_level: Optional[LogLevel] = None
    ) -> None:
        """Configure logging for the application.
        
        Args:
            level: Base logging level
            format_type: Log message format
            log_file: Optional log file path
            max_file_size: Maximum log file size in bytes
            backup_count: Number of backup log files to keep
            enable_console: Whether to enable console logging
            console_level: Console-specific log level (defaults to base level)
        """
        if self._configured:
            self.reset()
        
        self._log_level = level
        self._log_format = format_type
        self._log_file = log_file
        
        # Get the appropriate formatter
        formatter = self._get_formatter(format_type)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.value))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add console handler if enabled
        if enable_console:
            console_handler = logging.StreamHandler(sys.stderr)
            console_level_value = console_level or level
            console_handler.setLevel(getattr(logging, console_level_value.value))
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            self._handlers['console'] = console_handler
        
        # Add file handler if log file is specified
        if log_file:
            try:
                # Ensure log directory exists
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Use rotating file handler to manage log file size
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=max_file_size,
                    backupCount=backup_count,
                    encoding='utf-8'
                )
                file_handler.setLevel(getattr(logging, level.value))
                file_handler.setFormatter(formatter)
                root_logger.addHandler(file_handler)
                self._handlers['file'] = file_handler
                
            except Exception as e:
                # If file logging fails, log to console
                logging.error(f"Failed to configure file logging: {e}")
        
        # Configure specific loggers for better control
        self._configure_library_loggers()
        
        self._configured = True
        logging.info(f"Logging configured: level={level.value}, format={format_type.value}, file={log_file}")
    
    def _get_formatter(self, format_type: LogFormat) -> logging.Formatter:
        """Get the appropriate log formatter.
        
        Args:
            format_type: Format type to use
            
        Returns:
            Configured log formatter
        """
        if format_type == LogFormat.SIMPLE:
            return logging.Formatter(self.DEFAULT_FORMAT)
        elif format_type == LogFormat.DETAILED:
            return logging.Formatter(self.DETAILED_FORMAT)
        elif format_type == LogFormat.JSON:
            return logging.Formatter(self.JSON_FORMAT)
        else:
            return logging.Formatter(self.DEFAULT_FORMAT)
    
    def _configure_library_loggers(self) -> None:
        """Configure logging levels for third-party libraries."""
        # Reduce noise from third-party libraries
        library_configs = {
            'aiohttp': logging.WARNING,
            'git': logging.WARNING,
            'urllib3': logging.WARNING,
            'requests': logging.WARNING,
            'asyncio': logging.WARNING,
            'matplotlib': logging.WARNING,
            'PIL': logging.WARNING
        }
        
        for library, level in library_configs.items():
            logging.getLogger(library).setLevel(level)
    
    def set_level(self, level: LogLevel) -> None:
        """Change the logging level dynamically.
        
        Args:
            level: New logging level
        """
        self._log_level = level
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, level.value))
        
        # Update handler levels
        for handler in root_logger.handlers:
            handler.setLevel(getattr(logging, level.value))
        
        logging.info(f"Logging level changed to {level.value}")
    
    def add_context_filter(self, context: Dict[str, Any]) -> None:
        """Add contextual information to log records.
        
        Args:
            context: Dictionary of context information to add to logs
        """
        class ContextFilter(logging.Filter):
            def filter(self, record):
                for key, value in context.items():
                    setattr(record, key, value)
                return True
        
        context_filter = ContextFilter()
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            handler.addFilter(context_filter)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with the specified name.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)
    
    def reset(self) -> None:
        """Reset logging configuration."""
        root_logger = logging.getLogger()
        
        # Close and remove all handlers
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        
        # Clear our handler references
        self._handlers.clear()
        
        self._configured = False
    
    def is_configured(self) -> bool:
        """Check if logging is configured.
        
        Returns:
            True if logging is configured, False otherwise
        """
        return self._configured
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current logging configuration.
        
        Returns:
            Dictionary with current configuration details
        """
        return {
            'configured': self._configured,
            'level': self._log_level.value if self._log_level else None,
            'format': self._log_format.value if self._log_format else None,
            'log_file': self._log_file,
            'handlers': list(self._handlers.keys())
        }


# Global logging configuration instance
logging_config = LoggingConfig()


def setup_logging(
    level: str = "INFO",
    format_type: str = "simple",
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """Convenience function to set up logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Log format (simple, detailed, json)
        log_file: Optional log file path
        enable_console: Whether to enable console logging
    """
    try:
        log_level = LogLevel(level.upper())
    except ValueError:
        log_level = LogLevel.INFO
        print(f"Warning: Invalid log level '{level}', using INFO")
    
    try:
        log_format = LogFormat(format_type.lower())
    except ValueError:
        log_format = LogFormat.SIMPLE
        print(f"Warning: Invalid log format '{format_type}', using simple")
    
    logging_config.configure(
        level=log_level,
        format_type=log_format,
        log_file=log_file,
        enable_console=enable_console
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging_config.get_logger(name)


class StructuredLogger:
    """Logger wrapper that provides structured logging capabilities."""
    
    def __init__(self, name: str):
        """Initialize structured logger.
        
        Args:
            name: Logger name
        """
        self.logger = get_logger(name)
        self.name = name
    
    def _log_with_context(self, level: int, message: str, **context) -> None:
        """Log message with additional context.
        
        Args:
            level: Logging level
            message: Log message
            **context: Additional context information
        """
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} | {context_str}"
        else:
            full_message = message
        
        self.logger.log(level, full_message)
    
    def debug(self, message: str, **context) -> None:
        """Log debug message with context."""
        self._log_with_context(logging.DEBUG, message, **context)
    
    def info(self, message: str, **context) -> None:
        """Log info message with context."""
        self._log_with_context(logging.INFO, message, **context)
    
    def warning(self, message: str, **context) -> None:
        """Log warning message with context."""
        self._log_with_context(logging.WARNING, message, **context)
    
    def error(self, message: str, **context) -> None:
        """Log error message with context."""
        self._log_with_context(logging.ERROR, message, **context)
    
    def critical(self, message: str, **context) -> None:
        """Log critical message with context."""
        self._log_with_context(logging.CRITICAL, message, **context)
    
    def exception(self, message: str, **context) -> None:
        """Log exception with context."""
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            full_message = f"{message} | {context_str}"
        else:
            full_message = message
        
        self.logger.exception(full_message)