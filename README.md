<!-- vim: set noet ts=2 sts=2 sw=2 ft=markdown : -->

Simple Webcam Broadcasting Tool For Linux (swbt4l)
===================================================

__CAUTION : Not working on GStreamer 0.10.36+. determine in the cause of this problem.__

swbt4l is a very simple webcam broadcasting tools with Shellscript and Python.
This tools works, require other open source softwares. please see below.

Require Applications
--------------------

- ffmpeg N-37669-gf2b20b7 or later (compile with librtmp, libfaac and libx264)
  - https://ffmpeg.org/
- v4l2loopback 0.5.0 or later
  - https://github.com/umlaeute/v4l2loopback
- guvcview
  - http://guvcview.sourceforge.net/index.html
- Python 2.7.x without 3.x.x
  - http://www.python.org/

Require Python Modules
----------------------

- gst-python
  - http://gstreamer.freedesktop.org/modules/gst-python.html
- PyGtk
  - http://www.pygtk.org/

Usage
-----

	$ ./prepare
	$ ./broadcast <rmtp uri> <stream>

License
-------

This is under the 2-clause BSD License.

