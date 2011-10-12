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

RTMP_URI="${l:-dummy.swf}"
STREAM="$2"

# --- Settings ---
VIDEO_SOURCE="/dev/video1"
FPS="30"
VBITRATE="300"

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

HAS_GUVCVIEW="no"
if [ "`which guvcview`" ]; then
  HAS_GUVCVIEW="yes"
fi

# --- Install v4l2loopback module
if ! lsmod | grep -q v4l2loopback; then
   sudo modprobe v4l2loopback
fi

python counter.py &
python cameramuxer.py &

# --- startup Webcam controller, if available.
[ "$HAS_GUVCVIEW" = "yes" ] && guvcview -o >/dev/null 2>&1 &

echo "配信の準備ができたら Enterキーを押してください。"
read dummy

# --- Muxing video/audio and starting stream with ffmpeg to server.
ffmpeg -v 1 -threads 0 \
       -f video4linux2 -i ${VIDEO_SOURCE} -bt ${VBITRATE}k \
       -f alsa -i ${AUDIO_SOURCE} -ar ${ASAMPLINGRATE} -ab ${ABITRATE}k -ac ${ACHANNEL} -async 1 \
       -vcodec libx264 -vpre medium -x264opts "bitrate=${VBITRATE}" \
       -acodec libmp3lame \
       -f flv  -r ${FPS} \
       -y "${OUTPUT_URI}" &

wait 
