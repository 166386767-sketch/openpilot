#!/usr/bin/env bash

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1

# models get lower priority than ui
# - ui is ~5ms
# - modeld is 20ms
# - DM is 10ms
# in order to run ui at 60fps (16.67ms), we need to allow
# it to preempt the model workloads. we have enough
# headroom for this until ui is moved to the CPU.
export QCOM_PRIORITY=12

if [ -z "$AGNOS_VERSION" ]; then
  export AGNOS_VERSION="19.7"
fi

export STAGING_ROOT="/data/safe_staging"

# ---------------------------------------------------------------------------
# 车型与设备配置
# ---------------------------------------------------------------------------
# 欧尚 Z6 iDD（单车型定制分支）：
# 使用 openpilot/opendbc 官方的固定指纹机制（FINGERPRINT 环境变量，
# 对应 opendbc/car/car_helpers.py 中的 FingerprintSource.fixed），
# 开机即锁定本车型车控参数。实车固件数据采集后可在
# opendbc/car/changan/fingerprints.py 中补充，以启用固件自动识别。
export FINGERPRINT="CHANGAN_Z6_IDD"

# 本车型座舱无内置驾驶员监控摄像头，关闭 DMS 相关进程与提示，避免误报警告。
export DISABLE_DRIVER=1
