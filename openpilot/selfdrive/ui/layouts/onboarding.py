import os
import re
import threading
from enum import IntEnum

import pyray as rl
from openpilot.common.basedir import BASEDIR
from openpilot.system.ui.lib.application import FontWeight, gui_app, TextAlignment
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.button import Button, ButtonStyle
from openpilot.system.ui.widgets.label import Label
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.common.version import terms_version, training_version
from openpilot.selfdrive.ui.sinan_theme import SINANColors
from openpilot.system.ui.lib.text_measure import measure_text_cached
import math
import time

DEBUG = False

STEP_RECTS = [rl.Rectangle(104, 800, 633, 175), rl.Rectangle(1835, 0, 2159, 1080), rl.Rectangle(1835, 0, 2156, 1080),
              rl.Rectangle(1526, 473, 427, 472), rl.Rectangle(1643, 441, 217, 223), rl.Rectangle(1835, 0, 2155, 1080),
              rl.Rectangle(1786, 591, 267, 236), rl.Rectangle(1353, 0, 804, 1080), rl.Rectangle(1458, 485, 633, 211),
              rl.Rectangle(95, 794, 1158, 187), rl.Rectangle(1560, 170, 392, 397), rl.Rectangle(1835, 0, 2159, 1080),
              rl.Rectangle(1351, 0, 807, 1080), rl.Rectangle(1835, 0, 2158, 1080), rl.Rectangle(1531, 82, 441, 920),
              rl.Rectangle(1336, 438, 490, 393), rl.Rectangle(1835, 0, 2159, 1080), rl.Rectangle(1835, 0, 2159, 1080),
              rl.Rectangle(87, 795, 1187, 186)]

DM_RECORD_STEP = 9
DM_RECORD_YES_RECT = rl.Rectangle(695, 794, 558, 187)

RESTART_TRAINING_RECT = rl.Rectangle(87, 795, 472, 186)


class OnboardingState(IntEnum):
  WELCOME = 0
  TERMS = 1
  ONBOARDING = 2
  DECLINE = 3


class TrainingGuide(Widget):
  def __init__(self, completed_callback=None):
    super().__init__()
    self._completed_callback = completed_callback

    self._step = 0
    self._load_image_paths()

    # Load first image now so we show something immediately
    self._textures = [gui_app.texture(self._image_paths[0])]
    self._image_objs = []

    threading.Thread(target=self._preload_thread, daemon=True).start()

  def _load_image_paths(self):
    paths = [fn for fn in os.listdir(os.path.join(BASEDIR, "openpilot/selfdrive/assets/training")) if re.match(r'^step\d*\.png$', fn)]
    paths = sorted(paths, key=lambda x: int(re.search(r'\d+', x).group()))
    self._image_paths = [os.path.join(BASEDIR, "openpilot/selfdrive/assets/training", fn) for fn in paths]

  def _preload_thread(self):
    # PNG loading is slow in raylib, so we preload in a thread and upload to GPU in main thread
    # We've already loaded the first image on init
    for path in self._image_paths[1:]:
      self._image_objs.append(gui_app._load_image_from_path(path))

  def _handle_mouse_release(self, mouse_pos):
    if rl.check_collision_point_rec(mouse_pos, STEP_RECTS[self._step]):
      # Record DM camera?
      if self._step == DM_RECORD_STEP:
        yes = rl.check_collision_point_rec(mouse_pos, DM_RECORD_YES_RECT)
        print(f"putting RecordFront to {yes}")
        ui_state.params.put_bool("RecordFront", yes, block=True)

      # Restart training?
      elif self._step == len(self._image_paths) - 1:
        if rl.check_collision_point_rec(mouse_pos, RESTART_TRAINING_RECT):
          self._step = -1

      self._step += 1

      # Finished?
      if self._step >= len(self._image_paths):
        self._step = 0
        if self._completed_callback:
          self._completed_callback()

        # NOTE: this pops OnboardingWindow during real onboarding
        gui_app.pop_widget()

  def _update_state(self):
    if len(self._image_objs):
      self._textures.append(gui_app._load_texture_from_image(self._image_objs.pop(0)))

  def _render(self, _):
    # Safeguard against fast tapping
    step = min(self._step, len(self._textures) - 1)
    rl.draw_texture_ex(self._textures[step], rl.Vector2(0, 0), 0.0, 1.0, rl.WHITE)

    # progress bar
    if 0 < step < len(STEP_RECTS) - 1:
      h = 20
      w = int((step / (len(STEP_RECTS) - 1)) * self._rect.width)
      rl.draw_rectangle(int(self._rect.x), int(self._rect.y + self._rect.height - h),
                        w, h, rl.Color(70, 91, 234, 255))

    if DEBUG:
      rl.draw_rectangle_lines_ex(STEP_RECTS[step], 3, rl.RED)

    return -1



