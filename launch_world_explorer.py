#!/usr/bin/env python3
"""Launcher for WorldExplorer: file-explorer GUI for a world_state.h5 file."""

import sys
from pathlib import Path

from world_explorer.explorer_world_loader import load_explorer_world
from world_explorer.app import create_app


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Launch WorldExplorer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch_world_explorer.py --world-file data/world_state_medieval.h5
  python launch_world_explorer.py --world-file world.h5 --port 5001 --debug
        """
    )

    parser.add_argument('--world-file', type=str, required=True,
                        help='Path to world_state.h5')
    parser.add_argument('--host',  type=str, default='127.0.0.1',
                        help='Host (default: 127.0.0.1)')
    parser.add_argument('--port',  type=int, default=5001,
                        help='Port (default: 5001)')
    parser.add_argument('--debug', action='store_true',
                        help='Flask debug mode')

    args = parser.parse_args()

    world_path = Path(args.world_file)
    if not world_path.exists():
        print(f'\nERROR: file not found: {args.world_file}\n')
        sys.exit(1)
    if world_path.suffix.lower() not in ('.h5', '.hdf5'):
        print(f'\nERROR: expected .h5 or .hdf5, got {world_path.suffix!r}\n')
        sys.exit(1)

    print(f'Loading world from: {world_path}')
    try:
        world = load_explorer_world(str(world_path))
    except Exception as exc:
        print(f'\nERROR: failed to load world: {exc}\n')
        sys.exit(1)

    app = create_app(world, world_path)

    print(f'\n{"=" * 50}')
    print('  WorldExplorer')
    print(f'{"=" * 50}')
    print(f'  http://{args.host}:{args.port}')
    print('  Ctrl+C to stop')
    print(f'{"=" * 50}\n')

    try:
        app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)
    except KeyboardInterrupt:
        print('\nServer stopped.\n')


if __name__ == '__main__':
    main()
