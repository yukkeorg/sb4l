#!/usr/bin/env python
# coding: utf-8

import os
import sys
import codecs
import subprocess
import signal
try:
  import cPickle as pickle
except ImportError:
  import pickle

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import glib

import pygst
pygst.require('0.10')
import gst

_SETTING_FILENAME = os.path.expanduser('~/.cameracapturerc')
_SETTING_LATEST_VERSION = '0.1'
_N_TEXTAREA = 4

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

class CameraComposerSetting(object):
  def __init__(self):
    self.SRC_DEVICE = '/dev/video0'
    self.SRC_FORMAT = 'video/x-raw-yuv'
    self.SRC_WIDTH = '640'
    self.SRC_HEIGHT = '480'
    self.SRC_FRAMERATE = '30/1'
    self.DST_DEVICE = '/dev/video1'

    self.TELOP_PROPERTIES = [ {
      'valignment' : 'top',
      'halignment' : 'left',
      'line-alignment' : 'left',
      'xpad' : '0',
      'ypad' : '0',
      'text' : '',
      '_is_cmd' : False
    } for i in xrange(_N_TEXTAREA) ]


class GlobalSetting(object):
  def __init__(self):
    self.version = _SETTING_LATEST_VERSION
    self.cc = CameraComposerSetting()


def saveSetting(fn, s):
  with open(fn, "wb") as f:
    pickle.dump(s, f, -1)


def loadSetting(fn):
  try:
    with open(fn, "rb") as f:
      o = pickle.load(f)
      if o.version == _SETTING_LATEST_VERSION:
        return o
      else:
        print("different version had in RC file.") 
  except:
    pass
  return None
      
setting = loadSetting(_SETTING_FILENAME) or GlobalSetting()


class WebcamComposer(object):
  def __init__(self, settings=None, prev_panel=None):
    self.settings = settings
    self.prev_panel = prev_panel
    self.build_composer()


  def build_composer(self):
    #################
    # Make Elements #
    #################
    self.player = gst.Pipeline('CameraComposer')

    self.camerasource = gst.element_factory_make('v4l2src')
    capsfilter = gst.element_factory_make('capsfilter')
    videorate = gst.element_factory_make('videorate')
    self.textareas = [ gst.element_factory_make('textoverlay') for i in xrange(_N_TEXTAREA) ]
    self.v4l2sink = gst.element_factory_make('v4l2sink', 'v4l2')
    self.avsink = gst.element_factory_make('xvimagesink')

    tee = gst.element_factory_make('tee')
    queue1 = gst.element_factory_make('queue')
    queue2 = gst.element_factory_make('queue')

    self.player.add(self.camerasource, videorate, capsfilter,
                    self.v4l2sink, self.avsink, tee, queue1, queue2, 
                    *self.textareas)
    elements = [self.camerasource, videorate, capsfilter] + self.textareas + [tee]
    gst.element_link_many(*elements)
    gst.element_link_many(tee, queue1, self.v4l2sink)
    gst.element_link_many(tee, queue2, self.avsink)

    ########################
    # Configuring Elements #
    ########################
    self.camerasource.set_property('device', setting.cc.SRC_DEVICE)
    capsfilter.set_property('caps', 
        gst.caps_from_string('{0},width={1},height={2},framerate={3}' \
                      .format(setting.cc.SRC_FORMAT, setting.cc.SRC_WIDTH, 
                              setting.cc.SRC_HEIGHT, setting.cc.SRC_FRAMERATE)))
    self.v4l2sink.set_property('device', setting.cc.DST_DEVICE)

    for textarea in self.textareas:
      textarea.set_property("halignment", "left")  # left, right, center
      textarea.set_property("valignment", "top")   # top, bottom, center
      textarea.set_property("line-alignment", "left")  # left, right
      textarea.set_property("xpad", 10)
      textarea.set_property("ypad", 10)

    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect("message", self.on_message)
    bus.connect("sync-message::element", self.on_sync_message)


  def set_state(self, state):
    self.player.set_state(state)


  def set_textarea_text(self, text, *args, **kw):
    if "no" not in kw:
      return
    try:
      textarea = self.textareas[kw['no']]
    except IndexError:
      return 
    textarea.set_property("text", text)


  def set_textarea_property(self, no, propdict):
    try:
      textarea = self.textareas[no]
    except IndexError:
      return 

    for name, value in propdict.iteritems():
      if name in ("halignment", "valignment", "line-alignment", "xpad", "ypad", "text"):
        textarea.set_property(name, value)


  def get_textarea_property(self, no):
    try:
      textarea = self.textareas[no]
    except IndexError:
      return None

    properties = {}
    for prop in ("halignment", "valignment", "line-alignment", "xpad", "ypad", "text"):
      value = ta.get_property(prop)
      properties[prop] = value
    return (no, properties)


  #########
  # Event #
  #########
  def on_message(self, bus, message):
    type = message.type
    if type == gst.MESSAGE_EOS:
      self.player.set_state(gst.STATE_NULL)
    elif type == gst.MESSAGE_ERROR:
      msg = message.parse_error()
      print(u"{0}\n{1}".format(*msg))


  def on_sync_message(self, bus, message):
    if message.structure is None:
      return
    message_name = message.structure.get_name()
    if self.prev_panel and message_name == "prepare-xwindow-id":
      imagesink = message.src
      imagesink.set_property("force-aspect-ratio", True)
      gtk.gdk.threads_enter()
      imagesink.set_xwindow_id(self.prev_panel.window.xid)
      gtk.gdk.threads_leave()


