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
import optparse
import logging
import signal

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
BIT_SBONUS = CNT_SBONUS = 3
CNT_EXT_TOTALCOUNT = 4
CNT_EXT_COMBO = 5

if sys.platform == 'win32':
  CAHR_ENCODE = 'cp932'
else:
  CHAR_ENCODE = 'utf-8'


class PCounter(object):
  def __init__(self, rcfile=None, outputfile=None, output_callbacks=None):
    self.rcfile = rcfile if rcfile else RC_FILE 
    self.usbio = None
    self.counts = [ [0]*N_COUNT_GROUP ] * N_PORT_GROUP
    self.onFlag = 0
    if output_callbacks is None:
      self.output_callbacks = [None] * N_PORT_GROUP
    else:
      self.output_callbacks = output_callbacks

  def init_device(self):
    self.usbio = USBIO()
    if not self.usbio.find_and_init():
      logger.error(u"USB-IOモジュールの初期化に失敗しました。")
      return False
    return True

  def save(self):
    try:
      with open(self.rcfile, "wb") as f:
        pickle.dump(self.counts, f, -1)
    except IOError, e:
      logger.error(u"カウンタ値が保存できませんでした。原因：{0}".format(e.message))

  def load(self):
    try:
      with open(self.rcfile, "rb") as f:
        self.counts = pickle.load(f)
      return True
    except IOError, e:
      logger.error(u"カウンタ値を読み込めませんでした。原因：{0}".format(e.message))
      return False

  def countup(self):
    port0, port1 = self.usbio.send2read()
    port = (port1 << 8) + port0 
    # グループ単位で処理
    for i in xrange(N_PORT_GROUP):
      bitgroup = port & 0x0f;
      port = port >> 4
      for j in (BIT_COUNT, BIT_BONUS, BIT_CHANCE, BIT_SBONUS):
        idx = i * N_BIT_GROUP + j
        tbit = 1 << idx
        if bitgroup & (1 << j):
          # 状態がOff→Onになるとき
          if self.onFlag & tbit == 0:
            self.onFlag = self.onFlag | tbit
            self.counts[i][j] += 1
            # それがカウンターだったら 
            if j == BIT_COUNT:
              # 総回転数もカウントアップする
              self.counts[i][CNT_EXT_TOTALCOUNT] += 1
            # それがボだったら 
            elif j == BIT_BONUS:
              cbit = i * N_BIT_GROUP + BIT_CHANCE
              # かつチャンス中なら
              if bitgroup & cbit:
                # コンボカウンターもカウントアップする
                self.counts[i][CNT_EXT_COMBO] += 1
        else:
          # 状態がOn→Offになるとき
          if self.onFlag & tbit:
            self.onFlag = self.onFlag & (~tbit)
            # それがボーナスだったら
            if j == BIT_BONUS:
              # 回転数カウンタをリセットする
              self.counts[i][BIT_COUNT] = 0
            # それがチャンス中だったら
            elif j == BIT_CHANCE:
              # コンボカウンタをリセットする
              self.counts[i][CNT_EXT_COMBO] = 0

  def mainloop(self, reset=False, nonull=False):
    self.init_device()
    if not reset:
      if not self.load():
        return 1
    try:
      while True:
        self.countup()
        for i in range(N_PORT_GROUP):
          output_callback = self.output_callbacks[i]
          if output_callback and callable(output_callback):
            countstr = output_callback(self.counts[i])
            sys.stdout.write(countstr.encode(CHAR_ENCODE))
        if not nonull:
          sys.stdout.write("\x00")
        sys.stdout.flush()
        time.sleep(0.2)
    except KeyboardInterrupt:
      pass
    finally:
      self.save()
    return 0


def gen_bonusrate(total, now):
  try:
    bonus_rate = "1/{0:.1f}".format(float(total)/now)
  except ZeroDivisionError:
    bonus_rate = "1/-.-"
  return bonus_rate

def gen_combo(n_combo, suffix=None):
  if suffix is None:
    suffix = "Chain(s)"
  combo = ""
  if n_combo > 0:
    combo = '\n<span size="x-large">{0:3}</span> {1}'.format(n_combo, suffix)
  return combo

def output_for_stealth(counts):
  bonus_rate = gen_bonusrate(counts[CNT_EXT_TOTALCOUNT], counts[CNT_BONUS])
  combo = gen_combo(counts[CNT_EXT_COMBO], "Lock On!")

  return u"""<span font-desc="Ricty Bold 15">GameCount:\n<span size="x-large">{0:3}</span>({1})\nBonusCount:\n<span size="x-large">{2:3}</span>/{3} ({4}){5}</span>""" \
         .format(counts[CNT_COUNT], counts[CNT_EXT_TOTALCOUNT], 
                 counts[CNT_BONUS], counts[CNT_CHANCE], 
                 bonus_rate, combo)


def output_for_xfiles(counts):
  bonus_rate = gen_bonusrate(counts[CNT_EXT_TOTALCOUNT], counts[CNT_BONUS])
  sbonus_rate = gen_bonusrate(counts[CNT_EXT_TOTALCOUNT], counts[CNT_SBONUS])
  combo = gen_combo(counts[CNT_EXT_COMBO])

  return u"""<span font-desc="Ricty Bold 15">____\nGAME\_______\n<span size="x-large">{0:4}</span>({1})\n_____\nBONUS\________\nTOTAL:{6:5}({7})\nUZ+XR:{2:3}/{3}({4}){5}</span>""" \
         .format(counts[CNT_COUNT], counts[CNT_EXT_TOTALCOUNT], 
                 counts[CNT_BONUS], counts[CNT_CHANCE], bonus_rate, 
                 combo,
                 counts[CNT_SBONUS], sbonus_rate)


if __name__ == '__main__':
  output_funcs_table = {
      'stealth' : output_for_stealth,
      'xfiles'  : output_for_xfiles,
  }
  output_funcs = [None] * N_PORT_GROUP

  parse = optparse.OptionParser()
  parse.add_option("-r", "--reset", dest="reset", action="store_true")
  parse.add_option("-n", "--nonull", dest="nonull", action="store_true")
  parse.add_option("-t", "--types", dest="types")
  (opt, args) = parse.parse_args()

  if opt.types:
    _types = opt.types.split(',')
    l = min(len(_types), N_PORT_GROUP)
    output_funcs[0:l] = [ output_funcs_table.get(_types[i], None) for i in range(l) ]

  pc = PCounter(output_callbacks=output_funcs)

  # シグナルハンドラ用メソッド
  def signal_handler(signum, stackframe):
    if signum == signal.SIGTERM:
      pc.save()
      sys.exit(2)
  signal.signal(signal.SIGTERM, signal_handler)

  ret = pc.mainloop(opt.reset, opt.nonull)
  sys.exit(ret)

