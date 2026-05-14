#!/usr/bin/env python3
"""
Launcher script for World Map visualization.
Loads world_state.h5 with no dependencies on the may module.
"""

import sys
from pathlib import Path

from world_map.core.world_loader import load_world_from_hdf5

# Import the Flask app
from world_map.app import create_app


def load_world_from_file(filepath):
    """Load WorldData from a world_state.h5 file."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"World file not found: {filepath}")
    if path.suffix.lower() not in ('.h5', '.hdf5'):
        raise ValueError(f"Expected .h5 or .hdf5, got '{path.suffix}'")
    return load_world_from_hdf5(str(path))


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Launch World Map visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load a world_state.h5 with OpenStreetMap background
  python launch_world_map.py --world-file world_state.h5

  # Use a custom background image (local file)
  python launch_world_map.py --world-file world_state.h5 \\
      --map-background image \\
      --map-image /path/to/medieval_map.png \\
      --map-bounds "56.0,2.0,49.5,-6.0" \\
      --map-attribution "Medieval England Map - 1348 AD"

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

    # Map configuration arguments
    parser.add_argument(
        '--map-background',
        type=str,
        choices=['osm', 'image'],
        default='osm',
        help='Background map type: osm (OpenStreetMap) or image (custom image)'
    )

    parser.add_argument(
        '--map-image',
        type=str,
        help='Path or URL to custom map background image (required if --map-background=image)'
    )

    parser.add_argument(
        '--map-bounds',
        type=str,
        help='Geographic bounds for custom image: "north,east,south,west" (required if --map-background=image). Example: "55.0,2.0,50.0,-5.0"'
    )

    parser.add_argument(
        '--map-attribution',
        type=str,
        help='Attribution text for custom map image'
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

    # Parse map configuration
    map_config = None

    if args.map_background == 'image':
        if not args.map_image:
            print("\nERROR: --map-image is required when --map-background=image\n")
            sys.exit(1)

        if not args.map_bounds:
            print("\nERROR: --map-bounds is required when --map-background=image\n")
            sys.exit(1)

        # Parse bounds
        try:
            bounds_values = [float(x.strip()) for x in args.map_bounds.split(',')]
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
            print(f"\nERROR: Invalid bounds format: {e}")
            print("Expected format: 'north,east,south,west'")
            print("Example: '55.0,2.0,50.0,-5.0'\n")
            sys.exit(1)

        # Check if image file exists (if it's a local path)
        from pathlib import Path
        image_path = args.map_image

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
            'attribution': args.map_attribution or 'Custom Map Image'
        }

        print("\nMap Configuration:")
        print(f"  Type: Custom Image")
        print(f"  Image: {args.map_image}")
        print(f"  URL: {image_path}")
        print(f"  Bounds: {bounds}")
        print(f"  Attribution: {map_config['attribution']}")

    else:
        # Default OSM configuration
        map_config = {
            'background_type': 'osm',
            'image_url': None,
            'bounds': None,
            'attribution': '© OpenStreetMap contributors'
        }
        print("\nMap Configuration: OpenStreetMap (default)")

    # Initialize and run the Flask app
    from pathlib import Path as _Path
    config_path = _Path(args.config) if args.config else None
    app = create_app(world, map_config=map_config, config_path=config_path)

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
    print("🗺️  World Map Visualization")
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
