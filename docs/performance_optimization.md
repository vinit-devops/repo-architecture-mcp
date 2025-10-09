# Performance Optimization

The Repository Architecture MCP Server includes comprehensive performance optimization features to handle repositories of all sizes efficiently. This document describes the optimization components and how to use them.

## Overview

The performance optimization system consists of four main components:

1. **Cache Manager** - Intelligent caching with file modification tracking
2. **Parallel Processor** - Multi-threaded/multi-process file processing
3. **Memory Manager** - Memory monitoring and streaming for large repositories
4. **Performance Optimizer** - Integrated optimization coordinator

## Components

### Cache Manager

The `CacheManager` provides intelligent caching of analysis results with automatic invalidation based on file modification times.

```python
from repo_architecture_mcp import CacheManager

# Initialize cache manager
cache = CacheManager(
    cache_dir="~/.repo_architecture_cache",
    max_size_mb=500,
    max_age_days=30
)

# Cache and retrieve file structures
cache.set_file_structure(file_path, parsed_structure)
cached_structure = cache.get_file_structure(file_path)

# Cache analysis results
cache.set_analysis_result(repo_path, "dependencies", dependency_graph)
cached_deps = cache.get_analysis_result(repo_path, "dependencies")
```

**Features:**
- File modification time-based invalidation
- Configurable size and age limits
- Automatic cleanup of expired entries
- LRU eviction when size limits are exceeded
- Comprehensive cache statistics

### Parallel Processor

The `ParallelProcessor` enables concurrent processing of multiple files using either thread pools or process pools.

```python
from repo_architecture_mcp import ParallelProcessor, ProgressTracker

# Initialize parallel processor
async with ParallelProcessor(max_workers=8, memory_limit_mb=1024) as processor:
    # Create progress tracker
    progress = ProgressTracker(total_tasks=len(file_paths))
    
    # Process files in parallel
    results = await processor.process_files_parallel(
        file_paths, 
        parsing_function, 
        progress
    )
```

**Features:**
- Configurable worker pools (threads or processes)
- Progress tracking with callbacks
- Memory usage monitoring
- Batch processing for memory efficiency
- Dependency-aware task processing

### Memory Manager

The `MemoryManager` provides memory monitoring and streaming processing for large repositories.

```python
from repo_architecture_mcp import MemoryMonitor, StreamingProcessor, StreamingConfig

# Configure streaming
config = StreamingConfig(
    chunk_size=100,
    memory_threshold_mb=1024,
    max_cache_size=1000
)

# Process with streaming
with StreamingProcessor(config, memory_limit_mb=2048) as processor:
    for file_path, result in processor.stream_process_files(file_paths, parser_func):
        # Process results as they become available
        handle_result(file_path, result)
```

**Features:**
- Real-time memory usage monitoring
- Automatic streaming when memory thresholds are exceeded
- Disk-based caching with compression
- Configurable resource limits
- Graceful degradation under memory pressure

### Performance Optimizer

The `PerformanceOptimizer` integrates all optimization components for seamless performance enhancement.

```python
from repo_architecture_mcp import PerformanceOptimizer, ArchitectureAnalyzer

# Initialize optimizer
optimizer = PerformanceOptimizer(
    cache_dir="/path/to/cache",
    max_workers=8,
    memory_limit_mb=2048,
    enable_streaming=True
)

# Analyze repository with full optimization
results = await optimizer.analyze_repository_optimized(
    repo_path=repo_path,
    file_paths=file_paths,
    parser_function=parser_func,
    analyzer=ArchitectureAnalyzer(),
    progress_callback=progress_callback
)
```

**Features:**
- Automatic selection between parallel and streaming processing
- Integrated caching across all analysis stages
- Memory-aware processing decisions
- Comprehensive performance statistics
- Easy configuration for different repository sizes

## Configuration

### Small Repositories (< 100 files)

