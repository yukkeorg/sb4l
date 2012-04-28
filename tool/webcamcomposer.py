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
import codecs
import shlex
import subprocess
import signal
try:
  import cPickle as pickle
except ImportError:
  import pickle

from gi.repository import GLib, Gtk, Gdk

import pygst
pygst.require('0.10')
import gst


SETTING_FILENAME = os.path.expanduser('~/.cameracapturerc')
N_TELOP = 4

_CCS_HALIGN = {
  'left'   : 0,
  'center' : 1,
  'right'  : 2,
}

_CCS_VALIGN = {
  'top'    : 0,
  'center' : 1,
  'bottom' : 2,
}


class WebcamComposerSetting(object):
  SETTING_LATEST_VERSION = '0.1'

  def __init__(self):
    self._version = self.SETTING_LATEST_VERSION

    self.SRC_DEVICE = '/dev/video0'
    self.SRC_FORMAT = 'video/x-raw-yuv'
    self.SRC_WIDTH = '640'
    self.SRC_HEIGHT = '480'
    self.SRC_FRAMERATE = '30/1'
    self.DST_DEVICE = '/dev/video1'

    self.TELOP_PROPERTIES = [ {
      'valignment' : 'top',        # top, bottom, center
      'halignment' : 'left',       # left, right, center
      'line-alignment' : 'left',   # left, right, center
      'xpad' : '0',
      'ypad' : '0',
      'text' : '',
      '_is_cmd' : False,
    } for i in xrange(N_TELOP) ]


  def merge(self, other):
    if not isinstance(other, WebcamComposerSetting):
      return

    for key, value in other.__dict__.iteritems():
      if key == '_version':
        continue
      if key in self.__dict__:
        if isinstance(value, (list, tuple)):
          self.__dict__[key][:len(value)] = value
        elif isinstance(value, dict):
          self.__dict__[key].update(value)
        else:
          self.__dict__[key] = value
      else:
        self.__dict__[key] = value


def saveSetting(fn, s):
  with open(fn, "wb") as f:
    pickle.dump(s, f, -1)


def loadSetting(fn):
  try:
    with open(fn, "rb") as f:
      o = pickle.load(f)
    if o._version == WebcamComposerSetting.SETTING_LATEST_VERSION:
      return o
    n = WebcamComposerSetting()
    n.merge(o)
    return n
  except:
    pass
  return None
      
setting = loadSetting(SETTING_FILENAME) or WebcamComposerSetting()




