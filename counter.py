#/usr/bin/env python
# coding: utf-8

import os
import sys
import time
import codecs

BASEDIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASEDIR)

from pyusbio import USBIO

N_PORT_GROUP = 3

BIT_COUNT = 0
BIT_BONUS = 1
BIT_COMBO = 2
BIT_TOTALCOUNT = 3
BIT_GROUP = 4

def main():
  usbio = USBIO()
  if not usbio.find_and_init():
    return 1

  write_file = os.path.normpath(os.path.expanduser("~/counter.txt"))

  is_on = 0
  counts = [0]*(N_PORT_GROUP * BIT_GROUP)
  while 1:
    port0, port1 = usbio.send2read()
    save_port = port = (port1 << 8) + port0 
    for i in xrange(N_PORT_GROUP):
      p = port & 0x0f;
      port = port >> 4
      for j in (BIT_COUNT, BIT_BONUS, BIT_COMBO):
        idx = i * BIT_GROUP + j
        tbit = 1 << idx
        if p & (1 << j):
          if not (is_on & tbit):
            is_on = is_on | tbit
            counts[idx] += 1
            if j == BIT_COUNT:
              counts[i*N_PORT_GROUP+BIT_TOTALCOUNT] += 1
        else:
          if is_on & tbit:
            is_on = is_on & (~tbit)
            if j == BIT_BONUS:
              counts[i*N_PORT_GROUP+BIT_COUNT] = 0

    with codecs.open(write_file, "w", "utf-8") as f:
      countstr = u"""<span font-desc="Acknowledge TT BRK Regular 20">Count: <span size="x-large">{0}</span>/{1}\nBonus: <big>{2}</big></span>""" \
                 .format(counts[BIT_COUNT], counts[BIT_TOTALCOUNT], counts[BIT_BONUS])
      f.write(countstr)
    time.sleep(0.2)

if __name__ == '__main__':
  main()
