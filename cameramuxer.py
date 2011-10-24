#!/usr/bin/env python
# coding: utf-8

import os
import sys
import codecs
import subprocess
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

class Setting(object):
  def __init__(self):
    self.SRC_DEVICE = '/dev/video0'
    self.SRC_FORMAT = 'video/x-raw-yuv'
    self.SRC_WIDTH = '640'
    self.SRC_HEIGHT = '480'
    self.SRC_FRAMERATE = '30/1'
    self.DST_DEVICE = '/dev/video1'
    self.TITLE = u'<span font-desc="Acknowledge TT BRK Regular 16">CR stealth block.III</span>'


def saveSetting(fn, s):
  with open(fn, "wb") as f:
    pickle.dump(s, f, -1)


def loadSetting(fn):
  try:
    with open(fn, "rb") as f:
      return pickle.load(f)
  except:
    return None
      
setting = loadSetting(_SETTING_FILENAME) or Setting()


class WebcamStudio(object):
  def __init__(self, prev_panel):
    self.prev_panel = prev_panel
    self.player = None

    self.build_player()
    self.setup_elements()
    self.init_bus()


  def build_player(self):
    self.cameracaps = gst.caps_from_string('{0},width={1},height={2},framerate={3}' \
                        .format(setting.SRC_FORMAT, setting.SRC_WIDTH, 
                                setting.SRC_HEIGHT, setting.SRC_FRAMERATE))

    self.player = gst.Pipeline('CameraMuxer')

    self.camerasource = gst.element_factory_make('v4l2src')
    capsfilter = gst.element_factory_make('capsfilter')
    capsfilter.set_property('caps', self.cameracaps)
    videorate = gst.element_factory_make('videorate')
    self.textarea_topleft = gst.element_factory_make('textoverlay')
    self.textarea_topright = gst.element_factory_make('textoverlay')
    self.textarea_bottomleft = gst.element_factory_make('textoverlay')
    self.textarea_bottomright = gst.element_factory_make('textoverlay')
    self.v4l2sink = gst.element_factory_make('v4l2sink', 'v4l2')
    self.avsink = gst.element_factory_make('xvimagesink')

    tee = gst.element_factory_make('tee')
    queue1 = gst.element_factory_make('queue')
    queue2 = gst.element_factory_make('queue')

    self.player.add(self.camerasource, videorate, capsfilter, 
                    self.textarea_topleft, self.textarea_topright,
                    self.textarea_bottomleft, self.textarea_bottomright,
                    self.v4l2sink, self.avsink, tee, queue1, queue2)

    gst.element_link_many(self.camerasource, videorate, capsfilter, 
                          self.textarea_topleft, self.textarea_topright,
                          self.textarea_bottomleft, self.textarea_bottomright,
                          tee)
    gst.element_link_many(tee, queue1, self.v4l2sink)
    gst.element_link_many(tee, queue2, self.avsink)


  def setup_elements(self):
    self.camerasource.set_property('device', '/dev/video0')
    self.v4l2sink.set_property('device', '/dev/video1')

    self.textarea_topleft.set_property("halignment", "left")
    self.textarea_topleft.set_property("valignment", "top")
    self.textarea_topleft.set_property("line-alignment", "left")
    self.textarea_topleft.set_property("xpad", 10)
    self.textarea_topleft.set_property("ypad", 10)

    self.textarea_topright.set_property("halignment", "right")
    self.textarea_topright.set_property("valignment", "top")
    self.textarea_topright.set_property("line-alignment", "right")
    self.textarea_topright.set_property("xpad", 10)
    self.textarea_topright.set_property("ypad", 10)

    self.textarea_bottomleft.set_property("halignment", "left")
    self.textarea_bottomleft.set_property("valignment", "bottom")
    self.textarea_bottomleft.set_property("line-alignment", "left")
    self.textarea_bottomleft.set_property("xpad", 10)
    self.textarea_bottomleft.set_property("ypad", 10)

    self.textarea_bottomright.set_property("halignment", "left")
    self.textarea_bottomright.set_property("valignment", "bottom")
    self.textarea_bottomright.set_property("line-alignment", "right")
    self.textarea_bottomright.set_property("xpad", 10)
    self.textarea_bottomright.set_property("ypad", 10)


  def init_bus(self):
    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect("message", self.on_message)
    bus.connect("sync-message::element", self.on_sync_message)


  def set_state(self, state):
    if self.player:
      self.player.set_state(state)

    
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
    if message_name == "prepare-xwindow-id":
      imagesink = message.src
      imagesink.set_property("force-aspect-ratio", True)
      gtk.gdk.threads_enter()
      imagesink.set_xwindow_id(self.prev_panel.window.xid)
      gtk.gdk.threads_leave()


