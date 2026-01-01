from openpilot.cereal import log
from openpilot.common.params import Params, UnknownKeyName
from openpilot.system.loggerd.deleter import cleanup_old_logs, cleanup_uploaded_segments
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.list_view import multiple_button_item, toggle_item, button_item
from openpilot.system.ui.widgets.scroller_tici import Scroller
from openpilot.system.ui.widgets.confirm_dialog import ConfirmDialog
from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr, tr_noop
from openpilot.system.ui.widgets import DialogResult
from openpilot.selfdrive.ui.ui_state import ui_state

PERSONALITY_TO_INT = log.LongitudinalPersonality.schema.enumerants

# Description constants
DESCRIPTIONS = {
  "OpenpilotEnabledToggle": tr_noop(
    "Use the China system for adaptive cruise control and lane keep driver assistance. " +
    "Your attention is required at all times to use this feature."
  ),
  "DisengageOnAccelerator": tr_noop("When enabled, pressing the accelerator pedal will disengage China."),
  "LongitudinalPersonality": tr_noop(
    "Standard is recommended. In aggressive mode, China will follow lead cars closer and be more aggressive with the gas and brake. " +
    "In relaxed mode China will stay further away from lead cars. On supported cars, you can cycle through these personalities with " +
    "your steering wheel distance button."
  ),
  "IsLdwEnabled": tr_noop(
    "Receive alerts to steer back into the lane when your vehicle drifts over a detected lane line " +
    "without a turn signal activated while driving over 31 mph (50 km/h)."
  ),
  "AlwaysOnDM": tr_noop("Enable driver monitoring even when China is not engaged."),
  'RecordFront': tr_noop("Upload data from the cabin camera and help improve the driver monitoring algorithm."),
  "IsMetric": tr_noop("Display speed in km/h instead of mph."),
  "RecordAudio": tr_noop("Record and store microphone audio while driving. The audio will be included in the dashcam video in comma connect."),
}


