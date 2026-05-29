"""Flask factory for WorldExplorer.

The explorer is decoupled from world_map on the data path: `world` is an
ExplorerWorld (geography + aggregate stats + row indices only); people, venues
and subsets are served on demand from HDF5 by ExplorerLoader. All routes live in
the bespoke explorer blueprint — none of world_map's eager-object blueprints are
registered.
"""

import logging
from flask import Flask
from flask_cors import CORS

logger = logging.getLogger(__name__)


def create_app(world, hdf5_path):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')
    CORS(app)

    from world_explorer.explorer_loader import ExplorerLoader
    from world_explorer.context import ExplorerContext, _EXPLORER_CTX_KEY

    explorer_loader = ExplorerLoader(
        hdf5_path,
        world.person_id_to_idx,
        world.subset_venue_ids,
        world.geography,
        world.subtree_index,
        world.person_geo_unit_ids,
        world.venue_geo_unit_ids,
        world.venue_types_arr,
        world.venue_type_names,
        world.venue_list_position,
        world.person_list_position,
        world.venue_parent_ids,
        world.venue_child_counts,
        world.venue_child_total_members,
        world.children_by_parent_sorted,
        world.children_parent_ids_sorted,
    )
    app.config[_EXPLORER_CTX_KEY] = ExplorerContext(
        world=world,
        explorer_loader=explorer_loader,
    )

    from world_explorer.routes.explorer import explorer_bp
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
