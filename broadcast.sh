#!/bin/sh

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

#RENDERFONT="HeadlineNEWS 16"
TITLEFONT="Acknowledge TT BRK Regular 16"
TITLETEXT="CR STEALTH block.III Broadcast channel"
TITLEPOS="halign=left deltay=0 xpad=5 ypad=5"
CLOCKFONT="Simpleton BRK 16"

if [ "${1}x" = "x" ]; then
  OUTPUT_URI="file:///dev/null"
else
  RTMP_URI="$1"
  STREAM="$2"
  # to NicoNama Broadcast
  OUTPUT_URI="${RTMP_URI}/${STREAM} flashver=FMLE/3.0\20(compatible;\20FMSc/1.0) swfUrl=${RTMP_URI}"
fi

#----------

lsmod | grep -q v4l2loopback || sudo modprobe v4l2loopback

gst-launch -v v4l2src device=${CAMERA_SOURCE} ! \
           "video/x-raw-yuv,width=${WIDTH},height=${HEIGHT},bitrate=${FPS}/1" ! \
           clockoverlay halign="right" valign="top" font-desc="$CLOCKFONT" time-format="%H:%M" shaded-background=yes ! \
           textoverlay text="$TITLETEXT" font-desc="$TITLEFONT" $TITLEPOS shaded-background=yes ! \
           tee name=m ! \
                   queue ! v4l2sink device=${VIDEO_SOURCE} \
              m. ! queue ! xvimagesink &
sleep 3

guvcview -o &

ffmpeg -v 1 -threads 0 \
       -f video4linux2 -i ${VIDEO_SOURCE} -bt ${VBITRATE}k \
       -f alsa -i ${AUDIO_SOURCE} -ar ${ASAMPLINGRATE} -ab ${ABITRATE}k -ac ${ACHANNEL} -async 1 \
       -vcodec libx264 -vpre medium -x264opts "bitrate=${VBITRATE}" \
       -acodec libmp3lame \
       -f flv  -r ${FPS} \
       "${OUTPUT_URI}"
