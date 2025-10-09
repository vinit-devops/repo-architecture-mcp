"""Repository management for GitHub access and local analysis."""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import aiohttp
import git
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from .errors import (
    AuthenticationError,
    RepositoryError,
    RepositoryNotFoundError,
    RepositoryAccessError,
    RepositoryCloneError,
    NetworkError,
    ValidationError,
    ErrorHandler,
    handle_async_exception
)


logger = logging.getLogger(__name__)


class RepositoryManager:
    """Handles GitHub repository access and authentication."""
    
    def __init__(self, github_token: Optional[str] = None):
        """Initialize repository manager.
        
        Args:
            github_token: Optional GitHub personal access token for private repos
        """
        self.github_token = github_token
        self.session: Optional[aiohttp.ClientSession] = None
        self._temp_dirs: List[str] = []
        
    async def __aenter__(self) -> "RepositoryManager":
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit with cleanup."""
        if self.session:
            await self.session.close()
        self._cleanup_temp_dirs()
        
    def _cleanup_temp_dirs(self) -> None:
        """Clean up temporary directories created during operation."""
        for temp_dir in self._temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
        self._temp_dirs.clear()
        
    def _is_github_url(self, path: str) -> bool:
        """Check if the path is a GitHub URL.
        
        Args:
            path: Path or URL to check
            
        Returns:
            True if it's a GitHub URL, False if it's a local path
        """
        github_prefixes = ('https://github.com/', 'http://github.com/', 'github.com/')
        return any(path.startswith(prefix) for prefix in github_prefixes)
    
    def _parse_github_url(self, repo_url: str) -> Dict[str, str]:
        """Parse GitHub repository URL to extract owner and repo name.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Dictionary with 'owner' and 'repo' keys
            
        Raises:
            ValidationError: If URL is not a valid GitHub repository URL
        """
        try:
            # Validate URL first
            ErrorHandler.validate_github_url(repo_url)
            
            parsed = urlparse(repo_url)
            
            # Handle different GitHub URL formats
            if parsed.netloc == 'github.com':
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    owner = path_parts[0]
                    repo = path_parts[1]
                    # Remove .git suffix if present
                    if repo.endswith('.git'):
                        repo = repo[:-4]
                    return {'owner': owner, 'repo': repo}
            
            raise ValidationError(f"Invalid GitHub repository URL format: {repo_url}")
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to parse repository URL {repo_url}: {e}")
    
    async def authenticate(self, token: Optional[str] = None) -> bool:
        """Authenticate with GitHub API.
        
        Args:
            token: GitHub personal access token (overrides instance token)
            
        Returns:
            True if authentication successful, False otherwise
            
        Raises:
            AuthenticationError: If authentication fails
        """
        auth_token = token or self.github_token
        
        if not auth_token:
            # No token provided - will only work with public repositories
            logger.info("No GitHub token provided - only public repositories will be accessible")
            return True
            
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            'Authorization': f'token {auth_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'repo-architecture-mcp-server'
        }
        
        try:
            async with self.session.get('https://api.github.com/user', headers=headers, timeout=30) as response:
                if response.status == 200:
                    user_data = await response.json()
                    logger.info(f"Successfully authenticated as GitHub user: {user_data.get('login', 'unknown')}")
                    return True
                elif response.status == 401:
                    raise AuthenticationError("Invalid or expired GitHub token", token_provided=True)
                elif response.status == 403:
                    raise AuthenticationError("GitHub token lacks required permissions", token_provided=True)
                else:
                    error_text = await response.text()
                    raise AuthenticationError(
                        f"GitHub authentication failed: {response.status} - {error_text}",
                        token_provided=True
                    )
                    
        except asyncio.TimeoutError:
            raise NetworkError("GitHub authentication timed out", url="https://api.github.com/user")
        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error during GitHub authentication: {e}", url="https://api.github.com/user")
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Unexpected error during GitHub authentication: {e}", token_provided=bool(auth_token))
    
    async def check_repository_access(self, repo_url: str) -> Dict[str, Union[str, bool]]:
        """Check if repository is accessible and get basic information.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Dictionary with repository information and access status
            
        Raises:
            RepositoryNotFoundError: If repository is not found
            RepositoryAccessError: If repository cannot be accessed
            NetworkError: If network issues occur
        """
        repo_info = self._parse_github_url(repo_url)
        owner, repo = repo_info['owner'], repo_info['repo']
        
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'repo-architecture-mcp-server'
        }
        
        if self.github_token:
            headers['Authorization'] = f'token {self.github_token}'
            
        api_url = f'https://api.github.com/repos/{owner}/{repo}'
        
        try:
            async with self.session.get(api_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    repo_data = await response.json()
                    return {
                        'accessible': True,
                        'private': repo_data.get('private', False),
                        'name': repo_data.get('name', repo),
                        'full_name': repo_data.get('full_name', f'{owner}/{repo}'),
                        'description': repo_data.get('description', ''),
                        'language': repo_data.get('language', 'Unknown'),
                        'size': repo_data.get('size', 0),
                        'default_branch': repo_data.get('default_branch', 'main')
                    }
                elif response.status == 404:
                    raise RepositoryNotFoundError(repo_url)
                elif response.status == 403:
                    error_text = await response.text()
                    if "rate limit" in error_text.lower():
                        raise NetworkError(f"GitHub API rate limit exceeded", url=api_url, status_code=403)
                    else:
                        raise RepositoryAccessError(f"Access forbidden to repository: {repo_url}", repo_url=repo_url)
                elif response.status == 401:
                    raise AuthenticationError("GitHub authentication required for this repository", token_provided=bool(self.github_token))
                else:
                    error_text = await response.text()
                    raise RepositoryAccessError(
                        f"Failed to access repository {repo_url}: {response.status} - {error_text}",
                        repo_url=repo_url,
                        operation="check_access"
                    )
                    
        except asyncio.TimeoutError:
            raise NetworkError(f"Request timed out while accessing repository", url=api_url)
        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error accessing repository {repo_url}: {e}", url=api_url)
        except (RepositoryNotFoundError, RepositoryAccessError, AuthenticationError, NetworkError):
            raise
        except Exception as e:
            raise RepositoryAccessError(f"Unexpected error accessing repository {repo_url}: {e}", repo_url=repo_url)
    
    async def clone_repository(self, repo_url: str, target_dir: Optional[str] = None) -> str:
        """Clone repository to local directory for analysis.
        
        Args:
            repo_url: GitHub repository URL
            target_dir: Optional target directory (creates temp dir if not provided)
            
        Returns:
            Path to cloned repository directory
            
        Raises:
            RepositoryCloneError: If repository cannot be cloned
            RepositoryAccessError: If repository access fails
        """
        # First check if repository is accessible
        await self.check_repository_access(repo_url)
        
        if target_dir is None:
            try:
                target_dir = tempfile.mkdtemp(prefix='repo_analysis_')
                self._temp_dirs.append(target_dir)
                logger.debug(f"Created temporary directory for cloning: {target_dir}")
            except OSError as e:
                raise RepositoryCloneError(f"Failed to create temporary directory: {e}", repo_url=repo_url)
        
        # Prepare clone URL with authentication if token is available
        clone_url = repo_url
        if self.github_token:
            try:
                if not repo_url.startswith('https://'):
                    # Convert to HTTPS URL with token
                    repo_info = self._parse_github_url(repo_url)
                    clone_url = f"https://{self.github_token}@github.com/{repo_info['owner']}/{repo_info['repo']}.git"
                elif repo_url.startswith('https://github.com/'):
                    # Insert token into existing HTTPS URL
                    clone_url = repo_url.replace('https://github.com/', f'https://{self.github_token}@github.com/')
            except Exception as e:
                logger.warning(f"Failed to prepare authenticated clone URL: {e}")
                # Fall back to original URL
                clone_url = repo_url
        
        try:
            logger.info(f"Cloning repository {repo_url} to {target_dir}")
            
            # Use asyncio to run git clone in a thread to avoid blocking
            def _clone_sync() -> Repo:
                return Repo.clone_from(clone_url, target_dir, depth=1)  # Shallow clone for faster operation
            
            # Set a reasonable timeout for cloning
            repo = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, _clone_sync),
                timeout=300  # 5 minutes timeout
            )
            
            logger.info(f"Successfully cloned repository to {target_dir}")
            return target_dir
            
        except asyncio.TimeoutError:
            raise RepositoryCloneError(f"Repository clone timed out after 5 minutes", repo_url=repo_url)
        except GitCommandError as e:
            error_msg = str(e)
            if "authentication failed" in error_msg.lower():
                raise AuthenticationError(f"Git authentication failed for {repo_url}", token_provided=bool(self.github_token))
            elif "repository not found" in error_msg.lower():
                raise RepositoryNotFoundError(repo_url)
            elif "permission denied" in error_msg.lower():
                raise RepositoryAccessError(f"Permission denied cloning repository: {repo_url}", repo_url=repo_url)
            else:
                raise RepositoryCloneError(f"Git clone failed for {repo_url}: {error_msg}", repo_url=repo_url)
        except Exception as e:
            raise RepositoryCloneError(f"Unexpected error cloning repository {repo_url}: {e}", repo_url=repo_url)
    
    async def get_file_tree(self, repo_path: str, include_patterns: Optional[List[str]] = None, 
                           exclude_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get repository file structure with filtering options.
        
        Args:
            repo_path: Path to local repository directory
            include_patterns: List of glob patterns for files to include
            exclude_patterns: List of glob patterns for files to exclude
            
        Returns:
            Dictionary containing file tree structure and metadata
            
        Raises:
            RepositoryError: If repository path is invalid or cannot be read
        """
        if not os.path.exists(repo_path):
            raise RepositoryError(f"Repository path does not exist: {repo_path}", repo_url=None, operation="get_file_tree")
            
        if not os.path.isdir(repo_path):
            raise RepositoryError(f"Repository path is not a directory: {repo_path}", repo_url=None, operation="get_file_tree")
        
        # Default patterns if not provided
        if include_patterns is None:
            include_patterns = [
                "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx",
                "**/*.java", "**/*.go", "**/*.rs", "**/*.cpp", "**/*.c",
                "**/*.h", "**/*.hpp", "**/*.cs", "**/*.php", "**/*.rb",
                "**/*.swift", "**/*.kt", "**/*.scala", "**/*.clj"
            ]
            
        if exclude_patterns is None:
            exclude_patterns = [
                "**/node_modules/**", "**/__pycache__/**", "**/venv/**",
                "**/env/**", "**/.git/**", "**/build/**", "**/dist/**",
                "**/target/**", "**/*.pyc", "**/*.pyo", "**/*.class",
                "**/.pytest_cache/**", "**/coverage/**", "**/.coverage"
            ]
        
        try:
            repo_path_obj = Path(repo_path)
            file_tree: Dict[str, Any] = {
                'root': str(repo_path_obj),
                'files': [],
                'directories': [],
                'total_files': 0,
                'total_size': 0,
                'languages': {},
                'access_errors': []  # Track files that couldn't be accessed
            }
            
            def _should_include_file(file_path: Path) -> bool:
                """Check if file should be included based on patterns."""
                try:
                    relative_path = file_path.relative_to(repo_path_obj)
                    relative_str = str(relative_path)
                    
                    # Check exclude patterns first
                    for pattern in exclude_patterns:
                        if relative_path.match(pattern.replace('**/', '')):
                            return False
                    
                    # Check include patterns
                    for pattern in include_patterns:
                        if relative_path.match(pattern.replace('**/', '')):
                            return True
                            
                    return False
                except Exception:
                    return False
            
            def _get_language_from_extension(file_path: Path) -> str:
                """Determine programming language from file extension."""
                extension_map = {
                    '.py': 'Python',
                    '.js': 'JavaScript',
                    '.ts': 'TypeScript',
                    '.jsx': 'JavaScript',
                    '.tsx': 'TypeScript',
                    '.java': 'Java',
                    '.go': 'Go',
                    '.rs': 'Rust',
                    '.cpp': 'C++',
                    '.c': 'C',
                    '.h': 'C/C++',
                    '.hpp': 'C++',
                    '.cs': 'C#',
                    '.php': 'PHP',
                    '.rb': 'Ruby',
                    '.swift': 'Swift',
                    '.kt': 'Kotlin',
                    '.scala': 'Scala',
                    '.clj': 'Clojure'
                }
                return extension_map.get(file_path.suffix.lower(), 'Unknown')
            
            # Walk through repository directory with error handling
            try:
                for item in repo_path_obj.rglob('*'):
                    try:
                        if item.is_file() and _should_include_file(item):
                            try:
                                file_size = item.stat().st_size
                                relative_path = str(item.relative_to(repo_path_obj))
                                language = _get_language_from_extension(item)
                                
                                file_info = {
                                    'path': relative_path,
                                    'absolute_path': str(item),
                                    'size': file_size,
                                    'language': language,
                                    'extension': item.suffix.lower()
                                }
                                
                                file_tree['files'].append(file_info)
                                file_tree['total_files'] += 1
                                file_tree['total_size'] += file_size
                                
                                # Update language statistics
                                if language in file_tree['languages']:
                                    file_tree['languages'][language]['count'] += 1
                                    file_tree['languages'][language]['size'] += file_size
                                else:
                                    file_tree['languages'][language] = {'count': 1, 'size': file_size}
                                    
                            except (OSError, PermissionError) as e:
                                error_msg = f"Could not access file {item}: {e}"
                                file_tree['access_errors'].append(error_msg)
                                logger.warning(error_msg)
                                continue
                                
                        elif item.is_dir():
                            try:
                                # Check if directory should be excluded
                                relative_path = str(item.relative_to(repo_path_obj))
                                if relative_path and not any(item.match(pattern.replace('**/', '')) for pattern in exclude_patterns):
                                    file_tree['directories'].append(relative_path)
                            except Exception as e:
                                logger.debug(f"Could not process directory {item}: {e}")
                                continue
                                
                    except (OSError, PermissionError) as e:
                        error_msg = f"Could not access path {item}: {e}"
                        file_tree['access_errors'].append(error_msg)
                        logger.warning(error_msg)
                        continue
                        
            except Exception as e:
                logger.warning(f"Error during directory traversal: {e}")
                # Continue with partial results
            
            logger.info(f"Extracted file tree: {file_tree['total_files']} files in {len(file_tree['directories'])} directories")
            
            if file_tree['access_errors']:
                logger.warning(f"Encountered {len(file_tree['access_errors'])} file access errors during tree extraction")
            
            return file_tree
            
        except Exception as e:
            error_msg = f"Failed to extract file tree from {repo_path}: {e}"
            logger.error(error_msg)
            raise RepositoryError(error_msg, repo_url=None, operation="get_file_tree")
    
    async def get_repository_info(self, repo_path_or_url: str) -> Dict[str, Any]:
        """Get comprehensive repository information including file structure.
        
        Args:
            repo_path_or_url: GitHub repository URL or local repository path
            
        Returns:
            Dictionary with repository metadata and file structure
            
        Raises:
            RepositoryError: If repository cannot be analyzed
            RepositoryNotFoundError: If repository is not found
            RepositoryAccessError: If repository access fails
            NetworkError: If network issues occur
        """
        try:
            # Check if it's a GitHub URL or local path
            if self._is_github_url(repo_path_or_url):
                # Handle GitHub repository
                return await self._get_github_repository_info(repo_path_or_url)
            else:
                # Handle local repository
                return await self._get_local_repository_info(repo_path_or_url)
                
        except Exception as e:
            logger.error(f"Failed to get repository info for {repo_path_or_url}: {e}")
            raise
    
    async def _get_github_repository_info(self, repo_url: str) -> Dict[str, Any]:
        """Get repository information for GitHub repositories.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Dictionary with repository metadata and file structure
        """
        # Get basic repository information
        repo_info = await self.check_repository_access(repo_url)
        
        # Clone repository for local analysis
        repo_path = await self.clone_repository(repo_url)
        
        # Extract file tree with graceful error handling
        file_tree = await self.get_file_tree(repo_path)
        
        # Combine information
        comprehensive_info: Dict[str, Any] = {
            **repo_info,
            'file_tree': file_tree,
            'analysis_path': repo_path
        }
        
        # Add warning if there were access errors during file tree extraction
        if file_tree.get('access_errors'):
            comprehensive_info['warnings'] = [
                f"Some files could not be accessed during analysis ({len(file_tree['access_errors'])} errors)"
            ]
        
        return comprehensive_info
    
    async def _get_local_repository_info(self, repo_path: str) -> Dict[str, Any]:
        """Get repository information for local repositories.
        
        Args:
            repo_path: Local repository path
            
        Returns:
            Dictionary with repository metadata and file structure
        """
        import os
        from pathlib import Path
        
        # Resolve the path
        resolved_path = Path(repo_path).resolve()
        
        # Check if path exists and is a directory
        if not resolved_path.exists():
            raise RepositoryError(f"Repository path does not exist: {repo_path}", repo_url=None, operation="get_local_info")
        
        if not resolved_path.is_dir():
            raise RepositoryError(f"Repository path is not a directory: {repo_path}", repo_url=None, operation="get_local_info")
        
        # Extract file tree
        file_tree = await self.get_file_tree(str(resolved_path))
        
        # Create basic repository info for local repositories
        repo_info = {
            'accessible': True,
            'private': False,  # Local repos are considered "public" for analysis purposes
            'name': resolved_path.name,
            'full_name': str(resolved_path),
            'description': f"Local repository at {resolved_path}",
            'language': self._detect_primary_language(file_tree),
            'size': file_tree.get('total_size', 0) // 1024,  # Convert to KB like GitHub API
            'default_branch': 'main'  # Default assumption
        }
        
        # Combine information
        comprehensive_info: Dict[str, Any] = {
            **repo_info,
            'file_tree': file_tree,
            'analysis_path': str(resolved_path)
        }
        
        # Add warning if there were access errors during file tree extraction
        if file_tree.get('access_errors'):
            comprehensive_info['warnings'] = [
                f"Some files could not be accessed during analysis ({len(file_tree['access_errors'])} errors)"
            ]
        
        return comprehensive_info
    
    def _detect_primary_language(self, file_tree: Dict[str, Any]) -> str:
        """Detect the primary programming language from file tree.
        
        Args:
            file_tree: File tree structure with language statistics
            
        Returns:
            Primary language name or 'Unknown'
        """
        languages = file_tree.get('languages', {})
        if not languages:
            return 'Unknown'
        
        # Find language with most files
        primary_language = max(languages.items(), key=lambda x: x[1]['count'] if isinstance(x[1], dict) else x[1])
        return primary_language[0]