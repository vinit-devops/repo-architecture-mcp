"""Code parser factory and registry."""

from typing import Dict, List, Optional, Type
import logging
from pathlib import Path

from .base import CodeParser, ParseError
from ..models import CodeStructure
from ..errors import ParsingError, handle_async_exception
from ..logging_config import StructuredLogger


logger = StructuredLogger(__name__)


class ParserRegistry:
    """Registry for managing code parsers."""
    
    def __init__(self):
        self._parsers: Dict[str, CodeParser] = {}
        self._extension_map: Dict[str, str] = {}
    
    def register_parser(self, parser_class: Type[CodeParser]) -> None:
        """
        Register a parser class.
        
        Args:
            parser_class: The parser class to register
        """
        parser = parser_class()
        language = parser.language_name
        
        if language in self._parsers:
            logger.warning(f"Parser for {language} already registered, overwriting")
        
        self._parsers[language] = parser
        
        # Map file extensions to language
        for ext in parser.supported_extensions:
            if ext in self._extension_map:
                logger.warning(f"Extension {ext} already mapped to {self._extension_map[ext]}, overwriting with {language}")
            self._extension_map[ext] = language
        
        logger.info(f"Registered parser for {language} with extensions: {parser.supported_extensions}")
    
    def get_parser(self, file_path: str) -> Optional[CodeParser]:
        """
        Get the appropriate parser for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Parser instance if available, None otherwise
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension in self._extension_map:
            language = self._extension_map[extension]
            return self._parsers.get(language)
        
        return None
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions."""
        return list(self._extension_map.keys())
    
    def get_supported_languages(self) -> List[str]:
        """Get list of all supported programming languages."""
        return list(self._parsers.keys())
    
    def can_parse(self, file_path: str) -> bool:
        """
        Check if any registered parser can handle the file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if a parser is available
        """
        return self.get_parser(file_path) is not None


class CodeParserFactory:
    """Factory for creating and managing code parsers."""
    
    def __init__(self):
        self.registry = ParserRegistry()
        self._initialize_parsers()
    
    def _initialize_parsers(self) -> None:
        """Initialize and register all available parsers."""
        # Import and register parsers here
        # This will be expanded as we implement language-specific parsers
        try:
            from .python_parser import PythonParser
            self.registry.register_parser(PythonParser)
        except ImportError as e:
            logger.warning(f"Failed to import PythonParser: {e}")
        
        try:
            from .javascript_parser import JavaScriptParser
            self.registry.register_parser(JavaScriptParser)
        except ImportError as e:
            logger.warning(f"Failed to import JavaScriptParser: {e}")
        
        try:
            from .typescript_parser import TypeScriptParser
            self.registry.register_parser(TypeScriptParser)
        except ImportError as e:
            logger.warning(f"Failed to import TypeScriptParser: {e}")
        
        try:
            from .java_parser import JavaParser
            self.registry.register_parser(JavaParser)
        except ImportError as e:
            logger.warning(f"Failed to import JavaParser: {e}")
    
    async def parse_file(self, file_path: str, content: Optional[str] = None) -> Optional[CodeStructure]:
        """
        Parse a source code file using the appropriate parser.
        
        Args:
            file_path: Path to the source file
            content: Optional file content (if None, will read from file_path)
            
        Returns:
            CodeStructure if parsing succeeds, None if no parser available
            
        Raises:
            ParsingError: If parsing fails
        """
        parser = self.registry.get_parser(file_path)
        if not parser:
            logger.debug("No parser available for file", file_path=file_path)
            return None
        
        try:
            path = Path(file_path)
            language = parser.language_name
            
            logger.debug("Parsing file", file_path=file_path, language=language)
            result = await parser.parse_file(file_path, content)
            
            if result:
                logger.debug("File parsed successfully", 
                           file_path=file_path, 
                           classes=len(result.classes),
                           functions=len(result.functions),
                           imports=len(result.imports))
            
            return result
            
        except ParseError:
            # Re-raise ParseError as ParsingError
            raise
        except Exception as e:
            error_msg = f"Failed to parse {file_path}: {e}"
            logger.error("File parsing failed", file_path=file_path, error=str(e))
            raise ParsingError(error_msg, file_path=file_path, language=parser.language_name)
    
    def can_parse(self, file_path: str) -> bool:
        """
        Check if the factory can parse the given file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if a parser is available
        """
        return self.registry.can_parse(file_path)
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of all supported file extensions."""
        return self.registry.get_supported_extensions()
    
    def get_supported_languages(self) -> List[str]:
        """Get list of all supported programming languages."""
        return self.registry.get_supported_languages()


# Global factory instance
parser_factory = CodeParserFactory()


# Convenience functions
async def parse_file(file_path: str, content: Optional[str] = None) -> Optional[CodeStructure]:
    """Parse a source code file using the global parser factory."""
    return await parser_factory.parse_file(file_path, content)


def can_parse(file_path: str) -> bool:
    """Check if a file can be parsed using the global parser factory."""
    return parser_factory.can_parse(file_path)


def get_supported_extensions() -> List[str]:
    """Get list of all supported file extensions."""
    return parser_factory.get_supported_extensions()


def get_supported_languages() -> List[str]:
    """Get list of all supported programming languages."""
    return parser_factory.get_supported_languages()