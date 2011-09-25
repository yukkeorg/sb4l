#!/bin/sh

# --- Settings ---
CAMERA_SOURCE="/dev/video0"
WIDTH=640
HEIGHT=480
FPS=24

VIDEO_SOURCE="/dev/video1"
VBITRATE="244"

AUDIO_SOURCE="pulse"
ASAMPLINGRATE="44100"
ABITRATE="96"
ACHANNEL="2"

RENDERTEXT="CR STEALTH block.III配信"

RTMP_URI="$1"
STREAM="$2"
# to Nico Nama Broadcast
OUTPUT_URI="${RTMP_URI}/${STREAM} flashver=FMLE/3.0\20(compatible;\20FMSc/1.0) swfUrl=${RTMP_URI}"
#OUTPUT_URI="file:///home/yukke/test.swf"

#----------

lsmod | grep -q v4l2loopback || sudo modprobe v4l2loopback

gst-launch v4l2src device=${CAMERA_SOURCE} ! \
           "video/x-raw-yuv,width=${WIDTH},height=${HEIGHT},framerate=${FPS}/1" ! \
           cairotextoverlay text="$RENDERTEXT" halign=left deltay=-100 ! \
           tee name=m ! \
                   queue ! v4l2sink device=${VIDEO_SOURCE} \
              m. ! queue ! xvimagesink &

sleep 3

ffmpeg -v 1 -threads 4 \
       -f video4linux2 -i ${VIDEO_SOURCE} -bt ${VBITRATE}k -re \
       -f alsa -i ${AUDIO_SOURCE} -ar ${ASAMPLINGRATE} -ab ${ABITRATE} -ac ${ACHANNEL} -async 1 \
       -vcodec libx264 -vpre medium -x264opts "bitrate=${VBITRATE}" -acodec libmp3lame \
       -f flv -r ${FPS} \
       "${OUTPUT_URI}"
