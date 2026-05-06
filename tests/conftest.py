"""Shared pytest fixtures."""

import pytest
from flask import Flask

from world_map.context import AppContext, _CTX_KEY
from world_map.routes.geography import geography_bp
from world_map.routes.events import events_bp
from world_map.routes.venues import venues_bp
from world_map.routes.config_routes import config_bp
from world_map.routes.population import population_bp

_ALL_BLUEPRINTS = [geography_bp, events_bp, venues_bp, config_bp, population_bp]


@pytest.fixture
def client_for():
    """Return a factory that builds a Flask test client from an AppContext."""
    def _make(ctx: AppContext, blueprints=None):
        app = Flask(__name__)
        app.config[_CTX_KEY] = ctx
        app.config['TESTING'] = True
        for bp in (blueprints or _ALL_BLUEPRINTS):
            app.register_blueprint(bp)
        return app.test_client()
    return _make
