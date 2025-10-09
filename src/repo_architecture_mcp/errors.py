"""Comprehensive error handling for the Repository Architecture MCP Server."""

import logging
from typing import Any, Dict, Optional, Union
from enum import Enum


logger = logging.getLogger(__name__)


class ErrorCode(Enum):
    """Standard error codes for MCP responses."""
    # Validation errors
    INVALID_INPUT = "invalid_input"
    INVALID_URL = "invalid_url"
    INVALID_FORMAT = "invalid_format"
    INVALID_PARAMETERS = "invalid_parameters"
    
    # Authentication errors
    AUTH_FAILED = "authentication_failed"
    AUTH_TOKEN_INVALID = "invalid_token"
    AUTH_PERMISSION_DENIED = "permission_denied"
    
    # Repository errors
    REPO_NOT_FOUND = "repository_not_found"
    REPO_ACCESS_DENIED = "repository_access_denied"
    REPO_CLONE_FAILED = "repository_clone_failed"
    REPO_INVALID = "invalid_repository"
    
    # Parsing errors
    PARSE_FAILED = "parsing_failed"
    PARSE_SYNTAX_ERROR = "syntax_error"
    PARSE_UNSUPPORTED_LANGUAGE = "unsupported_language"
    
    # Analysis errors
    ANALYSIS_FAILED = "analysis_failed"
    ANALYSIS_NO_DATA = "no_data_found"
    ANALYSIS_TIMEOUT = "analysis_timeout"
    
    # Generation errors
    GENERATION_FAILED = "diagram_generation_failed"
    GENERATION_FORMAT_ERROR = "format_error"
    GENERATION_SIZE_LIMIT = "size_limit_exceeded"
    
    # Network errors
    NETWORK_ERROR = "network_error"
    NETWORK_TIMEOUT = "network_timeout"
    NETWORK_CONNECTION_FAILED = "connection_failed"
    
    # Resource errors
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    DISK_SPACE_ERROR = "disk_space_error"
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    
    # Internal errors
    INTERNAL_ERROR = "internal_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPENDENCY_ERROR = "dependency_error"


