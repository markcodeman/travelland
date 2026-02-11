"""
Centralized configuration management with validation and type conversion.

This module provides a centralized configuration system to replace
scattered os.getenv() calls and fix configuration-related issues:
- Missing environment variable validation
- Inconsistent timeout values
- No type conversion
- No configuration validation
"""

import os
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class TimeoutConfig:
    """Timeout configuration for different operations."""
    search: float = 10.0
    image: float = 15.0
    geo: float = 8.0
    ai: float = 30.0
    api: float = 30.0
    cache: float = 5.0
    ddgs: float = 5.0
    wikipedia: float = 10.0
    unsplash: float = 15.0
    geonames: float = 8.0
    
    def get(self, operation: str) -> float:
        """Get timeout for a specific operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Timeout value in seconds
        """
        return getattr(self, operation, self.api)


@dataclass
class RedisConfig:
    """Redis configuration."""
    url: str
    max_connections: int = 50
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    health_check_interval: int = 30


@dataclass
class ProviderConfig:
    """Provider-specific configuration."""
    # DDGS Provider
    ddgs_concurrency: int = 3
    ddgs_timeout: float = 5.0
    ddgs_max_results: int = 3
    
    # Unsplash Provider
    unsplash_timeout: float = 15.0
    unsplash_max_results: int = 5
    
    # Wikipedia Provider
    wikipedia_timeout: float = 10.0
    
    # GeoNames Provider
    geonames_timeout: float = 8.0
    
    # Blocked domains for DDGS
    blocked_ddgs_domains: Optional[list] = None

    def __post_init__(self):
        if self.blocked_ddgs_domains is None:
            self.blocked_ddgs_domains = [
                'tripsavvy.com', 'tripadvisor.com', 'wikipedia.org',
                'youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com'
            ]


@dataclass
class CacheConfig:
    """Cache configuration."""
    ttl_search: int = 1800  # 30 minutes
    ttl_neighborhood: int = 3600  # 1 hour
    ttl_image: int = 86400  # 24 hours
    ttl_geo: int = 7200  # 2 hours
    ttl_ai: int = 3600  # 1 hour
    ttl_rag: int = 21600  # 6 hours
    disable_prewarm: bool = False
    prewarm_ttl: int = 1800  # 30 minutes


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: Optional[str] = None
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5