class WelcomePage(Widget):
  """SINAN dark-tech welcome shown once on first boot before the terms page."""

  def __init__(self, on_continue=None):
    super().__init__()
    self._on_continue = on_continue
    self._params = ui_state.params

  def _handle_mouse_release(self, mouse_pos):
    if self._on_continue:
      self._on_continue()

  @staticmethod
  def _get_device_summary() -> str:
    cp = ui_state.CP
    if cp is not None:
      name = str(getattr(cp, "carName", "") or "")
      fprint = str(getattr(cp, "carFingerprint", "") or "")
      if "Z6" in name or "Z6" in fprint:
        return "欧尚 Z6 iDD 已就绪"
      if name:
        return f"{name} 已就绪"
    return "设备已就绪"

  def _render(self, rect: rl.Rectangle):
    cx = rect.x + rect.width / 2
    cy = rect.y + rect.height * 0.40
    pulse = (math.sin(time.monotonic() * 2.0) + 1.0) / 2.0  # 0~1 breathing

    # background
    rl.draw_rectangle_rec(rect, SINANColors.BG_DARK)

    # central glowing emblem: ring layers + road perspective + car silhouette
    ring_r = int(rect.width * 0.092)
    for i in range(4, 0, -1):
      alpha = int(0x1A + (4 - i) * 0x22 + pulse * 12)
      rl.draw_circle_lines(int(cx), int(cy), ring_r + (4 - i) * 16,
                           rl.Color(0x00, 0xE5, 0xFF, min(alpha, 255)))

    # road perspective lines inside emblem
    base_y = cy + ring_r * 0.62
    horizon = cy - ring_r * 0.30
    for spread in (0.92, 0.64, 0.36):
      rl.draw_line(int(cx - ring_r * spread), int(base_y), int(cx), int(horizon),
                   rl.Color(0x00, 0xE5, 0xFF, 0x5E))
      rl.draw_line(int(cx + ring_r * spread), int(base_y), int(cx), int(horizon),
                   rl.Color(0x00, 0xE5, 0xFF, 0x5E))
    rl.draw_line(int(cx), int(horizon), int(cx), int(base_y), rl.Color(0x00, 0xE5, 0xFF, 0x8C))

    # car silhouette (white body + cyan wheels)
    car_w, car_h = ring_r * 0.78, ring_r * 0.26
    car_y = base_y - car_h
    rl.draw_rectangle_rounded(rl.Rectangle(cx - car_w / 2, car_y, car_w, car_h),
                              0.35, 8, rl.Color(0xFF, 0xFF, 0xFF, 0xE6))
    rl.draw_circle(int(cx - car_w * 0.28), int(car_y + car_h + ring_r * 0.09), int(ring_r * 0.09),
                   rl.Color(0x00, 0xE5, 0xFF, 0xCC))
    rl.draw_circle(int(cx + car_w * 0.28), int(car_y + car_h + ring_r * 0.09), int(ring_r * 0.09),
                   rl.Color(0x00, 0xE5, 0xFF, 0xCC))

    # welcome title
    font_bold = gui_app.font(FontWeight.BOLD)
    title = tr("欢迎使用")
    title_size = 96
    tw = measure_text_cached(font_bold, title, title_size)
    rl.draw_text_ex(font_bold, title, rl.Vector2(cx - tw.x / 2, cy + ring_r + 70),
                    title_size, 0, SINANColors.TEXT_PRIMARY)

    # vehicle line (accent cyan)
    sub_font = gui_app.font(FontWeight.MEDIUM)
    sub = self._get_device_summary()
    sub_size = 44
    sw = measure_text_cached(sub_font, sub, sub_size)
    rl.draw_text_ex(sub_font, sub, rl.Vector2(cx - sw.x / 2, cy + ring_r + 190),
                    sub_size, 0, SINANColors.ACCENT_CYAN)

    # hint
    font = gui_app.font(FontWeight.NORMAL)
    hint = tr("长按方向盘按键开始驾驶辅助")
    hint_size = 32
    hw = measure_text_cached(font, hint, hint_size)
    rl.draw_text_ex(font, hint, rl.Vector2(cx - hw.x / 2, cy + ring_r + 270),
                    hint_size, 0, SINANColors.TEXT_SECONDARY)

    # bottom breathing light line
    line_w = rect.width * 0.64
    line_y = rect.y + rect.height - 180
    glow_alpha = int(0x40 + pulse * 0xBF)
    rl.draw_rectangle_rounded(rl.Rectangle(cx - line_w / 2, line_y, line_w, 4),
                              0.5, 4, rl.Color(0x00, 0xE5, 0xFF, glow_alpha))

    # corner info: version (left) + date (right)
    version = self._params.get("UpdaterCurrentDescription") or "SINAN"
    rl.draw_text_ex(font, "SINAN " + str(version),
                    rl.Vector2(rect.x + 60, rect.y + rect.height - 84), 26, 0,
                    SINANColors.TEXT_SECONDARY)
    date_str = time.strftime("%Y-%m-%d")
    dsize = measure_text_cached(font, date_str, 26)
    rl.draw_text_ex(font, date_str,
                    rl.Vector2(rect.x + rect.width - dsize.x - 60, rect.y + rect.height - 84),
                    26, 0, SINANColors.TEXT_SECONDARY)


