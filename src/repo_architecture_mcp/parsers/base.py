"""Base classes and interfaces for code parsers."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import logging
from pathlib import Path

from ..models import CodeStructure
from ..errors import ParsingError
from ..logging_config import StructuredLogger


logger = StructuredLogger(__name__)


class ParseError(ParsingError):
    """Exception raised when code parsing fails."""
    
    def __init__(self, message: str, file_path: str, line_number: Optional[int] = None):
        # Store original attributes for backward compatibility
        self._original_message = message
        self.file_path = file_path
        self.line_number = line_number
        
        details = {}
        if line_number:
            details["line_number"] = line_number
        
        # Create full message for the parent class
        full_message = f"{message} in {file_path}" + (f" at line {line_number}" if line_number else "")
        
        super().__init__(
            message=full_message,
            file_path=file_path,
            language=None
        )
        self.details.update(details)
    
    @property
    def message(self) -> str:
        """Return the original message for backward compatibility."""
        return self._original_message
    
    @message.setter
    def message(self, value: str) -> None:
        """Set the message (for parent class compatibility)."""
        # Don't override the original message, just ignore the setter
        pass


class CodeParser(ABC):
    """Abstract base class for all language-specific code parsers."""
    
    def __init__(self):
        self.logger = StructuredLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this parser supports."""
        pass
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the name of the programming language this parser handles."""
        pass
    
    @abstractmethod
    async def parse_file(self, file_path: str, content: Optional[str] = None) -> CodeStructure:
        """
        Parse a source code file and extract its structure.
        
        Args:
            file_path: Path to the source file
            content: Optional file content (if None, will read from file_path)
            
        Returns:
            CodeStructure containing parsed information
            
        Raises:
            ParseError: If parsing fails
        """
        pass
    
    def can_parse(self, file_path: str) -> bool:
        """
        Check if this parser can handle the given file.
        
        Args:
            file_path: Path to the file to check
            
        Returns:
            True if this parser can handle the file
        """
        path = Path(file_path)
        return path.suffix.lower() in self.supported_extensions
    
    def _read_file_content(self, file_path: str) -> str:
        """
        Read content from a file with proper encoding handling.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            File content as string
            
        Raises:
            ParseError: If file cannot be read
        """
        try:
            # Try UTF-8 first
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Fallback to latin-1 if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                raise ParseError(f"Failed to read file with encoding: {e}", file_path)
        except Exception as e:
            raise ParseError(f"Failed to read file: {e}", file_path)
    
    def _create_base_structure(self, file_path: str, content: str) -> CodeStructure:
        """
        Create a base CodeStructure with common information.
        
        Args:
            file_path: Path to the source file
            content: File content
            
        Returns:
            Base CodeStructure instance
        """
        return CodeStructure(
            file_path=file_path,
            language=self.language_name,
            encoding='utf-8'
        )
    
    def _handle_parse_error(self, error: Exception, file_path: str, 
                          line_number: Optional[int] = None) -> CodeStructure:
        """
        Handle parsing errors gracefully by creating a structure with error info.
        
        Args:
            error: The exception that occurred
            file_path: Path to the file being parsed
            line_number: Optional line number where error occurred
            
        Returns:
            CodeStructure with error information
        """
        error_msg = f"Parse error: {str(error)}"
        if line_number:
            error_msg += f" at line {line_number}"
            
        self.logger.warning("Parse error handled gracefully", 
                          file_path=file_path, 
                          error=str(error),
                          line_number=line_number)
        
        structure = CodeStructure(
            file_path=file_path,
            language=self.language_name,
            parse_errors=[error_msg]
        )
        
        return structure