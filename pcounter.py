#!/usr/bin/env python
# coding: utf-8

# Copyright (c) 2011, Yusuke Ohshima
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without modification, 
# are permitted provided that the following conditions are met:
# 
#   - Redistributions of source code must retain the above copyright notice, 
#     this list of conditions and the following disclaimer.
# 
#   - Redistributions in binary form must reproduce the above copyright notice, 
#     this list of conditions and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND 
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, 
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, 
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY 
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE 
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF 
# THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function

import os
import sys
import time
import pickle
import logging

BASEDIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASEDIR)

from pyusbio import USBIO

logger = logging.getLogger("PCounter")

RC_FILE = os.path.expanduser("~/.counterrc")

N_PORT_GROUP = 3
N_BIT_GROUP = 4
N_COUNT_GROUP = 6

BIT_COUNT = CNT_COUNT = 0
BIT_BONUS = CNT_BONUS = 1
BIT_CHANCE = CNT_CHANCE = 2
BIT_RESERVED = CNT_RESERVED = 3
CNT_EXT_TOTALCOUNT = 4
CNT_EXT_COMBO = 5

if sys.platform == 'win32':
  CAHR_ENCODE = 'cp932'
else:
  CHAR_ENCODE = 'utf-8'


class PCounter(object):
  def __init__(self, rcfile=None, outputfile=None):
    self._rcfile = rcfile if rcfile is not None else RC_FILE 
    self.usbio = None
    self.counts = [ [0]*N_COUNT_GROUP ] * N_PORT_GROUP
    self.onFlag = 0

  def init_device(self):
    self.usbio = USBIO()
    if not self.usbio.find_and_init():
      logger.error(u"USB-IOモジュールの初期化に失敗しました。")
      return False
    return True

  def save(self):
    try:
      with open(self._rcfile, "wb") as f:
        pickle.dump(self.counts, f, -1)
    except IOError, e:
      logger.error(u"カウンタ値が保存できませんでした。原因：{0}".format(e.message))


  def load(self):
    try:
      with open(self._rcfile, "rb") as f:
        self.counts = pickle.load(f)
      return True
    except IOError, e:
      logger.error(u"カウンタ値を読み込めませんでした。原因：{0}".format(e.message))
      return False


  def output(self):
    counts = self.counts[0]
    try:
      bonus_rate = "1/{0:.1f}".format(float(counts[CNT_EXT_TOTALCOUNT]) / counts[CNT_BONUS])
    except ZeroDivisionError:
      bonus_rate = "1/-.-"

    combo = ""
    if counts[CNT_EXT_COMBO] > 0:
      combo = '\n<span size="x-large">{0:3}</span> LockOn!'.format(counts[CNT_EXT_COMBO])

    countstr = u"""<span font-desc="Ricty Bold 15">GameCount:\n<span size="x-large">{0:3}</span>({1})\nBonusCount:\n<span size="x-large">{2:3}</span>/{3} ({4}){5}</span>\x00""" \
           .format(counts[BIT_COUNT], counts[CNT_EXT_TOTALCOUNT], 
                   counts[BIT_BONUS], counts[BIT_CHANCE], 
                   bonus_rate, combo)

    sys.stdout.write(countstr.encode(CHAR_ENCODE))
    sys.stdout.flush()


  def countup(self):
    port0, port1 = self.usbio.send2read()
    port = (port1 << 8) + port0 
    # グループ単位で処理
    for i in xrange(N_PORT_GROUP):
      bitgroup = port & 0x0f;
      port = port >> 4
      # カウンター、ボーナス、チャンス の状態をそれぞれチェック
      for j in (BIT_COUNT, BIT_BONUS, BIT_CHANCE):
        idx = i * N_BIT_GROUP + j
        tbit = 1 << idx
        if bitgroup & (1 << j):
          # 状態がOff→Onになるとき
          if self.onFlag & tbit == 0:
            self.onFlag = self.onFlag | tbit
            self.counts[i][j] += 1
            # それがカウンターだったら 
            if j == BIT_COUNT:
              self.counts[i][CNT_EXT_TOTALCOUNT] += 1
            # それがボーナスだったら 
            elif j == BIT_BONUS:
              cbit = i * N_BIT_GROUP + BIT_CHANCE
              if bitgroup & cbit:
                self.counts[i][CNT_EXT_COMBO] += 1
        else:
          # 状態がOn→Offになるとき
          if self.onFlag & tbit:
            self.onFlag = self.onFlag & (~tbit)
            # それがボーナスだったら
            if j == BIT_BONUS:
              self.counts[i][BIT_COUNT] = 0
            # それがボーナス+時短だったら
            elif j == BIT_CHANCE:
              self.counts[i][CNT_EXT_COMBO] = 0


  def mainloop(self, resetcount=False):
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
  c = PCounter()
  sys.exit(c.mainloop(resetcount))

