"""Cache manager for repository analysis results."""

import json
import logging
import os
import pickle
import shutil
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
import hashlib

from .models import RepositoryStructure, CodeStructure

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached analysis result."""
    
    def __init__(self, data: Any, file_path: str, file_mtime: float, 
                 created_at: float, access_count: int = 0):
        self.data = data
        self.file_path = file_path
        self.file_mtime = file_mtime
        self.created_at = created_at
        self.last_accessed = created_at
        self.access_count = access_count
    
    def is_valid(self) -> bool:
        """Check if cache entry is still valid based on file modification time."""
        try:
            current_mtime = os.path.getmtime(self.file_path)
            return current_mtime <= self.file_mtime
        except (OSError, FileNotFoundError):
            # File doesn't exist anymore
            return False
    
    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


class CacheManager:
    """Manages caching of repository analysis results."""
    
    def __init__(self, cache_dir: Optional[str] = None, max_size_mb: int = 500, 
                 max_age_days: int = 30, cleanup_interval_hours: int = 24):
        """Initialize cache manager.
        
        Args:
            cache_dir: Directory to store cache files (default: ~/.repo_architecture_cache)
            max_size_mb: Maximum cache size in megabytes
            max_age_days: Maximum age of cache entries in days
            cleanup_interval_hours: How often to run cleanup in hours
        """
        self.cache_dir = Path(cache_dir or Path.home() / ".repo_architecture_cache")
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_age_seconds = max_age_days * 24 * 3600
        self.cleanup_interval = cleanup_interval_hours * 3600
        
        # In-memory cache for frequently accessed items
        self._memory_cache: Dict[str, CacheEntry] = {}
        self._last_cleanup = time.time()
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Load cache index
        self._load_cache_index()
        
        logger.info(f"Cache manager initialized with directory: {self.cache_dir}")
    
    def _load_cache_index(self) -> None:
        """Load cache index from disk."""
        index_file = self.cache_dir / "cache_index.json"
        if index_file.exists():
            try:
                with open(index_file, 'r') as f:
                    index_data = json.load(f)
                
                # Validate and load entries
                for key, entry_data in index_data.items():
                    if self._validate_index_entry(entry_data):
                        # Don't load data into memory yet, just metadata
                        self._memory_cache[key] = CacheEntry(
                            data=None,  # Will be loaded on demand
                            file_path=entry_data['file_path'],
                            file_mtime=entry_data['file_mtime'],
                            created_at=entry_data['created_at'],
                            access_count=entry_data.get('access_count', 0)
                        )
                        self._memory_cache[key].last_accessed = entry_data.get('last_accessed', entry_data['created_at'])
                
                logger.info(f"Loaded {len(self._memory_cache)} cache entries from index")
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(f"Failed to load cache index: {e}")
                self._memory_cache = {}
    
    def _save_cache_index(self) -> None:
        """Save cache index to disk."""
        index_file = self.cache_dir / "cache_index.json"
        index_data = {}
        
        for key, entry in self._memory_cache.items():
            index_data[key] = {
                'file_path': entry.file_path,
                'file_mtime': entry.file_mtime,
                'created_at': entry.created_at,
                'last_accessed': entry.last_accessed,
                'access_count': entry.access_count
            }
        
        try:
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save cache index: {e}")
    
    def _validate_index_entry(self, entry_data: Dict[str, Any]) -> bool:
        """Validate cache index entry structure."""
        required_fields = ['file_path', 'file_mtime', 'created_at']
        return all(field in entry_data for field in required_fields)
    
    def _get_cache_key(self, file_path: str, analysis_type: str = "structure") -> str:
        """Generate cache key for a file and analysis type.
        
        Args:
            file_path: Path to the source file
            analysis_type: Type of analysis (structure, dependencies, etc.)
            
        Returns:
            Cache key string
        """
        # Create a hash of the file path and analysis type
        key_string = f"{file_path}:{analysis_type}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_file_path(self, cache_key: str) -> Path:
        """Get the file path for storing cached data.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Path to cache file
        """
        return self.cache_dir / f"{cache_key}.pkl"
    
    def get_file_structure(self, file_path: str) -> Optional[CodeStructure]:
        """Get cached code structure for a file.
        
        Args:
            file_path: Path to the source file
            
        Returns:
            Cached CodeStructure if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(file_path, "structure")
        return self._get_cached_data(cache_key, file_path)
    
    def set_file_structure(self, file_path: str, structure: CodeStructure) -> None:
        """Cache code structure for a file.
        
        Args:
            file_path: Path to the source file
            structure: Parsed code structure
        """
        cache_key = self._get_cache_key(file_path, "structure")
        self._set_cached_data(cache_key, file_path, structure)
    
    def get_repository_structure(self, repo_path: str) -> Optional[RepositoryStructure]:
        """Get cached repository structure.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Cached RepositoryStructure if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(repo_path, "repository")
        return self._get_cached_data(cache_key, repo_path)
    
    def set_repository_structure(self, repo_path: str, structure: RepositoryStructure) -> None:
        """Cache repository structure.
        
        Args:
            repo_path: Path to the repository
            structure: Parsed repository structure
        """
        cache_key = self._get_cache_key(repo_path, "repository")
        self._set_cached_data(cache_key, repo_path, structure)
    
    def get_analysis_result(self, repo_path: str, analysis_type: str) -> Optional[Any]:
        """Get cached analysis result.
        
        Args:
            repo_path: Path to the repository
            analysis_type: Type of analysis (dependencies, classes, dataflow)
            
        Returns:
            Cached analysis result if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(repo_path, analysis_type)
        return self._get_cached_data(cache_key, repo_path)
    
    def set_analysis_result(self, repo_path: str, analysis_type: str, result: Any) -> None:
        """Cache analysis result.
        
        Args:
            repo_path: Path to the repository
            analysis_type: Type of analysis
            result: Analysis result to cache
        """
        cache_key = self._get_cache_key(repo_path, analysis_type)
        self._set_cached_data(cache_key, repo_path, result)
    
    def _get_cached_data(self, cache_key: str, file_path: str) -> Optional[Any]:
        """Get cached data by key.
        
        Args:
            cache_key: Cache key
            file_path: Original file path for validation
            
        Returns:
            Cached data if valid, None otherwise
        """
        # Check if we need to run cleanup
        if time.time() - self._last_cleanup > self.cleanup_interval:
            self._cleanup_cache()
        
        if cache_key not in self._memory_cache:
            return None
        
        entry = self._memory_cache[cache_key]
        
        # Check if entry is still valid
        if not entry.is_valid():
            logger.debug(f"Cache entry invalid for {file_path}")
            self._remove_cache_entry(cache_key)
            return None
        
        # Load data if not already in memory
        if entry.data is None:
            cache_file = self._get_cache_file_path(cache_key)
            if not cache_file.exists():
                logger.debug(f"Cache file missing for {file_path}")
                self._remove_cache_entry(cache_key)
                return None
            
            try:
                with open(cache_file, 'rb') as f:
                    entry.data = pickle.load(f)
                logger.debug(f"Loaded cached data for {file_path}")
            except (pickle.PickleError, OSError) as e:
                logger.warning(f"Failed to load cached data for {file_path}: {e}")
                self._remove_cache_entry(cache_key)
                return None
        
        # Update access statistics
        entry.touch()
        
        return entry.data
    
    def _set_cached_data(self, cache_key: str, file_path: str, data: Any) -> None:
        """Set cached data by key.
        
        Args:
            cache_key: Cache key
            file_path: Original file path
            data: Data to cache
        """
        try:
            # Get file modification time
            file_mtime = os.path.getmtime(file_path)
            current_time = time.time()
            
            # Save data to disk
            cache_file = self._get_cache_file_path(cache_key)
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Create cache entry
            entry = CacheEntry(
                data=data,
                file_path=file_path,
                file_mtime=file_mtime,
                created_at=current_time
            )
            
            self._memory_cache[cache_key] = entry
            
            # Save updated index
            self._save_cache_index()
            
            logger.debug(f"Cached data for {file_path}")
            
        except (OSError, pickle.PickleError) as e:
            logger.error(f"Failed to cache data for {file_path}: {e}")
    
    def _remove_cache_entry(self, cache_key: str) -> None:
        """Remove cache entry.
        
        Args:
            cache_key: Cache key to remove
        """
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
        
        cache_file = self._get_cache_file_path(cache_key)
        if cache_file.exists():
            try:
                cache_file.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove cache file {cache_file}: {e}")
    
    def invalidate_file(self, file_path: str) -> None:
        """Invalidate all cache entries for a specific file.
        
        Args:
            file_path: Path to the file to invalidate
        """
        keys_to_remove = []
        for cache_key, entry in self._memory_cache.items():
            if entry.file_path == file_path:
                keys_to_remove.append(cache_key)
        
        for cache_key in keys_to_remove:
            self._remove_cache_entry(cache_key)
            logger.debug(f"Invalidated cache for {file_path}")
        
        if keys_to_remove:
            self._save_cache_index()
    
    def invalidate_repository(self, repo_path: str) -> None:
        """Invalidate all cache entries for a repository.
        
        Args:
            repo_path: Path to the repository to invalidate
        """
        keys_to_remove = []
        for cache_key, entry in self._memory_cache.items():
            if entry.file_path.startswith(repo_path):
                keys_to_remove.append(cache_key)
        
        for cache_key in keys_to_remove:
            self._remove_cache_entry(cache_key)
        
        if keys_to_remove:
            self._save_cache_index()
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries for repository {repo_path}")
    
    def _cleanup_cache(self) -> None:
        """Clean up expired and oversized cache entries."""
        logger.info("Starting cache cleanup")
        
        current_time = time.time()
        self._last_cleanup = current_time
        
        # Remove expired entries
        expired_keys = []
        for cache_key, entry in self._memory_cache.items():
            if current_time - entry.created_at > self.max_age_seconds:
                expired_keys.append(cache_key)
            elif not entry.is_valid():
                expired_keys.append(cache_key)
        
        for cache_key in expired_keys:
            self._remove_cache_entry(cache_key)
        
        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired cache entries")
        
        # Check cache size and remove least recently used entries if needed
        self._enforce_size_limit()
        
        # Save updated index
        self._save_cache_index()
    
    def _enforce_size_limit(self) -> None:
        """Enforce cache size limit by removing least recently used entries."""
        try:
            # Calculate current cache size
            total_size = 0
            for cache_file in self.cache_dir.glob("*.pkl"):
                total_size += cache_file.stat().st_size
            
            if total_size <= self.max_size_bytes:
                return
            
            logger.info(f"Cache size ({total_size / 1024 / 1024:.1f} MB) exceeds limit, removing LRU entries")
            
            # Sort entries by last accessed time (least recent first)
            sorted_entries = sorted(
                self._memory_cache.items(),
                key=lambda x: x[1].last_accessed
            )
            
            # Remove entries until we're under the size limit
            removed_count = 0
            for cache_key, entry in sorted_entries:
                if total_size <= self.max_size_bytes:
                    break
                
                cache_file = self._get_cache_file_path(cache_key)
                if cache_file.exists():
                    file_size = cache_file.stat().st_size
                    self._remove_cache_entry(cache_key)
                    total_size -= file_size
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Removed {removed_count} LRU cache entries to enforce size limit")
                
        except OSError as e:
            logger.error(f"Failed to enforce cache size limit: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            # Calculate cache size
            total_size = 0
            file_count = 0
            for cache_file in self.cache_dir.glob("*.pkl"):
                total_size += cache_file.stat().st_size
                file_count += 1
            
            # Calculate hit rate (simplified)
            total_accesses = sum(entry.access_count for entry in self._memory_cache.values())
            
            return {
                'cache_dir': str(self.cache_dir),
                'total_entries': len(self._memory_cache),
                'total_size_mb': total_size / 1024 / 1024,
                'max_size_mb': self.max_size_bytes / 1024 / 1024,
                'file_count': file_count,
                'total_accesses': total_accesses,
                'last_cleanup': datetime.fromtimestamp(self._last_cleanup).isoformat()
            }
        except OSError as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {'error': str(e)}
    
    def clear_cache(self) -> None:
        """Clear all cache entries."""
        logger.info("Clearing all cache entries")
        
        # Remove all cache files
        try:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            
            # Remove index file
            index_file = self.cache_dir / "cache_index.json"
            if index_file.exists():
                index_file.unlink()
            
            # Clear memory cache
            self._memory_cache.clear()
            
            logger.info("Cache cleared successfully")
            
        except OSError as e:
            logger.error(f"Failed to clear cache: {e}")