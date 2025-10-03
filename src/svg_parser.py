import xml.etree.ElementTree as ET
import math
import re
import cairo

class SvgDrawer:
	def __init__(self, filename, yacncc):
		self.filename = filename
		tree = ET.parse(self.filename)
		self.root = tree.getroot()
		self.yacncc = yacncc
		self._width, self._height = self.getSize()

		self.namespace = ''
		if self.root.tag.startswith('{'):
			self.namespace = self.root.tag.split('}')[0] + '}'


	def get_width(self):
		return self._width

	def get_height(self):
		return self._height


	"""
	Converte un valore SVG (es. '100mm', '5cm', '200px', '10in') in millimetri.
	Ritorna None se non riconosciuto.
	"""
	def _parse_length(self, value: str) -> float:
		if value is None:
			return None

		match = re.fullmatch(r"([0-9.]+)([a-z%]*)", value.strip())
		if not match:
			return None
		number, unit = match.groups()
		number = float(number)
		unit = unit.lower()
		if unit in ("mm", ""):
			return number
		elif unit == "cm":
			return number * 10.0
		elif unit == "in":
			return number * 25.4
		elif unit == "pt":  # 1 pt = 1/72 in
			return number * 25.4 / 72.0
		elif unit == "pc":  # 1 pc = 12 pt
			return number * 25.4 / 6.0
		else: # per standard SVG: 96 dpi
			return number * 25.4 / 96.0
		
	def getSize(self):
		width_attr = self.root.get("width")
		height_attr = self.root.get("height")
		viewBox_attr = self.root.get("viewBox")

		width_mm = self._parse_length(width_attr) if width_attr else None
		height_mm = self._parse_length(height_attr) if height_attr else None

		# return {
		# 	"width_attr": width_attr,
		# 	"height_attr": height_attr,
		# 	"width_mm": width_mm,
		# 	"height_mm": height_mm,
		# 	"viewBox": viewBox_attr,
		# }
		return width_mm, height_mm

	def parse_style(self, ctx, style_str):

		def hex_to_rgb(hex_color):
			hex_color = hex_color.lstrip('#')
			r = int(hex_color[0:2], 16) / 255
			g = int(hex_color[2:4], 16) / 255
			b = int(hex_color[4:6], 16) / 255
			return r, g, b
		
		style = {}
		if style_str:
			# Divide per ';' e filtra elementi vuoti
			declarations = [decl.strip() for decl in style_str.split(';') if decl.strip()]
			for decl in declarations:
				if ':' in decl:
					key, value = decl.split(':', 1)
					style[key.strip()] = value.strip()

			if style.get('fill', 'none') != 'none':
				ctx.set_fill_rule (cairo.FILL_RULE_EVEN_ODD if style.get('fill-rule', 'evenodd') else cairo.FILL_RULE_WINDING)
				color_r, color_g, color_b = hex_to_rgb (style.get('fill', '#ffffff'))
				color_a = float (style['fill-opacity']) if style['fill-opacity'] else 1.0
				ctx.set_source_rgba (color_r, color_g, color_b, color_a)

			if style.get('stroke', 'none') != 'none':
				ctx.set_line_join(cairo.LINE_JOIN_ROUND if style.get ('stroke-linejoin', round) == "round" else cairo.LINE_JOIN_MITER)
				ctx.set_line_cap(cairo.LINE_CAP_ROUND if style.get('stroke-linecap', 'round') == "round" else cairo.LINE_CAP_SQUARE)
				color_r, color_g, color_b = hex_to_rgb (style["stroke"])
				color_a = float (style['stroke-opacity']) if style.get("stroke-opacity", '1.0') else 1.0
				ctx.set_source_rgba (color_r, color_g, color_b, color_a)
				ctx.set_line_width(self.yacncc.mm_to_value (float(style.get("stroke-width", '1'))))

		
		return style

	def draw(self, ctx):
		self.draw_node (ctx, self.root)
	
	def draw_node (self, ctx, node):

		ctx.save()
		style = {}
		for elem in node:
			tag = elem.tag
			# toglie il namespace (se presente)
			if tag.startswith(self.namespace):
				tag = tag[len(self.namespace):]

			if tag == 'path':
				if (elem.attrib.get('style')):
					style = self.parse_style (ctx, elem.attrib.get('style'))
				
				d = elem.attrib.get('d')
				if d:
					self._parse_path(ctx, d, style)

			if tag == 'g':
				if (elem.attrib.get('style')):
					style = self.parse_style (ctx, elem.attrib.get('style'))

			elif tag == 'circle':
				cx = float(elem.attrib.get('cx', '0'))
				cy = float(elem.attrib.get('cy', '0'))
				r = float(elem.attrib.get('r', '0'))
				cx, cy = self.yacncc.mm_to_point (cx, -cy + self._height)
				ctx.arc(cx, cy, self.yacncc.mm_to_value (r), 0, 2 * math.pi)
				ctx.fill()
				
			self.draw_node (ctx, elem)
		ctx.restore()

	# def draw(self, ctx):
	# 	self.commands = []

	# 	# Namespace (se presente)
	# 	ns = ''
	# 	if self.root.tag.startswith('{'):
	# 		ns = self.root.tag.split('}')[0] + '}'

	# 	for elem in self.root.iter():
	# 		tag = elem.tag
	# 		if tag.startswith(ns):
	# 			tag = tag[len(ns):]

	# 		if tag == 'path':
	# 			ctx.save()
	# 			if (elem.attrib.get('style')):
	# 				style = self.parse_style (ctx, elem.attrib.get('style'))
	# 			d = elem.attrib.get('d')
	# 			if d:
	# 				self._parse_path(ctx, d, style)
	# 			ctx.restore()

	# 		if tag == 'g':
	# 			style = self.parse_style (ctx, elem.attrib.get('style'))

	# 		elif tag == 'circle':
	# 			cx = float(elem.attrib.get('cx', '0'))
	# 			cy = float(elem.attrib.get('cy', '0'))
	# 			r = float(elem.attrib.get('r', '0'))
	# 			# self.commands.append(f"ctx.arc({cx:.4f}, {cy:.4f}, {r:.4f}, 0, 2 * math.pi)")
	# 			cx, cy = self.yacncc.mm_to_point (cx, -cy + self._height)
	# 			ctx.arc(cx, cy, self.yacncc.mm_to_value (r), 0, 2 * math.pi)
	# 			ctx.fill()

	def _parse_path(self, ctx, d, style):
		# Semplice parser che supporta solo comandi M, L, Z assoluti
		# Esempio: "M 10,10 L 20,20 30,30 Z"
		tokens = re.findall(r'[MLZmlz]|-?\d*\.?\d+', d)
		cursor = 0
		current_command = None

		def get_point():
			nonlocal cursor
			x = float(tokens[cursor])
			y = float(tokens[cursor + 1])
			cursor += 2
			
			return self.yacncc.mm_to_point (x, -y + self._height)
		
		def hex_to_rgb(hex_color):
			hex_color = hex_color.lstrip('#')
			r = int(hex_color[0:2], 16) / 255
			g = int(hex_color[2:4], 16) / 255
			b = int(hex_color[4:6], 16) / 255
			return r, g, b
		

		while cursor < len(tokens):
			token = tokens[cursor]
			if token.upper() in ['M', 'L', 'Z']:
				current_command = token.upper()
				cursor += 1
				if current_command == 'Z':
					ctx.close_path()
					# if style['fill']:
					# 	mode = cairo.FILL_RULE_EVEN_ODD if style['fill-rule']=="evenodd" else cairo.FILL_RULE_WINDING
					# 	color_r, color_g, color_b = hex_to_rgb (style['fill'])
					# 	color_a = float (style['fill-opacity']) if style['fill-opacity'] else 1.0
					# 	ctx.set_source_rgba (color_r, color_g, color_b, color_a)
					# 	ctx.set_fill_rule(mode)
					# 	ctx.fill()
					if style.get('fill', 'none') != 'none':
						ctx.fill()
					if style.get('stroke', 'none') != 'none':
						ctx.stroke()
						
				elif current_command == 'M':
					ctx.new_path()
					x, y = get_point()
					ctx.move_to(x, y)

				elif current_command == 'L':
					ctx.close_path()
					x, y = get_point()
					ctx.line_to(x, y)
					ctx.stroke()

			else:
				# Se non è un comando, si assume coordinate per il punto del path
				x, y = get_point()
				ctx.line_to(x, y)

		# while cursor < len(tokens):
		# 	token = tokens[cursor]
		# 	if token.upper() in ['M', 'L', 'Z']:
		# 		current_command = token.upper()
		# 		cursor += 1
		# 		if current_command == 'Z':
		# 			ctx.close_path()
		# 			if style['fill']:
		# 				fillmode = cairo.FILL_RULE_EVEN_ODD if style['fill-rule']=="evenodd" else cairo.FILL_RULE_WINDING
		# 				fill_color_r, fill_color_g, fill_color_b = hex_to_rgb (style['fill'])
		# 				fill_color_a = float (style['fill-opacity']) if style['fill-opacity'] else 1.0
		# 				ctx.set_source_rgba (fill_color_r, fill_color_g, fill_color_g, fill_color_a)
		# 				ctx.set_fill_rule(fillmode)
		# 				ctx.fill()
		# 		elif current_command == 'M' or current_command == 'L':
		# 			x, y = get_point()
		# 			ctx.move_to(x, y)

		# 	else:
		# 		# Se non è un comando, si assume coordinate per il punto del path
		# 		x, y = get_point()
		# 		ctx.line_to(x, y)


