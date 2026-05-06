"""Events API and events page blueprint."""

from flask import Blueprint, jsonify, request, render_template
import logging

from world_map.context import get_app_context

logger = logging.getLogger(__name__)

events_bp = Blueprint('events', __name__)


@events_bp.route('/api/events/config')
def get_event_config():
    return jsonify(get_app_context().app_config.events)


@events_bp.route('/api/events/summary')
def get_events_summary():
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader
    time_min, time_max = loader.time_range
    return jsonify({
        'available_types': loader.available_event_types(),
        'counts': loader.event_summary(),
        'time_range': (time_min, time_max),
    })


@events_bp.route('/api/events/geojson/batch')
def get_events_geojson_batch():
    """Get GeoJSON for multiple event types in a single request.

    Query params:
        types:      repeated — e.g. ?types=infections&types=deaths
        time_start: float
        time_end:   float
        method:     'count' | 'rate'
        cumulative: 'true' | 'false'
    """
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    _, time_max = loader.time_range
    time_start = request.args.get('time_start', type=float, default=0.0)
    time_end = request.args.get('time_end', type=float, default=time_max)
    method = request.args.get('method', default='count')
    cumulative = request.args.get('cumulative', default='false').lower() == 'true'
    event_types = request.args.getlist('types')

    try:
        results = {
            event_type: loader.geojson(
                event_type, time_start, time_end,
                method=method, cumulative=cumulative,
            )
            for event_type in event_types
        }
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in batch geojson: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/api/events/geojson/<event_type>')
def get_events_geojson(event_type):
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    _, time_max = loader.time_range
    time_start = request.args.get('time_start', type=float, default=0.0)
    time_end = request.args.get('time_end', type=float, default=time_max)
    method = request.args.get('method', default='count')
    cumulative = request.args.get('cumulative', default='false').lower() == 'true'

    try:
        return jsonify(loader.geojson(event_type, time_start, time_end,
                                      method=method, cumulative=cumulative))
    except Exception as e:
        logger.error(f"Error getting events geojson: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/api/events/timeseries/<event_type>')
def get_events_timeseries(event_type):
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    try:
        return jsonify({
            'event_type': event_type,
            'data': ctx.event_loader.timeseries(event_type),
        })
    except Exception as e:
        logger.error(f"Error getting events timeseries: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/api/events/aggregated/<event_type>')
def get_events_aggregated(event_type):
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    _, time_max = loader.time_range
    time_start = request.args.get('time_start', type=float, default=0.0)
    time_end = request.args.get('time_end', type=float, default=time_max)
    method = request.args.get('method', default='count')

    try:
        return jsonify({
            'event_type': event_type,
            'time_start': time_start,
            'time_end': time_end,
            'method': method,
            'data': loader.aggregated(event_type, time_start, time_end, method),
        })
    except Exception as e:
        logger.error(f"Error getting aggregated events: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/events')
def events_page():
    return render_template('events_map.html')
