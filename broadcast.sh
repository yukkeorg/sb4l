#!/bin/sh

#
# broadcast.sh
# 
# this is script which broadcast with webcam on NicoNama, UStream and more.
# Sorry, this is for Linix only.
# 
# Required tool:
#  - ffmpeg (compiled with librtmp, libx264, libfaac)
# 

RTMP_URI="${1:-dummy.swf}"
STREAM="$2"

# --- Settings ---
VIDEO_FMT="video4linux2"
VIDEO_SOURCE="/dev/video1"
VBITRATE="280"

AUDIO_FMT="alsa"
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

# --- Muxing video/audio and sending stream to server with ffmpeg.
ffmpeg -y -stats -threads 0 \
       -f ${VIDEO_FMT} -i ${VIDEO_SOURCE} -bt ${VBITRATE}k \
       -f ${AUDIO_FMT} -i ${AUDIO_SOURCE} -ar ${ASAMPLINGRATE} \
           -ab ${ABITRATE}k -ac ${ACHANNEL} \
       -vcodec libx264 -vpre medium -x264opts "bitrate=${VBITRATE}" -level 31 \
       -acodec libfaac \
       -f flv \
       "${OUTPUT_URI}" &

wait