class MCPError(Exception):
    """Base class for all MCP server errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        user_message: Optional[str] = None
    ):
        """Initialize MCP error.
        
        Args:
            message: Technical error message for logging
            code: Error code for categorization
            details: Additional error details
            cause: Original exception that caused this error
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
        self.user_message = user_message or self._generate_user_message()
        
        # Log the error
        self._log_error()
    
    def _generate_user_message(self) -> str:
        """Generate a user-friendly error message based on the error code."""
        user_messages = {
            ErrorCode.INVALID_INPUT: "The provided input is invalid. Please check your parameters and try again.",
            ErrorCode.INVALID_URL: "The repository URL is not valid. Please provide a valid GitHub repository URL.",
            ErrorCode.INVALID_FORMAT: "The requested format is not supported. Please use one of: mermaid, svg, png.",
            ErrorCode.INVALID_PARAMETERS: "One or more parameters are invalid. Please check the documentation for valid parameter values.",
            
            ErrorCode.AUTH_FAILED: "GitHub authentication failed. Please check your access token and try again.",
            ErrorCode.AUTH_TOKEN_INVALID: "The provided GitHub token is invalid or expired. Please generate a new token.",
            ErrorCode.AUTH_PERMISSION_DENIED: "Access denied. You don't have permission to access this repository.",
            
            ErrorCode.REPO_NOT_FOUND: "Repository not found. Please check the URL and ensure the repository exists.",
            ErrorCode.REPO_ACCESS_DENIED: "Access to the repository is denied. The repository may be private or you may lack permissions.",
            ErrorCode.REPO_CLONE_FAILED: "Failed to clone the repository. Please check the URL and your network connection.",
            ErrorCode.REPO_INVALID: "The repository appears to be invalid or corrupted.",
            
            ErrorCode.PARSE_FAILED: "Failed to parse some files in the repository. The analysis may be incomplete.",
            ErrorCode.PARSE_SYNTAX_ERROR: "Syntax errors were found in some files. The analysis may be incomplete.",
            ErrorCode.PARSE_UNSUPPORTED_LANGUAGE: "Some files are in unsupported programming languages and were skipped.",
            
            ErrorCode.ANALYSIS_FAILED: "Repository analysis failed. Please try again or contact support.",
            ErrorCode.ANALYSIS_NO_DATA: "No analyzable code was found in the repository.",
            ErrorCode.ANALYSIS_TIMEOUT: "Analysis timed out. The repository may be too large or complex.",
            
            ErrorCode.GENERATION_FAILED: "Failed to generate the diagram. Please try again with different parameters.",
            ErrorCode.GENERATION_FORMAT_ERROR: "The diagram could not be generated in the requested format.",
            ErrorCode.GENERATION_SIZE_LIMIT: "The diagram is too large to generate. Try filtering or reducing complexity.",
            
            ErrorCode.NETWORK_ERROR: "A network error occurred. Please check your internet connection and try again.",
            ErrorCode.NETWORK_TIMEOUT: "The request timed out. Please try again later.",
            ErrorCode.NETWORK_CONNECTION_FAILED: "Failed to connect to GitHub. Please check your network connection.",
            
            ErrorCode.MEMORY_LIMIT_EXCEEDED: "The repository is too large to process. Try analyzing a smaller repository.",
            ErrorCode.DISK_SPACE_ERROR: "Insufficient disk space to complete the operation.",
            ErrorCode.RESOURCE_UNAVAILABLE: "Required resources are temporarily unavailable. Please try again later.",
            
            ErrorCode.INTERNAL_ERROR: "An internal error occurred. Please try again or contact support.",
            ErrorCode.CONFIGURATION_ERROR: "Server configuration error. Please contact support.",
            ErrorCode.DEPENDENCY_ERROR: "A required dependency is missing or incompatible."
        }
        
        return user_messages.get(self.code, "An unexpected error occurred. Please try again.")
    
    def _log_error(self) -> None:
        """Log the error with appropriate level based on error type."""
        log_message = f"[{self.code.value}] {self.message}"
        
        if self.details:
            log_message += f" | Details: {self.details}"
        
        if self.cause:
            log_message += f" | Caused by: {type(self.cause).__name__}: {self.cause}"
        
        # Determine log level based on error type
        if self.code in [ErrorCode.INTERNAL_ERROR, ErrorCode.CONFIGURATION_ERROR, ErrorCode.DEPENDENCY_ERROR]:
            logger.error(log_message)
        elif self.code in [ErrorCode.NETWORK_ERROR, ErrorCode.MEMORY_LIMIT_EXCEEDED, ErrorCode.ANALYSIS_TIMEOUT]:
            logger.warning(log_message)
        else:
            logger.info(log_message)
    
    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert error to MCP-compliant error response format.
        
        Returns:
            Dictionary formatted for MCP error response
        """
        return {
            "error": {
                "code": self.code.value,
                "message": self.user_message,
                "data": {
                    "technical_message": self.message,
                    "details": self.details,
                    "error_type": type(self).__name__
                }
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format for JSON serialization.
        
        Returns:
            Dictionary representation of the error
        """
        return {
            "error": self.user_message,
            "error_code": self.code.value,
            "error_type": type(self).__name__,
            "technical_details": self.message,
            "additional_info": self.details
        }


