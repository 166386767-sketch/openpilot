"""SINAN: apply UI-tuned Z6 iDD parameters at runtime.

Pure openpilot-side adapter. Reads the values chosen in the settings menu
from Params and overrides the class attributes of opendbc's
ChanganCarControllerParams. No opendbc source file is modified; the
overrides live for the lifetime of the card process and take effect on
the next ignition cycle after a settings change.
"""
from openpilot.common.params import Params

IDD_LAUNCH_BOOST_LEVELS = {0: 0.20, 1: 0.35, 2: 0.50}
IDD_EPS_BUDGET_LEVELS = {0: 4.6, 1: 5.2, 2: 5.8}


def apply_idd_tuning(params: Params, CP) -> None:
  """SINAN hook: called from card.py after get_car(). No-op for non-changan brands."""
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