class Config:
    """Centralized configuration with validation and type conversion."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.environment = self._get_environment()
        self.debug = self._get_bool("DEBUG", False)
        
        # API Keys
        self.groq_api_key = self._get_optional("GROQ_API_KEY")
        self.unsplash_key = self._get_optional("UNSPLASH_KEY")
        self.geonames_username = self._get_optional("GEONAMES_USERNAME")
        self.pixabay_key = self._get_optional("PIXABAY_KEY")
        
        # URLs
        self.redis_url: str = self._get_optional("REDIS_URL") or "redis://localhost:6379"
        
        # Timeouts
        self.timeout_config = TimeoutConfig(
            search=self._get_float("TIMEOUT_SEARCH", 10.0),
            image=self._get_float("TIMEOUT_IMAGE", 15.0),
            geo=self._get_float("TIMEOUT_GEO", 8.0),
            ai=self._get_float("TIMEOUT_AI", 30.0),
            api=self._get_float("TIMEOUT_API", 30.0),
            cache=self._get_float("TIMEOUT_CACHE", 5.0),
            ddgs=self._get_float("TIMEOUT_DDGS", 5.0),
            wikipedia=self._get_float("TIMEOUT_WIKIPEDIA", 10.0),
            unsplash=self._get_float("TIMEOUT_UNSPLASH", 15.0),
            geonames=self._get_float("TIMEOUT_GEONAMES", 8.0),
        )
        
        # Redis
        self.redis_config = RedisConfig(
            url=self.redis_url,
            max_connections=self._get_int("REDIS_MAX_CONNECTIONS", 50),
            socket_timeout=self._get_float("REDIS_SOCKET_TIMEOUT", 5.0),
            socket_connect_timeout=self._get_float("REDIS_SOCKET_CONNECT_TIMEOUT", 5.0),
            health_check_interval=self._get_int("REDIS_HEALTH_CHECK_INTERVAL", 30),
        )
        
        # Providers
        self.provider_config = ProviderConfig(
            ddgs_concurrency=self._get_int("DDGS_CONCURRENCY", 3),
            ddgs_timeout=self._get_float("DDGS_TIMEOUT", 5.0),
            ddgs_max_results=self._get_int("DDGS_MAX_RESULTS", 3),
            unsplash_timeout=self._get_float("UNSPLASH_TIMEOUT", 15.0),
            unsplash_max_results=self._get_int("UNSPLASH_MAX_RESULTS", 5),
            wikipedia_timeout=self._get_float("WIKIPEDIA_TIMEOUT", 10.0),
            geonames_timeout=self._get_float("GEONAMES_TIMEOUT", 8.0),
            blocked_ddgs_domains=self._get_list("BLOCKED_DDGS_DOMAINS", [
                'tripsavvy.com', 'tripadvisor.com', 'wikipedia.org',
                'youtube.com', 'facebook.com', 'instagram.com', 'tiktok.com'
            ]),
        )
        
        # Cache
        self.cache_config = CacheConfig(
            ttl_search=self._get_int("CACHE_TTL_SEARCH", 1800),
            ttl_neighborhood=self._get_int("CACHE_TTL_NEIGHBORHOOD", 3600),
            ttl_image=self._get_int("CACHE_TTL_IMAGE", 86400),
            ttl_geo=self._get_int("CACHE_TTL_GEO", 7200),
            ttl_ai=self._get_int("CACHE_TTL_AI", 3600),
            ttl_rag=self._get_int("RAG_CACHE_TTL", 21600),
            disable_prewarm=self._get_bool("DISABLE_PREWARM", False),
            prewarm_ttl=self._get_int("PREWARM_TTL", 1800),
        )
        
        # Logging
        self.logging_config = LoggingConfig(
            level=self._get_str("LOG_LEVEL", "INFO"),
            format=self._get_str("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file=self._get_optional("LOG_FILE"),
            max_bytes=self._get_int("LOG_MAX_BYTES", 10485760),
            backup_count=self._get_int("LOG_BACKUP_COUNT", 5),
        )
        
        # Popular cities for prewarming
        self.popular_cities = self._get_list("POPULAR_CITIES", [])
        
        # Pre-warm queries
        self.prewarm_queries = self._get_list("PREWARM_QUERIES", ["Top food", "Best attractions", "Local tips"])
        self.prewarm_rag_top_n = self._get_int("PREWARM_RAG_TOP_N", 10)
        self.prewarm_rag_concurrency = self._get_int("PREWARM_RAG_CONCURRENCY", 4)
        
        # Validation
        self._validate()
    
    def _get_environment(self) -> Environment:
        """Get application environment."""
        env_str = self._get_str("ENVIRONMENT", "development").lower()
        try:
            return Environment(env_str)
        except ValueError:
            raise ValueError(f"Invalid environment: {env_str}")
    
    def _require_env(self, key: str) -> str:
        """Get required environment variable.
        
        Args:
            key: Environment variable name
            
        Returns:
            Environment variable value
            
        Raises:
            ValueError: If environment variable is missing
        """
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Missing required environment variable: {key}")
        return value
    
    def _get_optional(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get optional environment variable.
        
        Args:
            key: Environment variable name
            default: Default value if not found
            
        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)
    
    def _get_str(self, key: str, default: str) -> str:
        """Get string environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value
            
        Returns:
            Environment variable value or default
        """
        return os.getenv(key, default)
    
    def _get_int(self, key: str, default: int) -> int:
        """Get integer environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value
            
        Returns:
            Environment variable value or default
            
        Raises:
            ValueError: If value cannot be converted to int
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Invalid integer for {key}: {value}")
    
    def _get_float(self, key: str, default: float) -> float:
        """Get float environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value
            
        Returns:
            Environment variable value or default
            
        Raises:
            ValueError: If value cannot be converted to float
        """
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            raise ValueError(f"Invalid float for {key}: {value}")
    
    def _get_bool(self, key: str, default: bool) -> bool:
        """Get boolean environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value
            
        Returns:
            Environment variable value or default
        """
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in ('1', 'true', 'yes', 'on')
    
    def _get_list(self, key: str, default: list) -> list:
        """Get list environment variable with default.
        
        Args:
            key: Environment variable name
            default: Default value
            
        Returns:
            Environment variable value or default
        """
        value = os.getenv(key)
        if value is None:
            return default
        return [item.strip() for item in value.split(',') if item.strip()]
    
    def _validate(self):
        """Validate configuration values."""
        # Validate timeouts
        for attr_name in ['search', 'image', 'geo', 'ai', 'api', 'cache']:
            timeout = getattr(self.timeout_config, attr_name)
            if timeout <= 0:
                raise ValueError(f"Invalid timeout for {attr_name}: {timeout}")
        
        # Validate Redis URL only if provided
        if self.redis_url and not self.redis_url.startswith(('redis://', 'rediss://')):
            raise ValueError(f"Invalid Redis URL: {self.redis_url}")
        
        # Optional API key warnings (don't crash)
        if not self.groq_api_key:
            print("WARNING: GROQ_API_KEY not set - AI features will be disabled")
        
        if not self.unsplash_key:
            print("WARNING: UNSPLASH_KEY not set - image features will be limited")
        
        if not self.geonames_username:
            print("WARNING: GEONAMES_USERNAME not set - geocoding may be limited")
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer environment variable with default (public method).
        
        Args:
            key: Environment variable name
            default: Default value
            
        Returns:
            Environment variable value or default
        """
        return self._get_int(key, default)
    
    def get_timeout(self, operation: str) -> float:
        """Get timeout for a specific operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Timeout value in seconds
        """
        return self.timeout_config.get(operation)
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION
    
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == Environment.TESTING
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for debugging.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'environment': self.environment.value,
            'debug': self.debug,
            'redis_url': self.redis_url,
            'timeout_config': {
                'search': self.timeout_config.search,
                'image': self.timeout_config.image,
                'geo': self.timeout_config.geo,
                'ai': self.timeout_config.ai,
                'api': self.timeout_config.api,
                'cache': self.timeout_config.cache,
            },
            'cache_config': {
                'ttl_search': self.cache_config.ttl_search,
                'ttl_neighborhood': self.cache_config.ttl_neighborhood,
                'ttl_image': self.cache_config.ttl_image,
                'ttl_geo': self.cache_config.ttl_geo,
                'ttl_ai': self.cache_config.ttl_ai,
                'ttl_rag': self.cache_config.ttl_rag,
            },
            'popular_cities': self.popular_cities,
            'prewarm_queries': self.prewarm_queries,
        }


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance.
    
    Returns:
        Configuration instance
    """
    return config


