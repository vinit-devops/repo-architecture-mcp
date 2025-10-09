#!/usr/bin/env python3
"""Example demonstrating performance optimization features."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the performance optimization components
from repo_architecture_mcp.performance_optimizer import PerformanceOptimizer
from repo_architecture_mcp.architecture_analyzer import ArchitectureAnalyzer
from repo_architecture_mcp.models import CodeStructure, RepositoryStructure


def create_sample_parser(file_path: str) -> CodeStructure:
    """Sample parser function for demonstration."""
    # Simulate parsing by creating a basic CodeStructure
    return CodeStructure(
        file_path=file_path,
        language="python" if file_path.endswith(".py") else "unknown",
        classes=[],
        functions=[],
        imports=[],
        exports=[]
    )


def create_sample_files(temp_dir: Path, num_files: int = 100) -> List[str]:
    """Create sample files for testing."""
    file_paths = []
    
    for i in range(num_files):
        file_path = temp_dir / f"sample_{i}.py"
        file_path.write_text(f"""
# Sample Python file {i}
class SampleClass{i}:
    def __init__(self):
        self.value = {i}
    
    def process(self):
        return self.value * 2

def sample_function_{i}():
    return {i}
""")
        file_paths.append(str(file_path))
    
    return file_paths


async def demonstrate_performance_optimization():
    """Demonstrate the performance optimization features."""
    logger.info("Starting performance optimization demonstration")
    
    # Create temporary directory and sample files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create sample files
        logger.info("Creating sample files...")
        file_paths = create_sample_files(temp_path, num_files=50)
        
        # Initialize performance optimizer
        logger.info("Initializing performance optimizer...")
        optimizer = PerformanceOptimizer(
            cache_dir=str(temp_path / "cache"),
            max_workers=4,
            memory_limit_mb=512,
            enable_streaming=True,
            streaming_chunk_size=10
        )
        
        # Initialize analyzer
        analyzer = ArchitectureAnalyzer()
        
        # Progress callback
        def progress_callback(progress_data):
            logger.info(f"Progress: {progress_data['progress_percentage']:.1f}% - {progress_data.get('current_task', 'Processing')}")
        
        # First run - no cache
        logger.info("First run (no cache)...")
        results1 = await optimizer.analyze_repository_optimized(
            repo_path=str(temp_path),
            file_paths=file_paths,
            parser_function=create_sample_parser,
            analyzer=analyzer,
            progress_callback=progress_callback
        )
        
        logger.info(f"First run completed using {results1['processing_method']}")
        logger.info(f"Processed {len(results1['repository_structure'].files)} files")
        
        # Second run - with cache
        logger.info("Second run (with cache)...")
        results2 = await optimizer.analyze_repository_optimized(
            repo_path=str(temp_path),
            file_paths=file_paths,
            parser_function=create_sample_parser,
            analyzer=analyzer,
            progress_callback=progress_callback
        )
        
        logger.info(f"Second run completed using {results2['processing_method']}")
        
        # Display performance stats
        logger.info("Performance Statistics:")
        stats = optimizer.get_performance_stats()
        logger.info(f"  Cache stats: {stats['cache_stats']}")
        logger.info(f"  Memory limit: {stats['memory_limit_mb']} MB")
        logger.info(f"  Max workers: {stats['max_workers']}")
        logger.info(f"  Streaming enabled: {stats['streaming_enabled']}")
        
        # Test with larger dataset to trigger streaming
        logger.info("Testing with larger dataset to trigger streaming...")
        large_file_paths = create_sample_files(temp_path / "large", num_files=200)
        
        results3 = await optimizer.analyze_repository_optimized(
            repo_path=str(temp_path / "large"),
            file_paths=large_file_paths,
            parser_function=create_sample_parser,
            analyzer=analyzer,
            progress_callback=progress_callback
        )
        
        logger.info(f"Large dataset run completed using {results3['processing_method']}")
        
        if 'processing_stats' in results3:
            proc_stats = results3['processing_stats']
            logger.info(f"  Files processed: {proc_stats['files_processed']}")
            logger.info(f"  Cache hits: {proc_stats['cache_hits']}")
            logger.info(f"  Cache misses: {proc_stats['cache_misses']}")
        
        # Cleanup
        optimizer.cleanup()
        
        logger.info("Performance optimization demonstration completed!")


async def demonstrate_memory_management():
    """Demonstrate memory management features."""
    logger.info("Starting memory management demonstration")
    
    from repo_architecture_mcp.memory_manager import MemoryMonitor, StreamingProcessor, StreamingConfig
    
    # Create memory monitor
    memory_monitor = MemoryMonitor(memory_limit_mb=256)
    
    def memory_callback(level, stats):
        logger.warning(f"Memory {level}: {stats.process_memory_mb:.1f} MB ({stats.process_memory_percent:.1f}%)")
    
    memory_monitor.add_callback(memory_callback)
    memory_monitor.start_monitoring()
    
    # Create streaming processor
    config = StreamingConfig(
        chunk_size=20,
        memory_threshold_mb=128,
        max_cache_size=100
    )
    
    with StreamingProcessor(config, memory_limit_mb=256) as processor:
        # Create some sample data
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            file_paths = create_sample_files(temp_path, num_files=100)
            
            # Process with streaming
            processed_count = 0
            for file_path, result in processor.stream_process_files(file_paths, create_sample_parser):
                processed_count += 1
                if processed_count % 20 == 0:
                    logger.info(f"Processed {processed_count} files")
            
            logger.info(f"Streaming processing completed: {processed_count} files")
            
            # Get processing stats
            stats = processor.get_processing_stats()
            logger.info(f"Processing stats: {stats}")
    
    memory_monitor.stop_monitoring()
    logger.info("Memory management demonstration completed!")


async def main():
    """Main demonstration function."""
    try:
        await demonstrate_performance_optimization()
        await demonstrate_memory_management()
    except Exception as e:
        logger.error(f"Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())