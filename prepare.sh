#!/bin/sh
SOURCEDIR=$(dirname "$0")

if [ ${SOURCEDIR}/config ]; then
  . ${SOURCEDIR}/config
else
  echo "Can't open config file." >2
  exit 1
fi

WEBCAMCONF="${SOURCEDIR}/webcam.d/${CAMERANAME}.gpfl"

# --- Install v4l2loopback module
grep -q v4l2loopback /proc/modules >/dev/null 2>&1
if [ "$?" != "0" ]; then
   sudo modprobe v4l2loopback
fi

guvcview -o -l "$WEBCAMCONF" >/dev/null 2>&1 &

${SOURCEDIR}/webcamcomposer &


