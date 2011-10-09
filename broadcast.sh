#!/bin/sh

#
# broadcast.sh
# 
# this is script which broadcast with webcam on NicoNama, UStream and more.
# Sorry, this is for Linix only.
# 
# Required tool:
#  - Gstreamer >= 0.10
#  - ffmpeg with librtmp
#  - v4l2looopback 
# 
# Optional tool:
#  - guvcview
# 

RTMP_URI="${1:-__cameratest__}"
STREAM="${2:-__local__}"

# --- Settings ---
CAMERA_SOURCE="/dev/video0"
WIDTH="640"
HEIGHT="480"
FPS="30"

VIDEO_SOURCE="/dev/video1"
VBITRATE="300"

AUDIO_SOURCE="pulse"
ASAMPLINGRATE="44100"
ABITRATE="96"
ACHANNEL="2"

TITLEFONT="Acknowledge TT BRK Regular 16"
TITLETEXT="CR STEALTH block.III"
TITLEPOS="halign=left deltay=0 xpad=5 ypad=5"
CLOCKFONT="Simpleton BRK 16"

DESKTOPCAP_OPT="startx=1920 starty=0 endx=2120 endy=32"
VIDEOBOX_OPT="border-alpha=0 top=-10 left=-10"


if [ "${RTMP_URI}" != "__cameratest__" ]; then
  if [ "${STREAM}" != "__local__" ]; then
    # to NicoNama Broadcast
    OUTPUT_URI="${RTMP_URI}/${STREAM} flashver=FMLE/3.0\20(compatible;\20FMSc/1.0) swfUrl=${RTMP_URI}"
  else
    OUTPUT_URI="${RTMP_URI}"
  fi
fi

HAS_GUVCVIEW="no"
if [ "`which guvcview`" ]; then
  HAS_GUVCVIEW="yes"
fi

# --- Install v4l2loopback module
if ! lsmod | grep -q v4l2loopback; then
   sudo modprobe v4l2loopback
fi

# --- Webcam stream send with editing to dummy device.
# FIXME: Problem that framerate down to half using videomix element.
gst-launch \
  v4l2src device=${CAMERA_SOURCE} ! videorate ! \
    "video/x-raw-yuv,width=${WIDTH},height=${HEIGHT},framerate=${FPS}/1" ! \
    clockoverlay halign="right" valign="top" font-desc="$CLOCKFONT" time-format="%H:%M" shaded-background=yes ! \
    textoverlay text="$TITLETEXT" font-desc="$TITLEFONT" $TITLEPOS shaded-background=yes ! \
    tee name=m ! queue2 ! v4l2sink device=${VIDEO_SOURCE} \
  m. ! queue2 ! xvimagesink \
  & 

# --- Waiting for a while ready to startup gst-launch.
sleep 3

# --- startup Webcam controller, if available.
[ "$HAS_GUVCVIEW" = "yes" ] && guvcview -o >/dev/null 2>&1 &

# --- Muxing video/audio and starting stream with ffmpeg to server.
if [ "$RTMP_URI" != "__cameratest__" ]; then
  ffmpeg -v 1 -threads 0 \
         -f video4linux2 -i ${VIDEO_SOURCE} -bt ${VBITRATE}k \
         -f alsa -i ${AUDIO_SOURCE} -ar ${ASAMPLINGRATE} -ab ${ABITRATE}k -ac ${ACHANNEL} -async 1 \
         -vcodec libx264 -vpre medium -x264opts "bitrate=${VBITRATE}" \
         -acodec libmp3lame \
         -f flv  -r ${FPS} \
         "${OUTPUT_URI}" &
fi

wait 
