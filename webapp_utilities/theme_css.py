"""Theme-to-CSS rendering and theme resolution shared by world_map and world_explorer."""

from pathlib import Path

import yaml


def hex_to_rgb(hex_color: str) -> str:
    """Convert '#00d4ff' to '0, 212, 255'."""
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


def build_css_vars(theme_config: dict) -> dict:
    """Expand 9-token theme config into a full CSS variable dict."""
    colors = theme_config.get('colors', {})
    fonts = theme_config.get('fonts', {})

    accent = colors.get('accent', '#000000')
    try:
        accent_rgb = hex_to_rgb(accent)
    except (ValueError, IndexError):
        accent_rgb = '0, 0, 0'

    display_font = fonts.get('display', 'sans-serif')
    body_font = fonts.get('body', 'sans-serif')

    return {
        '--theme-bg':              colors.get('bg', '#ffffff'),
        '--theme-surface':         colors.get('surface', '#f5f5f5'),
        '--theme-surface-raised':  colors.get('surface_raised', '#ffffff'),
        '--theme-border':          colors.get('border', '#dddddd'),
        '--theme-text':            colors.get('text', '#000000'),
        '--theme-text-muted':      colors.get('text_muted', '#666666'),
        '--theme-accent':          accent,
        '--theme-header-bg':       colors.get('header_bg', '#000000'),
        '--theme-header-text':     colors.get('header_text', '#ffffff'),
        '--theme-header-gradient': colors.get('header_gradient', 'var(--theme-header-bg)'),
        '--theme-header-border':   colors.get('header_border', 'transparent'),
        '--theme-header-shadow':   colors.get('header_shadow', '0 1px 4px rgba(0,0,0,0.12)'),
        '--theme-button-hover-bg':    f'rgba({accent_rgb}, 0.12)',
        '--theme-button-active-bg':   f'rgba({accent_rgb}, 0.18)',
        '--theme-button-hover-text':  'var(--theme-accent)',
        '--theme-button-active-text': 'var(--theme-accent)',
        '--theme-table-row-hover':    f'rgba({accent_rgb}, 0.06)',
        '--font-display': f"'{display_font}'",
        '--font-body':    f"'{body_font}'",
    }


def build_root_block(theme_config: dict) -> str:
    """Generate a CSS :root block from theme config."""
    css_vars = build_css_vars(theme_config)
    lines = [f"    {k}: {v};" for k, v in css_vars.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


def render_theme_css(theme_config: dict) -> str:
    """Render a full theme.css body: @font-face rules (served from /static/fonts) + :root block."""
    fonts = theme_config.get('fonts', {})

    display_font = fonts.get('display', 'sans-serif')
    body_font = fonts.get('body', 'sans-serif')
    display_file = fonts.get('display_file', '')
    body_file = fonts.get('body_file', '')

    css_lines = []

    if display_file:
        css_lines.append(
            f"@font-face {{\n"
            f"    font-family: '{display_font}';\n"
            f"    src: url('/static/fonts/{display_file}') format('woff2');\n"
            f"    font-weight: normal;\n"
            f"    font-style: normal;\n"
            f"}}"
        )
    if body_file and body_file != display_file:
        css_lines.append(
            f"@font-face {{\n"
            f"    font-family: '{body_font}';\n"
            f"    src: url('/static/fonts/{body_file}') format('woff2');\n"
            f"    font-weight: normal;\n"
            f"    font-style: normal;\n"
            f"}}"
        )

    css_lines.append(build_root_block(theme_config))

    return "\n\n".join(css_lines)


def resolve_theme(theme_ref: str, builtin_themes_dir: Path, config_dir: Path | None = None) -> dict:
    """Resolve theme_ref to a YAML file and load it.

    theme_ref is either a built-in name ('dark_scientific' — looked up in
    builtin_themes_dir) or a path relative to config_dir ('./my_theme.yaml').
    """
    if theme_ref.endswith('.yaml') or '/' in theme_ref or '\\' in theme_ref:
        if config_dir is None:
            raise ValueError(f"theme_ref {theme_ref!r} is a path but no config_dir given")
        theme_path = config_dir / theme_ref
    else:
        theme_path = builtin_themes_dir / f'{theme_ref}.yaml'
    with open(theme_path) as f:
        return yaml.safe_load(f) or {}
