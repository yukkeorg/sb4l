# coding: utf-8

import sys
import time
from DateTime import DateTime

class CountdownTimer(object):
  def __init__(self, targettime):
    self.targettime = targettime

  def timer_handler(self):
    dt = self.targettime - time.time() + 1.0
    a = []
    if int(dt) > 0:
      d = int(dt // 86400)
      if d > 0:
        a.append('{0:d}<span size="small">days</span>'.format(d))
      h = int((dt // 3600) % 24)
      if h > 0 or d > 0:
        a.append('{0:d}<span size="small">hour</span>'.format(h))
      m = int((dt // 60) % 60)
      if m > 0 or h > 0:
        a.append('{0:d}<span size="small">min</span>'.format(m))
      s = int(dt % 60)
      a.append('{0:d}<span size="small">sec</span>'.format(s))
    else:
      a.append("FINISH")
    sys.stdout.write(''.join(a) + "\0")
    sys.stdout.flush()


def main():
  if len(sys.argv) < 2:
    return 1
  ct = CountdownTimer(DateTime(sys.argv[1]).timeTime())
  try:
    while True:
      ct.timer_handler()
      time.sleep(0.2)
  except KeyboardInterrupt:
    pass
  return 0

if __name__ == '__main__':
  sys.exit(main())