class ValidationError(MCPError):
    """Error raised for input validation failures."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["invalid_value"] = str(value)
        
        super().__init__(
            message=message,
            code=ErrorCode.INVALID_INPUT,
            details=details
        )


class AuthenticationError(MCPError):
    """Error raised for GitHub authentication failures."""
    
    def __init__(self, message: str, token_provided: bool = False):
        code = ErrorCode.AUTH_TOKEN_INVALID if token_provided else ErrorCode.AUTH_FAILED
        details = {"token_provided": token_provided}
        
        super().__init__(
            message=message,
            code=code,
            details=details
        )


class RepositoryError(MCPError):
    """Error raised for repository access and manipulation issues."""
    
    def __init__(self, message: str, repo_url: Optional[str] = None, operation: Optional[str] = None):
        details = {}
        if repo_url:
            details["repository_url"] = repo_url
        if operation:
            details["operation"] = operation
        
        super().__init__(
            message=message,
            code=ErrorCode.REPO_ACCESS_DENIED,
            details=details
        )


class RepositoryNotFoundError(RepositoryError):
    """Error raised when repository cannot be found."""
    
    def __init__(self, repo_url: str):
        super().__init__(
            message=f"Repository not found: {repo_url}",
            repo_url=repo_url
        )
        self.code = ErrorCode.REPO_NOT_FOUND


class RepositoryAccessError(RepositoryError):
    """Error raised when repository access is denied."""
    
    def __init__(self, message: str, repo_url: Optional[str] = None):
        super().__init__(message=message, repo_url=repo_url)
        self.code = ErrorCode.REPO_ACCESS_DENIED


class RepositoryCloneError(RepositoryError):
    """Error raised when repository cloning fails."""
    
    def __init__(self, message: str, repo_url: Optional[str] = None):
        super().__init__(message=message, repo_url=repo_url)
        self.code = ErrorCode.REPO_CLONE_FAILED


class ParsingError(MCPError):
    """Error raised for code parsing failures."""
    
    def __init__(self, message: str, file_path: Optional[str] = None, language: Optional[str] = None):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if language:
            details["language"] = language
        
        super().__init__(
            message=message,
            code=ErrorCode.PARSE_FAILED,
            details=details
        )


class AnalysisError(MCPError):
    """Error raised for architecture analysis failures."""
    
    def __init__(self, message: str, analysis_type: Optional[str] = None):
        details = {}
        if analysis_type:
            details["analysis_type"] = analysis_type
        
        super().__init__(
            message=message,
            code=ErrorCode.ANALYSIS_FAILED,
            details=details
        )


class DiagramGenerationError(MCPError):
    """Error raised for diagram generation failures."""
    
    def __init__(self, message: str, diagram_type: Optional[str] = None, format_type: Optional[str] = None):
        details = {}
        if diagram_type:
            details["diagram_type"] = diagram_type
        if format_type:
            details["format"] = format_type
        
        super().__init__(
            message=message,
            code=ErrorCode.GENERATION_FAILED,
            details=details
        )


class NetworkError(MCPError):
    """Error raised for network-related failures."""
    
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None):
        details = {}
        if url:
            details["url"] = url
        if status_code:
            details["status_code"] = status_code
        
        super().__init__(
            message=message,
            code=ErrorCode.NETWORK_ERROR,
            details=details
        )


class ResourceError(MCPError):
    """Error raised for resource-related failures."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        
        super().__init__(
            message=message,
            code=ErrorCode.RESOURCE_UNAVAILABLE,
            details=details
        )


class MemoryLimitError(ResourceError):
    """Error raised when memory limits are exceeded."""
    
    def __init__(self, message: str, current_usage: Optional[int] = None, limit: Optional[int] = None):
        details = {}
        if current_usage:
            details["current_usage_mb"] = current_usage
        if limit:
            details["limit_mb"] = limit
        
        super().__init__(message=message, resource_type="memory")
        self.code = ErrorCode.MEMORY_LIMIT_EXCEEDED


class ConfigurationError(MCPError):
    """Error raised for configuration-related failures."""
    
    def __init__(self, message: str, config_file: Optional[str] = None, config_key: Optional[str] = None):
        details = {}
        if config_file:
            details["config_file"] = config_file
        if config_key:
            details["config_key"] = config_key
        
        super().__init__(
            message=message,
            code=ErrorCode.CONFIGURATION_ERROR,
            details=details
        )


def handle_exception(func):
    """Decorator to handle exceptions and convert them to MCPError instances.
    
    This decorator catches common exceptions and converts them to appropriate
    MCPError subclasses with user-friendly messages.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MCPError:
            # Re-raise MCPError instances as-is
            raise
        except ValueError as e:
            raise ValidationError(f"Invalid input: {str(e)}")
        except FileNotFoundError as e:
            raise RepositoryError(f"File not found: {str(e)}")
        except PermissionError as e:
            raise RepositoryError(f"Permission denied: {str(e)}")
        except ConnectionError as e:
            raise NetworkError(f"Connection failed: {str(e)}")
        except TimeoutError as e:
            raise NetworkError(f"Request timed out: {str(e)}")
        except MemoryError as e:
            raise MemoryLimitError(f"Memory limit exceeded: {str(e)}")
        except Exception as e:
            # Log unexpected errors for debugging
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            raise MCPError(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR,
                cause=e
            )
    
    return wrapper


def handle_async_exception(func):
    """Async version of the exception handling decorator."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except MCPError:
            # Re-raise MCPError instances as-is
            raise
        except ValueError as e:
            raise ValidationError(f"Invalid input: {str(e)}")
        except FileNotFoundError as e:
            raise RepositoryError(f"File not found: {str(e)}")
        except PermissionError as e:
            raise RepositoryError(f"Permission denied: {str(e)}")
        except ConnectionError as e:
            raise NetworkError(f"Connection failed: {str(e)}")
        except TimeoutError as e:
            raise NetworkError(f"Request timed out: {str(e)}")
        except MemoryError as e:
            raise MemoryLimitError(f"Memory limit exceeded: {str(e)}")
        except Exception as e:
            # Log unexpected errors for debugging
            logger.exception(f"Unexpected error in {func.__name__}: {e}")
            raise MCPError(
                message=f"Unexpected error in {func.__name__}: {str(e)}",
                code=ErrorCode.INTERNAL_ERROR,
                cause=e
            )
    
    return wrapper


