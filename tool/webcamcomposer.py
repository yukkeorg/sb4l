#!/usr/bin/env python
# coding: utf-8

# Copyright (c) 2011-2012, Yusuke Ohshima <createtool@yukke.org>
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

import pygtk
pygtk.require('2.0')
import gtk
import glib

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


class TelopSetting(object):
  def __init__(self, 
               valignment=None, halignment=None, linealignment=None,
               xpad=None, ypad=None, fontdesc=None, text=None,
               is_cmd=False, **kw):
      self.valignment = valignment or 'top'
      self.halignment = halignment or 'left'
      self.linealignment = linealignment or 'left'
      self.xpad = xpad or '0'
      self.ypad = ypad or '0'
      self.fontdesc = fontdesc or ''
      self.text = text or ''
      self.is_cmd = is_cmd or False


class WebcamComposerSetting(object):
  SETTING_LATEST_VERSION = '1.0'

  def __init__(self):
    self._version = self.SETTING_LATEST_VERSION

    self.source_device = '/dev/video0'
    self.source_format = 'video/x-raw-yuv'
    self.source_width = '640'
    self.source_height = '480'
    self.source_framerate = '30/1'
    self.sink_device = '/dev/video1'
    self.telops = [ TelopSetting() for i in xrange(N_TELOP) ]
    self.frame_svgfile = ''

  def Save(self, filename):
    with open(filename, "wb") as f:
      pickle.dump(self, f, -1)

  @staticmethod
  def Load(filename):
    try:
      with open(filename, "rb") as f:
        o = pickle.load(f)
        print(o)
      if isinstance(o, WebcamComposerSetting):
        return o
      else:
        print("Not WebcamComposerSetting.")
        return WebcamComposerSetting()
    except:
      return WebcamComposerSetting()


class WebcamComposer(object):
  ALLOW_TELOP_PROP_NAME = ("halignment", "valignment", 
                           "line-alignment", "xpad", "ypad", 
                           "text")

  def __init__(self, setting, prev_panel=None, on_err_callback=None):
    self.setting = setting
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
    capsfilter2 = gst.element_factory_make('capsfilter')
    videorate = gst.element_factory_make('videorate')
    videorate2 = gst.element_factory_make('videorate')
    jpegdec = gst.element_factory_make('jpegdec')
    self.framesvg = gst.element_factory_make('rsvgoverlay')
    self.textoverlays = [ gst.element_factory_make('textoverlay') for i in xrange(N_TELOP) ]
    self.v4l2sink = gst.element_factory_make('v4l2sink')
    self.monitorsink= gst.element_factory_make('xvimagesink')
    tee = gst.element_factory_make('tee')
    queue = gst.element_factory_make('queue')
    queue2 = gst.element_factory_make('queue')
    queue3 = gst.element_factory_make('queue')
    colorspace1 = gst.element_factory_make('ffmpegcolorspace')
    colorspace2 = gst.element_factory_make('ffmpegcolorspace')
    colorspace3 = gst.element_factory_make('ffmpegcolorspace')

    self.player.add(self.camerasource, self.v4l2sink, self.monitorsink, self.framesvg,
                    videorate, videorate2, capsfilter, capsfilter2, jpegdec,
                    tee, 
                    queue, queue2, queue3, 
                    colorspace1, colorspace2, colorspace3, 
                    *self.textoverlays)

    gst.element_link_many(*([self.camerasource,  capsfilter, queue, jpegdec, 
                             colorspace1, self.framesvg ] 
                            + self.textoverlays + [ tee ]))
    gst.element_link_many(tee, queue2, colorspace2, self.v4l2sink)
    gst.element_link_many(tee, queue3, colorspace3, self.monitorsink)

    ########################
    # Configuring Elements #
    ########################
    # v4l2src property
    self.camerasource.set_property('device', self.setting.source_device)
    self.camerasource.set_property('always-copy', False)
    #self.camerasource.set_property('queue-size', 4)
    self.camerasource.set_property('blocksize', 65536)

    # caps property
    srccaps = 'image/jpeg,width={0},height={1},framerate={2}' \
               .format(self.setting.source_width, 
                       self.setting.source_height, 
                       self.setting.source_framerate)
    capsfilter.set_property('caps', gst.caps_from_string(srccaps))

    # queue
    queue.set_property('leaky', 2)

    # v4l2sink
    self.v4l2sink.set_property('device', self.setting.sink_device)
    self.v4l2sink.set_property('sync', False)

    # textoverlay
    for i in xrange(N_TELOP):
      try:
        telop_prop = self.setting.telops[i]
      except IndexError:
        telop_prop = TelopSetting()

      self.SetTelopAtrribute(i, telop_prop)
      if telop_prop.is_cmd:
        self.SetTelopText(i, "")
      else:
        self.SetTelopText(i, telop_prop.text)

    # rsvgoverlay
    self.framesvg.set_property("location", self.setting.frame_svgfile)

    # sink
    self.monitorsink.set_property("sync", False)

    ########################
    # Connecting Callbacks #
    ########################
    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect("message", self.on_message)
    bus.connect("sync-message::element", self.on_sync_message)

  # Pipeline
  def Play(self):
    self.player.set_state(gst.STATE_PLAYING)

  def Pause(self):
    self.player.set_state(gst.STATE_PAUSED)

  def Null(self):
    self.player.set_state(gst.STATE_NULL)

  # TextOverlay
  def SetTelopText(self, no, text):
    textoverlay = self.textoverlays[no]
    textoverlay.set_property("text", text)

  def SetTelopAtrribute(self, no, telop_prop):
    textoverlay = self.textoverlays[no]
    textoverlay.set_property("halignment", telop_prop.halignment)
    textoverlay.set_property("valignment", telop_prop.valignment)
    textoverlay.set_property("line-alignment", telop_prop.linealignment)
    textoverlay.set_property("font-desc", telop_prop.fontdesc)
    textoverlay.set_property("xpad", int(telop_prop.xpad))
    textoverlay.set_property("ypad", int(telop_prop.ypad))

  # RSvgOverlay
  def SetFrameSvgFile(self, filepath):
    self.framesvg.set_property("location", filepath)

  #############
  # Callbacks #
  #############
  def on_message(self, bus, message):
    type = message.type
    if type == gst.MESSAGE_EOS:
      self.Null()
    elif type == gst.MESSAGE_ERROR:
      self.Null()
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
        gtk.gdk.threads_enter()
        imagesink.set_xwindow_id(self.prev_panel.window.xid)
        gtk.gdk.threads_leave()