class TermsPage(Widget):
  def __init__(self, on_accept=None, on_decline=None):
    super().__init__()
    self._on_accept = on_accept
    self._on_decline = on_decline

    self._title = Label(tr("Welcome to SINAN"), font_size=90, font_weight=FontWeight.BOLD, text_alignment=TextAlignment.LEFT)
    self._desc = Label(tr("You must accept the Terms and Conditions to use SINAN. Read the latest terms at https://comma.ai/terms before continuing."),
                       font_size=90, font_weight=FontWeight.MEDIUM, text_alignment=TextAlignment.LEFT)

    self._decline_btn = Button(tr("Decline"), click_callback=on_decline)
    self._accept_btn = Button(tr("Agree"), button_style=ButtonStyle.PRIMARY, click_callback=on_accept)

  def _render(self, _):
    welcome_x = self._rect.x + 165
    welcome_y = self._rect.y + 165
    welcome_rect = rl.Rectangle(welcome_x, welcome_y, self._rect.width - welcome_x, 90)
    self._title.render(welcome_rect)

    desc_x = welcome_x
    # TODO: Label doesn't top align when wrapping
    desc_y = welcome_y - 100
    desc_rect = rl.Rectangle(desc_x, desc_y, self._rect.width - desc_x, self._rect.height - desc_y - 250)
    self._desc.render(desc_rect)

    btn_y = self._rect.y + self._rect.height - 160 - 45
    btn_width = (self._rect.width - 45 * 3) / 2
    self._decline_btn.render(rl.Rectangle(self._rect.x + 45, btn_y, btn_width, 160))
    self._accept_btn.render(rl.Rectangle(self._rect.x + 45 * 2 + btn_width, btn_y, btn_width, 160))

    if DEBUG:
      rl.draw_rectangle_lines_ex(welcome_rect, 3, rl.RED)
      rl.draw_rectangle_lines_ex(desc_rect, 3, rl.RED)

    return -1


class DeclinePage(Widget):
  def __init__(self, back_callback=None):
    super().__init__()
    self._text = Label(tr("You must accept the Terms and Conditions in order to use SINAN."),
                       font_size=90, font_weight=FontWeight.MEDIUM, text_alignment=TextAlignment.LEFT)
    self._back_btn = Button(tr("Back"), click_callback=back_callback)
    self._uninstall_btn = Button(tr("Decline, uninstall SINAN"), button_style=ButtonStyle.DANGER,
                                 click_callback=self._on_uninstall_clicked)

  def _on_uninstall_clicked(self):
    ui_state.params.put_bool("DoUninstall", True, block=True)
    gui_app.request_close()

  def _render(self, _):
    btn_y = self._rect.y + self._rect.height - 160 - 45
    btn_width = (self._rect.width - 45 * 3) / 2
    self._back_btn.render(rl.Rectangle(self._rect.x + 45, btn_y, btn_width, 160))
    self._uninstall_btn.render(rl.Rectangle(self._rect.x + 45 * 2 + btn_width, btn_y, btn_width, 160))

    # text rect in middle of top and button
    text_height = btn_y - (200 + 45)
    text_rect = rl.Rectangle(self._rect.x + 165, self._rect.y + (btn_y - text_height) / 2 + 10, self._rect.width - (165 * 2), text_height)
    if DEBUG:
      rl.draw_rectangle_lines_ex(text_rect, 3, rl.RED)
    self._text.render(text_rect)


class OnboardingWindow(Widget):
  def __init__(self):
    super().__init__()
    self._accepted_terms: bool = ui_state.params.get("HasAcceptedTerms") == terms_version
    self._training_done: bool = ui_state.params.get("CompletedTrainingVersion") == training_version

    self._state = OnboardingState.WELCOME if not self._accepted_terms else OnboardingState.ONBOARDING

    # Windows
    self._welcome = WelcomePage(on_continue=self._on_welcome_continue)
    self._terms = TermsPage(on_accept=self._on_terms_accepted, on_decline=self._on_terms_declined)
    self._training_guide: TrainingGuide | None = None
    self._decline_page = DeclinePage(back_callback=self._on_decline_back)

  @property
  def completed(self) -> bool:
    return self._accepted_terms and self._training_done

  def _on_welcome_continue(self):
    self._state = OnboardingState.TERMS

  def _on_terms_declined(self):
    self._state = OnboardingState.DECLINE

  def _on_decline_back(self):
    self._state = OnboardingState.TERMS

  def _on_terms_accepted(self):
    ui_state.params.put("HasAcceptedTerms", terms_version, block=True)
    self._state = OnboardingState.ONBOARDING
    if self._training_done:
      gui_app.pop_widget()

  def _on_completed_training(self):
    ui_state.params.put("CompletedTrainingVersion", training_version, block=True)

  def _render(self, _):
    if self._training_guide is None:
      self._training_guide = TrainingGuide(completed_callback=self._on_completed_training)

    if self._state == OnboardingState.WELCOME:
      self._welcome.render(self._rect)
    if self._state == OnboardingState.TERMS:
      self._terms.render(self._rect)
    if self._state == OnboardingState.ONBOARDING:
      self._training_guide.render(self._rect)
    elif self._state == OnboardingState.DECLINE:
      self._decline_page.render(self._rect)
    return -1
