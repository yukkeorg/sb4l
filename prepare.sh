#!/bin/sh
SOURCEDIR=$(dirname "$0")

. ${SOURCEDIR}/config

WEBCAMCONF="${SOURCEDIR}/webcamsettings/${CAMERANAME}.gpfl"

# --- Install v4l2loopback module
grep -q v4l2loopback /proc/modules >/dev/null 2>&1
if [ "$?" != "0" ]; then
   sudo modprobe v4l2loopback
fi

# --- startup Webcam controller, if available.
guvcview -o -l "$WEBCAMCONF" >/dev/null 2>&1 &

