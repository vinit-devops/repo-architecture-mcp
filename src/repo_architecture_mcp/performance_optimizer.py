"""Performance optimization integration module."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Union

from .cache_manager import CacheManager
from .parallel_processor import ParallelProcessor, ProgressTracker, ProcessingTask
from .memory_manager import (
    MemoryMonitor, StreamingProcessor, StreamingConfig, 
    memory_limit_context, optimize_memory_usage
)
from .models import RepositoryStructure, CodeStructure
from .architecture_analyzer import ArchitectureAnalyzer

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """Integrates caching, parallel processing, and memory management for optimal performance."""
    
    def __init__(self, 
                 cache_dir: Optional[str] = None,
                 max_workers: Optional[int] = None,
                 memory_limit_mb: Optional[int] = None,
                 enable_streaming: bool = True,
                 streaming_chunk_size: int = 100):
        """Initialize performance optimizer.
        
        Args:
            cache_dir: Directory for cache storage
            max_workers: Maximum number of parallel workers
            memory_limit_mb: Memory limit in megabytes
            enable_streaming: Whether to enable streaming for large repositories
            streaming_chunk_size: Chunk size for streaming processing
        """
        self.cache_manager = CacheManager(cache_dir=cache_dir, memory_limit_mb=memory_limit_mb)
        self.memory_limit_mb = memory_limit_mb
        self.max_workers = max_workers
        self.enable_streaming = enable_streaming
        
        # Configure streaming
        self.streaming_config = StreamingConfig(
            chunk_size=streaming_chunk_size,
            memory_threshold_mb=memory_limit_mb or 1024,
            max_cache_size=1000,
            enable_compression=True
        )
        
        # Apply memory optimizations
        optimize_memory_usage()
        
        logger.info("Performance optimizer initialized")
    
    async def analyze_repository_optimized(self, 
                                         repo_path: str,
                                         file_paths: List[str],
                                         parser_function: Callable[[str], CodeStructure],
                                         analyzer: ArchitectureAnalyzer,
                                         progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Analyze repository with full performance optimizations.
        
        Args:
            repo_path: Path to repository
            file_paths: List of file paths to analyze
            parser_function: Function to parse individual files
            analyzer: Architecture analyzer instance
            progress_callback: Optional progress callback function
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Starting optimized repository analysis: {len(file_paths)} files")
        
        # Check if we should use streaming based on repository size
        should_stream = (self.enable_streaming and 
                        (len(file_paths) > self.streaming_config.chunk_size * 2 or
                         self._estimate_memory_usage(file_paths) > self.streaming_config.memory_threshold_mb))
        
        if should_stream:
            return await self._analyze_with_streaming(
                repo_path, file_paths, parser_function, analyzer, progress_callback
            )
        else:
            return await self._analyze_with_parallel_processing(
                repo_path, file_paths, parser_function, analyzer, progress_callback
            )
    
    async def _analyze_with_parallel_processing(self,
                                              repo_path: str,
                                              file_paths: List[str],
                                              parser_function: Callable[[str], CodeStructure],
                                              analyzer: ArchitectureAnalyzer,
                                              progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Analyze repository using parallel processing."""
        logger.info("Using parallel processing for repository analysis")
        
        # Create progress tracker
        total_tasks = len(file_paths) + 3  # files + 3 analysis tasks
        progress_tracker = ProgressTracker(total_tasks)
        
        if progress_callback:
            progress_tracker.add_progress_callback(progress_callback)
        
        # Check cache for repository structure
        cached_repo_structure = self.cache_manager.get_repository_structure(repo_path)
        if cached_repo_structure:
            logger.info("Using cached repository structure")
            progress_tracker.update_progress(completed=len(file_paths))
            repo_structure = cached_repo_structure
        else:
            # Parse files with caching and parallel processing
            repo_structure = await self._parse_files_parallel(
                repo_path, file_paths, parser_function, progress_tracker
            )
            
            # Cache repository structure
            self.cache_manager.set_repository_structure(repo_path, repo_structure)
        
        # Perform analysis with caching
        analysis_results = await self._perform_analysis_with_cache(
            repo_path, repo_structure, analyzer, progress_tracker
        )
        
        return {
            'repository_structure': repo_structure,
            'analysis_results': analysis_results,
            'cache_stats': self.cache_manager.get_cache_stats(),
            'processing_method': 'parallel'
        }
    
    async def _analyze_with_streaming(self,
                                    repo_path: str,
                                    file_paths: List[str],
                                    parser_function: Callable[[str], CodeStructure],
                                    analyzer: ArchitectureAnalyzer,
                                    progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Analyze repository using streaming processing."""
        logger.info("Using streaming processing for large repository analysis")
        
        with memory_limit_context(self.memory_limit_mb or 2048) as memory_monitor:
            with StreamingProcessor(self.streaming_config, self.memory_limit_mb) as processor:
                
                # Create progress tracking
                total_files = len(file_paths)
                processed_files = 0
                
                # Check cache for repository structure
                cached_repo_structure = self.cache_manager.get_repository_structure(repo_path)
                if cached_repo_structure:
                    logger.info("Using cached repository structure")
                    repo_structure = cached_repo_structure
                else:
                    # Stream process files
                    parsed_files = []
                    
                    for file_path, result in processor.stream_process_files(file_paths, parser_function):
                        if result is not None:
                            parsed_files.append(result)
                        
                        processed_files += 1
                        
                        # Update progress
                        if progress_callback:
                            progress_data = {
                                'completed_tasks': processed_files,
                                'total_tasks': total_files + 3,
                                'progress_percentage': (processed_files / (total_files + 3)) * 100,
                                'current_task': f"Parsing {Path(file_path).name}"
                            }
                            progress_callback(progress_data)
                    
                    # Create repository structure
                    repo_structure = RepositoryStructure(
                        repository_path=repo_path,
                        files=parsed_files,
                        total_files=len(parsed_files)
                    )
                    
                    # Cache repository structure
                    self.cache_manager.set_repository_structure(repo_path, repo_structure)
                
                # Perform analysis
                analysis_results = {}
                
                # Dependency analysis
                if progress_callback:
                    progress_callback({
                        'completed_tasks': processed_files + 1,
                        'total_tasks': total_files + 3,
                        'current_task': "Analyzing dependencies"
                    })
                
                cached_deps = self.cache_manager.get_analysis_result(repo_path, "dependencies")
                if cached_deps:
                    analysis_results['dependencies'] = cached_deps
                else:
                    deps = analyzer.build_dependency_graph(repo_structure)
                    analysis_results['dependencies'] = deps
                    self.cache_manager.set_analysis_result(repo_path, "dependencies", deps)
                
                # Class analysis
                if progress_callback:
                    progress_callback({
                        'completed_tasks': processed_files + 2,
                        'total_tasks': total_files + 3,
                        'current_task': "Analyzing classes"
                    })
                
                cached_classes = self.cache_manager.get_analysis_result(repo_path, "classes")
                if cached_classes:
                    analysis_results['classes'] = cached_classes
                else:
                    classes = analyzer.extract_class_relationships(repo_structure)
                    analysis_results['classes'] = classes
                    self.cache_manager.set_analysis_result(repo_path, "classes", classes)
                
                # Data flow analysis
                if progress_callback:
                    progress_callback({
                        'completed_tasks': processed_files + 3,
                        'total_tasks': total_files + 3,
                        'current_task': "Analyzing data flow"
                    })
                
                cached_dataflow = self.cache_manager.get_analysis_result(repo_path, "dataflow")
                if cached_dataflow:
                    analysis_results['dataflow'] = cached_dataflow
                else:
                    dataflow = analyzer.analyze_data_flow(repo_structure)
                    analysis_results['dataflow'] = dataflow
                    self.cache_manager.set_analysis_result(repo_path, "dataflow", dataflow)
                
                return {
                    'repository_structure': repo_structure,
                    'analysis_results': analysis_results,
                    'cache_stats': self.cache_manager.get_cache_stats(),
                    'processing_stats': processor.get_processing_stats(),
                    'processing_method': 'streaming'
                }
    
    async def _parse_files_parallel(self,
                                  repo_path: str,
                                  file_paths: List[str],
                                  parser_function: Callable[[str], CodeStructure],
                                  progress_tracker: ProgressTracker) -> RepositoryStructure:
        """Parse files using parallel processing with caching."""
        
        # Create cached parser function
        def cached_parser(file_path: str) -> Optional[CodeStructure]:
            # Check cache first
            cached_result = self.cache_manager.get_file_structure(file_path)
            if cached_result:
                return cached_result
            
            # Parse file
            try:
                result = parser_function(file_path)
                # Cache result
                self.cache_manager.set_file_structure(file_path, result)
                return result
            except Exception as e:
                logger.error(f"Error parsing file {file_path}: {e}")
                return None
        
        # Use parallel processor
        async with ParallelProcessor(
            max_workers=self.max_workers,
            memory_limit_mb=self.memory_limit_mb
        ) as processor:
            
            results = await processor.process_files_parallel(
                file_paths, cached_parser, progress_tracker
            )
        
        # Collect successful results
        parsed_files = []
        for result in results:
            if result.success and result.result:
                parsed_files.append(result.result)
        
        # Create repository structure
        repo_structure = RepositoryStructure(
            repository_path=repo_path,
            files=parsed_files,
            total_files=len(parsed_files)
        )
        
        return repo_structure
    
    async def _perform_analysis_with_cache(self,
                                         repo_path: str,
                                         repo_structure: RepositoryStructure,
                                         analyzer: ArchitectureAnalyzer,
                                         progress_tracker: ProgressTracker) -> Dict[str, Any]:
        """Perform analysis with caching."""
        analysis_results = {}
        
        # Dependency analysis
        cached_deps = self.cache_manager.get_analysis_result(repo_path, "dependencies")
        if cached_deps:
            logger.info("Using cached dependency analysis")
            analysis_results['dependencies'] = cached_deps
        else:
            logger.info("Performing dependency analysis")
            deps = analyzer.build_dependency_graph(repo_structure)
            analysis_results['dependencies'] = deps
            self.cache_manager.set_analysis_result(repo_path, "dependencies", deps)
        
        progress_tracker.update_progress(completed=1)
        
        # Class analysis
        cached_classes = self.cache_manager.get_analysis_result(repo_path, "classes")
        if cached_classes:
            logger.info("Using cached class analysis")
            analysis_results['classes'] = cached_classes
        else:
            logger.info("Performing class analysis")
            classes = analyzer.extract_class_relationships(repo_structure)
            analysis_results['classes'] = classes
            self.cache_manager.set_analysis_result(repo_path, "classes", classes)
        
        progress_tracker.update_progress(completed=1)
        
        # Data flow analysis
        cached_dataflow = self.cache_manager.get_analysis_result(repo_path, "dataflow")
        if cached_dataflow:
            logger.info("Using cached data flow analysis")
            analysis_results['dataflow'] = cached_dataflow
        else:
            logger.info("Performing data flow analysis")
            dataflow = analyzer.analyze_data_flow(repo_structure)
            analysis_results['dataflow'] = dataflow
            self.cache_manager.set_analysis_result(repo_path, "dataflow", dataflow)
        
        progress_tracker.update_progress(completed=1)
        
        return analysis_results
    
    def _estimate_memory_usage(self, file_paths: List[str]) -> int:
        """Estimate memory usage for processing files (in MB)."""
        # Rough estimation: 1MB per 100 files
        estimated_mb = len(file_paths) // 100 + 1
        
        # Add overhead for analysis
        estimated_mb *= 2
        
        return estimated_mb
    
    def invalidate_cache(self, repo_path: str) -> None:
        """Invalidate all cache entries for a repository."""
        self.cache_manager.invalidate_repository(repo_path)
        logger.info(f"Invalidated cache for repository: {repo_path}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return {
            'cache_stats': self.cache_manager.get_cache_stats(),
            'memory_limit_mb': self.memory_limit_mb,
            'max_workers': self.max_workers,
            'streaming_enabled': self.enable_streaming,
            'streaming_config': {
                'chunk_size': self.streaming_config.chunk_size,
                'memory_threshold_mb': self.streaming_config.memory_threshold_mb,
                'max_cache_size': self.streaming_config.max_cache_size
            }
        }
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        # Clear cache if needed
        # self.cache_manager.clear_cache()
        logger.info("Performance optimizer cleanup completed")


# Utility functions for performance optimization

def configure_for_large_repositories(optimizer: PerformanceOptimizer) -> None:
    """Configure optimizer for large repositories."""
    optimizer.streaming_config.chunk_size = 50  # Smaller chunks
    optimizer.streaming_config.memory_threshold_mb = 512  # Lower threshold
    optimizer.streaming_config.max_cache_size = 500  # Smaller cache
    logger.info("Configured optimizer for large repositories")


def configure_for_small_repositories(optimizer: PerformanceOptimizer) -> None:
    """Configure optimizer for small repositories."""
    optimizer.streaming_config.chunk_size = 200  # Larger chunks
    optimizer.streaming_config.memory_threshold_mb = 2048  # Higher threshold
    optimizer.streaming_config.max_cache_size = 2000  # Larger cache
    logger.info("Configured optimizer for small repositories")


async def benchmark_performance(optimizer: PerformanceOptimizer,
                              repo_path: str,
                              file_paths: List[str],
                              parser_function: Callable,
                              analyzer: ArchitectureAnalyzer) -> Dict[str, Any]:
    """Benchmark performance of repository analysis."""
    import time
    
    start_time = time.time()
    
    # Run analysis
    results = await optimizer.analyze_repository_optimized(
        repo_path, file_paths, parser_function, analyzer
    )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # Calculate performance metrics
    files_per_second = len(file_paths) / processing_time if processing_time > 0 else 0
    
    benchmark_results = {
        'total_files': len(file_paths),
        'processing_time_seconds': processing_time,
        'files_per_second': files_per_second,
        'processing_method': results.get('processing_method', 'unknown'),
        'cache_hit_ratio': 0,  # Would need to track this
        'memory_usage_mb': 0,  # Would need to track this
        'performance_stats': optimizer.get_performance_stats()
    }
    
    logger.info(f"Benchmark completed: {files_per_second:.2f} files/sec")
    return benchmark_results