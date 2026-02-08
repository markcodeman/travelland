"""
Admin routes: Health checks, metrics, and smoke tests
"""
import os
import time
import asyncio
from quart import Blueprint, jsonify

# Import dependencies from parent app
from city_guides.src.metrics import get_metrics as get_metrics_dict
from city_guides.providers import multi_provider

bp = Blueprint('admin', __name__)


@bp.route('/healthz')
async def healthz():
    """Lightweight health endpoint returning component status."""
    # Import app globals
    from city_guides.src.app import aiohttp_session, redis_client
    
    status = {
        'app': 'ok',
        'time': time.time(),
        'ready': bool(aiohttp_session is not None),
        'redis': bool(redis_client is not None),
        'geoapify': bool(os.getenv('GEOAPIFY_API_KEY')),
        'geonames': bool(os.getenv('GEONAMES_USERNAME'))
    }
    return jsonify(status)


@bp.route('/metrics/json')
async def metrics_json():
    """Return simple JSON metrics (counters and latency summaries)"""
    try:
        metrics = await get_metrics_dict()
        return jsonify(metrics)
    except Exception:
        from city_guides.src.app import app
        app.logger.exception('Failed to get metrics')
        return jsonify({'error': 'failed to fetch metrics'}), 500


@bp.route('/smoke')
async def smoke():
    """Run a small end-to-end smoke check: reverse lookup + neighborhoods fetch.

    Returns JSON { ok: bool, details: {...} }
    """
    # Import app globals
    from city_guides.src.app import aiohttp_session
    
    out = {'ok': False, 'details': {}}
    # pick a stable test coordinate (Tlaquepaque center as representative)
    lat = 20.58775
    lon = -103.30449
    try:
        # Reverse lookup
        try:
            import importlib
            mod = importlib.import_module('city_guides.providers.overpass_provider')
            geoapify_reverse_geocode_raw = getattr(mod, 'geoapify_reverse_geocode_raw', None)
            async_reverse_geocode = getattr(mod, 'async_reverse_geocode', None)
            
            addr = None
            props = None
            if geoapify_reverse_geocode_raw and callable(geoapify_reverse_geocode_raw):
                result = geoapify_reverse_geocode_raw(lat, lon, session=aiohttp_session)
                if asyncio.iscoroutine(result):
                    props = await result
                else:
                    props = result
                if props and isinstance(props, dict):
                    addr = props.get('formatted') or ''
            
            if not addr and async_reverse_geocode and callable(async_reverse_geocode):
                result = async_reverse_geocode(lat, lon, session=aiohttp_session)
                if asyncio.iscoroutine(result):
                    addr = await result
                else:
                    addr = result
        except Exception:
            addr = None
            props = None
        out['details']['reverse'] = {'display_name': addr or '', 'props': bool(props)}

        # Neighborhoods
        try:
            nb = await multi_provider.async_get_neighborhoods(city=None, lat=lat, lon=lon, lang='en', session=aiohttp_session)
            out['details']['neighborhoods_count'] = len(nb)
        except Exception as e:
            out['details']['neighborhoods_error'] = str(e)
            out['details']['neighborhoods_count'] = 0

        # If reverse lookup or neighborhoods returned anything, consider smoke OK
        if (addr and isinstance(addr, str) and addr.strip()) or out['details'].get('neighborhoods_count', 0) > 0:
            out['ok'] = True
    except Exception as e:
        out['details']['exception'] = str(e)
    return jsonify(out)


def register(app):
    """Register admin blueprint with app"""
    app.register_blueprint(bp)