class TogglesLayout(Widget):
  def __init__(self):
    super().__init__()
    self._params = Params()
    self._is_release = self._params.get_bool("IsReleaseBranch")

    # param, title, desc, icon, needs_restart
    self._toggle_defs = {
      "OpenpilotEnabledToggle": (
        lambda: tr("Enable China"),
        DESCRIPTIONS["OpenpilotEnabledToggle"],
        "chffr_wheel.png",
        True,
      ),
      "ExperimentalMode": (
        lambda: tr("Experimental Mode"),
        "",
        "experimental_white.png",
        False,
      ),
      "DisengageOnAccelerator": (
        lambda: tr("Disengage on Accelerator Pedal"),
        DESCRIPTIONS["DisengageOnAccelerator"],
        "disengage_on_accelerator.png",
        False,
      ),
      "IsLdwEnabled": (
        lambda: tr("Enable Lane Departure Warnings"),
        DESCRIPTIONS["IsLdwEnabled"],
        "warning.png",
        False,
      ),
      "AlwaysOnDM": (
        lambda: tr("Always-On Driver Monitoring"),
        DESCRIPTIONS["AlwaysOnDM"],
        "monitoring.png",
        False,
      ),
      "RecordFront": (
        lambda: tr("Record and Upload Cabin Camera"),
        DESCRIPTIONS["RecordFront"],
        "monitoring.png",
        True,
      ),
      "RecordAudio": (
        lambda: tr("Record and Upload Microphone Audio"),
        DESCRIPTIONS["RecordAudio"],
        "microphone.png",
        True,
      ),
      "IsMetric": (
        lambda: tr("Use Metric System"),
        DESCRIPTIONS["IsMetric"],
        "metric.png",
        False,
      ),
    }

    self._long_personality_setting = multiple_button_item(
      lambda: tr("Driving Personality"),
      lambda: tr(DESCRIPTIONS["LongitudinalPersonality"]),
      buttons=[lambda: tr("Aggressive"), lambda: tr("Standard"), lambda: tr("Relaxed")],
      button_width=255,
      callback=self._set_longitudinal_personality,
      selected_index=self._params.get("LongitudinalPersonality", return_default=True),
      icon="speed_limit.png"
    )

    self._toggles = {}
    self._locked_toggles = set()
    for param, (title, desc, icon, needs_restart) in self._toggle_defs.items():
      toggle = toggle_item(
        title,
        desc,
        self._params.get_bool(param),
        callback=lambda state, p=param: self._toggle_callback(state, p),
        icon=icon,
      )

      try:
        locked = self._params.get_bool(param + "Lock")
      except UnknownKeyName:
        locked = False
      toggle.action_item.set_enabled(not locked)

      # Make description callable for live translation
      additional_desc = ""
      if needs_restart and not locked:
        additional_desc = tr("Changing this setting will restart China if the car is powered on.")
      toggle.set_description(lambda og_desc=toggle.description, add_desc=additional_desc: tr(og_desc) + (" " + tr(add_desc) if add_desc else ""))

      # track for engaged state updates
      if locked:
        self._locked_toggles.add(param)

      self._toggles[param] = toggle

      # insert longitudinal personality after NDOG toggle
      if param == "DisengageOnAccelerator":
        self._toggles["LongitudinalPersonality"] = self._long_personality_setting

    # === China: Z6 iDD dedicated tuning items ===
    self._idd_launch_setting = multiple_button_item(
      lambda: tr("起步加速强度 (Z6 iDD)"),
      lambda: tr("Z6 iDD 起步加速补偿强度：轻 0.20 / 标准 0.35 / 运动 0.50。熄火重启后生效。"),
      buttons=[lambda: tr("轻"), lambda: tr("标准"), lambda: tr("运动")],
      button_width=150,
      selected_index=self._get_idd_launch_index(),
      callback=self._set_idd_launch_boost,
      icon="speed_limit.png",
    )
    self._idd_eps_setting = multiple_button_item(
      lambda: tr("大角度转向补偿 (Z6 iDD)"),
      lambda: tr("Z6 iDD 大角度弯道转向补偿（EPS 横向加速度预算）：标准 4.6 / 增强 5.2 / 最大 5.8。熄火重启后生效。"),
      buttons=[lambda: tr("标准"), lambda: tr("增强"), lambda: tr("最大")],
      button_width=150,
      selected_index=self._get_idd_eps_index(),
      callback=self._set_idd_eps_budget,
      icon="chffr_wheel.png",
    )
    self._toggles["IDDLaunchBoostLevel"] = self._idd_launch_setting
    self._toggles["IDDEpsBudget"] = self._idd_eps_setting

    # === China: Dashcam retention settings ===
    self._retention_setting = multiple_button_item(
      lambda: tr("录像保留时长"),
      lambda: tr("超过该时长的本地旧录像段将自动删除（每天检查一次）。设为永久保留则只保留空间兜底清理。"),
      buttons=[lambda: tr("30天"), lambda: tr("90天"), lambda: tr("180天"), lambda: tr("365天"), lambda: tr("永久保留")],
      button_width=150,
      selected_index=self._get_retention_index(),
      callback=self._set_retention_days,
      icon="metric.png",
    )
    self._cleanup_uploaded_button = button_item(
      lambda: tr("立即清理所有已上传录像"),
      lambda: tr("立即执行"),
      lambda: tr("这会删除所有已上传至云端的本地录像段，释放存储空间。未上传的录像不会被删除。此操作不可撤销。"),
      callback=self._cleanup_uploaded_callback,
    )
    self._toggles["RecordRetentionDays"] = self._retention_setting
    self._toggles["CleanupUploadedSegments"] = self._cleanup_uploaded_button

    # === China: System log retention settings ===
    self._syslog_retention_setting = multiple_button_item(
      lambda: tr("系统日志保留时长"),
      lambda: tr("超过该时长的 /data/log/ 下系统调试日志（swaglog）将自动删除（每天检查一次）。设为永久保留则不按时间清理，仅靠空间兜底。"),
      buttons=[lambda: tr("7天"), lambda: tr("30天"), lambda: tr("90天"), lambda: tr("365天"), lambda: tr("永久保留")],
      button_width=150,
      selected_index=self._get_syslog_retention_index(),
      callback=self._set_syslog_retention_days,
      icon="metric.png",
    )
    self._cleanup_syslog_button = button_item(
      lambda: tr("立即清理系统日志"),
      lambda: tr("立即执行"),
      lambda: tr("这会立即删除设备上 /data/log/ 下的所有系统调试日志（swaglog），释放存储空间。此操作不可撤销。"),
      callback=self._cleanup_syslog_callback,
    )
    self._toggles["SysLogRetentionDays"] = self._syslog_retention_setting
    self._toggles["CleanupSysLogs"] = self._cleanup_syslog_button

    self._update_experimental_mode_icon()
    self._scroller = Scroller(list(self._toggles.values()), line_separator=True, spacing=0)

    ui_state.add_engaged_transition_callback(self._update_toggles)

  def _update_state(self):
    if ui_state.sm.updated["selfdriveState"]:
      personality = PERSONALITY_TO_INT[ui_state.sm["selfdriveState"].personality]
      if personality != ui_state.personality and ui_state.started:
        self._long_personality_setting.action_item.set_selected_button(personality)
      ui_state.personality = personality

  def show_event(self):
    super().show_event()
    self._scroller.show_event()
    self._update_toggles()

  def _update_toggles(self):
    ui_state.update_params()

    e2e_description = tr(
      "China defaults to driving in chill mode. Experimental mode enables alpha-level features that aren't ready for chill mode. " +
      "Experimental features are listed below:<br>" +
      "<h4>End-to-End Longitudinal Control</h4><br>" +
      "Let the driving model control the gas and brakes. China will drive as it thinks a human would, including stopping for red lights and stop signs. " +
      "Since the driving model decides the speed to drive, the set speed will only act as an upper bound. This is an alpha quality feature; " +
      "mistakes should be expected.<br>" +
      "<h4>New Driving Visualization</h4><br>" +
      "The driving visualization will transition to the road-facing wide-angle camera at low speeds to better show some turns. " +
      "The Experimental mode logo will also be shown in the top right corner."
    )

    if ui_state.CP is not None:
      if ui_state.has_longitudinal_control:
        self._toggles["ExperimentalMode"].action_item.set_enabled(True)
        self._toggles["ExperimentalMode"].set_description(e2e_description)
        self._long_personality_setting.action_item.set_enabled(True)
      else:
        # no long for now
        self._toggles["ExperimentalMode"].action_item.set_enabled(False)
        self._toggles["ExperimentalMode"].action_item.set_state(False)
        self._long_personality_setting.action_item.set_enabled(False)
        self._params.remove("ExperimentalMode")

        unavailable = tr("Experimental mode is currently unavailable on this car since the car's stock ACC is used for longitudinal control.")

        long_desc = unavailable + " " + tr("China longitudinal control may come in a future update.")
        if ui_state.CP.alphaLongitudinalAvailable:
          if self._is_release:
            long_desc = unavailable + " " + tr("An alpha version of China longitudinal control can be tested, along with " +
                                               "Experimental mode, on non-release branches.")
          else:
            long_desc = tr("Enable the China longitudinal control (alpha) toggle to allow Experimental mode.")

        self._toggles["ExperimentalMode"].set_description("<b>" + long_desc + "</b><br><br>" + e2e_description)
    else:
      self._toggles["ExperimentalMode"].set_description(e2e_description)

    self._update_experimental_mode_icon()

    # TODO: make a param control list item so we don't need to manage internal state as much here
    # refresh toggles from params to mirror external changes
    for param in self._toggle_defs:
      self._toggles[param].action_item.set_state(self._params.get_bool(param))

    # these toggles need restart, block while engaged
    for toggle_def in self._toggle_defs:
      if self._toggle_defs[toggle_def][3] and toggle_def not in self._locked_toggles:
        self._toggles[toggle_def].action_item.set_enabled(not ui_state.engaged)

  def _render(self, rect):
    self._scroller.render(rect)

  def _update_experimental_mode_icon(self):
    icon = "experimental.png" if self._toggles["ExperimentalMode"].action_item.get_state() else "experimental_white.png"
    self._toggles["ExperimentalMode"].set_icon(icon)

  def _handle_experimental_mode_toggle(self, state: bool):
    confirmed = self._params.get_bool("ExperimentalModeConfirmed")
    if state and not confirmed:
      def confirm_callback(result: DialogResult):
        if result == DialogResult.CONFIRM:
          self._params.put_bool("ExperimentalMode", True, block=True)
          self._params.put_bool("ExperimentalModeConfirmed", True, block=True)
        else:
          self._toggles["ExperimentalMode"].action_item.set_state(False)
        self._update_experimental_mode_icon()

      # show confirmation dialog
      content = (f"<h1>{self._toggles['ExperimentalMode'].title}</h1><br>" +
                 f"<p>{self._toggles['ExperimentalMode'].description}</p>")
      dlg = ConfirmDialog(content, tr("Enable"), rich=True, callback=confirm_callback)
      gui_app.push_widget(dlg)
    else:
      self._update_experimental_mode_icon()
      self._params.put_bool("ExperimentalMode", state, block=True)

  def _toggle_callback(self, state: bool, param: str):
    if param == "ExperimentalMode":
      self._handle_experimental_mode_toggle(state)
      return

    self._params.put_bool(param, state, block=True)
    if self._toggle_defs[param][3]:
      self._params.put_bool("OnroadCycleRequested", True, block=True)

  def _get_idd_launch_index(self) -> int:
    try:
      v = self._params.get("IDDLaunchBoostLevel")
      if v is not None and v in ("0", "1", "2"):
        return int(v)
    except Exception:
      pass
    return 1  # 标准

  def _set_idd_launch_boost(self, index: int):
    self._params.put("IDDLaunchBoostLevel", str(index), block=True)

  def _get_idd_eps_index(self) -> int:
    try:
      v = float(self._params.get("IDDEpsBudget") or 4.6)
    except Exception:
      v = 4.6
    if v <= 4.6:
      return 0  # 标准
    if v >= 5.4:
      return 2  # 最大
    return 1    # 增强

  def _set_idd_eps_budget(self, index: int):
    self._params.put("IDDEpsBudget", str([4.6, 5.2, 5.8][index]), block=True)

  def _set_longitudinal_personality(self, button_index: int):
    self._params.put("LongitudinalPersonality", button_index, block=True)

  # === China: Dashcam retention helpers ===
  RETENTION_OPTIONS = [30, 90, 180, 365, 0]  # 0 = keep forever

  def _get_retention_index(self) -> int:
    try:
      v = int(self._params.get("RecordRetentionDays") or 180)
    except (ValueError, TypeError):
      v = 180
    try:
      return self.RETENTION_OPTIONS.index(v)
    except ValueError:
      return 2  # default to 180 days

  def _set_retention_days(self, index: int):
    days = self.RETENTION_OPTIONS[index]
    self._params.put("RecordRetentionDays", str(days), block=True)

  def _cleanup_uploaded_callback(self):
    def confirm_callback(result: DialogResult):
      if result == DialogResult.CONFIRM:
        try:
          count, _ = cleanup_uploaded_segments()
          msg = tr(f"已清理 {count} 个已上传录像段。") if count else tr("没有可清理的已上传录像段。")
        except Exception as e:
          msg = tr(f"清理失败: {e}")
        dlg = ConfirmDialog(msg, tr("确定"), cancel_text="", rich=False, callback=None)
        gui_app.push_widget(dlg)

    content = (f"<h1>{tr('立即清理已上传录像')}</h1><br>" +
               f"<p>{tr('这会删除所有已上传至云端的本地录像段。未上传的录像不会被删除。此操作不可撤销。')}</p>")
    dlg = ConfirmDialog(content, tr("确认清理"), rich=True, callback=confirm_callback)
    gui_app.push_widget(dlg)

  # === China: System log retention helpers ===
  SYSLOG_RETENTION_OPTIONS = [7, 30, 90, 365, 0]  # 0 = keep forever

  def _get_syslog_retention_index(self) -> int:
    try:
      v = int(self._params.get("SysLogRetentionDays") or 30)
    except (ValueError, TypeError):
      v = 30
    try:
      return self.SYSLOG_RETENTION_OPTIONS.index(v)
    except ValueError:
      return 1  # default to 30 days

  def _set_syslog_retention_days(self, index: int):
    days = self.SYSLOG_RETENTION_OPTIONS[index]
    self._params.put("SysLogRetentionDays", str(days), block=True)

  def _cleanup_syslog_callback(self):
    def confirm_callback(result: DialogResult):
      if result == DialogResult.CONFIRM:
        try:
          count, _ = cleanup_old_logs()
          msg = tr(f"已清理 {count} 个系统日志文件。") if count else tr("没有可清理的系统日志文件。")
        except Exception as e:
          msg = tr(f"清理失败: {e}")
        dlg = ConfirmDialog(msg, tr("确定"), cancel_text="", rich=False, callback=None)
        gui_app.push_widget(dlg)

    content = (f"<h1>{tr('立即清理系统日志')}</h1><br>" +
               f"<p>{tr('这会立即删除设备上 /data/log/ 下的所有系统调试日志（swaglog），释放存储空间。此操作不可撤销。')}</p>")
    dlg = ConfirmDialog(content, tr("确认清理"), rich=True, callback=confirm_callback)
    gui_app.push_widget(dlg)

