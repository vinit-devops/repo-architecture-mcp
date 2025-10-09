"""Memory management and streaming processing for large repositories."""

import gc
import logging
import os
import sys
import threading
import time
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Set, Tuple, Union
from collections import deque
import tempfile
import pickle

from .models import CodeStructure, RepositoryStructure

logger = logging.getLogger(__name__)


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    total_memory_mb: float
    available_memory_mb: float
    process_memory_mb: float
    process_memory_percent: float
    gc_collections: Dict[int, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class StreamingConfig:
    """Configuration for streaming processing."""
    chunk_size: int = 100  # Number of files to process in each chunk
    memory_threshold_mb: int = 1024  # Memory threshold to trigger streaming
    max_cache_size: int = 1000  # Maximum number of items to keep in memory cache
    temp_dir: Optional[str] = None  # Directory for temporary files
    enable_compression: bool = True  # Enable compression for temporary files
    cleanup_interval: int = 300  # Cleanup interval in seconds


class MemoryMonitor:
    """Monitors memory usage and triggers cleanup when needed."""
    
    def __init__(self, memory_limit_mb: Optional[int] = None, 
                 warning_threshold: float = 0.8, critical_threshold: float = 0.9):
        """Initialize memory monitor.
        
        Args:
            memory_limit_mb: Memory limit in megabytes (None for auto-detection)
            warning_threshold: Threshold for warning (0.0-1.0)
            critical_threshold: Threshold for critical memory usage (0.0-1.0)
        """
        self.memory_limit_mb = memory_limit_mb or self._detect_memory_limit()
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._callbacks: List[callable] = []
        self._stats_history: deque = deque(maxlen=100)
        self._lock = threading.Lock()
        
        logger.info(f"Memory monitor initialized with limit: {self.memory_limit_mb} MB")
    
    def _detect_memory_limit(self) -> int:
        """Auto-detect reasonable memory limit based on system memory."""
        try:
            import psutil
            system_memory = psutil.virtual_memory()
            # Use 80% of available system memory as limit
            limit_mb = int((system_memory.total * 0.8) / 1024 / 1024)
            logger.info(f"Auto-detected memory limit: {limit_mb} MB")
            return limit_mb
        except ImportError:
            # Fallback to conservative limit
            logger.warning("psutil not available, using conservative memory limit")
            return 2048  # 2GB default
    
    def start_monitoring(self, interval: float = 5.0) -> None:
        """Start memory monitoring in background thread."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            args=(interval,), 
            daemon=True
        )
        self._monitor_thread.start()
        logger.debug("Started memory monitoring")
    
    def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.debug("Stopped memory monitoring")
    
    def _monitor_loop(self, interval: float) -> None:
        """Main monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_memory_stats()
                
                with self._lock:
                    self._stats_history.append(stats)
                
                # Check thresholds
                usage_ratio = stats.process_memory_mb / self.memory_limit_mb
                
                if usage_ratio >= self.critical_threshold:
                    self._trigger_callbacks('critical', stats)
                elif usage_ratio >= self.warning_threshold:
                    self._trigger_callbacks('warning', stats)
                
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")
                time.sleep(interval * 2)  # Wait longer on error
    
    def _trigger_callbacks(self, level: str, stats: MemoryStats) -> None:
        """Trigger registered callbacks."""
        for callback in self._callbacks:
            try:
                callback(level, stats)
            except Exception as e:
                logger.error(f"Memory callback failed: {e}")
    
    def add_callback(self, callback: callable) -> None:
        """Add callback for memory events."""
        self._callbacks.append(callback)
    
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics."""
        try:
            import psutil
            
            # System memory
            system_memory = psutil.virtual_memory()
            
            # Process memory
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # Garbage collection stats
            gc_stats = {}
            for i in range(3):
                gc_stats[i] = gc.get_count()[i]
            
            return MemoryStats(
                total_memory_mb=system_memory.total / 1024 / 1024,
                available_memory_mb=system_memory.available / 1024 / 1024,
                process_memory_mb=process_memory.rss / 1024 / 1024,
                process_memory_percent=(process_memory.rss / system_memory.total) * 100,
                gc_collections=gc_stats
            )
            
        except ImportError:
            # Fallback without psutil
            return MemoryStats(
                total_memory_mb=0,
                available_memory_mb=0,
                process_memory_mb=0,
                process_memory_percent=0
            )
    
    def is_memory_critical(self) -> bool:
        """Check if memory usage is critical."""
        stats = self.get_memory_stats()
        if stats.process_memory_mb == 0:
            return False
        return (stats.process_memory_mb / self.memory_limit_mb) >= self.critical_threshold
    
    def get_memory_usage_ratio(self) -> float:
        """Get current memory usage ratio (0.0-1.0)."""
        stats = self.get_memory_stats()
        if stats.process_memory_mb == 0:
            return 0.0
        return stats.process_memory_mb / self.memory_limit_mb


class StreamingCache:
    """Memory-aware cache that streams data to disk when memory is low."""
    
    def __init__(self, config: StreamingConfig, memory_monitor: MemoryMonitor):
        self.config = config
        self.memory_monitor = memory_monitor
        
        # In-memory cache
        self._memory_cache: Dict[str, Any] = {}
        self._access_order: deque = deque()  # For LRU eviction
        self._access_counts: Dict[str, int] = {}
        
        # Disk cache
        self._temp_dir = Path(config.temp_dir or tempfile.gettempdir()) / "repo_analysis_cache"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._disk_cache_keys: Set[str] = set()
        
        # Cleanup tracking
        self._last_cleanup = time.time()
        
        # Register memory callback
        memory_monitor.add_callback(self._on_memory_event)
        
        logger.info(f"Streaming cache initialized with temp dir: {self._temp_dir}")
    
    def _on_memory_event(self, level: str, stats: MemoryStats) -> None:
        """Handle memory events from monitor."""
        if level == 'critical':
            logger.warning("Critical memory usage detected, forcing cache cleanup")
            self._force_cleanup()
        elif level == 'warning':
            logger.info("High memory usage detected, performing cache cleanup")
            self._cleanup_memory_cache()
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache (memory or disk)."""
        # Check memory cache first
        if key in self._memory_cache:
            self._update_access(key)
            return self._memory_cache[key]
        
        # Check disk cache
        if key in self._disk_cache_keys:
            data = self._load_from_disk(key)
            if data is not None:
                # Move back to memory cache if there's space
                if len(self._memory_cache) < self.config.max_cache_size:
                    self._memory_cache[key] = data
                    self._update_access(key)
                return data
        
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set item in cache."""
        # Check if we need to cleanup first
        if self._should_cleanup():
            self._cleanup_memory_cache()
        
        # Store in memory cache
        self._memory_cache[key] = value
        self._update_access(key)
        
        # If memory is getting full, move some items to disk
        if (len(self._memory_cache) > self.config.max_cache_size or 
            self.memory_monitor.is_memory_critical()):
            self._move_to_disk()
    
    def _update_access(self, key: str) -> None:
        """Update access tracking for LRU."""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        self._access_counts[key] = self._access_counts.get(key, 0) + 1
    
    def _should_cleanup(self) -> bool:
        """Check if cleanup is needed."""
        return (time.time() - self._last_cleanup > self.config.cleanup_interval or
                self.memory_monitor.is_memory_critical())
    
    def _cleanup_memory_cache(self) -> None:
        """Clean up memory cache by moving LRU items to disk."""
        if not self._memory_cache:
            return
        
        # Calculate how many items to move
        target_size = max(self.config.max_cache_size // 2, 10)
        items_to_move = len(self._memory_cache) - target_size
        
        if items_to_move <= 0:
            return
        
        # Move least recently used items to disk
        moved_count = 0
        while moved_count < items_to_move and self._access_order:
            key = self._access_order.popleft()
            if key in self._memory_cache:
                self._save_to_disk(key, self._memory_cache[key])
                del self._memory_cache[key]
                moved_count += 1
        
        self._last_cleanup = time.time()
        logger.debug(f"Moved {moved_count} items from memory to disk cache")
    
    def _force_cleanup(self) -> None:
        """Force aggressive cleanup of memory cache."""
        # Move most items to disk, keep only most frequently accessed
        if not self._memory_cache:
            return
        
        # Sort by access count (keep most accessed)
        sorted_items = sorted(
            self._memory_cache.items(),
            key=lambda x: self._access_counts.get(x[0], 0),
            reverse=True
        )
        
        # Keep only top 10% or minimum 5 items
        keep_count = max(5, len(sorted_items) // 10)
        items_to_keep = dict(sorted_items[:keep_count])
        
        # Move the rest to disk
        moved_count = 0
        for key, value in self._memory_cache.items():
            if key not in items_to_keep:
                self._save_to_disk(key, value)
                moved_count += 1
        
        # Update memory cache
        self._memory_cache = items_to_keep
        self._access_order = deque(items_to_keep.keys())
        
        # Force garbage collection
        gc.collect()
        
        logger.info(f"Force cleanup: moved {moved_count} items to disk, kept {keep_count} in memory")
    
    def _move_to_disk(self) -> None:
        """Move some items from memory to disk."""
        if len(self._memory_cache) <= self.config.max_cache_size // 2:
            return
        
        # Move oldest items to disk
        items_to_move = len(self._memory_cache) - (self.config.max_cache_size // 2)
        moved_count = 0
        
        while moved_count < items_to_move and self._access_order:
            key = self._access_order.popleft()
            if key in self._memory_cache:
                self._save_to_disk(key, self._memory_cache[key])
                del self._memory_cache[key]
                moved_count += 1
    
    def _save_to_disk(self, key: str, value: Any) -> None:
        """Save item to disk cache."""
        try:
            cache_file = self._temp_dir / f"{self._hash_key(key)}.cache"
            
            with open(cache_file, 'wb') as f:
                if self.config.enable_compression:
                    import gzip
                    with gzip.open(f, 'wb') as gz_f:
                        pickle.dump(value, gz_f, protocol=pickle.HIGHEST_PROTOCOL)
                else:
                    pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            self._disk_cache_keys.add(key)
            
        except Exception as e:
            logger.error(f"Failed to save cache item to disk: {e}")
    
    def _load_from_disk(self, key: str) -> Optional[Any]:
        """Load item from disk cache."""
        try:
            cache_file = self._temp_dir / f"{self._hash_key(key)}.cache"
            
            if not cache_file.exists():
                self._disk_cache_keys.discard(key)
                return None
            
            with open(cache_file, 'rb') as f:
                if self.config.enable_compression:
                    import gzip
                    with gzip.open(f, 'rb') as gz_f:
                        return pickle.load(gz_f)
                else:
                    return pickle.load(f)
                    
        except Exception as e:
            logger.error(f"Failed to load cache item from disk: {e}")
            # Remove corrupted cache file
            try:
                cache_file = self._temp_dir / f"{self._hash_key(key)}.cache"
                if cache_file.exists():
                    cache_file.unlink()
                self._disk_cache_keys.discard(key)
            except Exception:
                pass
            return None
    
    def _hash_key(self, key: str) -> str:
        """Generate hash for cache key."""
        import hashlib
        return hashlib.md5(key.encode()).hexdigest()
    
    def clear(self) -> None:
        """Clear all cache data."""
        # Clear memory cache
        self._memory_cache.clear()
        self._access_order.clear()
        self._access_counts.clear()
        
        # Clear disk cache
        try:
            for cache_file in self._temp_dir.glob("*.cache"):
                cache_file.unlink()
        except Exception as e:
            logger.error(f"Failed to clear disk cache: {e}")
        
        self._disk_cache_keys.clear()
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        memory_size = len(self._memory_cache)
        disk_size = len(self._disk_cache_keys)
        
        # Calculate disk cache size
        disk_size_bytes = 0
        try:
            for cache_file in self._temp_dir.glob("*.cache"):
                disk_size_bytes += cache_file.stat().st_size
        except Exception:
            pass
        
        return {
            'memory_items': memory_size,
            'disk_items': disk_size,
            'total_items': memory_size + disk_size,
            'disk_size_mb': disk_size_bytes / 1024 / 1024,
            'max_cache_size': self.config.max_cache_size,
            'temp_dir': str(self._temp_dir)
        }


class StreamingProcessor:
    """Processes large repositories using streaming and memory management."""
    
    def __init__(self, config: StreamingConfig, memory_limit_mb: Optional[int] = None):
        self.config = config
        self.memory_monitor = MemoryMonitor(memory_limit_mb)
        self.cache = StreamingCache(config, self.memory_monitor)
        
        # Processing state
        self._processing_stats = {
            'files_processed': 0,
            'chunks_processed': 0,
            'memory_cleanups': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def __enter__(self) -> "StreamingProcessor":
        """Context manager entry."""
        self.memory_monitor.start_monitoring()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.memory_monitor.stop_monitoring()
        self.cache.clear()
    
    def stream_process_files(self, file_paths: List[str], 
                           processing_function: callable) -> Generator[Tuple[str, Any], None, None]:
        """Stream process files in chunks to manage memory usage.
        
        Args:
            file_paths: List of file paths to process
            processing_function: Function to process each file
            
        Yields:
            Tuples of (file_path, result) for each processed file
        """
        logger.info(f"Starting streaming processing of {len(file_paths)} files")
        
        # Process files in chunks
        for i in range(0, len(file_paths), self.config.chunk_size):
            chunk_files = file_paths[i:i + self.config.chunk_size]
            
            logger.debug(f"Processing chunk {i // self.config.chunk_size + 1}: {len(chunk_files)} files")
            
            # Process chunk
            for file_path in chunk_files:
                try:
                    # Check cache first
                    cached_result = self.cache.get(file_path)
                    if cached_result is not None:
                        self._processing_stats['cache_hits'] += 1
                        yield file_path, cached_result
                        continue
                    
                    self._processing_stats['cache_misses'] += 1
                    
                    # Process file
                    result = processing_function(file_path)
                    
                    # Cache result
                    self.cache.set(file_path, result)
                    
                    # Yield result
                    yield file_path, result
                    
                    self._processing_stats['files_processed'] += 1
                    
                    # Check memory usage
                    if self.memory_monitor.is_memory_critical():
                        logger.warning("Critical memory usage during streaming, forcing cleanup")
                        self._force_memory_cleanup()
                        self._processing_stats['memory_cleanups'] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    yield file_path, None
            
            self._processing_stats['chunks_processed'] += 1
            
            # Cleanup between chunks
            if self._processing_stats['chunks_processed'] % 10 == 0:
                self._cleanup_between_chunks()
    
    def stream_process_repository(self, repo_structure: RepositoryStructure,
                                processing_functions: Dict[str, callable]) -> Iterator[Dict[str, Any]]:
        """Stream process entire repository structure.
        
        Args:
            repo_structure: Repository structure to process
            processing_functions: Dictionary of processing functions by type
            
        Yields:
            Processing results as they become available
        """
        logger.info(f"Starting streaming repository processing: {len(repo_structure.files)} files")
        
        # Process files in streaming fashion
        file_paths = [f.file_path for f in repo_structure.files]
        
        # Parse files
        if 'parse' in processing_functions:
            parse_results = {}
            for file_path, result in self.stream_process_files(file_paths, processing_functions['parse']):
                if result is not None:
                    parse_results[file_path] = result
                    yield {
                        'type': 'file_parsed',
                        'file_path': file_path,
                        'result': result
                    }
        
        # Analyze dependencies (requires all files to be parsed)
        if 'analyze_dependencies' in processing_functions and parse_results:
            logger.info("Starting dependency analysis")
            try:
                dependency_result = processing_functions['analyze_dependencies'](repo_structure)
                yield {
                    'type': 'dependencies_analyzed',
                    'result': dependency_result
                }
            except Exception as e:
                logger.error(f"Error in dependency analysis: {e}")
        
        # Analyze classes
        if 'analyze_classes' in processing_functions:
            logger.info("Starting class analysis")
            try:
                class_result = processing_functions['analyze_classes'](repo_structure)
                yield {
                    'type': 'classes_analyzed',
                    'result': class_result
                }
            except Exception as e:
                logger.error(f"Error in class analysis: {e}")
        
        # Analyze data flow
        if 'analyze_dataflow' in processing_functions:
            logger.info("Starting data flow analysis")
            try:
                dataflow_result = processing_functions['analyze_dataflow'](repo_structure)
                yield {
                    'type': 'dataflow_analyzed',
                    'result': dataflow_result
                }
            except Exception as e:
                logger.error(f"Error in data flow analysis: {e}")
    
    def _force_memory_cleanup(self) -> None:
        """Force aggressive memory cleanup."""
        # Force garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection freed {collected} objects")
        
        # Clear weak references
        try:
            import weakref
            weakref.WeakSet()._cleanup()
        except Exception:
            pass
    
    def _cleanup_between_chunks(self) -> None:
        """Perform cleanup between processing chunks."""
        # Light garbage collection
        gc.collect()
        
        # Log memory stats
        stats = self.memory_monitor.get_memory_stats()
        logger.debug(f"Memory usage: {stats.process_memory_mb:.1f} MB ({stats.process_memory_percent:.1f}%)")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        memory_stats = self.memory_monitor.get_memory_stats()
        cache_stats = self.cache.get_stats()
        
        return {
            **self._processing_stats,
            'memory_stats': {
                'process_memory_mb': memory_stats.process_memory_mb,
                'memory_usage_ratio': self.memory_monitor.get_memory_usage_ratio(),
                'is_critical': self.memory_monitor.is_memory_critical()
            },
            'cache_stats': cache_stats
        }


@contextmanager
def memory_limit_context(limit_mb: int):
    """Context manager for enforcing memory limits."""
    monitor = MemoryMonitor(limit_mb)
    monitor.start_monitoring()
    
    try:
        yield monitor
    finally:
        monitor.stop_monitoring()


def optimize_memory_usage():
    """Optimize memory usage by tuning garbage collection."""
    # Tune garbage collection for better memory management
    gc.set_threshold(700, 10, 10)  # More aggressive collection
    
    # Enable garbage collection debugging in development
    if logger.isEnabledFor(logging.DEBUG):
        gc.set_debug(gc.DEBUG_STATS)
    
    logger.debug("Memory optimization settings applied")