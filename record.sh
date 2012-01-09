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

OUTPUT_URI="${1:-record.dat}"

# --- Settings ---
VIDEO_FMT="video4linux2"
VIDEO_SOURCE="/dev/video1"

AUDIO_FMT="alsa"
AUDIO_SOURCE="pulse"


# --- Muxing video/audio and sending stream to server with ffmpeg.
ffmpeg -y -threads 0 \
       -f ${VIDEO_FMT} -i ${VIDEO_SOURCE} \
       -f ${AUDIO_FMT} -i ${AUDIO_SOURCE} \
       -vcodec mjpeg -q 20 \
       -acodec libvorbis -aq 6 \
       -f matroska \
       "${OUTPUT_URI}" &

wait

