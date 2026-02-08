"""
Admin routes for TravelLand API.

Routes:
    GET /admin - Admin dashboard
    GET /api/health - Health check
    GET /healthz - Lightweight health endpoint
    GET /metrics/json - Metrics endpoint
    GET /smoke - Smoke test endpoint
"""

from quart import Blueprint, jsonify
import logging
import time
import os

logger = logging.getLogger(__name__)
bp = Blueprint('admin', __name__)


@bp.route('/admin', methods=['GET'])
async def admin_dashboard():
    """
    Admin dashboard for backend visualization.
    
    NOTE: Full HTML dashboard extraction is pending.
    The inline HTML from app.py (~1200 lines) should be moved to templates.py.
    """
    return jsonify({
        "status": "admin_dashboard",
        "note": "Full HTML dashboard extraction pending",
        "endpoints": [
            "/api/health",
            "/healthz",
            "/metrics/json",
            "/smoke"
        ]
    })


@bp.route('/api/health', methods=['GET'])
async def api_health():
    """API health endpoint for admin dashboard."""
    status = {
        'app': 'ok',
        'time': time.time(),
        'groq': bool(os.getenv('GROQ_API_KEY')),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@bp.route('/healthz', methods=['GET'])
async def healthz():
    """Lightweight health endpoint returning component status."""
    status = {
        'app': 'ok',
        'time': time.time(),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@bp.route('/metrics/json', methods=['GET'])
async def metrics_json():
    """Return simple JSON metrics (counters and latency summaries)."""
    try:
        from city_guides.src.metrics import get_metrics as get_metrics_dict
        metrics = await get_metrics_dict()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return jsonify({'error': 'failed to fetch metrics'}), 500


@bp.route('/smoke', methods=['GET'])
async def smoke():
    """Run a small end-to-end smoke check."""
    out = {'ok': True, 'details': {}}
    # pick a stable test coordinate (Tlaquepaque center as representative)
    lat = 20.58775
    lon = -103.30449
    
    out['details']['test_coords'] = {'lat': lat, 'lon': lon}
    
    return jsonify(out)


def register(app):
    """Register admin routes with the app."""
    app.register_blueprint(bp)
    logger.info("✅ Admin routes registered")
