"""
Route registration module for TravelLand API.

This module provides a centralized way to register all API routes
using Flask/Quart Blueprint pattern for better organization and
maintainability.

Usage:
    from city_guides.src.routes import register_all_routes
    register_all_routes(app)
"""

from quart import Quart
import logging

logger = logging.getLogger(__name__)


def register_all_routes(app: Quart) -> None:
    """
    Register all API routes with the Quart application.
    
    This function imports and registers all route blueprints.
    Each route module should expose a `register(app)` function
    that handles its own blueprint registration.
    
    Args:
        app: The Quart application instance
    """
    
    # Import route modules dynamically to avoid circular imports
    # and allow graceful handling of partially implemented modules
    
    route_modules = [
        ('city_guides.src.routes.chat', 'Chat routes'),
        ('city_guides.src.routes.search', 'Search routes'),
        ('city_guides.src.routes.locations', 'Location routes'),
        ('city_guides.src.routes.poi', 'POI discovery routes'),
        ('city_guides.src.routes.media', 'Media search routes'),
        ('city_guides.src.routes.guide', 'Guide generation routes'),
        ('city_guides.src.routes.admin', 'Admin routes'),
        ('city_guides.src.routes.utils', 'Utility routes'),
    ]
    
    registered_count = 0
    
    for module_path, description in route_modules:
        try:
            module = __import__(module_path, fromlist=['register'])
            if hasattr(module, 'register'):
                module.register(app)
                logger.info(f"✅ Registered {description}")
                registered_count += 1
            else:
                logger.warning(f"⚠️  {description} module missing register function")
        except ImportError as e:
            logger.warning(f"⚠️  {description} not yet implemented: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to register {description}: {e}")
    
    logger.info(f"📡 Registered {registered_count}/{len(route_modules)} route modules")


# Re-export for convenience
__all__ = ['register_all_routes']
