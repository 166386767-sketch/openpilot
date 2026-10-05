"""
SiNan-Z6 openpilot SINAN Branch — Dark Tech HUD Theme

Pure visual layer, decoupled from vehicle control logic.
Based on the UI design specification for Changan Oushang Z6 iDD.

Usage:
  from openpilot.selfdrive.ui.sinan_theme import SINANColors, SINANFonts, SINANLayout
"""
import pyray as rl


class SINANColors:
  """Color palette for the dark tech HUD style."""

  # ── Base Colors ──
  BG_DARK = rl.Color(0x0A, 0x0E, 0x12, 0xFF)          # #0A0E12 — OLED-friendly dark
  CARD_BG = rl.Color(0x14, 0x1A, 0x21, 0xE6)           # #141A21 ~90% opacity
  DIVIDER = rl.Color(0x1F, 0x27, 0x30, 0xFF)          # #1F2730 — 1px separators

  # ── Text Colors ──
  TEXT_PRIMARY = rl.Color(0xFF, 0xFF, 0xFF, 0xFF)     # White — speed, titles
  TEXT_SECONDARY = rl.Color(0x8A, 0x96, 0xA3, 0xFF)   # #8A96A3 — descriptions
  TEXT_DISABLED = rl.Color(0x3A, 0x45, 0x50, 0xFF)  # #3A4550 — inactive icons

  # ── Accent Colors ──
  ACCENT_CYAN = rl.Color(0x00, 0xE5, 0xFF, 0xFF)     # #00E5FF — active, lanes, progress
  ACCENT_GREEN = rl.Color(0x7C, 0xFF, 0xB2, 0xFF)    # #7CFFB2 — success, ready

  # ── Status Colors ──
  ALERT_TAKEOVER = rl.Color(0xFF, 0x9F, 0x43, 0xFF)  # #FF9F43 — takeover (amber)
  ALERT_CRITICAL = rl.Color(0xFF, 0x47, 0x57, 0xFF)  # #FF4757 — fault / AEB (red)
  ALERT_WARNING = rl.Color(0xFF, 0xD1, 0x66, 0xFF)  # #FFD166 — degradation (yellow)

  # ── Glow Presets (for accent elements) ──
  # Use as: draw_glow_rect(rect, color, radius, alpha)
  GLOW_CYAN = rl.Color(0x00, 0xE5, 0xFF, 0x66)      # 40% opacity cyan glow
  GLOW_GREEN = rl.Color(0x7C, 0xFF, 0xB2, 0x66)     # 40% opacity green glow
  GLOW_AMBER = rl.Color(0xFF, 0x9F, 0x43, 0x66)     # 40% opacity amber glow

  # ── Lane & Lead Vehicle ──
  LANE_ACTIVE = ACCENT_CYAN
  LANE_INACTIVE = rl.Color(0x00, 0xE5, 0xFF, 0x4D)  # 30% opacity cyan
  LEAD_VEHICLE_BOX = rl.Color(0x00, 0xE5, 0xFF, 0x80) # 50% opacity cyan
  LEAD_VEHICLE_GLOW = rl.Color(0x00, 0xE5, 0xFF, 0x33) # 20% opacity cyan

  # ── UI State Colors (replacing old BORDER_COLORS) ──
  STATE_DISENGAGED = rl.Color(0x3A, 0x45, 0x50, 0xFF)  # Gray when off
  STATE_ENGAGED = ACCENT_GREEN                           # Green when active
  STATE_OVERRIDE = rl.Color(0x8A, 0x96, 0xA3, 0xFF)     # Gray when driver override


class SINANFonts:
  """Font size hierarchy (baseline: 2160x1080, scale for other resolutions)."""

  L1_SPEED = 176          # Speed number — bold
  L2_TITLE = 48           # Welcome, alert title
  L3_MENU = 28            # Menu items, card text
  L4_STATUS = 22          # Status values, numbers
  L5_BODY = 18            # Descriptions, version
  L6_UNIT = 16            # km/h, units

  @staticmethod
  def scale_for_resolution(base_size: int, screen_height: int = 1080) -> int:
    """Scale font size based on screen resolution."""
    return int(base_size * screen_height / 1080)


class SINANLayout:
  """Layout grid and spacing constants."""

  SCREEN_MARGIN = 48      # Left/right safe margin
  HEADER_HEIGHT = 72      # Top status bar
  FOOTER_HEIGHT = 64      # Mode bar
  FUNCTION_BAR_HEIGHT = 56  # Function status bar

  # 8px grid multiples
  SPACING_XS = 8
  SPACING_SM = 16
  SPACING_MD = 24
  SPACING_LG = 32
  SPACING_XL = 48

  # Border radius
  CARD_RADIUS = 16
  BUTTON_RADIUS = 12
  TAG_RADIUS = 8

  # Road view occupies 60% of vertical space
  ROAD_VIEW_RATIO = 0.60


# ── Helper: draw glowing rectangle ──
def draw_glow_rect(rect: rl.Rectangle, color: rl.Color, glow_alpha: int = 0x66, blur_radius: float = 12.0):
  """Draw a rectangle with outer glow effect using multiple concentric rectangles."""
  glow_color = rl.Color(color.r, color.g, color.b, glow_alpha)
  # Draw 3 layers of decreasing opacity for glow effect
  for i in range(3, 0, -1):
    expansion = blur_radius * i
    glow_rect = rl.Rectangle(
      rect.x - expansion,
      rect.y - expansion,
      rect.width + 2 * expansion,
      rect.height + 2 * expansion,
    )
    alpha = int(glow_alpha / (i + 1))
    layer_color = rl.Color(color.r, color.g, color.b, alpha)
    rl.draw_rectangle_rounded(glow_rect, 0.3, 8, layer_color)
  rl.draw_rectangle_rounded(rect, 0.15, 8, color)


# ── Helper: draw breathing border ──
def draw_breathing_border(rect: rl.Rectangle, color: rl.Color, period_ms: float = 1000.0, phase: float = 0.0):
  """Draw a breathing (pulsing) border around a rectangle.

  period_ms: full breathe cycle duration in milliseconds
  phase: 0.0~1.0 position in cycle
  """
  import time
  t = (time.monotonic() * 1000.0 + phase * period_ms) % period_ms
  # Sine wave 0~1
  intensity = (math.sin(t / period_ms * 2 * math.pi) + 1.0) / 2.0
  alpha = int(0x40 + intensity * 0xBF)  # 64~255
  border_color = rl.Color(color.r, color.g, color.b, alpha)
  border_thickness = int(2 + intensity * 4)  # 2~6px
  rl.draw_rectangle_lines_ex(rect, border_thickness, border_color)


# ── Helper: hex string to rl.Color ──
def hex_to_color(hex_str: str, alpha: int = 0xFF) -> rl.Color:
  """Convert '#RRGGBB' or 'RRGGBB' to pyray Color."""
  hex_str = hex_str.lstrip('#')
  r = int(hex_str[0:2], 16)
  g = int(hex_str[2:4], 16)
  b = int(hex_str[4:6], 16)
  return rl.Color(r, g, b, alpha)