class SpawnStdoutReader(object):
  START = 1
  READY = 2
  END = 3 

  def __init__(self, cmd_and_args, callback, callback_args):
    self.cmd_and_args = cmd_and_args
    self.callback = callback
    self.callback_args = callback_args
    self.child = None

  def run(self):
    try:
      self.child = subprocess.Popen(self.cmd_and_args, 
                                    stdout=subprocess.PIPE, 
                                    close_fds=True)
    except OSError as e:
      print(e.message)
      return

    try:
      glib.io_add_watch(self.child.stdout, 
                        glib.IO_IN | glib.IO_HUP, 
                        self._event)
    except glib.GError as e:
      self.terminate()
      print(e.message)
      return

    if self.callback:
        self.callback(self.START, None, self.callback_args)

  def _event(self, fd, condition):
    if condition & glib.IO_IN:
      buf = []
      while True:
        data = fd.read(1)
        if data == "\x00": 
          break
        buf.append(data)
      text = ''.join(buf)
      if self.callback:
        self.callback(self.READY, text, self.callback_args)

    if condition & glib.IO_HUP:
      self.child.poll()
      if self.callback:
        self.callback(self.END, None, self.callback_args)
      return False
    return True

  def terminate(self):
    if self.child:
      self.child.terminate()

  def is_running(self):
    if not self.child:
      return False
    return (self.child.returncode is None)


