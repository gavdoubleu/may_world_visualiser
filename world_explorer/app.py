"""Flask factory for WorldExplorer.

The explorer is decoupled from world_map on the data path: `world` is a
WorldStore (geography + aggregate stats + row indices only); people, venues
and subsets are served on demand from HDF5 by RecordReader. All routes live in
the bespoke explorer blueprint — none of world_map's eager-object blueprints are
registered.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILTIN_THEMES_DIR = Path(__file__).parent.parent / 'world_map' / 'yaml' / 'themes'
_DEFAULT_THEME = 'dark_scientific'


def create_app(world, hdf5_path, theme=None):
    """Build the WorldExplorer Flask app.

    theme: built-in theme name (e.g. 'dark_scientific', 'clean_minimal');
        defaults to _DEFAULT_THEME, mirroring world_map's config-driven theme.
    """
    from webapp_utilities import make_app, resolve_theme
    from world_reader import RecordReader
    from world_explorer.context import ExplorerContext, _EXPLORER_CTX_KEY
    from world_explorer.routes.explorer import explorer_bp

    record_reader = RecordReader(hdf5_path, world)
    active_theme_name = theme or _DEFAULT_THEME
    theme_dict = resolve_theme(active_theme_name, _BUILTIN_THEMES_DIR)
    context = ExplorerContext(world=world, record_reader=record_reader, theme=theme_dict,
                              active_theme_name=active_theme_name)

    app = make_app(
        __name__,
        blueprints=[explorer_bp],
        context=context,
        context_key=_EXPLORER_CTX_KEY,
        template_folder='templates',
        static_folder='static',
        static_url_path='/static',
    )

    logger.info(f"WorldExplorer initialised: {world}")
    return app
