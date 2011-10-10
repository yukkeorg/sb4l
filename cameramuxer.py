#!/usr/bin/env python
# coding: utf-8

import pygtk
pygtk.require('2.0')
import gtk
import gobject

import pygst
pygst.require('0.10')
import gst


SRC_FORMAT = 'video/x-raw-yuv'
SRC_WIDTH = '640'
SRC_HEIGHT = '480'
SRC_FRAMERATE = '30/1'

class Element(object):
  def __init__(self):
    self.name = None
    self.inst = None
    self.order = -1

class CameraMuxerWindow(gtk.Window):
  def __init__(self):
    gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
    self.player = None

    self.build_window()
    self.build_player()
    self.init_bus()

  # ===
  def build_window(self):
    self.set_title("Camera Muxer")
    self.set_default_size(500, 400)
    self.connect("delete-event", self.on_delete)
    self.connect("destroy", self.on_destroy)

    vbox = gtk.VBox()
    vbox.set_border_width(8)
    self.add(vbox)

#    self.movie_window = gtk.DrawingArea()
#    self.add(self.movie_window)
#     vbox.add(self.movie_window)

    self.ent_text = gtk.TextView()
    vbox.pack_start(self.ent_text, True)
    self.btn_update = gtk.Button("Update")
    self.btn_update.connect("clicked", self.on_update)
    vbox.pack_start(self.btn_update, False)
    self.lbl_streamingstatus = gtk.Label()
    self.lbl_streamingstatus.set_text("Streaming is stopped.")
    vbox.pack_start(self.lbl_streamingstatus, False)
    self.btn_startstop = gtk.ToggleButton("Streaming")
    self.btn_startstop.connect("toggled", self.on_startstop)
    vbox.pack_start(self.btn_startstop, False)

    self.show_all()

  #---
  def on_update(self, widget, *args):
    if self.player is None:
      return 
    buf = self.ent_text.get_buffer()
    start, end = buf.get_bounds()
    text = buf.get_text(start, end)
    self.textarea.set_property("text", text)

  def on_startstop(self, widget, *args):
    if self.player is None:
      return

    if widget.get_active():
      self.player.set_state(gst.STATE_PLAYING)
      self.lbl_streamingstatus.set_text("Streraming is started.")
    else:
      self.player.set_state(gst.STATE_NULL)
      self.lbl_streamingstatus.set_text("Streraming is stopped.")


  def on_delete(self, widget, *args):
    print("OnDelete is called.")
    return False 

  def on_destroy(self, widget, *args):
    print("OnQuit is called.")
    if self.player:
      self.player.set_state(gst.STATE_NULL)
    gtk.main_quit()


  # ===
  def build_player(self):
    self.cameracaps = gst.caps_from_string('{0},width={1},height={2},framerate={3}' \
                        .format(SRC_FORMAT, SRC_WIDTH, SRC_HEIGHT, SRC_FRAMERATE))

    self.player = gst.Pipeline('CameraMuxer')

    camerasource = gst.element_factory_make('v4l2src')
    camerasource.set_property('device', '/dev/video0')
    capsfilter = gst.element_factory_make('capsfilter')
    capsfilter.set_property('caps', self.cameracaps)
    videorate = gst.element_factory_make('videorate')
    textarea = gst.element_factory_make('textoverlay')
    outputsink = gst.element_factory_make('v4l2sink')
    outputsink.set_property('device', '/dev/video1')

    self.player.add(camerasource, videorate, capsfilter, textarea, outputsink)
    gst.element_link_many(camerasource, videorate, capsfilter, textarea, outputsink)

    self.textarea = textarea


  def init_bus(self):
    bus = self.player.get_bus()
    bus.add_signal_watch()
    bus.enable_sync_message_emission()
    bus.connect("message", self.on_message)
    bus.connect("sync-message::element", self.on_sync_message)

  #---
  def on_message(self, bus, message):
    type = message.type
    if type == gst.MESSAGE_EOS:
      self.player.set_state(gst.STATE_NULL)

  def on_sync_message(self, bus, message):
    if message.structure is None:
      return

  #---
  def main(self):
    gtk.gdk.threads_init()
    gtk.main()


if __name__ == "__main__":
  cm = CameraMuxerWindow()
  cm.main()