class StdoutReader(object):
  def __init__(self, cmd_and_args, callback=None, *args, **kw):
    self.cmd_and_args = cmd_and_args
    self.callback = callback
    self.callback_args = args
    self.callback_kw = kw
    self._spawn()


  def _spawn(self):
    self.child = None
    try:
      self.child = subprocess.Popen(self.cmd_and_args, stdout=subprocess.PIPE, close_fds=False)
      glib.io_add_watch(self.child.stdout, glib.IO_IN | glib.IO_HUP, self._event)
    except (OSError, glib.GError), e:
      print(e.message)


  def _event(self, fd, condition):
    if condition & glib.IO_IN:
      text = []
      while True:
        data = fd.readline()
        if data == "":
          break
        text.append(data)
      if self.callback:
        self.callback(text, *self.callback_args, **self.callback_kw)

    if condition & glib.IO_HUP:
      self.child.poll()
      return False
    return True


  def terminate(self):
    if self.child:
      self.child.terminate()


  def is_running(self):
    if self.child:
      return self.child.returncode is None
    else:
      return False


class CameraMuxerWindow(gtk.Window):
  def __init__(self):
    gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
    self.player = None
    self.spawnlist = []
    self.buildWindow()
    self.loadSettings()


  def buildWindow(self):
    self.set_title("Camera Muxer")
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
    vbox_main.pack_start(self.build_telop_box(), False)
    vbox_main.pack_start(self.build_streaming_box(), False)

    self.show_all()


  def build_camera_box(self):
    vbox = gtk.VBox()

    hbox = gtk.HBox()
    hbox.set_spacing(8)
    vbox.pack_start(hbox, False)

    label1 = gtk.Label("Source:")
    hbox.pack_start(label1, False)
    self.ent_camera_src = gtk.Entry()
    self.ent_camera_src.set_size_request(150, -1)
    hbox.pack_start(self.ent_camera_src, False)

    label2 = gtk.Label("Width:")
    hbox.pack_start(label2, False)
    self.ent_camera_width = gtk.Entry()
    self.ent_camera_width.set_size_request(70, -1)
    hbox.pack_start(self.ent_camera_width, False)

    label3 = gtk.Label("Height:")
    hbox.pack_start(label3, False)
    self.ent_camera_height = gtk.Entry()
    self.ent_camera_height.set_size_request(70, -1)
    hbox.pack_start(self.ent_camera_height, False)

    label4 = gtk.Label("FPS:")
    hbox.pack_start(label4, False)
    self.ent_camera_fps= gtk.Entry()
    self.ent_camera_fps.set_size_request(70, -1)
    hbox.pack_start(self.ent_camera_fps, False)

    self.btn_camera_tgl = gtk.ToggleButton("Camera Off")
    self.btn_camera_tgl.connect("toggled", self.on_camera_startstop)
    hbox.pack_start(self.btn_camera_tgl, True)

    self.movie_window = gtk.DrawingArea()
    vbox.pack_start(self.movie_window, True)

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
    for i in xrange(_N_TEXTAREA):
      self.cmb_text_idx.append_text(str(i))

    hbox.pack_start(gtk.Label("H:"), False)
    self.cmb_text_valign = gtk.combo_box_new_text()
    hbox.pack_start(self.cmb_text_valign, True)
    self.cmb_text_valign.append_text("top")
    self.cmb_text_valign.append_text("center")
    self.cmb_text_valign.append_text("bottom")

    hbox.pack_start(gtk.Label("V:"), False)
    self.cmb_text_halign = gtk.combo_box_new_text()
    hbox.pack_start(self.cmb_text_halign, True)
    self.cmb_text_halign.append_text("left")
    self.cmb_text_halign.append_text("center")
    self.cmb_text_halign.append_text("right")

    hbox.pack_start(gtk.Label("L:"), False)
    self.cmb_text_lalign = gtk.combo_box_new_text()
    hbox.pack_start(self.cmb_text_lalign, True)
    self.cmb_text_lalign.append_text("left")
    self.cmb_text_lalign.append_text("center")
    self.cmb_text_lalign.append_text("right")

    hbox.pack_start(gtk.Label("xpad:"), False)
    self.ent_text_xpad = gtk.Entry()
    self.ent_text_xpad.set_size_request(50, -1)
    hbox.pack_start(self.ent_text_xpad, True)

    hbox.pack_start(gtk.Label("ypad:"), False)
    self.ent_text_ypad = gtk.Entry()
    self.ent_text_ypad.set_size_request(50, -1)
    hbox.pack_start(self.ent_text_ypad, True)

    hbox2 = gtk.HBox()
    vbox.pack_start(hbox2, True)

    self.chk_text_is_cmdline = gtk.CheckButton("Command")
    self.chk_text_is_cmdline.set_alignment(0, 0)
    hbox2.pack_start(self.chk_text_is_cmdline, True)

    self.btn_update = gtk.Button("Update")
    self.btn_update.set_property("width-request", 200)
    self.btn_update.connect("clicked", self.on_update)
    hbox2.pack_end(self.btn_update, False)

    scroll_text_view = gtk.ScrolledWindow()
    scroll_text_view.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    self.ent_text = gtk.TextView()
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
    vbox_left.pack_start(label1, False, False)

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
    menu_quit = gtk.MenuItem(u'Quit')

    filemenu = gtk.Menu()
    filemenu.append(menu_quit)

    filemenutop = gtk.MenuItem(u'File')
    filemenutop.set_submenu(filemenu)

    menubar = gtk.MenuBar()
    menubar.append(filemenutop)

    return menubar


  ############
  #  Events  #
  ############
  def on_cmb_text_idx_changed(self, widget):
    idx = widget.get_active()
    try:
      properties = setting.cc.TELOP_PROPERTIES[idx]
    except IndexError:
      return
    if 'halignment' in properties:
      self.cmb_text_halign.set_active(_CCS_HALIGN.get(properties['halignment'], 0))
    if 'valignment' in properties:
      self.cmb_text_valign.set_active(_CCS_VALIGN.get(properties['valignment'], 0))
    if 'line-alignment' in properties:
      self.cmb_text_lalign.set_active(_CCS_HALIGN.get(properties['line-alignment'], 0))
    if 'xpad' in properties:
      self.ent_text_xpad.set_text(properties['xpad'])
    if 'ypad' in properties:
      self.ent_text_ypad.set_text(properties['ypad'])
    if 'text' in properties:
      self.ent_text.get_buffer().set_text(properties['text'])
    if '_is_cmd' in properties:
      self.chk_text_is_cmdline.set_active(properties['_is_cmd'])



  def on_update(self, widget, *args):
    no = self.cmb_text_idx.get_active()
    if no < 0:
      return 
    properties = {}
    properties['halignment'] = self.cmb_text_halign.get_active_text()
    properties['valignment'] = self.cmb_text_valign.get_active_text()
    properties['line-alignment'] = self.cmb_text_lalign.get_active_text()
    properties['_is_cmd'] = self.chk_text_is_cmdline.get_active()
    properties['text'] = self.getTextViewValue(self.ent_text)

    try:
      setting.cc.TELOP_PROPERTIES[no] = properties
    except IndexError:
      return

    if self.player:
      self.player.set_textarea_property(no, properties)
      if properties['_is_cmd']:
        sr = StdoutReader(properties['text'], self.player.set_textarea_text, no=no)
        if sr.child:
          self.spawnlist(sr)


  def on_camera_startstop(self, widget):
    if widget.get_active(): 
      self.player = WebcamComposer(prev_panel=self.movie_window)
      self.player.set_state(gst.STATE_PAUSED)
      self.player.set_state(gst.STATE_PLAYING)
      self.btn_camera_tgl.set_label("Camera On")
    else:
      self.player.set_state(gst.STATE_NULL)
      self.player = None
      self.btn_camera_tgl.set_label("Camera Off")


  def on_delete(self, widget, *args):
    print("OnDelete is called.")
    return False 


  def on_destroy(self, widget, *args):
    print("OnQuit is called.")
    if self.player:
      self.player.set_state(gst.STATE_NULL)
    gtk.main_quit()


  ##########
  #  Misc  #
  ##########
  def getTextViewValue(self, textview):
    buf = textview.get_buffer()
    start, end = buf.get_bounds()
    text = buf.get_text(start, end)
    return text

    
  def loadSettings(self):
    self.ent_camera_src.set_text(setting.cc.SRC_DEVICE)
    self.ent_camera_width.set_text(setting.cc.SRC_WIDTH)
    self.ent_camera_height.set_text(setting.cc.SRC_HEIGHT)
    self.ent_camera_fps.set_text(setting.cc.SRC_FRAMERATE)

    self.cmb_text_idx.set_active(0)

    
  def storeItemValues(self):
    #setting.TITLE = self.getTextViewValue(self.ent_text)
    ## TODO
    pass


  def readFromFile(self, filename):
    filename = os.path.normpath(os.path.expanduser(filename))
    if os.path.exists(filename):
      with codecs.open(filename, 'r', 'utf-8') as f:
        text = f.read()
    else:
        text = u'Not Found'
    return text


if __name__ == "__main__":
  cm = CameraMuxerWindow()
  gtk.gdk.threads_init()
  gtk.main()
  saveSetting(_SETTING_FILENAME, setting)