class ErrorHandler:
    """Centralized error handling utility class."""
    
    @staticmethod
    def validate_github_url(url: str) -> None:
        """Validate GitHub repository URL.
        
        Args:
            url: Repository URL to validate
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url or not isinstance(url, str):
            raise ValidationError("Repository URL must be a non-empty string", field="url", value=url)
        
        if not url.strip():
            raise ValidationError("Repository URL cannot be empty", field="url", value=url)
        
        # Normalize and validate GitHub URL format
        url = url.strip()
        valid_prefixes = ('https://github.com/', 'http://github.com/', 'github.com/')
        
        if not any(url.startswith(prefix) for prefix in valid_prefixes):
            raise ValidationError(
                "URL must be a valid GitHub repository URL",
                field="url",
                value=url
            )
    
    @staticmethod
    def validate_repository_path(path: str) -> None:
        """Validate repository path (GitHub URL or local path).
        
        Args:
            path: Repository URL or local path to validate
            
        Raises:
            ValidationError: If path is invalid
        """
        if not path or not isinstance(path, str):
            raise ValidationError("Repository path must be a non-empty string", field="path", value=path)
        
        if not path.strip():
            raise ValidationError("Repository path cannot be empty", field="path", value=path)
        
        path = path.strip()
        
        # Check if it's a GitHub URL
        github_prefixes = ('https://github.com/', 'http://github.com/', 'github.com/')
        if any(path.startswith(prefix) for prefix in github_prefixes):
            # It's a GitHub URL, validate as such
            return
        
        # Check if it's a local path
        import os
        from pathlib import Path
        
        # Handle common path formats
        if path in ('.', './'):
            # Current directory
            return
        
        if path.startswith(('/', '~', './', '../')):
            # Absolute or relative path
            return
        
        # Check if it looks like a Windows path
        if len(path) > 1 and path[1] == ':':
            # Windows drive path like C:\path
            return
        
        # If we get here, try to see if it's a valid path
        try:
            Path(path).resolve()
            return
        except Exception:
            pass
        
        # If nothing matches, it might still be valid, so allow it
        # The repository manager will handle the actual validation
        return
    
    @staticmethod
    def validate_format(format_type: str, valid_formats: list) -> None:
        """Validate output format.
        
        Args:
            format_type: Format to validate
            valid_formats: List of valid formats
            
        Raises:
            ValidationError: If format is invalid
        """
        if not format_type or format_type not in valid_formats:
            raise ValidationError(
                f"Format must be one of: {', '.join(valid_formats)}",
                field="format",
                value=format_type
            )
    
    @staticmethod
    def validate_positive_integer(value: int, field_name: str, max_value: Optional[int] = None) -> None:
        """Validate positive integer parameter.
        
        Args:
            value: Value to validate
            field_name: Name of the field for error reporting
            max_value: Optional maximum allowed value
            
        Raises:
            ValidationError: If value is invalid
        """
        if not isinstance(value, int) or value < 1:
            raise ValidationError(
                f"{field_name} must be a positive integer",
                field=field_name,
                value=value
            )
        
        if max_value and value > max_value:
            raise ValidationError(
                f"{field_name} must not exceed {max_value}",
                field=field_name,
                value=value
            )
    
    @staticmethod
    def create_graceful_degradation_result(
        partial_result: Dict[str, Any],
        errors: list,
        operation: str
    ) -> Dict[str, Any]:
        """Create a result with graceful degradation information.
        
        Args:
            partial_result: Partial results that were successfully obtained
            errors: List of errors that occurred
            operation: Name of the operation being performed
            
        Returns:
            Dictionary with partial results and error information
        """
        return {
            **partial_result,
            "status": "partial_success",
            "warnings": [
                f"Some errors occurred during {operation}. Results may be incomplete."
            ],
            "error_summary": {
                "total_errors": len(errors),
                "error_types": list(set(type(e).__name__ for e in errors if isinstance(e, Exception))),
                "sample_errors": [str(e) for e in errors[:3]]  # Show first 3 errors
            },
            "recommendations": [
                "Check the error details for specific issues",
                "Some files may have been skipped due to parsing errors",
                "Consider filtering problematic files or directories"
            ]
        }