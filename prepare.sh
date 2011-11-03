#!/bin/sh
WEBCAMCONF="${HOME}/.default.gpfl"

# --- Install v4l2loopback module
if ! lsmod | grep -q v4l2loopback; then
   sudo modprobe v4l2loopback
fi

# --- startup Webcam controller, if available.
guvcview -o -l "$WEBCAMCONF" >/dev/null 2>&1 &

