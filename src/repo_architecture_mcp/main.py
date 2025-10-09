"""Main entry point for the Repository Architecture MCP Server."""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from .server import RepoArchitectureMCPServer
from .logging_config import setup_logging, LogLevel, LogFormat
from .config import ConfigManager, create_sample_config
from .models import AnalysisConfig
from .errors import ConfigurationError


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Repository Architecture MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Run with stdio transport
  %(prog)s --config config.yaml              # Use specific config file
  %(prog)s --log-level DEBUG                 # Run with debug logging
  %(prog)s --log-file server.log             # Log to file
  %(prog)s --create-config config.yaml       # Create sample config file
  %(prog)s --github-token YOUR_TOKEN         # Set GitHub token
  %(prog)s --max-workers 8                   # Set number of worker threads
        """
    )
    
    # Server operation
    parser.add_argument(
        "--transport",
        choices=["stdio"],
        default="stdio",
        help="Transport type for MCP communication (default: stdio)"
    )
    
    # Configuration
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration file (JSON or YAML)"
    )
    
    parser.add_argument(
        "--create-config",
        type=str,
        metavar="PATH",
        help="Create a sample configuration file at the specified path and exit"
    )
    
    # Authentication
    parser.add_argument(
        "--github-token",
        type=str,
        help="GitHub personal access token for private repositories"
    )
    
    # Performance settings
    parser.add_argument(
        "--max-workers",
        type=int,
        help="Maximum number of worker threads for parallel processing"
    )
    
    parser.add_argument(
        "--memory-limit",
        type=int,
        metavar="MB",
        help="Memory limit in megabytes"
    )
    
    parser.add_argument(
        "--cache-ttl",
        type=int,
        metavar="HOURS",
        help="Cache time-to-live in hours"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )
    
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing"
    )
    
    # Analysis settings
    parser.add_argument(
        "--max-depth",
        type=int,
        help="Maximum analysis depth"
    )
    
    parser.add_argument(
        "--max-nodes",
        type=int,
        help="Maximum number of nodes in generated diagrams"
    )
    
    parser.add_argument(
        "--output-format",
        choices=["mermaid", "plantuml", "svg", "png"],
        help="Default output format for diagrams"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for generated files"
    )
    
    # Logging
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    parser.add_argument(
        "--log-format",
        choices=["simple", "detailed", "json"],
        default="simple",
        help="Log message format (default: simple)"
    )
    
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path (optional, logs to console if not specified)"
    )
    
    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Disable console logging (only effective with --log-file)"
    )
    
    # Utility
    parser.add_argument(
        "--version",
        action="version",
        version="Repository Architecture MCP Server 0.1.0"
    )
    
    return parser.parse_args()


def merge_config_with_args(config: AnalysisConfig, args: argparse.Namespace) -> AnalysisConfig:
    """Merge command line arguments with configuration.
    
    Args:
        config: Base configuration
        args: Command line arguments
        
    Returns:
        Merged configuration with CLI args taking precedence
    """
    # Create a copy of the config
    merged_config = AnalysisConfig.from_dict(config.to_dict())
    
    # Override with command line arguments
    if args.github_token:
        merged_config.github_token = args.github_token
    
    if args.max_workers:
        merged_config.max_workers = args.max_workers
    
    if args.memory_limit:
        merged_config.memory_limit_mb = args.memory_limit
    
    if args.cache_ttl:
        merged_config.cache_ttl_hours = args.cache_ttl
    
    if args.no_cache:
        merged_config.cache_enabled = False
    
    if args.no_parallel:
        merged_config.parallel_processing = False
    
    if args.max_depth:
        merged_config.max_depth = args.max_depth
    
    if args.max_nodes:
        merged_config.max_nodes = args.max_nodes
    
    if args.output_format:
        merged_config.output_format = args.output_format
    
    if args.output_dir:
        merged_config.output_directory = args.output_dir
    
    return merged_config


class ServerManager:
    """Manages server lifecycle with proper cleanup."""
    
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.server: Optional[RepoArchitectureMCPServer] = None
        self.shutdown_event = asyncio.Event()
        self.logger = logging.getLogger(__name__)
    
    async def start(self, transport_type: str = "stdio") -> None:
        """Start the MCP server.
        
        Args:
            transport_type: Type of transport to use
        """
        try:
            self.server = RepoArchitectureMCPServer(config=self.config)
            self.logger.info(f"Available tools: {', '.join(self.server.get_available_tools())}")
            
            # Set up signal handlers for graceful shutdown
            self._setup_signal_handlers()
            
            self.logger.info("Starting MCP server...")
            await self.server.run(transport_type=transport_type)
            
        except Exception as e:
            self.logger.error(f"Failed to start server: {e}")
            raise
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the server."""
        self.logger.info("Shutting down server...")
        
        if self.server:
            try:
                await self.server.cleanup()
                self.logger.info("Server cleanup completed")
            except Exception as e:
                self.logger.error(f"Error during server cleanup: {e}")
        
        self.shutdown_event.set()
    
    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self.shutdown_event.wait()


async def main_async() -> None:
    """Async main function."""
    args = parse_args()
    
    # Handle create-config command
    if args.create_config:
        try:
            create_sample_config(args.create_config)
            return
        except Exception as e:
            print(f"Error creating configuration file: {e}")
            sys.exit(1)
    
    # Configure logging with enhanced options
    setup_logging(
        level=args.log_level,
        format_type=args.log_format,
        log_file=args.log_file,
        enable_console=not args.no_console or not args.log_file
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Initializing Repository Architecture MCP Server")
    logger.debug(f"Command line arguments: {vars(args)}")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        try:
            config = config_manager.load_config(args.config)
            logger.info(f"Configuration loaded from: {config_manager.get_config_path() or 'defaults'}")
        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            sys.exit(1)
        
        # Merge CLI arguments with configuration
        final_config = merge_config_with_args(config, args)
        
        # Log configuration summary
        logger.info(f"Server configuration:")
        logger.info(f"  - Max workers: {final_config.max_workers}")
        logger.info(f"  - Memory limit: {final_config.memory_limit_mb}MB")
        logger.info(f"  - Cache enabled: {final_config.cache_enabled}")
        logger.info(f"  - Parallel processing: {final_config.parallel_processing}")
        logger.info(f"  - Output format: {final_config.output_format}")
        if final_config.github_token:
            logger.info(f"  - GitHub token: {'*' * 8}...{final_config.github_token[-4:]}")
        
        # Create and start server manager
        server_manager = ServerManager(final_config)
        
        # Start server in background task
        server_task = asyncio.create_task(server_manager.start(args.transport))
        
        # Wait for shutdown signal or server completion
        done, pending = await asyncio.wait(
            [server_task, asyncio.create_task(server_manager.wait_for_shutdown())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Check if server task completed with an exception
        for task in done:
            if task == server_task and task.exception():
                raise task.exception()
        
        logger.info("Server shutdown completed")
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.debug("Server error details:", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()