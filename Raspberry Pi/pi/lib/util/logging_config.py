"""
Logging Configuration
Structured logging for all rover services
"""

import logging
import logging.handlers
import structlog
from pathlib import Path
import sys


def setup_logging(config: dict):
    """
    Setup structured logging for rover services
    
    Args:
        config: Logging configuration dict from rover_config.yaml
    """
    log_level = getattr(logging, config.get('level', 'INFO').upper())
    log_format = config.get('format', 'json')
    log_dir = Path(config.get('log_dir', '/tmp/rover'))
    enable_console = config.get('enable_console', True)
    enable_file = config.get('enable_file', True)
    max_bytes = config.get('max_log_size_mb', 100) * 1024 * 1024
    backup_count = config.get('backup_count', 5)
    
    # Create log directory
    if enable_file:
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure standard logging
    logging.basicConfig(
        level=log_level,
        format='%(message)s',
        handlers=[]
    )
    
    # Setup structlog
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if log_format == 'json':
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        if log_format == 'json':
            console_formatter = logging.Formatter('%(message)s')
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler (rotating)
    if enable_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / 'rover.log',
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(log_level)
        
        file_formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Log startup
    logger = structlog.get_logger()
    logger.info("logging_initialized", level=log_level, format=log_format)


def get_logger(name: str):
    """
    Get a structured logger
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)