def setup_logging():
    """Set up logging based on configuration."""
    import logging
    from logging.handlers import RotatingFileHandler
    
    config = get_config()
    
    # Set logging level
    logging.basicConfig(
        level=getattr(logging, config.logging_config.level.upper()),
        format=config.logging_config.format,
    )
    
    # Add file handler if configured
    if config.logging_config.file:
        file_handler = RotatingFileHandler(
            config.logging_config.file,
            maxBytes=config.logging_config.max_bytes,
            backupCount=config.logging_config.backup_count,
        )
        file_handler.setFormatter(logging.Formatter(config.logging_config.format))
        logging.getLogger().addHandler(file_handler)
    
    # Set up specific loggers
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    if config.is_development():
        logging.getLogger().setLevel(logging.DEBUG)
    elif config.is_production():
        logging.getLogger().setLevel(logging.INFO)


# Configuration validation functions

def validate_environment():
    """Validate that all required environment variables are set.
    
    Raises:
        ValueError: If any required environment variables are missing
    """
    required_vars = [
        'GROQ_API_KEY',
        'UNSPLASH_ACCESS_KEY', 
        'GEONAMES_USERNAME',
        'REDIS_URL'
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def print_config_summary():
    """Print a summary of the current configuration."""
    config = get_config()
    print("=== Configuration Summary ===")
    print(f"Environment: {config.environment.value}")
    print(f"Debug: {config.debug}")
    print(f"Redis URL: {config.redis_url[:20]}..." if config.redis_url else "None")
    print(f"Popular Cities: {len(config.popular_cities)} cities")
    print(f"Prewarm Queries: {config.prewarm_queries}")
    print(f"Timeouts: {config.timeout_config.get('api')}s (API), {config.timeout_config.get('search')}s (Search)")
    print("==========================")