import math
from svgpathtools import svg2paths2
from shapely.geometry import Polygon, LineString, Point, MultiLineString
from shapely.ops import unary_union
import xml.etree.ElementTree as ET

class SVG2GCode:
    def __init__(self, svg_file):
        self.svg_file = svg_file
        self.polygons = self._parse_svg()
        self.union_poly = unary_union(self.polygons) if self.polygons else None

    # -------------------- SVG parsing --------------------
    def _segment_to_points(self, seg, n=30):
        return [(seg.point(i/n).real, seg.point(i/n).imag) for i in range(n+1)]

    def _path_to_polygon(self, path, samples_per_seg=40):
        pts = []
        for seg in path:
            pts.extend(self._segment_to_points(seg, n=samples_per_seg)[:-1])
        if len(pts) < 3:
            return None
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        poly = Polygon(pts)
        return poly.buffer(0) if not poly.is_valid else poly

    def _parse_svg(self):
        polys = []
        paths, attributes, svg_att = svg2paths2(self.svg_file)
        for p in paths:
            poly = self._path_to_polygon(p)
            if poly and poly.area > 1e-9:
                polys.append(poly)

        tree = ET.parse(self.svg_file)
        root = tree.getroot()

        # rect
        for elem in root.findall('.//{*}rect'):
            x = float(elem.attrib.get('x', '0'))
            y = float(elem.attrib.get('y', '0'))
            w = float(elem.attrib.get('width', '0'))
            h = float(elem.attrib.get('height', '0'))
            polys.append(Polygon([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]))

        # circle
        for elem in root.findall('.//{*}circle'):
            cx = float(elem.attrib.get('cx','0'))
            cy = float(elem.attrib.get('cy','0'))
            r = float(elem.attrib.get('r','0'))
            polys.append(Point(cx,cy).buffer(r, resolution=64))

        return polys

    # -------------------- Fill generators --------------------
    def _generate_hatch_lines(self, polygon, angle_deg=0.0, spacing=1.0):
        minx, miny, maxx, maxy = polygon.bounds
        angle = math.radians(angle_deg)
        dx, dy = math.cos(angle), math.sin(angle)
        ox, oy = -dy, dx

        corners = [(minx,miny),(minx,maxy),(maxx,miny),(maxx,maxy)]
        projections = [cx*ox + cy*oy for (cx,cy) in corners]
        lo, hi = min(projections), max(projections)

        segments = []
        for i in range(int((hi-lo)/spacing)+2):
            s = lo + i*spacing
            cx, cy = s*ox, s*oy
            line = LineString([(cx-dx*1e4, cy-dy*1e4), (cx+dx*1e4, cy+dy*1e4)])
            inter = polygon.intersection(line)
            if inter.is_empty:
                continue
            if isinstance(inter, LineString):
                segments.append(inter)
            elif isinstance(inter, MultiLineString):
                for seg in inter.geoms:
                    if seg.length > 1e-6:
                        segments.append(seg)
        return segments

    def _generate_concentric_offsets(self, polygon, step=0.5, tool_diameter=0.0):
        results = []
        dist = tool_diameter/2.0
        current = polygon.buffer(-dist)
        while current and current.area > 1e-6:
            if isinstance(current, Polygon):
                results.append(LineString(current.exterior.coords))
            else:
                for p in current:
                    results.append(LineString(p.exterior.coords))
            dist += step
            current = polygon.buffer(-dist)
        return results

    # -------------------- G-code generation --------------------
    def _gcode_header(self, z_safe=5.0, spindle_rpm=10000):
        return f"""%
G21
G90
G0 Z{z_safe:.3f}
M3 S{int(spindle_rpm)}
"""

    def _gcode_footer(self):
        return """M5
G0 Z5.000
G0 X0 Y0
M2
%"""

    def _segments_to_gcode(self, segments, z_cut=-1.0, z_safe=5.0, feed=600, travel_feed=2000):
        lines = [self._gcode_header(z_safe=z_safe)]
        for seg in segments:
            coords = list(seg.coords)
            sx, sy = coords[0]
            lines.append(f"G0 X{sx:.3f} Y{sy:.3f} F{travel_feed}")
            lines.append(f"G1 Z{z_cut:.3f} F{feed}")
            for (x,y) in coords[1:]:
                lines.append(f"G1 X{x:.3f} Y{y:.3f} F{feed}")
            lines.append(f"G0 Z{z_safe:.3f}")
        lines.append(self._gcode_footer())
        return "\n".join(lines)

    # -------------------- Public API --------------------
    def to_gcode(self, out_file="out.gcode", method="hatch", hatch_spacing=1.0,
                 hatch_angle=0.0, offset_step=0.5, tool_diameter=0.0,
                 z_cut=-1.0, z_safe=5.0, feed=600, travel_feed=2000):

        if not self.union_poly or self.union_poly.is_empty:
            raise RuntimeError("Nessuna geometria valida trovata.")

        segments = []
        if method == "hatch":
            polys = self.union_poly.geoms if hasattr(self.union_poly, 'geoms') else [self.union_poly]
            for p in polys:
                segments.extend(self._generate_hatch_lines(p, angle_deg=hatch_angle, spacing=hatch_spacing))
        elif method == "concentric":
            polys = self.union_poly.geoms if hasattr(self.union_poly, 'geoms') else [self.union_poly]
            for p in polys:
                segments.extend(self._generate_concentric_offsets(p, step=offset_step, tool_diameter=tool_diameter))
        else:
            raise ValueError("Metodo non supportato: usa 'hatch' o 'concentric'")

        gcode = self._segments_to_gcode(segments, z_cut=z_cut, z_safe=z_safe, feed=feed, travel_feed=travel_feed)
        with open(out_file, "w") as f:
            f.write(gcode)
        return out_file