#!/usr/bin/env python3
import gi
import os
import ctypes

from yacncc import YACNCC
gi.require_version("Gtk", "3.0")
import serial.tools.list_ports
from gi.repository import Gtk, Gdk, GLib,GdkPixbuf, Gdk, cairo, Pango, PangoCairo
from gi.repository import Rsvg, GdkPixbuf, Gio
import cairosvg

gi.require_versions({
    "Rsvg": "2.0",
    "GdkPixbuf": "2.0"
})

import json
import os
from utils import *
from config import *


def load_theme(theme_path):
	provider = Gtk.CssProvider()
	css_file = os.path.join(theme_path, "gtk.css")

	if os.path.exists(css_file):
		provider.load_from_path(css_file)
		Gtk.StyleContext.add_provider_for_screen(
			Gdk.Screen.get_default(),
			provider,
			Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
		)
	else:
		print("⚠️ CSS not found:", css_file)

def load_font_from_file(font_path):
	"""Carica un font TTF/OTF in fontconfig senza installarlo globalmente"""
	fontconfig = ctypes.CDLL("libfontconfig.so.1")
	fontconfig.FcInit()
	fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
	config = fontconfig.FcInitLoadConfigAndFonts()
	font_path_bytes = font_path.encode("utf-8")
	result = fontconfig.FcConfigAppFontAddFile(config, font_path_bytes)
	if result == 0:
		print("⚠️ Font non caricato:", font_path)
	else:
		print("✅ Font caricato:", font_path)



load_config()
config = get_config()
print ("config", config)
load_theme(resources_path +  "/theme")
load_font_from_file (resources_path+ "/BebasNeue-Regular.ttf")
# avvia l'app
app = YACNCC()
Gtk.main()
