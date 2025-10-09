"""Parallel processing system for large repository analysis."""

import asyncio
import logging
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from queue import Queue
import threading

from .models import CodeStructure, RepositoryStructure

logger = logging.getLogger(__name__)


@dataclass
class ProcessingTask:
    """Represents a processing task for parallel execution."""
    task_id: str
    file_path: str
    task_type: str  # 'parse', 'analyze', 'generate'
    priority: int = 1  # Higher number = higher priority
    dependencies: List[str] = None  # Task IDs this task depends on
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ProcessingResult:
    """Represents the result of a processing task."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    processing_time: float = 0.0
    memory_usage: Optional[int] = None


class ProgressTracker:
    """Tracks progress of parallel processing operations."""
    
    def __init__(self, total_tasks: int):
        self.total_tasks = total_tasks
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._cancelled = False
    
    def add_progress_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Add a callback function to be called on progress updates."""
        self._callbacks.append(callback)
    
    def update_progress(self, completed: int = 1, failed: int = 0) -> None:
        """Update progress counters."""
        with self.lock:
            self.completed_tasks += completed
            self.failed_tasks += failed
            
            progress_data = self.get_progress_data()
            
            # Call progress callbacks
            for callback in self._callbacks:
                try:
                    callback(progress_data)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")
    
    def get_progress_data(self) -> Dict[str, Any]:
        """Get current progress data."""
        with self.lock:
            elapsed_time = time.time() - self.start_time
            total_processed = self.completed_tasks + self.failed_tasks
            
            if total_processed > 0:
                estimated_total_time = elapsed_time * (self.total_tasks / total_processed)
                remaining_time = max(0, estimated_total_time - elapsed_time)
            else:
                remaining_time = 0
            
            return {
                'total_tasks': self.total_tasks,
                'completed_tasks': self.completed_tasks,
                'failed_tasks': self.failed_tasks,
                'remaining_tasks': self.total_tasks - total_processed,
                'progress_percentage': (total_processed / self.total_tasks) * 100 if self.total_tasks > 0 else 0,
                'elapsed_time': elapsed_time,
                'estimated_remaining_time': remaining_time,
                'tasks_per_second': total_processed / elapsed_time if elapsed_time > 0 else 0,
                'cancelled': self._cancelled
            }
    
    def cancel(self) -> None:
        """Cancel the operation."""
        with self.lock:
            self._cancelled = True
    
    def is_cancelled(self) -> bool:
        """Check if operation is cancelled."""
        with self.lock:
            return self._cancelled


