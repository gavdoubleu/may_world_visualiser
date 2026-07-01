#!/usr/bin/env python3
"""
Launcher script for World Map visualization.
Loads world_state.h5 with no dependencies on the may module.
"""

import sys
from pathlib import Path

from world_reader import build_world_store

# Import the Flask app
from world_map.app import create_app


def load_world_from_file(filepath):
    """Build a WorldStore from a world_state.h5 file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"World file not found: {filepath}")
    if path.suffix.lower() not in ('.h5', '.hdf5'):
        raise ValueError(f"Expected .h5 or .hdf5, got '{path.suffix}'")
    return build_world_store(str(path))


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Launch World Map visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load a world_state.h5 (map background, title etc. come from --config's
  # 'map'/'title' keys — see world_map/yaml/config.yaml)
  python launch_world_map.py --world-file world_state.h5

  # Include simulation events
  python launch_world_map.py --world-file world_state.h5 \\
      --events-file simulation_events.h5

  # Custom host and port
  python launch_world_map.py --world-file world_state.h5 --host 0.0.0.0 --port 8080
        """
    )

    parser.add_argument(
        '--world-file',
        type=str,
        help='Path to saved World instance file'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='127.0.0.1',
        help='Host to run the server on (default: 127.0.0.1)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to run the server on (default: 5000)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )

    parser.add_argument(
        '--events-file',
        type=str,
        help='Path to simulation_events.h5 file for event visualization'
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config.yaml (default: world_map/yaml/config.yaml)'
    )

    args = parser.parse_args()

    if not args.world_file:
        parser.print_help()
        print("\n\nERROR: --world-file is required\n")
        sys.exit(1)

    print(f"Loading world from: {args.world_file}")
    try:
        world = load_world_from_file(args.world_file)
    except Exception as e:
        print(f"\nERROR: Failed to load world: {e}\n")
        sys.exit(1)

    if not world.geography:
        print("WARNING: World has no geography data")

    if not world.population:
        print("WARNING: World has no population data")

    # Parse map configuration — sourced from --config's 'map' block, not CLI args,
    # so the live server and the static exporter share one source of truth.
    from world_map.config import AppConfig, _DEFAULT_CONFIG_PATH
    config_path = Path(args.config) if args.config else None
    cfg = AppConfig.load(config_path or _DEFAULT_CONFIG_PATH)
    map_settings = cfg.map

    if map_settings.get('background') == 'image':
        image = map_settings.get('image')
        bounds_str = map_settings.get('bounds')
        if not image:
            print("\nERROR: config's 'map.image' is required when map.background=image\n")
            sys.exit(1)
        if not bounds_str:
            print("\nERROR: config's 'map.bounds' is required when map.background=image\n")
            sys.exit(1)

        # Parse bounds
        try:
            bounds_values = [float(x.strip()) for x in bounds_str.split(',')]
            if len(bounds_values) != 4:
                raise ValueError("Expected 4 values")

            north, east, south, west = bounds_values

            # Validate bounds
            if not (-90 <= south < north <= 90):
                raise ValueError(f"Invalid latitude bounds: {south}, {north}")
            if not (-180 <= west < east <= 180):
                raise ValueError(f"Invalid longitude bounds: {west}, {east}")

            bounds = [[south, west], [north, east]]

        except Exception as e:
            print(f"\nERROR: Invalid 'map.bounds' format: {e}")
            print("Expected format: 'north,east,south,west'")
            print("Example: '55.0,2.0,50.0,-5.0'\n")
            sys.exit(1)

        # Check if image file exists (if it's a local path)
        image_path = image

        # If it's a local file path, convert to URL
        if not image_path.startswith(('http://', 'https://')):
            image_file = Path(image_path)
            if not image_file.exists():
                print(f"\nERROR: Image file not found: {image_path}\n")
                sys.exit(1)

            # Copy image to static directory
            import shutil
            static_images_dir = Path(__file__).parent / 'world_map' / 'static' / 'map_images'
            static_images_dir.mkdir(parents=True, exist_ok=True)

            dest_file = static_images_dir / image_file.name
            shutil.copy(image_file, dest_file)

            # Convert to URL path
            image_path = f'/static/map_images/{image_file.name}'
            print(f"Copied image to: {dest_file}")

        map_config = {
            'background_type': 'image',
            'image_url': image_path,
            'bounds': bounds,
            'attribution': map_settings.get('attribution') or 'Custom Map Image'
        }

        print("\nMap Configuration:")
        print(f"  Type: Custom Image")
        print(f"  Image: {image}")
        print(f"  URL: {image_path}")
        print(f"  Bounds: {bounds}")
        print(f"  Attribution: {map_config['attribution']}")

    else:
        # Default OSM configuration
        map_config = {
            'background_type': 'osm',
            'image_url': None,
            'bounds': None,
            'attribution': map_settings.get('attribution') or '© OpenStreetMap contributors'
        }
        print("\nMap Configuration: OpenStreetMap (default)")

    # Initialize and run the Flask app
    app = create_app(world, args.world_file, map_config=map_config, config_path=config_path)

    # Initialize events if provided
    if args.events_file:
        events_path = Path(args.events_file)
        if events_path.exists():
            print(f"\nLoading events from: {events_path}")
            try:
                from world_map.app import initialize_events
                initialize_events(str(events_path), app, world)
                print("Events loaded successfully!")
            except Exception as e:
                print(f"WARNING: Failed to load events: {e}")
        else:
            print(f"\nWARNING: Events file not found: {events_path}")

    print("\n" + "=" * 60)
    print("World Map Visualization")
    print("=" * 60)
    print(f"\nStarting server at http://{args.host}:{args.port}")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60 + "\n")

    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=False  # Prevents Werkzeug's reloader from spawning a second
                                # process that re-executes the script (and re-loads the world)
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user\n")


if __name__ == '__main__':
    main()
