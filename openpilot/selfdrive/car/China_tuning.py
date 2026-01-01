"""China: apply UI-tuned Z6 iDD parameters at runtime.

Pure openpilot-side adapter. Reads the values chosen in the settings menu
from Params and overrides the class attributes of opendbc's
ChanganCarControllerParams. No opendbc source file is modified; the
overrides live for the lifetime of the card process and take effect on
the next ignition cycle after a settings change.
"""
from openpilot.common.params import Params

# Factory default tuning for Z6 iDD (from params_backup JSON)
IDD_DEFAULTS = {
  "IDDLaunchBoostLevel": b"1",
  "IDDEpsBudget": b"4.6",
  "LateralTorqueKf": b"120",
  "LateralTorqueFriction": b"120",
  "LateralTorqueAccelFactor": b"2800",
  "LatMpcSteeringRateCost": b"400",
  "LatMpcJerkCost": b"5",
  "LatMpcPathCost": b"120",
  "LatMpcMotionCost": b"11",
  "LatMpcAccelCost": b"20",
  "LongTuningKiV": b"15",
  "RadarLatFactor": b"100",
  "TFollowGap2": b"130",
  "TFollowGap4": b"170",
  "CruiseMaxVals0": b"210",
  "CruiseMaxVals2": b"170",
  "CruiseMaxVals3": b"140",
  "CruiseMaxVals4": b"110",
  "CruiseMaxVals5": b"95",
  "CruiseSpeed3": b"80",
  "CruiseSpeed4": b"110",
  "CruiseSpeed5": b"130",
  "VEgoStopping": b"40",
  "LongActuatorDelay": b"20",
  "AutoTurnControl": b"2",
  "VehicleSpeedCameraDistanceTime": b"60",
  "VehicleSpeedCameraControlMode": b"1",
  "VehicleNaviCurveCtrlEnd": b"80",
  "AutoRoadSpeedAdjust": b"50",
  "AutoRoadSpeedLimitOffset": b"-1",
  "SpeedFromPCM": b"2",
  "ApplyModelSpeed": b"2",
  "ShowLaneInfo": b"1",
  "EnableRadarTracks": b"1",
  "EnableCornerRadar": b"1",
  "ChinaRadarCutInSensitivity": b"5",
  "TrafficLightDetectMode": b"2",
  "AutoNaviCountDownMode": b"2",
  "DynamicTFollowLC": b"100",
  "SoundVolumeAdjust": b"100",
  "SoundVolumeAdjustEngage": b"10",
  "SoundLanguageSetting": b"auto",
  "LanguageSetting": b"zh-CHS",
  "DisengageOnAccelerator": b"False",
  "SoftHoldOnCancel": b"True",
  "OpenpilotEnabledToggle": b"True",
  "DisableDM": b"1",
}


def _ensure_defaults(params):
  """Write factory defaults on first boot if params are empty."""
  for key, val in IDD_DEFAULTS.items():
    if params.get(key) is None:
      params.put(key, val)

IDD_LAUNCH_BOOST_LEVELS = {0: 0.20, 1: 0.35, 2: 0.50}
IDD_EPS_BUDGET_LEVELS = {0: 4.6, 1: 5.2, 2: 5.8}


def apply_idd_tuning(params: Params, CP) -> None:
  """China hook: called from card.py after get_car(). No-op for non-changan brands."""
  _ensure_defaults(params)
  if getattr(CP, "brand", None) != "changan":
    return
  try:
    from opendbc.car.changan.values import CarControllerParams
  except Exception:
    return

  level = params.get("IDDLaunchBoostLevel")
  if level is not None:
    try:
      CarControllerParams.IDD_LAUNCH_BOOST = IDD_LAUNCH_BOOST_LEVELS.get(int(level), 0.35)
    except Exception:
      pass

  eps = params.get("IDDEpsBudget")
  if eps is not None:
    try:
      CarControllerParams.EPS_LATERAL_ACCEL_BUDGET = float(eps)
    except Exception:
      pass
