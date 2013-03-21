<!-- vim: set noet ts=2 sts=2 sw=2 ft=markdown : -->

Simple Webcam Broadcasting Tool For Linux (sb4l)
===================================================

swbt4l is a very simple webcam broadcasting tools with Shellscript and Python.
This tools works, require other open source softwares. please see below.

Require Applications
--------------------

- ffmpeg N-37669-gf2b20b7 or later (compile with librtmp, libfaac and libx264)
  - https://ffmpeg.org/
- Gstreamer 0.10.32 or later 
  - http://gstreamer.freedesktop.org/
- v4l2loopback (fd822cf) or later 
  - https://github.com/umlaeute/v4l2loopback
- guvcview (recommended latest repository revision)
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

	# ... 1. Setup webcam and desined video stream.
	# ... 2. Setup the broadcast on nicolive, ustream, ...

	$ ./broadcast <rmtpuri> <stream>

License
-------

This is under the 2-clause BSD License.