class ResourceMonitor:
    """Monitors system resources during processing."""
    
    def __init__(self, memory_limit_mb: Optional[int] = None, cpu_limit_percent: Optional[int] = None):
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024 if memory_limit_mb else None
        self.cpu_limit_percent = cpu_limit_percent
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._resource_data: Dict[str, Any] = {}
        self._lock = threading.Lock()
    
    def start_monitoring(self) -> None:
        """Start resource monitoring in background thread."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self._monitor_thread.start()
        logger.debug("Started resource monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.debug("Stopped resource monitoring")
    
    def _monitor_resources(self) -> None:
        """Monitor system resources in background."""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not available - resource monitoring disabled")
            return
        
        process = psutil.Process()
        
        while self._monitoring:
            try:
                # Get memory usage
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # Get CPU usage
                cpu_percent = process.cpu_percent()
                
                # Get system memory
                system_memory = psutil.virtual_memory()
                
                with self._lock:
                    self._resource_data = {
                        'memory_mb': memory_mb,
                        'memory_percent': (memory_info.rss / system_memory.total) * 100,
                        'cpu_percent': cpu_percent,
                        'system_memory_available_mb': system_memory.available / 1024 / 1024,
                        'timestamp': time.time()
                    }
                
                # Check limits
                if self.memory_limit_bytes and memory_info.rss > self.memory_limit_bytes:
                    logger.warning(f"Memory usage ({memory_mb:.1f} MB) exceeds limit")
                
                if self.cpu_limit_percent and cpu_percent > self.cpu_limit_percent:
                    logger.warning(f"CPU usage ({cpu_percent:.1f}%) exceeds limit")
                
                time.sleep(1.0)  # Monitor every second
                
            except Exception as e:
                logger.error(f"Error monitoring resources: {e}")
                time.sleep(5.0)  # Wait longer on error
    
    def get_resource_data(self) -> Dict[str, Any]:
        """Get current resource usage data."""
        with self._lock:
            return self._resource_data.copy()
    
    def is_memory_limit_exceeded(self) -> bool:
        """Check if memory limit is exceeded."""
        if not self.memory_limit_bytes:
            return False
        
        with self._lock:
            current_memory = self._resource_data.get('memory_mb', 0) * 1024 * 1024
            return current_memory > self.memory_limit_bytes


class ParallelProcessor:
    """Manages parallel processing of repository analysis tasks."""
    
    def __init__(self, max_workers: Optional[int] = None, memory_limit_mb: Optional[int] = None,
                 cpu_limit_percent: Optional[int] = None, use_process_pool: bool = True):
        """Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of worker processes/threads
            memory_limit_mb: Memory limit in megabytes
            cpu_limit_percent: CPU usage limit percentage
            use_process_pool: Whether to use process pool (True) or thread pool (False)
        """
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit_percent = cpu_limit_percent
        self.use_process_pool = use_process_pool
        
        self.resource_monitor = ResourceMonitor(memory_limit_mb, cpu_limit_percent)
        self._executor: Optional[Union[ProcessPoolExecutor, ThreadPoolExecutor]] = None
        self._active_tasks: Set[str] = set()
        self._completed_tasks: Dict[str, ProcessingResult] = {}
        self._task_dependencies: Dict[str, List[str]] = {}
        
        logger.info(f"Initialized parallel processor with {self.max_workers} workers")
    
    async def __aenter__(self) -> "ParallelProcessor":
        """Async context manager entry."""
        self._executor = (ProcessPoolExecutor(max_workers=self.max_workers) 
                         if self.use_process_pool 
                         else ThreadPoolExecutor(max_workers=self.max_workers))
        self.resource_monitor.start_monitoring()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._executor:
            self._executor.shutdown(wait=True)
        self.resource_monitor.stop_monitoring()
    
    async def process_files_parallel(self, file_paths: List[str], 
                                   processing_function: Callable[[str], Any],
                                   progress_tracker: Optional[ProgressTracker] = None,
                                   batch_size: int = 100) -> List[ProcessingResult]:
        """Process multiple files in parallel.
        
        Args:
            file_paths: List of file paths to process
            processing_function: Function to apply to each file
            progress_tracker: Optional progress tracker
            batch_size: Number of files to process in each batch
            
        Returns:
            List of processing results
        """
        if not file_paths:
            return []
        
        if not self._executor:
            raise RuntimeError("ParallelProcessor not initialized - use async context manager")
        
        logger.info(f"Starting parallel processing of {len(file_paths)} files")
        
        # Create progress tracker if not provided
        if progress_tracker is None:
            progress_tracker = ProgressTracker(len(file_paths))
        
        results: List[ProcessingResult] = []
        
        # Process files in batches to manage memory usage
        for i in range(0, len(file_paths), batch_size):
            if progress_tracker.is_cancelled():
                logger.info("Processing cancelled by user")
                break
            
            batch_files = file_paths[i:i + batch_size]
            batch_results = await self._process_batch(
                batch_files, processing_function, progress_tracker
            )
            results.extend(batch_results)
            
            # Check memory usage and potentially reduce batch size
            if self.resource_monitor.is_memory_limit_exceeded():
                batch_size = max(10, batch_size // 2)
                logger.warning(f"Memory limit approached, reducing batch size to {batch_size}")
                
                # Force garbage collection
                import gc
                gc.collect()
        
        logger.info(f"Completed parallel processing: {len(results)} results")
        return results
    
    async def _process_batch(self, file_paths: List[str], 
                           processing_function: Callable[[str], Any],
                           progress_tracker: ProgressTracker) -> List[ProcessingResult]:
        """Process a batch of files."""
        loop = asyncio.get_event_loop()
        futures = []
        
        # Submit tasks to executor
        for file_path in file_paths:
            if progress_tracker.is_cancelled():
                break
            
            future = loop.run_in_executor(
                self._executor,
                self._safe_process_file,
                file_path,
                processing_function
            )
            futures.append((file_path, future))
        
        # Collect results as they complete
        results = []
        for file_path, future in futures:
            try:
                result = await future
                results.append(result)
                
                # Update progress
                if result.success:
                    progress_tracker.update_progress(completed=1)
                else:
                    progress_tracker.update_progress(failed=1)
                    
            except Exception as e:
                logger.error(f"Unexpected error processing {file_path}: {e}")
                error_result = ProcessingResult(
                    task_id=file_path,
                    success=False,
                    error=str(e)
                )
                results.append(error_result)
                progress_tracker.update_progress(failed=1)
        
        return results
    
    def _safe_process_file(self, file_path: str, 
                          processing_function: Callable[[str], Any]) -> ProcessingResult:
        """Safely process a single file with error handling."""
        start_time = time.time()
        task_id = file_path
        
        try:
            # Monitor memory usage
            memory_before = self._get_memory_usage()
            
            # Process the file
            result = processing_function(file_path)
            
            # Calculate processing time and memory usage
            processing_time = time.time() - start_time
            memory_after = self._get_memory_usage()
            memory_used = memory_after - memory_before if memory_after and memory_before else None
            
            return ProcessingResult(
                task_id=task_id,
                success=True,
                result=result,
                processing_time=processing_time,
                memory_usage=memory_used
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing file {file_path}: {e}")
            
            return ProcessingResult(
                task_id=task_id,
                success=False,
                error=str(e),
                processing_time=processing_time
            )
    
    def _get_memory_usage(self) -> Optional[int]:
        """Get current memory usage in bytes."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return None
        except Exception:
            return None
    
    async def process_with_dependencies(self, tasks: List[ProcessingTask],
                                      processing_functions: Dict[str, Callable],
                                      progress_tracker: Optional[ProgressTracker] = None) -> Dict[str, ProcessingResult]:
        """Process tasks with dependency resolution.
        
        Args:
            tasks: List of processing tasks with dependencies
            processing_functions: Dictionary mapping task types to processing functions
            progress_tracker: Optional progress tracker
            
        Returns:
            Dictionary mapping task IDs to results
        """
        if not tasks:
            return {}
        
        logger.info(f"Starting dependency-aware processing of {len(tasks)} tasks")
        
        # Create progress tracker if not provided
        if progress_tracker is None:
            progress_tracker = ProgressTracker(len(tasks))
        
        # Build dependency graph
        task_map = {task.task_id: task for task in tasks}
        dependency_graph = self._build_dependency_graph(tasks)
        
        # Process tasks in dependency order
        results: Dict[str, ProcessingResult] = {}
        ready_tasks = self._get_ready_tasks(tasks, set())
        
        while ready_tasks and not progress_tracker.is_cancelled():
            # Process ready tasks in parallel
            batch_results = await self._process_task_batch(
                ready_tasks, processing_functions, progress_tracker
            )
            
            # Update results and find next ready tasks
            for result in batch_results:
                results[result.task_id] = result
                if result.success:
                    progress_tracker.update_progress(completed=1)
                else:
                    progress_tracker.update_progress(failed=1)
            
            # Find next batch of ready tasks
            completed_task_ids = set(results.keys())
            ready_tasks = self._get_ready_tasks(tasks, completed_task_ids)
        
        logger.info(f"Completed dependency-aware processing: {len(results)} results")
        return results
    
    def _build_dependency_graph(self, tasks: List[ProcessingTask]) -> Dict[str, List[str]]:
        """Build dependency graph from tasks."""
        graph = {}
        for task in tasks:
            graph[task.task_id] = task.dependencies.copy()
        return graph
    
    def _get_ready_tasks(self, all_tasks: List[ProcessingTask], 
                        completed_task_ids: Set[str]) -> List[ProcessingTask]:
        """Get tasks that are ready to be processed (all dependencies completed)."""
        ready_tasks = []
        
        for task in all_tasks:
            if task.task_id in completed_task_ids:
                continue  # Already completed
            
            # Check if all dependencies are completed
            if all(dep_id in completed_task_ids for dep_id in task.dependencies):
                ready_tasks.append(task)
        
        # Sort by priority (higher priority first)
        ready_tasks.sort(key=lambda t: t.priority, reverse=True)
        return ready_tasks
    
    async def _process_task_batch(self, tasks: List[ProcessingTask],
                                processing_functions: Dict[str, Callable],
                                progress_tracker: ProgressTracker) -> List[ProcessingResult]:
        """Process a batch of tasks."""
        if not tasks:
            return []
        
        loop = asyncio.get_event_loop()
        futures = []
        
        # Submit tasks to executor
        for task in tasks:
            if progress_tracker.is_cancelled():
                break
            
            processing_function = processing_functions.get(task.task_type)
            if not processing_function:
                logger.error(f"No processing function found for task type: {task.task_type}")
                continue
            
            future = loop.run_in_executor(
                self._executor,
                self._safe_process_task,
                task,
                processing_function
            )
            futures.append(future)
        
        # Collect results
        results = []
        for future in futures:
            try:
                result = await future
                results.append(result)
            except Exception as e:
                logger.error(f"Unexpected error in task processing: {e}")
        
        return results
    
    def _safe_process_task(self, task: ProcessingTask, 
                          processing_function: Callable) -> ProcessingResult:
        """Safely process a single task with error handling."""
        start_time = time.time()
        
        try:
            # Monitor memory usage
            memory_before = self._get_memory_usage()
            
            # Process the task
            result = processing_function(task.file_path, task.metadata)
            
            # Calculate processing time and memory usage
            processing_time = time.time() - start_time
            memory_after = self._get_memory_usage()
            memory_used = memory_after - memory_before if memory_after and memory_before else None
            
            return ProcessingResult(
                task_id=task.task_id,
                success=True,
                result=result,
                processing_time=processing_time,
                memory_usage=memory_used
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing task {task.task_id}: {e}")
            
            return ProcessingResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                processing_time=processing_time
            )
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        resource_data = self.resource_monitor.get_resource_data()
        
        return {
            'max_workers': self.max_workers,
            'use_process_pool': self.use_process_pool,
            'memory_limit_mb': self.memory_limit_mb,
            'cpu_limit_percent': self.cpu_limit_percent,
            'active_tasks': len(self._active_tasks),
            'completed_tasks': len(self._completed_tasks),
            'current_resources': resource_data
        }


