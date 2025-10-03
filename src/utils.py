
import os
import re
import xml.etree.ElementTree as ET


def _parse_length(value: str) -> float:
	"""
	Converte un valore SVG (es. '100mm', '5cm', '200px', '10in') in millimetri.
	Ritorna None se non riconosciuto.
	"""
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
	elif unit == "px":  # per standard SVG: 96 dpi
		return number * 25.4 / 96.0
	else:
		return None


def get_svg_size(svg_path: str):
	tree = ET.parse(svg_path)
	root = tree.getroot()
	width_attr = root.get("width")
	height_attr = root.get("height")
	viewBox_attr = root.get("viewBox")

	width_mm = _parse_length(width_attr) if width_attr else None
	height_mm = _parse_length(height_attr) if height_attr else None

	return {
		"width_attr": width_attr,
		"height_attr": height_attr,
		"width_mm": width_mm,
		"height_mm": height_mm,
		"viewBox": viewBox_attr,
	}



resources_path = os.path.join(os.path.dirname(__file__), "resources")
