import colorsys
import io
import math
import threading
import gi
import serial
import time
gi.require_version("Gtk", "3.0")
import serial.tools.list_ports
from gi.repository import Gtk, Gdk, GLib,GdkPixbuf, Gdk, cairo, Pango, PangoCairo
from gi.repository import Rsvg, GdkPixbuf, Gio
import cairosvg

gi.require_versions({
    "Rsvg": "2.0",
    "GdkPixbuf": "2.0"
})

from svgpathtools import Path, Line, CubicBezier, QuadraticBezier, Arc
from shapely.geometry import Polygon, LineString, Point, LinearRing
import xml.etree.ElementTree as ET
# from svg2gcode import SVG2GCode
from pathlib import Path
from svg_parser import SvgDrawer
from utils import *
from config import *

class YACNCC:

	INFO = 1
	ERROR = 2

	def __init__(self):
		self.ser = None
		self.responses = []
		self.last_command = ""
		self.last_response_readed = ""
		self.command_done = False
		self.machine_ready = False
		self.plate_pixbuf = None
		self.scaled_plate_pixbuf = None
		self.origin_x = 0
		self.origin_y = 0
		self.plate_margin_x = 25
		self.plate_margin_y = 25
		self.laser_resolution = 0.6 # default laser resolution (mm)
		# self.pixel_resolution = 1.0 # 1mm = 1px
		# self.pixel_resolution = 0.5 # 2mm = 1px
		self.plate_scale = 2.0 # 1mm = 2px

		self.plate_show_boundaries = True # visualizza i bordi dell'oggetto
		self.svg_drawer = None

		self.old_mouse_x = 0
		self.old_mouse_y = 0

		self.color1_r, self.color1_g, self.color1_b = colorsys.hsv_to_rgb(160/360, 31/100, 45/100)
		self.color2_r, self.color2_g, self.color2_b = colorsys.hsv_to_rgb(160/360, 11/100, 93/100)
		self.color_cursor_r, self.color_cursor_g, self.color_cursor_b = colorsys.hsv_to_rgb(79/360, 50/100, 75/100)


		self.builder = Gtk.Builder()
		self.builder.add_from_file(resources_path + "/main-form.glade")

		self.window = self.builder.get_object("main_window")
		self.window.connect("destroy", Gtk.main_quit)

		self.btn_connect = self.builder.get_object("btn_connect")

		self.drawing_preview = self.builder.get_object("drawing_preview")

		self.btn_send_command = self.builder.get_object("btn_send_command")
		self.txt_command = self.builder.get_object("txt_command")

		self.img_jog = GdkPixbuf.Pixbuf.new_from_file(resources_path + "/jog.png")



		# power
		self.val_power = self.builder.get_object("val_power")

		# speed
		self.val_speed = self.builder.get_object("val_speed")

		# serial
		self.val_baud = self.builder.get_object("val_baud")
		self.combo_ports = self.builder.get_object("combo_ports")
		self.refresh_ports(None)

		self.serial_log = self.builder.get_object("serial_log")
		self.serial_log_buffer = self.serial_log.get_buffer()
		self.error_tag = self.serial_log_buffer.create_tag("error", foreground="red")
		style_context = self.serial_log.get_style_context()
		color = style_context.get_color(Gtk.StateFlags.NORMAL)
		self.info_tag = self.serial_log_buffer.create_tag("info", foreground=color)
		# self.info_tag = self.serial_log_buffer.create_tag("info", foreground="black")

		# collega segnali
		self.builder.connect_signals(self)

		self.window.show_all()


	def serialLog(self, msg, level = INFO):
		end_iter = self.serial_log_buffer.get_end_iter()
		# if not end_iter:
		# 	return


		if level == YACNCC.ERROR:
			self.serial_log_buffer.insert_with_tags(end_iter, msg+"\n", self.error_tag)
		else:
			self.serial_log_buffer.insert_with_tags(end_iter, msg+"\n", self.info_tag)
 		# Scroll automatico in basso
		mark = self.serial_log_buffer.create_mark("end_mark", self.serial_log_buffer.get_end_iter(), False)
		# if not end_iter:
		# 	return
		self.serial_log.scroll_to_mark(mark, 0.0, True, 0.5, 1.0)
		return False

	"""
		serial thread
	"""
	def serial_thread(self):
		print ("Serial thread running")
		# delay iniziale per reset
		time.sleep(2)
		self.ser.reset_input_buffer()

		# soft-reset
		self.ser.write(b"\x18")

		# wait for reset-ack
		reset_ack = False
		while not reset_ack and self.running and self.ser.is_open:
			if self.ser.in_waiting > 0:
				try:
					line = self.ser.readline().decode("utf-8", errors="ignore").strip()
					print ("::: ", line)
					if line[:4] == "Grbl":
						reset_ack = True
				except Exception as e:
					GLib.idle_add (self.serialLog, f"{e}", YACNCC.ERROR)

			time.sleep(0.05)  # cpu yeld
		GLib.idle_add (self.onMachineReady)

		# reading responses
		while self.running and self.ser.is_open:
			if self.ser.in_waiting > 0:
				try:
					line = self.ser.readline().decode("utf-8", errors="ignore").strip()
					# line = self.ser.readline()
					print ("readed: ", line)
					if line:
						if line == "ok":
							self.command_done = True;
							GLib.idle_add (self.onCommandSuccess)
						elif line[:6] == "error:":
							self.command_done = True
							GLib.idle_add (self.onCommandError, line[6:])
						else:
							self.responses.append (line)
							self.last_response_readed = line
							GLib.idle_add (self.serialLog, ">> " + line)

				except Exception as e:
					GLib.idle_add (self.serialLog, f"** ERROR: {e}", YACNCC.ERROR)
			time.sleep(0.05) # cpu yeld
		print ("Serial thread ENDED")

	def close_serial(self):
		if self.ser and self.ser.is_open:
			self.ser.close()


	def refresh_ports(self, widget):
		self.combo_ports.remove_all()
		ports = serial.tools.list_ports.comports()
		for port in ports:
			self.combo_ports.append_text(port.device)
		if ports:
			self.combo_ports.set_active(0)

	def get_selected_port(self):
		return self.combo_ports.get_active_text()

	def send_command(self, command: str):
		if not self.machine_ready:
			return

		self.responses.clear()
		self.last_response_readed = ""
		self.command_done = False
		self.last_command = command
		if self.ser and self.ser.is_open:
			print ("Sending: " + command)
			try:
				# self.serialLog("<< " + command)
				self.ser.write((command + "\n").encode("utf-8"))
				# self.ser.write(command + "\r\n")
			except Exception as e:
				self.serialLog(f"Error: {e}", YACNCC.ERROR)

	def send_command_wait_ok(self, command: str, timeout:int= 2):
		self.send_command (command)
		start = time.time()
		while (not self.command_done) and (time.time() - start < timeout):
			time.sleep(0.05) # cpu yeld
		# print ("Response ", self.responses)
		if not self.command_done:
			self.serialLog(f"Command {command} timeouted", YACNCC.ERROR)
			return False
		return True

	def onConnect(self, button):
		if self.ser and self.ser.is_open:
			self.close_serial()
			self.btn_connect.set_label ("Connect")
			self.btn_send_command.set_sensitive(False)
			# self.txt_command.set_sensitive(False)
		else:
			port = self.get_selected_port()
			baud = self.val_baud.get_active_text()
			try:
				# self.ser = serial.Serial(port, 115200, timeout=1)
				self.ser = serial.Serial(port, baud, timeout=1)
				self.running = True
				threading.Thread(target=self.serial_thread, daemon=True).start()
				self.serialLog(f"✅ Connected to {port} {baud}baud  8N1")

				self.btn_connect.set_label ("Disconnect")
				self.btn_send_command.set_sensitive(True)
				# self.txt_command.set_sensitive(True)


				# GRBL supporta comandi come:
				# $$ → mostra configurazione corrente.
				# $X → sblocca se è in stato di alarm.
				# G21 → unità in millimetri.
				# G90 → coordinate assolute.
				# G0 X0 Y0 → muove all’origine.				



			except Exception as e:
				self.serialLog(f"Error: {e}", YACNCC.INFO)
		
		return True


	def onChangeScale(self):
		return

		if (not self.plate_pixbuf):
			return
		
		# Scale a pixbuf to new dimensions
		new_x = self.mm_to_x (self.plate_image_width_mm)
		new_y = self.mm_to_y (self.plate_image_height_mm)

		new_x = int(self.plate_pixbuf.get_width() * self.plate_scale * self.laser_resolution)
		new_y = int(self.plate_pixbuf.get_height() * self.plate_scale * self.laser_resolution)

		# print (f"Scalo {self.plate_image_width_mm}mm x {self.plate_image_height_mm}mm to {new_x}pix x {new_x}pix")
		print (f"Scalo {self.plate_pixbuf.get_width()}x{self.plate_pixbuf.get_height()}px to {new_x}x{new_x}px")
		self.scaled_plate_pixbuf = self.plate_pixbuf.scale_simple(
			new_x,
			new_y,
			# GdkPixbuf.InterpType.BILINEAR
			GdkPixbuf.InterpType.NEAREST
		)

	def onPlateScroll(self, widget, event):
		if event.direction == Gdk.ScrollDirection.UP:
			if self.plate_scale < 1500:
				self.plate_scale *= 1.3
			self.onChangeScale ()
			self.drawing_preview.queue_draw()
			print("Scroll UP", self.plate_scale)
		elif event.direction == Gdk.ScrollDirection.DOWN:
			if self.plate_scale > 0.3:
				self.plate_scale /= 1.3
			self.onChangeScale ()
			self.drawing_preview.queue_draw()
			print("Scroll DOWN", self.plate_scale)
		elif event.direction == Gdk.ScrollDirection.LEFT:
			print("Scroll LEFT")
		elif event.direction == Gdk.ScrollDirection.RIGHT:
			print("Scroll RIGHT")
		else:
			print("Altro evento scroll")
		return True   # True = evento gestito, False = propaga oltre		
		

	def onCommand(self, entry):
		self.send_command (entry.get_text())
		self.txt_command.set_text ("")
		return False

	def onSendCommand(self, entry):
		self.onCommand (self.txt_command)
		return False

	def onSetZeroPoint(self, button):
		self.send_command("G92 X0 Y0 Z0")
		return False


	def get_pixel_rgb(self, pixbuf, x, y):
		pixels = pixbuf.get_pixels()
		rowstride = pixbuf.get_rowstride()
		n_channels = pixbuf.get_n_channels()

		# Calcola offset del pixel
		offset = y * rowstride + x * n_channels

		r = pixels[offset]
		g = pixels[offset + 1]
		b = pixels[offset + 2]
		# A = pixels[offset + 3]  ← se serve l'alpha

		return r, g, b
	
	def onJogMouseDown(self, widget, event):
		if not self.machine_ready:
			return
		
		width = widget.get_allocated_width()
		height = widget.get_allocated_height()
		center_x = width / 2
		center_y = height / 2

		dx = event.x - center_x
		dy = center_y - event.y  # Inverti Y per avere 0° in alto

		distance = math.hypot(dx, dy) - 30

		
		r,g,b = self.get_pixel_rgb (self.img_jog, int(event.x + width), int(event.y))
		if r != 255:
			mm = 10
			mm = 50 * distance / 60
			sector = int(r / 10)
			speed = int(self.val_speed.get_value())
			# speed = 6000 * distance / 60

			print(f"sector:{sector}")
			if sector == 1:
				# self.send_command_wait_ok (f"G91G1Y+{mm}F{speed}")
				self.send_command_wait_ok (f"$J=G91 Y+{mm}F{speed}")
			elif sector == 2:
				self.send_command_wait_ok (f"$J=G91 X+{mm}Y+{mm}F{speed}")
			elif sector == 3:
				self.send_command_wait_ok (f"$J=G91 X+{mm}F{speed}")
			elif sector == 4:
				self.send_command_wait_ok (f"$J=G91 X+{mm}Y-{mm}F{speed}")
			elif sector == 5:
				self.send_command_wait_ok (f"$J=G91 Y-{mm}F{speed}")
			elif sector == 6:
				self.send_command_wait_ok (f"$J=G91 Y-{mm}X-{mm}F{speed}")
			elif sector == 7:
				self.send_command_wait_ok (f"$J=G91 X-{mm}F{speed}")
			elif sector == 8:
				self.send_command_wait_ok (f"$J=G91 X-{mm}Y+{mm}F{speed}")
			elif sector == 9:
				# self.send_command("!")
				self.ser.write(b"\x85")
		return False


	def onJogKeyPress(self, widget, event):

		# print("🖱️ Mouse UP: tasto", event.button, event.x, event.y)
		keyval = event.keyval
		keyname = Gdk.keyval_name(keyval)
		print(f"Hai premuto: {keyname}")
		return False

	def onJogMouseUp(self, widget, event):
		# print("🖱️ Mouse UP: tasto", event.button, event.x, event.y)
		return False

	def onMachineReady(self):
		print("Machine ready")
		# self.send_command("G21") # set in mm
		self.machine_ready = True
		self.serialLog(f"✅ Machine ready")
		self.send_command_wait_ok("G21") # set in mm
		return False

	def onJogDraw(self, widget, cr):
		Gdk.cairo_set_source_pixbuf(cr, self.img_jog, 0, 0)
		cr.paint()
		return False



	def onCommandSuccess(self):
		# self.serialLog (f"✔️ Comando {self.last_command} eseguito con successo")
		self.serialLog (f"✔️ {self.last_command}")
		return False

	def onCommandError(self, error):
		self.serialLog(f"⛔ Error: {error}", YACNCC.ERROR)
		return False

	def onSoftReset(self, error):
		self.ser.write(b"\x18")
		return False
	
	def draw_rounded_rectangle(self, cr, x, y, width, height, radius):
		"""
		Disegna un rettangolo con angoli arrotondati su un Cairo context.
		- cr: Cairo context
		- x, y: coordinate angolo superiore sinistro
		- width, height: dimensioni
		- radius: raggio degli angoli stondati
		"""
		r = radius
		if r > min(width, height) / 2:
				r = min(width, height) / 2  # limita il raggio per non sforare

		cr.new_sub_path()

		# Angolo in alto a sinistra
		cr.arc(x + r, y + r, r, 3.14159, 3.14159 * 1.5)

		# Lato superiore
		cr.line_to(x + width - r, y)

		# Angolo in alto a destra
		cr.arc(x + width - r, y + r, r, 3.14159 * 1.5, 0)

		# Lato destro
		cr.line_to(x + width, y + height - r)

		# Angolo in basso a destra
		cr.arc(x + width - r, y + height - r, r, 0, 3.14159 * 0.5)

		# Lato inferiore
		cr.line_to(x + r, y + height)

		# Angolo in basso a sinistra
		cr.arc(x + r, y + height - r, r, 3.14159 * 0.5, 3.14159)

		cr.close_path()
		cr.fill_preserve()

		return False



	def onLoadSVG(self, menu):
		dialog = Gtk.FileChooserDialog(
			title="Select SVG file",
			parent=None,
			action=Gtk.FileChooserAction.OPEN
		)
		dialog.add_buttons(
			Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
			Gtk.STOCK_OPEN, Gtk.ResponseType.OK
		)

		# 🌟 Filtro: Solo file SVG
		svg_filter = Gtk.FileFilter()
		svg_filter.set_name("File SVG (*.svg)")
		svg_filter.add_pattern("*.svg")
		dialog.add_filter(svg_filter)

		# 🌟 Filtro: Tutti i file (*.*)
		all_filter = Gtk.FileFilter()
		all_filter.set_name("Tutti i file (*.*)")
		all_filter.add_pattern("*")
		dialog.add_filter(all_filter)

		# Mostra il dialogo
		response = dialog.run()
		filename = dialog.get_filename()
		dialog.destroy()

		if response == Gtk.ResponseType.OK:
			self.loadSVG (filename)
			self.onChangeScale()





	"""
	Load SVG
	"""
	def loadSVG(self, filename):
		config = get_config()
		svg_size = get_svg_size (filename)

		# Dimensioni in millimetri
		width_mm = svg_size["width_mm"]
		height_mm = svg_size["height_mm"]
		# resolution = config["machine"]["resolution"]
		self.laser_resolution = config["machine"]["resolution"]
		
		self.plate_image_width_mm = width_mm
		self.plate_image_height_mm = height_mm

		# Calcola dimensioni renderizzate
		width_px = int(round(width_mm / self.laser_resolution))
		height_px = int(round(height_mm / self.laser_resolution))

		print (f"SVG size: {width_mm} mm x {height_mm} mm @ {self.laser_resolution} mm laser-point-size \nImage size: {width_px}x{height_px} px")

		self.svg_drawer = SvgDrawer (filename, self)


		# tmpfile=tempfile.gettempdir()+"/yacncc.tmp.png"
		# cairosvg.svg2png(
		# 	url=filename,
		# 	write_to=tmpfile,
		# 	output_width=width_px,
		# 	output_height=height_px
		# )
		# # Carica PNG in Pixbuf
		# self.plate_pixbuf = GdkPixbuf.Pixbuf.new_from_file(tmpfile)
		# os.remove(tmpfile)

		# output = io.BytesIO()
		# cairosvg.svg2png(url=filename, write_to=output, output_width=width_px, output_height=height_px)
		# png_bytes = output.getvalue()
		# loader = GdkPixbuf.PixbufLoader.new_with_type('png')
		# loader.write(png_bytes)
		# loader.close()
		# self.plate_pixbuf = loader.get_pixbuf()

		# # calcola bordi dell'immagine
		# n_channels = self.plate_pixbuf.get_n_channels()  # 3 = RGB, 4 = RGBA
		# rowstride = self.plate_pixbuf.get_rowstride()
		# pixels = self.plate_pixbuf.get_pixels()
		# self.plate_boundaries = [666666,666666,  0,0]
		# for x in range(self.plate_pixbuf.get_width()):
		# 	for y in range(self.plate_pixbuf.get_height()):
		# 		offset = y * rowstride + x * n_channels
		# 		r = pixels[offset]
		# 		g = pixels[offset + 1]
		# 		b = pixels[offset + 2]
		# 		a = pixels[offset + 3] if n_channels == 4 else 255




	def mm_to_x_norm (self, mm):
		return mm * self.plate_scale - self.origin_x + self.plate_margin_x + self.plate_width / 2

	def mm_to_y_norm (self, mm):
		return -mm * self.plate_scale - self.origin_y + self.plate_height / 2

	def mm_to_x (self, mm):
		return mm * self.plate_scale - self.origin_x

	def mm_to_y (self, mm):
		return -(mm * self.plate_scale) - self.origin_y

	def pix_to_mm (self, pix):
		return pix / self.plate_scale

	def mm_to_point (self, mmx, mmy):
		return self.mm_to_x_norm (mmx), self.mm_to_y_norm (mmy)

	def mm_to_value (self, mm):
		return mm * self.plate_scale


	"""
	draw Axes
	"""
	def drawAxes(self, cr, alpha = 0.8):
		w = self.plate_width
		h = self.plate_height

		cr.new_path()
		cr.set_source_rgba(self.color2_r, self.color2_g, self.color2_b, alpha)

		cr.set_line_width(1)
		cr.move_to(self.plate_margin_x, self.mm_to_y_norm (0));	cr.line_to (w, self.mm_to_y_norm (0))
		cr.move_to(self.mm_to_x_norm (0), 0);	cr.line_to (self.mm_to_x_norm (0), h -  self.plate_margin_y)
		cr.stroke()

	"""
	draw  Grid
	"""
	def drawGrid(self, cr, step = 10, alpha = 0.1):
		w = self.plate_width
		h = self.plate_height

		cr.new_path()
		cr.set_line_width(1)
		cr.set_source_rgba(self.color2_r, self.color2_g, self.color2_b, alpha)
		mm = 0;
		while True:
			y = self.mm_to_y_norm (mm)
			if y < 0:
				break
			cr.move_to(0+self.plate_margin_x, y)
			cr.line_to (w, y)
			cr.stroke()
			mm += step


		mm = 0
		while True:
			y = self.mm_to_y_norm (mm)
			if y > h - self.plate_margin_y:
				break
			cr.move_to(0+self.plate_margin_x, y)
			cr.line_to (w, y)
			cr.stroke()
			mm -= step

		mm = 0
		while True:
			x = self.mm_to_x_norm (mm)
			if x > w:
				break
			cr.move_to(x+self.plate_margin_x, 0)
			cr.line_to (x+self.plate_margin_x, h - self.plate_margin_y)
			cr.stroke()
			mm += step

		mm = 0
		while True:
			x = self.mm_to_x_norm (mm)
			if x < 0:
				break
			cr.move_to(x+self.plate_margin_x, 0)
			cr.line_to (x+self.plate_margin_x, h - self.plate_margin_y)
			cr.stroke()
			mm -= step

		return 

	"""
	draw mouse position
	"""
	def drawMousePosition(self, cr):
		radius = 10
		w = self.plate_width
		h = self.plate_height


		cr.set_source_rgb(self.color_cursor_r, self.color_cursor_g, self.color_cursor_b)


		cr.new_path()
		cr.arc(self.old_mouse_x, self.old_mouse_y, radius, 0, 2 * 3.14159)
		# cr.close_path()
		# cr.stroke()
		# cr.new_sub_path()
		# # cr.new_path()

		# Y axis
		cr.move_to(self.old_mouse_x, 0)
		cr.line_to(self.old_mouse_x, self.old_mouse_y - radius)
		cr.move_to(self.old_mouse_x, self.old_mouse_y + radius)
		cr.line_to(self.old_mouse_x, h)

		# X axis
		cr.move_to(0, self.old_mouse_y)
		cr.line_to(self.old_mouse_x - radius, self.old_mouse_y)
		cr.move_to(self.old_mouse_x + radius, self.old_mouse_y)
		cr.line_to(w, self.old_mouse_y)
		cr.stroke()
		return
	
	"""
	draw axes Legend
	"""
	def drawAxesLegend(self, cr,  step = 10.0, alpha = 1.0):
		w = self.plate_width
		h = self.plate_height
		# Crea layout Pango
		layout = PangoCairo.create_layout(cr)
		layout.set_alignment(Pango.Alignment.RIGHT)
		layout.set_width (20)
		font_desc = Pango.FontDescription("Bebas Neue 9")
		layout.set_font_description(font_desc)
		cr.set_source_rgb(self.color2_r, self.color2_g, self.color2_b)


		cr.set_line_width(1)
		cr.set_source_rgba(self.color2_r, self.color2_g, self.color2_b, alpha)

		# Y axis
		mm = 0;
		while True:
			i = self.mm_to_y_norm (mm)
			if i < 0:
				break
			cr.move_to(20, i - 7)
			layout.set_text(f"+{mm}", -1)
			PangoCairo.show_layout(cr, layout)
			mm += step

		mm = -step;
		while True:
			i = self.mm_to_y_norm (mm)
			if i > h - self.plate_margin_y :
				break
			cr.move_to(20, i - 7)
			layout.set_text(f"{mm}", -1)
			PangoCairo.show_layout(cr, layout)
			mm -= step

		# X axis
		layout.set_alignment(Pango.Alignment.CENTER)
		mm = 0;
		while True:
			i = self.mm_to_x_norm (mm)
			if i > w - self.plate_margin_x :
				break
			cr.move_to(i , h - self.plate_margin_y)
			layout.set_text(f"+{mm}", -1)
			PangoCairo.show_layout(cr, layout)
			mm += step

		mm = -step;
		while True:
			i = self.mm_to_x_norm (mm)
			if i < 0:
				break
			cr.move_to(i , h - self.plate_margin_y)
			layout.set_text(f"{mm}", -1)
			PangoCairo.show_layout(cr, layout)
			mm -= step

		return 

	def onPlateEnter(self, widget, event):
		display = Gdk.Display.get_default()
		cursor = Gdk.Cursor.new_from_name(display, "none")  # "none" = invisibile
		widget.get_window().set_cursor(cursor)		

	def onPlateLeave(self, widget, event):
		widget.get_window().set_cursor(None)


	def onPlateMouseMove(self, widget, event):
		if event.state & Gdk.ModifierType.BUTTON1_MASK:
			dx = event.x - self.old_mouse_x
			dy = event.y - self.old_mouse_y
			self.origin_x -= dx
			self.origin_y -= dy
	
		self.old_mouse_x = event.x
		self.old_mouse_y = event.y
		self.drawing_preview.queue_draw()
		return 
	
	"""
	draw  Plate
	"""
	def onPlateDraw(self, widget, cr):
		self.plate_width = width = widget.get_allocated_width()
		self.plate_height = height = widget.get_allocated_height()
		center_x = width / 2
		center_y = height / 2


		cr.set_source_rgb(self.color1_r, self.color1_g, self.color1_b)
		cr.rectangle(0, 0, width, height)
		cr.fill()

		self.drawAxes(cr)
		if (self.plate_scale > 1):
			self.drawGrid(cr)
			if (self.plate_scale > 10):
				self.drawGrid(cr, 1, 0.08)
			if (self.plate_scale > 130):
				self.drawGrid(cr, 0.5, 0.05)
			if (self.plate_scale > 300):
				self.drawGrid(cr, 0.1, 0.04)
		else:
			self.drawGrid(cr, 50)

		if (self.plate_scale <= 1.5):
			self.drawAxesLegend (cr, 50)
		else:
			if (self.plate_scale > 1400):
				self.drawAxesLegend (cr, 0.01)
			if (self.plate_scale > 300):
				self.drawAxesLegend (cr, 0.1)
			if (self.plate_scale > 130):
				self.drawAxesLegend (cr, 0.5)
			elif (self.plate_scale > 10):
				self.drawAxesLegend (cr, 1)
			else:
				self.drawAxesLegend (cr, 10)


		# if self.plate_pixbuf:
		# 	cr.save()
		# 	scale = self.plate_scale * self.laser_resolution
		# 	cr.scale(scale, scale)
		# 	Gdk.cairo_set_source_pixbuf(cr, self.plate_pixbuf, self.mm_to_x_norm (0) / scale, self.mm_to_y_norm (0) / scale - self.plate_pixbuf.get_height())
		# 	cr.paint()
		# 	cr.restore()

		# 	if self.plate_show_boundaries:
		# 		a = 10

		# if self.scaled_plate_pixbuf:
		# 	Gdk.cairo_set_source_pixbuf(cr, self.scaled_plate_pixbuf, self.mm_to_x_norm (0), self.mm_to_y_norm (0) - self.scaled_plate_pixbuf.get_height())
		# 	cr.paint()

		if self.svg_drawer:
			self.svg_drawer.draw (cr)

		self.drawMousePosition (cr)