class WebcamComposerWindow(gtk.Window):
  def __init__(self, setting):
    gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)

    self.setting = setting
    self.player = None
    self.spawnlist = [None] * N_TELOP

    self.build_window()
    self.set_values()

  def build_window(self):
    self.set_title("Webcam Comporser")
    self.set_default_size(800, 600)
    self.connect("delete-event", self.on_delete)
    self.connect("destroy", self.on_destroy)

    vbox_root = gtk.VBox()
    self.add(vbox_root)

    self.menubar = self.build_menu()
    vbox_root.pack_start(self.menubar, False)

    vbox_main = gtk.VBox()
    vbox_main.set_spacing(8)
    vbox_root.pack_start(vbox_main, True)

    vbox_main.pack_start(self.build_camera_box(), True)
    vbox_main.pack_start(self.build_frame_box(), False)
    vbox_main.pack_start(self.build_telop_box(), False)
    # vbox_main.pack_start(self.build_streaming_box(), False)

    self.show_all()

  def build_camera_box(self):
    vbox = gtk.VBox()

    hbox = gtk.HBox()
    hbox.set_spacing(8)
    vbox.pack_start(hbox, False)

    hbox.pack_start(gtk.Label("Src:"), False)
    self.ent_camera_src = gtk.Entry()
    self.ent_camera_src.set_size_request(100, -1)
    hbox.pack_start(self.ent_camera_src, False)

    hbox.pack_start(gtk.Label("Fmt:"), False)
    self.ent_camera_fmt = gtk.Entry()
    self.ent_camera_fmt.set_size_request(100, -1)
    hbox.pack_start(self.ent_camera_fmt, False)

    hbox.pack_start(gtk.Label("Width:"), False)
    self.ent_camera_width = gtk.Entry()
    self.ent_camera_width.set_size_request(50, -1)
    hbox.pack_start(self.ent_camera_width, False)

    hbox.pack_start(gtk.Label("Height:"), False)
    self.ent_camera_height = gtk.Entry()
    self.ent_camera_height.set_size_request(50, -1)
    hbox.pack_start(self.ent_camera_height, False)

    hbox.pack_start(gtk.Label("FPS:"), False)
    self.ent_camera_fps = gtk.Entry()
    self.ent_camera_fps.set_size_request(50, -1)
    hbox.pack_start(self.ent_camera_fps, False)

    hbox.pack_start(gtk.Label("Sink:"), False)
    self.ent_sink = gtk.Entry()
    self.ent_sink.set_size_request(100, -1)
    hbox.pack_start(self.ent_sink, False)

    self.btn_camera_tgl = gtk.ToggleButton("Camera Off")
    self.btn_camera_tgl.connect("toggled", self.on_camera_startstop)
    hbox.pack_start(self.btn_camera_tgl, True)

    self.movie_window = gtk.DrawingArea()
    vbox.pack_start(self.movie_window, True)

    return vbox

  def build_frame_box(self):
    vbox = gtk.VBox()

    hbox = gtk.HBox()
    hbox.set_spacing(8)
    vbox.pack_start(hbox, False)

    hbox.pack_start(gtk.Label("Frame SVG :"), False)
    self.setframe_btn = gtk.FileChooserButton("Set Frame from SVG")
    self.setframe_btn.connect("file-set", self.on_setframe_fileset)
    hbox.pack_start(self.setframe_btn, True)

    return vbox

  def build_telop_box(self):
    vbox = gtk.VBox()
    vbox.set_spacing(8)

    hbox = gtk.HBox()
    hbox.set_spacing(8)
    vbox.pack_start(hbox, True)

    hbox.pack_start(gtk.Label("TNO."), False)
    self.cmb_text_idx = gtk.combo_box_new_text()
    self.cmb_text_idx.connect('changed', self.on_cmb_text_idx_changed)
    hbox.pack_start(self.cmb_text_idx, True)
    for i in xrange(N_TELOP):
      self.cmb_text_idx.append_text(str(i))

    hbox.pack_start(gtk.Label("V:"), False)
    self.cmb_text_valign = gtk.combo_box_new_text()
    hbox.pack_start(self.cmb_text_valign, True)
    self.cmb_text_valign.append_text("top")
    self.cmb_text_valign.append_text("center")
    self.cmb_text_valign.append_text("bottom")

    hbox.pack_start(gtk.Label("H:"), False)
    self.cmb_text_halign = gtk.combo_box_new_text()
    hbox.pack_start(self.cmb_text_halign, True)
    self.cmb_text_halign.append_text("left")
    self.cmb_text_halign.append_text("center")
    self.cmb_text_halign.append_text("right")

    hbox.pack_start(gtk.Label("Line:"), False)
    self.cmb_text_lalign = gtk.combo_box_new_text()
    hbox.pack_start(self.cmb_text_lalign, True)
    self.cmb_text_lalign.append_text("left")
    self.cmb_text_lalign.append_text("center")
    self.cmb_text_lalign.append_text("right")

    hbox.pack_start(gtk.Label("X-pad:"), False)
    self.ent_text_xpad = gtk.Entry()
    self.ent_text_xpad.set_size_request(50, -1)
    hbox.pack_start(self.ent_text_xpad, True)

    hbox.pack_start(gtk.Label("Y-pad:"), False)
    self.ent_text_ypad = gtk.Entry()
    self.ent_text_ypad.set_size_request(50, -1)
    hbox.pack_start(self.ent_text_ypad, True)

    hbox2 = gtk.HBox()
    vbox.pack_start(hbox2, True)
    vbox.set_spacing(8)

    self.chk_text_is_cmdline = gtk.CheckButton("Command")
    self.chk_text_is_cmdline.set_alignment(0, 0)
    hbox2.pack_start(self.chk_text_is_cmdline, False)

    self.btn_exec = gtk.Button("Exec")
    self.btn_exec.connect("clicked", self.on_exec)
    self.btn_exec.set_sensitive(False)
    hbox2.pack_start(self.btn_exec, False)

    self.btn_kill = gtk.Button("Kill")
    self.btn_kill.connect("clicked", self.on_kill)
    self.btn_kill.set_sensitive(False)
    hbox2.pack_start(self.btn_kill, False)

    # self.chk_background = gtk.CheckButton("Shaded Background")
    # hbox2.pack_start(self.chk_background, False)

    hbox2.pack_start(gtk.Label("Display Font:"), False)
    self.fontselector = gtk.FontButton();
    self.fontselector.connect("font-set", self.on_font_set)
    hbox2.pack_start(self.fontselector, False)


    self.btn_update = gtk.Button("Update")
    self.btn_update.set_property("width-request", 200)
    self.btn_update.connect("clicked", self.on_update)
    hbox2.pack_end(self.btn_update, False)

    scroll_text_view = gtk.ScrolledWindow()
    scroll_text_view.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    self.ent_text = gtk.TextView()
    self.ent_text.set_size_request(-1, 64)
    scroll_text_view.add(self.ent_text)
    vbox.pack_start(scroll_text_view, True)

    return vbox

  def build_streaming_box(self):
    hbox = gtk.HBox()
    hbox.set_spacing(8)

    vbox_left = gtk.VBox()
    vbox_left.set_spacing(8)
    hbox.pack_start(vbox_left)

    label1 = gtk.Label("Streaming Command-line")
    label1.set_justify(gtk.JUSTIFY_LEFT)
    label1.set_alignment(0,0)
    vbox_left.pack_start(label1, False)

    scroll_text_view = gtk.ScrolledWindow()
    scroll_text_view.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    self.ent_stream_cmdline = gtk.TextView()
    scroll_text_view.add(self.ent_stream_cmdline)
    vbox_left.pack_start(scroll_text_view)

    vbox_right = gtk.VBox()
    vbox_right.set_spacing(8)
    hbox.pack_start(vbox_right, False)

    self.lbl_streamingstatus = gtk.Label()
    self.lbl_streamingstatus.set_text("Streaming is stopped.")
    vbox_right.pack_end(self.lbl_streamingstatus, False)
    self.btn_startstop = gtk.ToggleButton("Streaming")
    vbox_right.pack_end(self.btn_startstop, False)

    return hbox

  def build_menu(self):
    # File
    menu_quit = gtk.MenuItem(u'Quit')

    filemenu = gtk.Menu()
    filemenu.append(menu_quit)

    # TOP Menu
    filemenutop = gtk.MenuItem(u'File')
    filemenutop.set_submenu(filemenu)

    menubar = gtk.MenuBar()
    menubar.append(filemenutop)

    return menubar

  def set_values(self):
    self.ent_camera_src.set_text(self.setting.source_device)
    self.ent_camera_fmt.set_text(self.setting.source_format)
    self.ent_camera_width.set_text(self.setting.source_width)
    self.ent_camera_height.set_text(self.setting.source_height)
    self.ent_camera_fps.set_text(self.setting.source_framerate)
    self.ent_sink.set_text(self.setting.sink_device)

    self.setframe_btn.set_filename(self.setting.frame_svgfile)

    self.cmb_text_idx.set_active(0)

  ###############
  #  Callbacks  #
  ###############

  # -- Callback for events

  def on_cmb_text_idx_changed(self, widget):
    idx = widget.get_active()
    try:
      telop = self.setting.telops[idx]
    except IndexError:
      return

    self.cmb_text_halign.set_active(_CCS_HALIGN.get(telop.halignment, 0))
    self.cmb_text_valign.set_active(_CCS_VALIGN.get(telop.valignment, 0))
    self.cmb_text_lalign.set_active(_CCS_HALIGN.get(telop.linealignment, 0))
    self.ent_text_xpad.set_text(str(telop.xpad))
    self.ent_text_ypad.set_text(str(telop.ypad))
    self.chk_text_is_cmdline.set_active(telop.is_cmd)
    self.fontselector.set_font_name(telop.fontdesc)
    self.btn_kill.set_sensitive(False)
    if telop.is_cmd:
      spawn = self.spawnlist[idx]
      if spawn and spawn.is_running():
        self.btn_kill.set_sensitive(True)
    # self.chk_background.set_active(1 if telop.get('shaded-background', False) else 0)
    self.ent_text.get_buffer().set_text(telop.text)

  def on_update(self, widget, *args):
    idx = self.cmb_text_idx.get_active()
    if idx < 0:
      return

    telop = self.setting.telops[idx]

    telop.halignment = self.cmb_text_halign.get_active_text()
    telop.valignment = self.cmb_text_valign.get_active_text()
    telop.linealignment = self.cmb_text_lalign.get_active_text()
    telop.xpad = int(self.ent_text_xpad.get_text())
    telop.ypad = int(self.ent_text_ypad.get_text())
    telop.is_cmd = self.chk_text_is_cmdline.get_active()
    telop.fontdesc = self.fontselector.get_font_name()
    telop.text = self.GetTextViewValue(self.ent_text)

    if self.player:
      self.player.SetTelopAtrribute(idx, telop)
      if telop.is_cmd:
        if self.spawnlist[idx] is None or not self.spawnlist[idx].is_running():
          cmdline = shlex.split(telop.text)
          self.spawnlist[idx] = SpawnStdoutReader(cmdline, self.on_read_from_stdout, (idx,))
          self.spawnlist[idx].run()
      else:
        t = self.DecolateDisplayFont(idx, telop.text)
        self.player.SetTelopText(idx, t)

  def on_camera_startstop(self, widget):
    if widget.get_active():
      self.setting.source_device = self.ent_camera_src.get_text()
      self.setting.source_format = self.ent_camera_fmt.get_text()
      self.setting.source_width = self.ent_camera_width.get_text()
      self.setting.source_height = self.ent_camera_height.get_text()
      self.setting.source_framerate = self.ent_camera_fps.get_text()
      self.setting.sink_device = self.ent_sink.get_text()

      self.player = WebcamComposer(self.setting,
                                   prev_panel=self.movie_window,
                                   on_err_callback=self.on_webcamcomposer_error)
      self.player.Play()
      self.btn_camera_tgl.set_label("Camera Off")
    else:
      for spawn in self.spawnlist:
        if spawn and spawn.is_running():
          spawn.terminate()
      self.player.Null()
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
      self.player.Null()
    return False 

  def on_destroy(self, widget, *args):
    print("OnDestroy is called.")
    gtk.main_quit()

  def on_font_set(self, widget):
    font_name = widget.get_font_name()
    print("Set font is '{0}'.".format(font_name))

  def on_setframe_fileset(self, widget, *args):
    filepath = widget.get_filename()
    if self.player:
      self.player.SetFrameSvgFile(filepath)
    self.setting.frame_svgfile = filepath
    print(filepath)

  # -- External 
  def on_webcamcomposer_error(self, message): 
    """ WebcamComposer Error Callback """
    print("{0}:{1}".format(*message), file=sys.stderr)
    self.btn_camera_tgl.set_active(False)
    self.btn_camera_tgl.set_label("Camera Off")

  def on_read_from_stdout(self, msgtype, text, args):
    """ SpawnStdoutReader read data from stdout callback """
    (idx, ) = args
    if msgtype == SpawnStdoutReader.READY:
      if self.player:
        self.player.SetTelopText(idx, text)
    elif msgtype == SpawnStdoutReader.START:
      self.btn_kill.set_sensitive(True)
    elif msgtype == SpawnStdoutReader.END:
      self.btn_kill.set_sensitive(False)

  ##########
  #  Misc  #
  ##########
  def GetTextViewValue(self, textview):
    buf = textview.get_buffer()
    start, end = buf.get_bounds()
    text = buf.get_text(start, end)
    return text

  def DecolateDisplayFont(self, no, text):
    try:
      p = self.setting.telops[no]
    except IndexError:
      return
    if p.fontdesc != '':
      text = '<span font="{0}">{1}</span>'.format(p.fontdesc, text)
    return text


if __name__ == "__main__":
  setting = WebcamComposerSetting.Load(SETTING_FILENAME)
  cm = WebcamComposerWindow(setting)
  gtk.gdk.threads_init()
  try:
    gtk.main()
  except:
    raise
  finally:
    setting.Save(SETTING_FILENAME)
    print("Saved settings to {0}.".format(SETTING_FILENAME))