```python
optimizer = PerformanceOptimizer(
    max_workers=4,
    memory_limit_mb=512,
    enable_streaming=False,
    streaming_chunk_size=200
)
```

### Medium Repositories (100-1000 files)

```python
optimizer = PerformanceOptimizer(
    max_workers=8,
    memory_limit_mb=1024,
    enable_streaming=True,
    streaming_chunk_size=100
)
```

### Large Repositories (> 1000 files)

```python
optimizer = PerformanceOptimizer(
    max_workers=16,
    memory_limit_mb=2048,
    enable_streaming=True,
    streaming_chunk_size=50
)

# Additional configuration for large repos
configure_for_large_repositories(optimizer)
```

## Memory Management

### Monitoring

The system automatically monitors memory usage and triggers cleanup when thresholds are exceeded:

- **Warning threshold (80%)**: Triggers cache cleanup
- **Critical threshold (90%)**: Forces aggressive memory cleanup
- **Streaming threshold**: Automatically switches to streaming mode

### Optimization Strategies

1. **Caching**: Avoids re-parsing unchanged files
2. **Streaming**: Processes files in chunks to limit memory usage
3. **Parallel Processing**: Utilizes multiple CPU cores efficiently
4. **Memory Monitoring**: Prevents out-of-memory conditions
5. **Garbage Collection**: Optimized GC settings for better performance

## Performance Metrics

The system provides comprehensive performance metrics:

```python
stats = optimizer.get_performance_stats()
print(f"Cache hit ratio: {stats['cache_stats']['hit_ratio']}")
print(f"Memory usage: {stats['memory_stats']['process_memory_mb']} MB")
print(f"Processing method: {stats['processing_method']}")
```

## Best Practices

### 1. Configure Appropriate Limits

Set memory limits based on your system's available RAM:

```python
# For systems with 8GB RAM
optimizer = PerformanceOptimizer(memory_limit_mb=2048)

# For systems with 16GB RAM
optimizer = PerformanceOptimizer(memory_limit_mb=4096)
```

### 2. Use Progress Callbacks

Implement progress callbacks for long-running operations:

```python
def progress_callback(progress_data):
    print(f"Progress: {progress_data['progress_percentage']:.1f}%")
    print(f"Current task: {progress_data.get('current_task', 'Processing')}")

results = await optimizer.analyze_repository_optimized(
    # ... other parameters
    progress_callback=progress_callback
)
```

### 3. Cache Management

Regularly clean up cache to prevent disk space issues:

```python
# Get cache statistics
stats = cache.get_cache_stats()
if stats['total_size_mb'] > 1000:  # If cache > 1GB
    cache.clear_cache()
```

### 4. Error Handling

Handle performance-related errors gracefully:

```python
try:
    results = await optimizer.analyze_repository_optimized(...)
except MemoryError:
    # Reduce memory limits and retry with streaming
    optimizer.memory_limit_mb = 512
    optimizer.enable_streaming = True
    results = await optimizer.analyze_repository_optimized(...)
```

## Troubleshooting

### High Memory Usage

1. Reduce `max_workers` to limit concurrent processing
2. Enable streaming with smaller `chunk_size`
3. Lower `memory_limit_mb` to trigger earlier cleanup
4. Clear cache if it's consuming too much disk space

### Slow Performance

1. Increase `max_workers` if CPU usage is low
2. Disable streaming for small repositories
3. Increase cache size limits
4. Check if cache directory is on a fast disk

### Cache Issues

1. Verify cache directory permissions
2. Check available disk space
3. Clear corrupted cache entries
4. Adjust cache size limits

## Dependencies

The performance optimization features require:

- **Core**: No additional dependencies
- **Memory monitoring**: `psutil` (optional, install with `pip install repo-architecture-mcp-server[performance]`)
- **Compression**: `gzip` (built-in Python module)

## Examples

See `examples/performance_optimization_example.py` for a complete demonstration of the performance optimization features.