"""
Admin routes for TravelLand API.

Routes:
    GET /admin - Admin dashboard
    GET /api/health - Health check
    GET /healthz - Lightweight health endpoint
    GET /metrics/json - Metrics endpoint
    GET /smoke - Smoke test endpoint

TODO: Extract these from app.py:
    - @app.route("/admin", methods=["GET"])
    - @app.route('/api/health')
    - @app.route('/healthz')
    - @app.route('/metrics/json')
    - @app.route('/smoke')
"""

from quart import Blueprint, jsonify, render_template_string
import logging
import time
import os

logger = logging.getLogger(__name__)
bp = Blueprint('admin', __name__)

# Import admin dashboard HTML template
# TODO: Move from app.py to templates.py
# from .templates import admin_dashboard_html


@bp.route('/admin', methods=['GET'])
async def admin_dashboard():
    """
    Admin dashboard for backend visualization.
    
    TODO: Extract HTML template from app.py
    Current location in app.py: ~line 250-1500 (large HTML string)
    """
    # TODO: Import from .templates once extracted
    # html = admin_dashboard_html()
    # return render_template_string(html, ...)
    return jsonify({"error": "Not yet implemented - extract from app.py"}), 501


@bp.route('/api/health', methods=['GET'])
async def api_health():
    """API health endpoint for admin dashboard."""
    # TODO: Extract from app.py
    status = {
        'app': 'ok',
        'time': time.time(),
        # 'ready': bool(aiohttp_session is not None),
        # 'redis': bool(redis_client is not None),
        'groq': bool(os.getenv('GROQ_API_KEY')),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@bp.route('/healthz', methods=['GET'])
async def healthz():
    """Lightweight health endpoint returning component status."""
    # TODO: Extract from app.py
    status = {
        'app': 'ok',
        'time': time.time(),
        # 'ready': bool(aiohttp_session is not None),
        # 'redis': bool(redis_client is not None),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@bp.route('/metrics/json', methods=['GET'])
async def metrics_json():
    """Return simple JSON metrics (counters and latency summaries)."""
    # TODO: Extract from app.py - uses get_metrics_dict()
    try:
        # from city_guides.src.metrics import get_metrics as get_metrics_dict
        # metrics = await get_metrics_dict()
        # return jsonify(metrics)
        return jsonify({'status': 'not yet implemented'})
    except Exception:
        return jsonify({'error': 'failed to fetch metrics'}), 500


@bp.route('/smoke', methods=['GET'])
async def smoke():
    """Run a small end-to-end smoke check."""
    # TODO: Extract from app.py
    out = {'ok': False, 'details': {}}
    # pick a stable test coordinate (Tlaquepaque center as representative)
    lat = 20.58775
    lon = -103.30449
    
    # TODO: Add smoke test logic from app.py
    out['details']['test_coords'] = {'lat': lat, 'lon': lon}
    
    return jsonify(out)


def register(app):
    """Register admin routes with the app."""
    app.register_blueprint(bp)
    logger.info("✅ Admin routes registered")