class WebcamComposer(object):
  ALLOW_TELOP_PROP_NAME = ("halignment", "valignment", 
                           "line-alignment", "xpad", "ypad", 
                           "text", "shaded-background")

  def __init__(self, prev_panel=None, on_err_callback=None):
    self.prev_panel = prev_panel
    self.on_err_callback = on_err_callback
    self.build_composer()

  def build_composer(self):
    #################
    # Make Elements #
    #################
    self.player = gst.Pipeline('WebcamComposer')
    self.camerasource = gst.element_factory_make('v4l2src')
    capsfilter = gst.element_factory_make('capsfilter')
    videorate = gst.element_factory_make('videorate')
    self.telops = [ gst.element_factory_make('textoverlay') for i in xrange(N_TELOP) ]
    self.v4l2sink = gst.element_factory_make('v4l2sink')
    self.avsink = gst.element_factory_make('xvimagesink')
    tee = gst.element_factory_make('tee')
    queue1 = gst.element_factory_make('queue')
    queue2 = gst.element_factory_make('queue')
    queue3 = gst.element_factory_make('queue')
    colorspace = gst.element_factory_make('ffmpegcolorspace')

    self.player.add(self.camerasource, videorate, capsfilter,
                    self.v4l2sink, self.avsink, tee, 
                    queue1, queue2, queue3, colorspace,
                    *self.telops)
    firstelements = [self.camerasource, queue1, videorate, 
                     capsfilter] + self.telops + [ tee ]
    gst.element_link_many(*firstelements)
    gst.element_link_many(tee, queue2, self.v4l2sink)
    gst.element_link_many(tee, queue3, colorspace, self.avsink)

    ########################
    # Configuring Elements #
    ########################
    # v4l2src property
    self.camerasource.set_property('device', setting.SRC_DEVICE)
    self.camerasource.set_property('blocksize', 65536)
    # caps property
    srccaps = '{0},width={1},height={2},framerate={3}' \
               .format(setting.SRC_FORMAT, setting.SRC_WIDTH, 
                       setting.SRC_HEIGHT, setting.SRC_FRAMERATE)
    capsfilter.set_property('caps', gst.caps_from_string(srccaps))
    self.v4l2sink.set_property('device', setting.DST_DEVICE)

    for i in xrange(N_TELOP):
      telop = self.telops[i]
      try:
        tp = setting.TELOP_PROPERTIES[i]
      except IndexError:
        tp = { "_is_cmd" : False }

      telop.set_property("halignment", tp.get("halignment", "left"))
      print(" ***************** " + tp.get("halignment", "left"))
      telop.set_property("valignment", tp.get("valignment", "top"))  # top, bottom, center
      telop.set_property("line-alignment",  tp.get("line-alignment", "left"))  # left, right
      telop.set_property("xpad", int(tp.get("xpad", 0))) 
      telop.set_property("ypad", int(tp.get("ypad", 0)))
      if tp.get("_is_cmd", False):
        telop.set_property("text", "")
      else:
        telop.set_property("text", tp.get("text", ""))

    ########################
    # Connecting Callbacks #
    ########################
    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect("message", self.on_message)
    bus.connect("sync-message::element", self.on_sync_message)


  def set_state(self, state):
    self.player.set_state(state)


  def set_telop_text(self, no, text):
    try:
      telop = self.telops[no]
    except IndexError:
      return 
    telop.set_property("text", text)


  def set_telop_property(self, no, propdict):
    try:
      telop = self.telops[no]
    except IndexError:
      return 
    for name, value in propdict.iteritems():
      if name in self.ALLOW_TELOP_PROP_NAME:
        telop.set_property(name, value)


  #########
  # Event #
  #########
  def on_message(self, bus, message):
    type = message.type
    if type == gst.MESSAGE_EOS:
      self.player.set_state(gst.STATE_NULL)
    elif type == gst.MESSAGE_ERROR:
      self.player.set_state(gst.STATE_NULL)
      msg = message.parse_error()
      if self.on_err_callback and callable(self.on_err_callback):
        self.on_err_callback(msg)


  def on_sync_message(self, bus, message):
    if message.structure is None:
      return
    message_name = message.structure.get_name()
    if message_name == "prepare-xwindow-id":
      imagesink = message.src
      imagesink.set_property("force-aspect-ratio", True)
      if self.prev_panel: 
        Gtk.gdk.threads_enter()
        imagesink.set_xwindow_id(self.prev_panel.window.xid)
        Gtk.gdk.threads_leave()



class StdoutReader(object):
  SR_START = 1
  SR_READY = 2
  SR_END = 3 

  def __init__(self, cmd_and_args, callback, telop_no):
    self.cmd_and_args = cmd_and_args
    self.callback = callback
    self.telop_no = telop_no
    self.child = None
    self._spawn()


  def _spawn(self):
    try:
      self.child = subprocess.Popen(self.cmd_and_args, 
                                    stdout=subprocess.PIPE, 
                                    close_fds=True)
    except OSError, e:
      print(e.message)
      return

    try:
      GLib.io_add_watch(self.child.stdout, 
                        GLib.IO_IN | GLib.IO_HUP, 
                        self._event)
    except GLib.GError, e:
      self.terminate()
      print(e.message)
      return

    if self.callback:
        self.callback(self.SR_START, self, None)


  def _event(self, fd, condition):
    if condition & GLib.IO_IN:
      text = []
      while True:
        data = fd.read(1)
        if data == "\x00" or data == "": 
          break
        text.append(data)
      text = ''.join(text)
      if self.callback:
        self.callback(self.SR_READY, self, text)

    if condition & GLib.IO_HUP:
      self.child.poll()
      if self.callback:
        self.callback(self.SR_END, self, None)
      return False
    return True


  def terminate(self):
    if self.child:
      self.child.terminate()


  def is_running(self):
    if self.child:
      return (self.child.returncode is None)
    else:
      return False




