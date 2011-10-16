#!/usr/bin/env python
# coding: utf-8

from __future__ import print_function

import os
import sys
import time
import codecs
import pickle

BASEDIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASEDIR)

from pyusbio import USBIO

N_PORT_GROUP = 3
N_BIT_GROUP = 4
N_COUNT_GROUP = 6

BIT_COUNT = CNT_COUNT = 0
BIT_BONUS = CNT_BONUS = 1
BIT_CHANCE = CNT_CHANCE = 2
BIT_RESERVED = CNT_RESERVED = 3

CNT_EXT_TOTALCOUNT = 4
CNT_EXT_COMBO = 5
  
RC_FILE = os.path.expanduser("~/.counterrc")
OUTPUT_FILE = os.path.expanduser("~/counter.txt")

class Counter(object):
  def __init__(self, rcfile=None, outputfile=None):
    self._rcfile = rcfile if rcfile is not None else RC_FILE 
    self._outputfile = outputfile if outputfile is not None else OUTPUT_FILE
    self.usbio = None
    self.counts = [ [0]*N_COUNT_GROUP ] * N_PORT_GROUP
    self.isOn = 0

  def init_device(self):
    self.usbio = USBIO()
    if not self.usbio.find_and_init():
      return False
    return True

  def save(self):
    try:
      with open(self._rcfile, "wb") as f:
        pickle.dump(self.counts, f, -1)
    except IOError, e:
      print(u"カウンタ値が保存できませんでした。原因：{0}".format(e.message), file=sys.stderr)


  def load(self):
    try:
      with open(self._rcfile, "rb") as f:
        self.counts = pickle.load(f)
      return True
    except IOError, e:
      print(u"カウンタ値を読み込めませんでした。原因：{0}".format(e.message), file=sys.stderr)
      return False


  def output(self):
    counts = self.counts[0]
    try:
      bonus_rate = "1/{0:.2f}".format(float(counts[CNT_EXT_TOTALCOUNT]) / counts[CNT_CHANCE])
    except ZeroDivisionError:
      bonus_rate = "1/-.--"

    combo = ""
    if counts[CNT_EXT_COMBO] > 0:
      combo = "{0} bonus combo".format(counts[CNT_EXT_COMBO])

      
    countstr = u"""<span font-desc="Acknowledge TT BRK Regular 18"><small>Count:</small> <span size="x-large">{0}</span>/{1}\n<small>Bonus:</small> <span size="x-large">{2}</span>/{3} ({4}) {5}</span>""" \
           .format(counts[BIT_COUNT], counts[CNT_EXT_TOTALCOUNT], 
                   counts[BIT_BONUS], counts[BIT_CHANCE], 
                   bonus_rate, combo)

    with codecs.open(self._outputfile, "w", "utf-8") as f:
      f.write(countstr)
      f.close()


  def countup(self):
    port0, port1 = self.usbio.send2read()
    port = (port1 << 8) + port0 
    for i in xrange(N_PORT_GROUP):
      bitgroup = port & 0x0f;
      port = port >> 4
      for j in (BIT_COUNT, BIT_BONUS, BIT_CHANCE):
        idx = i * N_BIT_GROUP + j
        tbit = 1 << idx
        if bitgroup & (1 << j):
          if self.isOn & tbit == 0:
            self.isOn = self.isOn | tbit
            self.counts[i][j] += 1
            if j == BIT_COUNT:
              self.counts[i][CNT_EXT_TOTALCOUNT] += 1
            elif j == BIT_BONUS:
              cbit = i * N_BIT_GROUP + BIT_CHANCE
              if bitgroup & cbit:
                self.counts[i][CNT_EXT_COMBO] += 1

        else:
          if self.isOn & tbit:
            self.isOn = self.isOn & (~tbit)
            if j == BIT_BONUS:
              self.counts[i][BIT_COUNT] = 0
            elif j == BIT_CHANCE:
              self.counts[i][CNT_EXT_COMBO] = 0


  def main(self, resetcount=False):
    self.init_device()
    if not resetcount:
      if not self.load():
        return 1
    try:
      while True:
        self.countup()
        self.output()
        time.sleep(0.2)
    except KeyboardInterrupt:
      pass
    finally:
      self.save()
    return 0


if __name__ == '__main__':
  resetcount = False
  if len(sys.argv) > 1:
    if sys.argv[1] == "-i":
      resetcount = True
  c = Counter()
  sys.exit(c.main(resetcount))

