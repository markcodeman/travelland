"""
Routes package for TravelLand API
Blueprint-based modular route organization
"""

from quart import Blueprint


def register_blueprints(app):
    """
    Register all route blueprints with the Quart app
    
    Import order matters for route precedence:
    - Admin routes (health, metrics) first
    - Specific API routes
    - Frontend catch-all routes last
    """
    from .admin import register as register_admin
    from .media import register as register_media
    from .utils import register as register_utils
    from .poi import register as register_poi
    from .search import register as register_search
    from .chat import register as register_chat
    from .locations import register as register_locations
    from .suggestions import register as register_suggestions
    from .guide import register as register_guide
    from .frontend import register as register_frontend
    
    # Register in order of specificity (most specific first)
    register_admin(app)
    register_media(app)
    register_utils(app)
    register_poi(app)
    register_search(app)
    register_chat(app)
    register_locations(app)
    register_suggestions(app)
    register_guide(app)
    register_frontend(app)  # Must be last (catch-all routes)
