#!/bin/sh
#
# Record.sh 
# =========
# this is script which recording with a webcam.
# 

SOURCEDIR=$(dirname "$0")
OUTPUT_FILE="${1:-record.dat}"

. ${SOURCEDIR}/config

# --- Muxing video/audio and saving to a file with ffmpeg.
ffmpeg -y -threads 0 \
       -f ${VIDEO_SRC_FMT} -i ${VIDEO_SRC_DEV} \
       -f ${AUDIO_SRC_FMT} -i ${AUDIO_SRC_DEV} \
       -vcodec mjpeg -q 20 \
       -acodec libvorbis -aq 6 \
       -f matroska \
       "${OUTPUT_FILE}" &

wait