class WebcamComposerWindow(Gtk.Window):
  def __init__(self):
    Gtk.Window.__init__(self, Gtk.WindowType.TOPLEVEL)
    self.player = None
    self.spawnlist = [None] * N_TELOP

    self.build_window()
    self.set_values()


  def build_window(self):
    self.set_title("Webcam Comporser")
    self.set_default_size(800, 600)
    self.connect("delete-event", self.on_delete)
    self.connect("destroy", self.on_destroy)

    vbox_root = Gtk.VBox()
    self.add(vbox_root)

    self.menubar = self.build_menu()
    vbox_root.pack_start(self.menubar, False, True, 0)

    vbox_main = Gtk.VBox()
    vbox_main.set_spacing(8)
    vbox_root.pack_start(vbox_main, True, True, 0)

    vbox_main.pack_start(self.build_camera_box(), True, True, 0)
    vbox_main.pack_start(self.build_telop_box(), False, True, 0)
    # vbox_main.pack_start(self.build_streaming_box(), False)

    self.show_all()


  def build_camera_box(self):
    vbox = Gtk.VBox()

    hbox = Gtk.HBox()
    hbox.set_spacing(8)
    vbox.pack_start(hbox, False, True, 0)

    hbox.pack_start(Gtk.Label("Src:"), False, True, 0)
    self.ent_camera_src = Gtk.Entry()
    self.ent_camera_src.set_size_request(100, -1)
    hbox.pack_start(self.ent_camera_src, False, True, 0)

    hbox.pack_start(Gtk.Label("Fmt:"), False, True, 0)
    self.ent_camera_fmt = Gtk.Entry()
    self.ent_camera_fmt.set_size_request(100, -1)
    hbox.pack_start(self.ent_camera_fmt, False, True, 0)

    hbox.pack_start(Gtk.Label("Width:"), False, True, 0)
    self.ent_camera_width = Gtk.Entry()
    self.ent_camera_width.set_size_request(50, -1)
    hbox.pack_start(self.ent_camera_width, False, True, 0)

    hbox.pack_start(Gtk.Label("Height:"), False, True, 0)
    self.ent_camera_height = Gtk.Entry()
    self.ent_camera_height.set_size_request(50, -1)
    hbox.pack_start(self.ent_camera_height, False, True, 0)

    hbox.pack_start(Gtk.Label("FPS:"), False, True, 0)
    self.ent_camera_fps= Gtk.Entry()
    self.ent_camera_fps.set_size_request(50, -1)
    hbox.pack_start(self.ent_camera_fps, False, True, 0)

    hbox.pack_start(Gtk.Label("Dst:"), False, True, 0)
    self.ent_camera_dst= Gtk.Entry()
    self.ent_camera_dst.set_size_request(100, -1)
    hbox.pack_start(self.ent_camera_dst, False, True, 0)

    self.btn_camera_tgl = Gtk.ToggleButton("Camera Off")
    self.btn_camera_tgl.connect("toggled", self.on_camera_startstop)
    hbox.pack_start(self.btn_camera_tgl, True, True, 0)

    self.movie_window = Gtk.DrawingArea()
    vbox.pack_start(self.movie_window, True, True, 0)

    return vbox


  def build_telop_box(self):
    vbox = Gtk.VBox()
    vbox.set_spacing(8)

    hbox = Gtk.HBox()
    hbox.set_spacing(8)
    vbox.pack_start(hbox, True, True, 0)

    hbox.pack_start(Gtk.Label("TNO."), False, True, 0)
    self.cmb_text_idx = Gtk.ComboBoxText()
    self.cmb_text_idx.connect('changed', self.on_cmb_text_idx_changed)
    hbox.pack_start(self.cmb_text_idx, True, True, 0)
    for i in xrange(N_TELOP):
      self.cmb_text_idx.append_text(str(i))

    hbox.pack_start(Gtk.Label("V:"), False, True, 0)
    self.cmb_text_valign = Gtk.ComboBoxText()
    hbox.pack_start(self.cmb_text_valign, True, True, 0)
    self.cmb_text_valign.append_text("top")
    self.cmb_text_valign.append_text("center")
    self.cmb_text_valign.append_text("bottom")

    hbox.pack_start(Gtk.Label("H:"), False, True, 0)
    self.cmb_text_halign = Gtk.ComboBoxText()
    hbox.pack_start(self.cmb_text_halign, True, True, 0)
    self.cmb_text_halign.append_text("left")
    self.cmb_text_halign.append_text("center")
    self.cmb_text_halign.append_text("right")

    hbox.pack_start(Gtk.Label("Line:"), False, True, 0)
    self.cmb_text_lalign = Gtk.ComboBoxText()
    hbox.pack_start(self.cmb_text_lalign, True, True, 0)
    self.cmb_text_lalign.append_text("left")
    self.cmb_text_lalign.append_text("center")
    self.cmb_text_lalign.append_text("right")

    hbox.pack_start(Gtk.Label("X-pad:"), False, True, 0)
    self.ent_text_xpad = Gtk.Entry()
    self.ent_text_xpad.set_size_request(50, -1)
    hbox.pack_start(self.ent_text_xpad, True, True, 0)

    hbox.pack_start(Gtk.Label("Y-pad:"), False, True, 0)
    self.ent_text_ypad = Gtk.Entry()
    self.ent_text_ypad.set_size_request(50, -1)
    hbox.pack_start(self.ent_text_ypad, True, True, 0)

    hbox2 = Gtk.HBox()
    vbox.pack_start(hbox2, True, True, 0)

    self.chk_text_is_cmdline = Gtk.CheckButton("Command")
    self.chk_text_is_cmdline.set_alignment(0, 0)
    hbox2.pack_start(self.chk_text_is_cmdline, False, True, 0)

    self.btn_exec = Gtk.Button("Exec")
    self.btn_exec.connect("clicked", self.on_exec)
    self.btn_exec.set_sensitive(False)
    hbox2.pack_start(self.btn_exec, False, True, 0)

    self.btn_kill = Gtk.Button("Kill")
    self.btn_kill.connect("clicked", self.on_kill)
    self.btn_kill.set_sensitive(False)
    hbox2.pack_start(self.btn_kill, False, True, 0)

    self.chk_background = Gtk.CheckButton("Shaded Background")
    hbox2.pack_start(self.chk_background, False, True, 0)

    self.btn_update = Gtk.Button("Update")
    self.btn_update.set_property("width-request", 200)
    self.btn_update.connect("clicked", self.on_update)
    hbox2.pack_end(self.btn_update, False, True, 0)

    scroll_text_view = Gtk.ScrolledWindow()
    scroll_text_view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    self.ent_text = Gtk.TextView()
    self.ent_text.set_size_request(-1, 64)
    scroll_text_view.add(self.ent_text)
    vbox.pack_start(scroll_text_view, True, True, 0)

    return vbox


  def build_streaming_box(self):
    hbox = Gtk.HBox()
    hbox.set_spacing(8)

    vbox_left = Gtk.VBox()
    vbox_left.set_spacing(8)
    hbox.pack_start(vbox_left, False, True, 0)

    label1 = Gtk.Label("Streaming Command-line")
    label1.set_justify(Gtk.JUSTIFY_LEFT)
    label1.set_alignment(0,0)
    vbox_left.pack_start(label1, False, True, 0)

    scroll_text_view = Gtk.ScrolledWindow()
    scroll_text_view.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    self.ent_stream_cmdline = Gtk.TextView()
    scroll_text_view.add(self.ent_stream_cmdline)
    vbox_left.pack_start(scroll_text_view)

    vbox_right = Gtk.VBox()
    vbox_right.set_spacing(8)
    hbox.pack_start(vbox_right, False, True, 0)

    self.lbl_streamingstatus = Gtk.Label()
    self.lbl_streamingstatus.set_text("Streaming is stopped.")
    vbox_right.pack_end(self.lbl_streamingstatus, False, True, 0)
    self.btn_startstop = Gtk.ToggleButton("Streaming")
    vbox_right.pack_end(self.btn_startstop, False, True, 0)

    return hbox


  def build_menu(self):
    # File
    menu_quit = Gtk.MenuItem(u'Quit')

    filemenu = Gtk.Menu()
    filemenu.append(menu_quit)

    # TOP Menu
    filemenutop = Gtk.MenuItem(u'File')
    filemenutop.set_submenu(filemenu)

    menubar = Gtk.MenuBar()
    menubar.append(filemenutop)

    return menubar


  def set_values(self):
    self.ent_camera_src.set_text(setting.SRC_DEVICE)
    self.ent_camera_fmt.set_text(setting.SRC_FORMAT)
    self.ent_camera_width.set_text(setting.SRC_WIDTH)
    self.ent_camera_height.set_text(setting.SRC_HEIGHT)
    self.ent_camera_fps.set_text(setting.SRC_FRAMERATE)
    self.ent_camera_dst.set_text(setting.DST_DEVICE)

    self.cmb_text_idx.set_active(0)

  ###############
  #  Callbacks  #
  ###############

  # -- Internal 

  def on_cmb_text_idx_changed(self, widget):
    idx = widget.get_active()
    try:
      properties = setting.TELOP_PROPERTIES[idx]
    except IndexError:
      return

    self.cmb_text_halign.set_active(
        _CCS_HALIGN.get(properties.get('halignment', 'left'), 0))
    self.cmb_text_valign.set_active(
        _CCS_VALIGN.get(properties.get('valignment', 'top'), 0))
    self.cmb_text_lalign.set_active(
        _CCS_HALIGN.get(properties.get('line-alignment', 'left'), 0))
    self.ent_text_xpad.set_text(str(properties.get('xpad', 0)))
    self.ent_text_ypad.set_text(str(properties.get('ypad', 0)))
    is_cmd = properties.get('_is_cmd', False)
    self.chk_text_is_cmdline.set_active(is_cmd)
    self.btn_kill.set_sensitive(False)
    if is_cmd:
      spawn = self.spawnlist[idx]
      if spawn and spawn.is_running():
        self.btn_kill.set_sensitive(True)
    self.chk_background.set_active(1 if properties.get('shaded-background', False) else 0)
    self.ent_text.get_buffer().set_text(properties.get('text', ''))


  def on_update(self, widget, *args):
    properties = {}
    properties['halignment'] = self.cmb_text_halign.get_active_text()
    properties['valignment'] = self.cmb_text_valign.get_active_text()
    properties['line-alignment'] = self.cmb_text_lalign.get_active_text()
    properties['xpad'] = int(self.ent_text_xpad.get_text())
    properties['ypad'] = int(self.ent_text_ypad.get_text())
    properties['_is_cmd'] = self.chk_text_is_cmdline.get_active()
    properties['shaded-background'] = 1 if self.chk_background.get_active() else 0
    properties['text'] = self.getTextViewValue(self.ent_text)

    no = self.cmb_text_idx.get_active()
    if no < 0:
      return 
    try:
      setting.TELOP_PROPERTIES[no] = properties
    except IndexError:
      return

    if self.player:
      self.player.set_telop_property(no, properties)
      if properties['_is_cmd']:
        cmdline = shlex.split(properties['text'])
        self.spawnlist[no] = StdoutReader(cmdline, self.on_read_from_stdout, no)


  def on_camera_startstop(self, widget):
    if widget.get_active(): 
      setting.SRC_DEVICE = self.ent_camera_src.get_text()
      setting.SRC_FORMAT = self.ent_camera_fmt.get_text()
      setting.SRC_WIDTH = self.ent_camera_width.get_text()
      setting.SRC_HEIGHT = self.ent_camera_height.get_text()
      setting.SRC_FRAMERATE = self.ent_camera_fps.get_text()
      setting.DST_DEVICE = self.ent_camera_dst.get_text()

      self.player = WebcamComposer(prev_panel=self.movie_window, 
                                   on_err_callback=self.on_cc_error)
      self.player.set_state(gst.STATE_PAUSED)
      self.player.set_state(gst.STATE_PLAYING)
      self.btn_camera_tgl.set_label("Camera Off")
    else:
      for spawn in self.spawnlist:
        if spawn and spawn.is_running():
          spawn.terminate()
      self.player.set_state(gst.STATE_NULL)
      self.player = None
      self.btn_camera_tgl.set_label("Camera On")


  def on_exec(self, widget):
    pass


  def on_kill(self, widget):
    no = self.cmb_text_idx.get_active()
    sr = self.spawnlist[no]
    if sr and sr.is_running():
      sr.terminate()

    
  def on_delete(self, widget, *args):
    print("OnDelete is called.")
    if self.player:
      self.player.set_state(gst.STATE_NULL)
    return False 


  def on_destroy(self, widget, *args):
    print("OnDestroy is called.")
    Gtk.main_quit()


  # -- External 

  def on_cc_error(self, message): 
    """ WebcamComposer Error Callback """
    print("{0}:{1}".format(*message), file=sys.stderr)
    if self.player:
      self.player.set_state(gst.STATE_NULL)
    self.btn_camera_tgl.set_active(False)
    self.btn_camera_tgl.set_label("Camera Off")


  def on_read_from_stdout(self, msgtype, sr, text):
    """ StdoutReader read data from stdout callback """
    if msgtype == StdoutReader.SR_READY:
      if self.player:
        self.player.set_telop_text(sr.telop_no, text)
    elif msgtype == StdoutReader.SR_START:
      self.btn_kill.set_sensitive(True)
    elif msgtype == StdoutReader.SR_END:
      self.btn_kill.set_sensitive(False)


  ##########
  #  Misc  #
  ##########
  def getTextViewValue(self, textview):
    buf = textview.get_buffer()
    start, end = buf.get_bounds()
    text = buf.get_text(start, end, False)
    return text

    



if __name__ == "__main__":
  cm = WebcamComposerWindow()
  Gdk.threads_init()
  Gtk.main()
  saveSetting(SETTING_FILENAME, setting)

