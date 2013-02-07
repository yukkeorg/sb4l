#/bin/sh

set -e

SCRIPTDIR=$(cd -P "$(dirname "$0")" && pwd)
BUILDDIR=${SCRIPTDIR}/_build
INSTALLDIR="${SCRIPTDIR}/bin"
FFMPEGCP="n1.1.2"

[ ! -d "${BUILDDIR}" ] && mkdir "${BUILDDIR}"
cd "${BUILDDIR}"

if [ ! -d ffmpeg ]; then
    git clone git://source.ffmpeg.org/ffmpeg.git ffmpeg
    cd ffmpeg
    git checkout "${FFMPEGCP}"
else
    cd ffmpeg
fi

git clean -dfx

./configure \
  --enable-libx264 \
  --enable-libpulse \
  --enable-libfaac \
  --enable-openssl \
  --enable-nonfree \
  --enable-gpl \
  --enable-version3 \
  --enable-librtmp \
  --enable-x11grab \
  --enable-libutvideo \
  --enable-libfdk-aac \
  --disable-doc
make -j4 

if [ -f ffmpeg ]; then
    install -d "${INSTALLDIR}"
    install -m 755 ffmpeg "${INSTALLDIR}"
fi


