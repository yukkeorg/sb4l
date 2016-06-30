include() {
  if [ -e "$1" ]; then
    . "$1"
  else
    echo "Can't open ${1}." 1>&2
    exit 1
  fi
}

load_kmod_if_not() {
    cut -d ' ' -f 1 /proc/modules | grep -q "$1" >/dev/null 2>&1
    if [ "$?" != "0" ]; then
       sudo modprobe "$@"
    fi
}

exec_if_exist() {
    which "$1" >/dev/null 2>&1 && "$@" || echo "WARNING: ${1} is not found."
}
