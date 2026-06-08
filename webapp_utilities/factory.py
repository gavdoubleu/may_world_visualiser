"""Shared Flask app-assembly skeleton: construction, context stash, error handlers."""

from flask import Flask, current_app, jsonify
from flask_cors import CORS


def make_app(import_name, *, blueprints, context, context_key,
             template_folder=None, static_folder=None, static_url_path=None):
    """Build a Flask app wired with CORS, a stashed typed context, blueprints
    and the standard 404/500 JSON error handlers — the skeleton both
    world_map and world_explorer assemble around their app-specific contexts.
    """
    kwargs = {}
    if template_folder is not None:
        kwargs['template_folder'] = template_folder
    if static_folder is not None:
        kwargs['static_folder'] = static_folder
    if static_url_path is not None:
        kwargs['static_url_path'] = static_url_path

    app = Flask(import_name, **kwargs)
    CORS(app)

    app.config[context_key] = context

    for blueprint in blueprints:
        app.register_blueprint(blueprint)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app


def make_context_accessor(context_key):
    """Return a `get_*_context()`-shaped accessor reading `current_app.config[context_key]`."""
    def get_context():
        return current_app.config[context_key]
    return get_context
