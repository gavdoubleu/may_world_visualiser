"""Flask factory for WorldExplorer."""

import logging
import numpy as np
import h5py
from flask import Flask
from flask_cors import CORS

logger = logging.getLogger(__name__)


def create_app(world, hdf5_path):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')
    CORS(app)

    venue_index = {}
    if world.venues:
        for venue in world.venues.get_all_venues().values():
            venue_index[venue.id] = venue

    # Build lookup structures from HDF5 (cheap reads only, done once at startup)
    app.config['HDF5_PATH'] = str(hdf5_path)
    with h5py.File(str(hdf5_path), 'r') as f:
        person_ids = f['population/ids'][:]                      # ~19 MB
        person_id_to_idx = np.empty_like(person_ids)
        person_id_to_idx[person_ids] = np.arange(len(person_ids), dtype=person_ids.dtype)
        app.config['PERSON_ID_TO_IDX'] = person_id_to_idx       # inverse permutation

        subset_venue_ids = f['venues/subsets/venue_ids'][:]      # ~11 MB sorted array
        app.config['SUBSET_VENUE_IDS'] = subset_venue_ids

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