# Utility functions for common processing patterns

def create_file_parsing_tasks(file_paths: List[str], parser_type: str = "parse") -> List[ProcessingTask]:
    """Create processing tasks for file parsing.
    
    Args:
        file_paths: List of file paths to parse
        parser_type: Type of parsing task
        
    Returns:
        List of processing tasks
    """
    tasks = []
    for i, file_path in enumerate(file_paths):
        task = ProcessingTask(
            task_id=f"parse_{i}_{Path(file_path).name}",
            file_path=file_path,
            task_type=parser_type,
            priority=1,
            metadata={'index': i}
        )
        tasks.append(task)
    
    return tasks


def create_analysis_tasks(repo_structure: RepositoryStructure) -> List[ProcessingTask]:
    """Create processing tasks for repository analysis.
    
    Args:
        repo_structure: Repository structure to analyze
        
    Returns:
        List of processing tasks with dependencies
    """
    tasks = []
    
    # Create dependency analysis task (depends on all parsing tasks)
    parse_task_ids = [f"parse_{i}_{Path(f.file_path).name}" 
                     for i, f in enumerate(repo_structure.files)]
    
    dependency_task = ProcessingTask(
        task_id="analyze_dependencies",
        file_path=repo_structure.repository_path,
        task_type="analyze_dependencies",
        priority=2,
        dependencies=parse_task_ids,
        metadata={'repo_structure': repo_structure}
    )
    tasks.append(dependency_task)
    
    # Create class analysis task (depends on parsing)
    class_task = ProcessingTask(
        task_id="analyze_classes",
        file_path=repo_structure.repository_path,
        task_type="analyze_classes",
        priority=2,
        dependencies=parse_task_ids,
        metadata={'repo_structure': repo_structure}
    )
    tasks.append(class_task)
    
    # Create data flow analysis task (depends on parsing)
    dataflow_task = ProcessingTask(
        task_id="analyze_dataflow",
        file_path=repo_structure.repository_path,
        task_type="analyze_dataflow",
        priority=2,
        dependencies=parse_task_ids,
        metadata={'repo_structure': repo_structure}
    )
    tasks.append(dataflow_task)
    
    return tasks