"""Tests for repository manager functionality."""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from repo_architecture_mcp.repository_manager import (
    RepositoryManager,
    RepositoryError,
    AuthenticationError,
    RepositoryAccessError
)
from repo_architecture_mcp.errors import ValidationError


class TestRepositoryManager:
    """Test cases for RepositoryManager class."""
    
    def test_parse_github_url_valid(self):
        """Test parsing valid GitHub URLs."""
        manager = RepositoryManager()
        
        # Test HTTPS URL
        result = manager._parse_github_url("https://github.com/owner/repo")
        assert result == {"owner": "owner", "repo": "repo"}
        
        # Test HTTPS URL with .git suffix
        result = manager._parse_github_url("https://github.com/owner/repo.git")
        assert result == {"owner": "owner", "repo": "repo"}
        
        # Test with additional path components
        result = manager._parse_github_url("https://github.com/owner/repo/tree/main")
        assert result == {"owner": "owner", "repo": "repo"}
    
    def test_parse_github_url_invalid(self):
        """Test parsing invalid GitHub URLs."""
        manager = RepositoryManager()
        
        with pytest.raises(ValidationError):
            manager._parse_github_url("https://gitlab.com/owner/repo")
            
        with pytest.raises(ValidationError):
            manager._parse_github_url("invalid-url")
            
        with pytest.raises(ValidationError):
            manager._parse_github_url("https://github.com/")
    
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self):
        """Test authentication without token."""
        manager = RepositoryManager()
        result = await manager.authenticate()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_authenticate_valid_token(self):
        """Test authentication with valid token."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {"login": "testuser"}
            mock_get.return_value.__aenter__.return_value = mock_response
            
            manager = RepositoryManager("valid_token")
            result = await manager.authenticate()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self):
        """Test authentication with invalid token."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_get.return_value.__aenter__.return_value = mock_response
            
            manager = RepositoryManager("invalid_token")
            with pytest.raises(AuthenticationError):
                await manager.authenticate()
    
    @pytest.mark.asyncio
    async def test_check_repository_access_public(self):
        """Test checking access to public repository."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "name": "test-repo",
                "full_name": "owner/test-repo",
                "private": False,
                "description": "Test repository",
                "language": "Python",
                "size": 1024,
                "default_branch": "main"
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            manager = RepositoryManager()
            result = await manager.check_repository_access("https://github.com/owner/test-repo")
            
            assert result["accessible"] is True
            assert result["private"] is False
            assert result["name"] == "test-repo"
            assert result["language"] == "Python"
    
    @pytest.mark.asyncio
    async def test_check_repository_access_not_found(self):
        """Test checking access to non-existent repository."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 404
            mock_get.return_value.__aenter__.return_value = mock_response
            
            manager = RepositoryManager()
            with pytest.raises(RepositoryAccessError):
                await manager.check_repository_access("https://github.com/owner/nonexistent")
    
    @pytest.mark.asyncio
    async def test_clone_repository_success(self):
        """Test successful repository cloning."""
        with patch('repo_architecture_mcp.repository_manager.Repo.clone_from') as mock_clone:
            with patch.object(RepositoryManager, 'check_repository_access') as mock_check:
                mock_check.return_value = {"accessible": True, "private": False}
                mock_repo = MagicMock()
                mock_clone.return_value = mock_repo
                
                manager = RepositoryManager()
                result = await manager.clone_repository("https://github.com/owner/test-repo")
                
                assert os.path.exists(result)
                assert result in manager._temp_dirs
                mock_clone.assert_called_once()
    
    def test_get_file_tree_invalid_path(self):
        """Test file tree extraction with invalid path."""
        manager = RepositoryManager()
        
        with pytest.raises(RepositoryError):
            asyncio.run(manager.get_file_tree("/nonexistent/path"))
    
    @pytest.mark.asyncio
    async def test_get_file_tree_valid_path(self):
        """Test file tree extraction with valid path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            test_files = [
                "main.py",
                "utils.js",
                "config.json",
                "src/module.py",
                "tests/test_main.py"
            ]
            
            for file_path in test_files:
                full_path = os.path.join(temp_dir, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write("# Test content")
            
            manager = RepositoryManager()
            result = await manager.get_file_tree(temp_dir)
            
            assert result["root"] == temp_dir
            assert result["total_files"] > 0
            assert "Python" in result["languages"]
            assert "JavaScript" in result["languages"]
            
            # Check that JSON file is excluded by default patterns
            file_paths = [f["path"] for f in result["files"]]
            assert "config.json" not in file_paths
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with RepositoryManager() as manager:
            assert manager.session is not None
        
        # Session should be closed after context exit
        assert manager.session.closed
    
    @pytest.mark.asyncio
    async def test_cleanup_temp_dirs(self):
        """Test cleanup of temporary directories."""
        manager = RepositoryManager()
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        manager._temp_dirs.append(temp_dir)
        
        # Verify directory exists
        assert os.path.exists(temp_dir)
        
        # Cleanup
        manager._cleanup_temp_dirs()
        
        # Verify directory is removed
        assert not os.path.exists(temp_dir)
        assert len(manager._temp_dirs) == 0