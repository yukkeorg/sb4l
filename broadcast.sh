#!/bin/sh
#
# broadcast.sh
# ============
# This is script which broadcast with a webcam to NiconicoNamahousou.
# Sorry, this is for Linix only.
# 
# Required extra tools:
#  - ffmpeg ver.N-37669 or later (compiling with librtmp, libx264 and libfaac)
# 

SOURCEDIR=$(dirname "$0")
RTMP_URI="$1"
STREAM="$2"

. ${SOURCEDIR}/config

if [ "${RTMP_URI}x" = "x" -o "${STREAM}x" = "x" ]; then
  if [ "${RTMP_URI}x" = "localx" ]; then
    OUTPUT_URI=test.flv
  else
    echo "Please specified RTMP_URI and STREAM."
    exit 1
  fi
fi

if [ "${OUTPUT_URI}x" = "x" ]; then
  OUTPUT_URI="${RTMP_URI}/${STREAM} flashver=FME/3.0\20(compatible;\20FMSc/1.0) swfUrl=${RTMP_URI}"
fi

# --- Muxing video/audio and sending stream to server with ffmpeg.
ffmpeg -y -stats -threads 0 \
       -f ${VIDEO_SRC_FMT} -i ${VIDEO_SRC_DEV} -bt ${VBITRATE}k \
       -f ${AUDIO_SRC_FMT} -i ${AUDIO_SRC_DEV} -ar ${ASAMPLINGRATE} \
           -ab ${ABITRATE}k -ac ${ACHANNEL} \
       -vcodec libx264 \
           -pass 1 \
           -flags "+loop" \
           -b-pyramid 1 -wpredp 1 -mixed-refs 1 -mbtree 1 -fast-pskip 0 \
           -cmp "+chroma" \
           -subq 6 -qmin 10 -qmax 51 -keyint_min 25 -b ${VBITRATE}k \
           -partitions i4x4,p8x8,p4x4,b8x8,i8x8 \
           -sc_threshold 10 -g 50 \
       -acodec libfaac \
       -f flv \
       "${OUTPUT_URI}" &

wait

