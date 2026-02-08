"""
Frontend routes: Static file serving for React app
"""
from quart import Blueprint, abort

bp = Blueprint('frontend', __name__)


@bp.route("/", methods=["GET"])
async def index():
    """Serve the React app at root"""
    from city_guides.src.app import app
    return await app.send_static_file("index.html")


@bp.route("/<path:path>", methods=["GET"])
async def catch_all(path):
    """Catch-all route for client-side routing"""
    from city_guides.src.app import app
    # Serve React app for client-side routing
    if path.startswith("api/") or path.startswith("static/"):
        # Let Quart handle API and static routes normally
        abort(404)
    return await app.send_static_file("index.html")


def register(app):
    """Register frontend blueprint with app"""
    app.register_blueprint(bp)
