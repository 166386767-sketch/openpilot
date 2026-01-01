#!/usr/bin/env python3
import os
import shutil
import threading
import time
import datetime
from openpilot.common.hardware.hw import Paths
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.system.loggerd.config import get_available_bytes, get_available_percent
from openpilot.system.loggerd.uploader import listdir_by_creation
from openpilot.system.loggerd.xattr_cache import getxattr

MIN_BYTES = 5 * 1024 * 1024 * 1024
MIN_PERCENT = 10

DELETE_LAST = ['boot', 'crash']

PRESERVE_ATTR_NAME = 'user.preserve'
PRESERVE_ATTR_VALUE = b'1'
PRESERVE_COUNT = 5

UPLOAD_ATTR_NAME = 'user.upload'
UPLOAD_ATTR_VALUE = b'1'

AGE_CHECK_INTERVAL = 24 * 3600  # seconds between age-based cleanups
_last_age_cleanup_time = 0
_last_syslog_cleanup_time = 0


def has_preserve_xattr(d: str) -> bool:
  return getxattr(os.path.join(Paths.log_root(), d), PRESERVE_ATTR_NAME) == PRESERVE_ATTR_VALUE


def get_preserved_segments(dirs_by_creation: list[str]) -> set[str]:
  # skip deleting most recent N preserved segments (and their prior segment)
  preserved = set()
  for n, d in enumerate(filter(has_preserve_xattr, reversed(dirs_by_creation))):
    if n == PRESERVE_COUNT:
      break
    date_str, _, seg_str = d.rpartition("--")

    # ignore non-segment directories
    if not date_str:
      continue
    try:
      seg_num = int(seg_str)
    except ValueError:
      continue

    # preserve segment and two prior
    for _seg_num in range(max(0, seg_num - 2), seg_num + 1):
      preserved.add(f"{date_str}--{_seg_num}")

  return preserved


def _should_skip_dir(delete_dir: str, preserved_dirs: set[str]) -> bool:
  if delete_dir in DELETE_LAST:
    return True
  if delete_dir in preserved_dirs:
    return True
  return False


def _is_dir_locked(delete_path: str) -> bool:
  try:
    return any(name.endswith(".lock") for name in os.listdir(delete_path))
  except OSError:
    return True


def deleter_step() -> tuple[bool, str | None]:
  out_of_bytes = get_available_bytes(default=MIN_BYTES + 1) < MIN_BYTES
  out_of_percent = get_available_percent(default=MIN_PERCENT + 1) < MIN_PERCENT
  out_of_space = out_of_percent or out_of_bytes
  if not out_of_space:
    return False, None

  dirs = listdir_by_creation(Paths.log_root())
  preserved_dirs = get_preserved_segments(dirs)

  # remove the earliest directory we can
  for delete_dir in sorted(dirs, key=lambda d: (d in DELETE_LAST, d in preserved_dirs)):
    if _should_skip_dir(delete_dir, preserved_dirs):
      continue
    delete_path = os.path.join(Paths.log_root(), delete_dir)
    if _is_dir_locked(delete_path):
      continue

    try:
      cloudlog.info(f"deleting {delete_path}")
      shutil.rmtree(delete_path)
      return True, delete_path
    except OSError:
      cloudlog.exception(f"issue deleting {delete_path}")
  return True, None


def cleanup_old_segments_by_age(retention_days: int | None = None) -> tuple[int, list[str]]:
  """Delete local segments older than retention_days (default from params)."""
  if retention_days is None:
    try:
      retention_days = int(Params().get("RecordRetentionDays") or 180)
    except (ValueError, TypeError):
      retention_days = 180

  if retention_days <= 0:
    return 0, []  # disabled / keep forever

  cutoff = datetime.datetime.now() - datetime.timedelta(days=retention_days)
  dirs = listdir_by_creation(Paths.log_root())
  preserved_dirs = get_preserved_segments(dirs)

  deleted = 0
  deleted_list: list[str] = []
  for d in dirs:
    if _should_skip_dir(d, preserved_dirs):
      continue

    # Parse date from directory name: YYYY-MM-DD--HH-MM-SS or YYYY-MM-DD--HH-MM-SS--N
    try:
      date_part = d.rsplit('--', 1)[0] if '--' in d else d
      dt = datetime.datetime.strptime(date_part, "%Y-%m-%d--%H-%M-%S")
    except ValueError:
      continue

    if dt < cutoff:
      delete_path = os.path.join(Paths.log_root(), d)
      if _is_dir_locked(delete_path):
        continue
      try:
        cloudlog.info(f"age cleanup deleting {delete_path}")
        shutil.rmtree(delete_path)
        deleted += 1
        deleted_list.append(delete_path)
      except OSError:
        cloudlog.exception(f"age cleanup failed for {delete_path}")

  return deleted, deleted_list