class StdoutReader(object):
  def __init__(self, executable):
    self.subp = subprocess.Popen(executable, stdout=subprocess.PIPE, close_fds=True)
    glib.io_add_watch(self.subp.stdout, glib.IO_IN | glib.IO_HUP, self._event)

  def _event(self, fd, condition, *argv):
    if self.subp:
      if condition & glib.IO_IN:
        data = fd.read()
        print(data)
        if self.subp.poll():
          self.subp = None
          return False
        return True
    else:
      return False


  def terminate(self):
    if self.subp:
      self.subp.terminate()
      self.subp = None
    


class CameraMuxerWindow(gtk.Window):
  def __init__(self):
    gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
    self.timer = None

    self.build_window()
    self.player = WebcamStudio(self.movie_window)


  # ===
  def build_window(self):
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

    self.movie_window = gtk.DrawingArea()
    vbox_main.pack_start(self.movie_window, True)

    self.btn_camera_tgl = gtk.ToggleButton("Camera Off")
    self.btn_camera_tgl.connect("toggled", self.on_camera_startstop)
    vbox_main.pack_start(self.btn_camera_tgl, False, False)

    vbox_main.pack_start(self.build_telop_box(), False)
    vbox_main.pack_start(self.build_streaming_box(), False)

    self.show_all()


  def build_telop_box(self):
    hbox = gtk.HBox()
    hbox.set_spacing(8)

    vbox_left = gtk.VBox()
    vbox_left.set_spacing(8)
    hbox.pack_start(vbox_left, True)

    self.cmb_select_text_loc = gtk.combo_box_new_text()
    vbox_left.pack_start(self.cmb_select_text_loc, False)

    scroll_text_view = gtk.ScrolledWindow()
    scroll_text_view.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

    self.ent_text = gtk.TextView()
    self.ent_text.get_buffer().set_text(setting.TITLE)

    scroll_text_view.add(self.ent_text)
    vbox_left.pack_start(scroll_text_view, True)

    vbox_right = gtk.VBox()
    hbox.pack_end(vbox_right, False)

    self.btn_update = gtk.Button("Update")
    self.btn_update.connect("clicked", self.on_update)
    vbox_right.pack_start(self.btn_update, False)

    return hbox


  def build_streaming_box(self):
    hbox = gtk.HBox()
    hbox.set_spacing(8)

    vbox_left = gtk.VBox()
    vbox_left.set_spacing(8)
    hbox.pack_start(vbox_left)

    vbox_left.pack_start(gtk.Label("Streaming Command-line"), False)

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
    menu_quit = gtk.MenuItem(u'終了')

    filemenu = gtk.Menu()
    filemenu.append(menu_quit)

    filemenutop = gtk.MenuItem(u'ファイル')
    filemenutop.set_submenu(filemenu)

    menubar = gtk.MenuBar()
    menubar.append(filemenutop)

    return menubar


  def create_timer(self):
    self.destroy_timer()
    self.timer = gobject.timeout_add(500, self.on_interval_timer)


  def destroy_timer(self):
    if self.timer:
      gobject.source_remove(self.timer)

  #---
  def on_interval_timer(self):
    # text = self.readFromFile("~/counter.txt")
    # self.textarea_bottomleft.set_property("text", text)
    return True 


  def on_update(self, widget, *args):
    if self.player is None:
      return 
    self.textarea_topright.set_property("text", self.getTitleText(self.ent_text))


  def on_camera_startstop(self, widget, *args):
    if self.player is None:
      return

    if widget.get_active(): 
      self.create_timer()
      self.player.set_state(gst.STATE_PLAYING)
      self.btn_camera_tgl.set_label("Camera On")
    else:
      self.destroy_timer()
      self.player.set_state(gst.STATE_NULL)
      self.btn_camera_tgl.set_label("Camera Off")


  def on_delete(self, widget, *args):
    print("OnDelete is called.")
    return False 


  def on_destroy(self, widget, *args):
    self.storeItemValues()
    print("OnQuit is called.")
    self.destroy_timer()
    if self.player:
      self.player.set_state(gst.STATE_NULL)
    gtk.main_quit()

  def getTextViewValue(self, textview):
    buf = textview.get_buffer()
    start, end = buf.get_bounds()
    text = buf.get_text(start, end)
    return text
    
  def storeItemValues(self):
    setting.TITLE = self.getTextViewValue(self.ent_text)
    ## TODO

  # ===
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

