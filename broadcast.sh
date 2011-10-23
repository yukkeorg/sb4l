#!/bin/sh

#
# broadcast.sh
# 
# this is script which broadcast with webcam on NicoNama, UStream and more.
# Sorry, this is for Linix only.
# 
# Required tool:
#  - Gstreamer >= 0.10
#  - ffmpeg (compiled with librtmp, libx264, libfaac)
#  - v4l2looopback 
# 
# Optional tool:
#  - guvcview
# 

RTMP_URI="${1:-dummy.swf}"
STREAM="$2"

# --- Settings ---
WEBCAMCONF="${HOME}/.default.gpfl"
VIDEO_SOURCE="/dev/video1"
FPS="30"
VBITRATE="280"

AUDIO_SOURCE="pulse"
ASAMPLINGRATE="44100"
ABITRATE="96"
ACHANNEL="2"


if [ "${STREAM}x" != "x" ]; then
  # to NicoNama Broadcast
  OUTPUT_URI="${RTMP_URI}/${STREAM} flashver=FMLE/3.0\20(compatible;\20FMSc/1.0) swfUrl=${RTMP_URI}"
else
  OUTPUT_URI="${RTMP_URI}"
fi

HAS_UVCDYNCTRL="no"
HAS_GUVCVIEW="no"
if [ "`which uvcdynctrl`" -a -f "$WEBCAMCONF" ]; then
  HAS_UVCDYNCTRL="yes"
else
  if [ "`which guvcview`" ]; then
    HAS_GUVCVIEW="yes"
  fi
fi

# --- Install v4l2loopback module
if ! lsmod | grep -q v4l2loopback; then
   sudo modprobe v4l2loopback
fi

# --- startup Webcam controller, if available.
[ "$HAS_UVCDYNCTRL" = "yes" ] && uvcdynctrl -L "$WEBCAMCONF" >/dev/null 2>&1 
[ "$HAS_GUVCVIEW" = "yes" ] && guvcview -o -l "$WEBCAMCONF" >/dev/null 2>&1 &

sleep 3

echo "配信の準備ができたら Enterキーを押してください。"
read dummy

# --- Muxing video/audio and starting stream with ffmpeg to server.
ffmpeg -y -stats -threads 0 \
       -f video4linux2 -i ${VIDEO_SOURCE} -bt ${VBITRATE}k \
       -f alsa -i ${AUDIO_SOURCE} -ar ${ASAMPLINGRATE} -ab ${ABITRATE}k -ac ${ACHANNEL} -async 1 \
       -vcodec libx264 -vpre fast -x264opts "bitrate=${VBITRATE}" -level 31 \
       -acodec libfaac \
       -f flv -r ${FPS} \
       "${OUTPUT_URI}" &

wait 
