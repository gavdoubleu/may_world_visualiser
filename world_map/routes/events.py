"""Events API and events page blueprint."""

from flask import Blueprint, jsonify, request, render_template
import logging

from world_map.app import _convert_numpy_types
from world_map.context import get_app_context

logger = logging.getLogger(__name__)

events_bp = Blueprint('events', __name__)


@events_bp.route('/api/events/config')
def get_event_config():
    """Get event visualization configuration."""
    return jsonify(get_app_context().event_config)


@events_bp.route('/api/events/summary')
def get_events_summary():
    """Get summary of available events."""
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    return jsonify({
        'available_types': loader.get_available_event_types(),
        'counts': loader.get_event_summary(),
        'time_range': loader.get_time_range()
    })


@events_bp.route('/api/events/geojson/batch')
def get_events_geojson_batch():
    """Get GeoJSON for multiple event types in a single request.

    Query params:
        types:      repeated param — e.g. ?types=infections&types=deaths
        time_start: float
        time_end:   float
        method:     'count' | 'rate'
        cumulative: 'true' | 'false'

    Returns:
        JSON object mapping event_type -> GeoJSON FeatureCollection
    """
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    time_start  = request.args.get('time_start', type=float, default=0.0)
    time_end    = request.args.get('time_end',   type=float, default=loader.time_max)
    method      = request.args.get('method', default='count')
    cumulative  = request.args.get('cumulative', default='false').lower() == 'true'
    event_types = request.args.getlist('types')

    try:
        results = {}
        for event_type in event_types:
            results[event_type] = loader.get_events_geojson(
                event_type=event_type,
                time_start=time_start,
                time_end=time_end,
                method=method,
                cumulative=cumulative
            )
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error in batch geojson: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/api/events/geojson/<event_type>')
def get_events_geojson(event_type):
    """Get events as GeoJSON for map display."""
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    time_start = request.args.get('time_start', type=float, default=0.0)
    time_end = request.args.get('time_end', type=float, default=loader.time_max)
    method = request.args.get('method', default='count')
    cumulative = request.args.get('cumulative', default='false').lower() == 'true'

    try:
        geojson = loader.get_events_geojson(
            event_type=event_type,
            time_start=time_start,
            time_end=time_end,
            method=method,
            cumulative=cumulative
        )
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Error getting events geojson: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/api/events/timeseries/<event_type>')
def get_events_timeseries(event_type):
    """Get daily event counts as timeseries."""
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    try:
        df = loader.get_daily_events_timeseries(event_type)
        return jsonify({
            'event_type': event_type,
            'data': df.to_dict(orient='records')
        })
    except Exception as e:
        logger.error(f"Error getting events timeseries: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/api/events/aggregated/<event_type>')
def get_events_aggregated(event_type):
    """Get aggregated events by geo_unit."""
    ctx = get_app_context()
    if ctx.event_loader is None:
        return jsonify({'error': 'Events not loaded'}), 404
    loader = ctx.event_loader

    time_start = request.args.get('time_start', type=float, default=0.0)
    time_end = request.args.get('time_end', type=float, default=loader.time_max)
    method = request.args.get('method', default='count')

    try:
        aggregated = loader.aggregate_events_by_geo_unit(
            event_type=event_type,
            time_start=time_start,
            time_end=time_end,
            method=method
        )

        result = {}
        for geo_unit_id, data in aggregated.items():
            result[str(geo_unit_id)] = _convert_numpy_types(data)

        return jsonify({
            'event_type': event_type,
            'time_start': time_start,
            'time_end': time_end,
            'method': method,
            'data': result
        })
    except Exception as e:
        logger.error(f"Error getting aggregated events: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/events')
def events_page():
    """Serve the events visualization page."""
    return render_template('events_map.html')
