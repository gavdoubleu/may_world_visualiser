"""Flask factory for WorldExplorer."""

import logging
from flask import Flask
from flask_cors import CORS

logger = logging.getLogger(__name__)


def create_app(world):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')
    CORS(app)

    venue_index = {}
    if world.venues:
        for venue in world.venues.get_all_venues().values():
            venue_index[venue.id] = venue

    from world_map.context import AppContext, _CTX_KEY
    from world_map.config import AppConfig
    from world_map.projection.web_mercator import WebMercatorConfig

    app.config[_CTX_KEY] = AppContext(
        world=world,
        venue_index=venue_index,
        projection=WebMercatorConfig(),
        map_config={},
        app_config=AppConfig.minimal(),
    )

    from world_map.routes.geography import geography_bp
    from world_map.routes.population import population_bp
    from world_map.routes.venues import venues_bp
    from world_explorer.routes.explorer import explorer_bp

    app.register_blueprint(geography_bp)
    app.register_blueprint(population_bp)
    app.register_blueprint(venues_bp)
    app.register_blueprint(explorer_bp)

    @app.errorhandler(404)
    def not_found(error):
        from flask import jsonify
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        return jsonify({'error': 'Internal server error'}), 500

    logger.info(f"WorldExplorer initialised: {world}")
    return app