def cleanup_uploaded_segments() -> tuple[int, list[str]]:
  """Delete local segments whose files are all marked as uploaded."""
  dirs = listdir_by_creation(Paths.log_root())
  preserved_dirs = get_preserved_segments(dirs)

  deleted = 0
  deleted_list: list[str] = []
  for d in dirs:
    if _should_skip_dir(d, preserved_dirs):
      continue
    delete_path = os.path.join(Paths.log_root(), d)
    if _is_dir_locked(delete_path):
      continue

    try:
      names = os.listdir(delete_path)
      if not names:
        continue
      # Check if every file in the segment has been uploaded
      all_uploaded = True
      for name in names:
        fn = os.path.join(delete_path, name)
        if os.path.isfile(fn):
          if getxattr(fn, UPLOAD_ATTR_NAME) != UPLOAD_ATTR_VALUE:
            all_uploaded = False
            break
      if all_uploaded:
        cloudlog.info(f"uploaded cleanup deleting {delete_path}")
        shutil.rmtree(delete_path)
        deleted += 1
        deleted_list.append(delete_path)
    except OSError:
      cloudlog.exception(f"uploaded cleanup failed for {delete_path}")

  return deleted, deleted_list


def cleanup_old_logs_by_age(retention_days: int | None = None) -> tuple[int, list[str]]:
  """Delete system logs older than retention_days (default from params)."""
  if retention_days is None:
    try:
      retention_days = int(Params().get("SysLogRetentionDays") or 30)
    except (ValueError, TypeError):
      retention_days = 30

  if retention_days <= 0:
    return 0, []  # disabled / keep forever

  cutoff = time.time() - retention_days * 24 * 3600
  log_root = Paths.swaglog_root()
  deleted = 0
  deleted_list: list[str] = []

  try:
    for fn in os.listdir(log_root):
      if not fn.startswith("swaglog."):
        continue
      fpath = os.path.join(log_root, fn)
      if not os.path.isfile(fpath):
        continue
      try:
        if os.path.getmtime(fpath) < cutoff:
          cloudlog.info(f"syslog age cleanup deleting {fpath}")
          os.remove(fpath)
          deleted += 1
          deleted_list.append(fpath)
      except OSError:
        cloudlog.exception(f"syslog age cleanup failed for {fpath}")
  except OSError:
    cloudlog.exception("syslog age cleanup failed to list directory")

  return deleted, deleted_list


def cleanup_old_logs() -> tuple[int, list[str]]:
  """Delete all system logs unconditionally."""
  log_root = Paths.swaglog_root()
  deleted = 0
  deleted_list: list[str] = []

  try:
    for fn in os.listdir(log_root):
      if not fn.startswith("swaglog."):
        continue
      fpath = os.path.join(log_root, fn)
      if not os.path.isfile(fpath):
        continue
      try:
        cloudlog.info(f"syslog cleanup deleting {fpath}")
        os.remove(fpath)
        deleted += 1
        deleted_list.append(fpath)
      except OSError:
        cloudlog.exception(f"syslog cleanup failed for {fpath}")
  except OSError:
    cloudlog.exception("syslog cleanup failed to list directory")

  return deleted, deleted_list


def deleter_thread(exit_event: threading.Event):
  global _last_age_cleanup_time, _last_syslog_cleanup_time
  while not exit_event.is_set():
    out_of_space, _ = deleter_step()

    # Periodic age-based cleanup (once per day)
    now = time.time()
    if now - _last_age_cleanup_time >= AGE_CHECK_INTERVAL:
      _last_age_cleanup_time = now
      try:
        count, _ = cleanup_old_segments_by_age()
        if count:
          cloudlog.info(f"age cleanup removed {count} old segments")
      except Exception:
        cloudlog.exception("age cleanup error")

    # Periodic system log cleanup (once per day)
    if now - _last_syslog_cleanup_time >= AGE_CHECK_INTERVAL:
      _last_syslog_cleanup_time = now
      try:
        count, _ = cleanup_old_logs_by_age()
        if count:
          cloudlog.info(f"syslog cleanup removed {count} old log files")
      except Exception:
        cloudlog.exception("syslog cleanup error")

    exit_event.wait(.1 if out_of_space else 30)


def main():
  deleter_thread(threading.Event())


if __name__ == "__main__":
  main()
