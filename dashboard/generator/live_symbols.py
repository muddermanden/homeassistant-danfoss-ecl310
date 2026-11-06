"""Split Danfoss' A266.1 SVG into a static background and full-canvas overlays for live symbols.

Each overlay is the original element cut out of its cell, wrapped in an SVG with the
same viewBox, so it lines up exactly when stretched over the background.
"""
import base64
import math
import re

GREEN = "#1ec31e"
OPEN_RED = "#e2000f"
CLOSE_BLUE = "#1f61a3"

# ECL mode (PNU 4201/4202) and status (PNU 4211/4212) codes, same order as the drawio states.
# HA's template sensors agree: mode 1 = "Auto" (schedule), status 2 = "Comfort".
MODES = {"0": "manual", "1": "schedule", "2": "comfort", "3": "setback", "4": "frost"}
STATUSES = {"0": "setback", "1": "pre_comfort", "2": "comfort", "3": "pre_setback"}

CIRCUITS = {
    "4201": ("sensor.mode_heating_raw", "sensor.status_heating_raw"),
    "4202": ("sensor.mode_dhw_raw", "sensor.status_dhw_raw"),
}
OVERRIDES = {  # manual_override PNU -> HA sensors; a valve hand shows if either of its registers is set
    "4062": ["sensor.m2_override_raw", "sensor.m2_override_2_raw"],
    "4077": ["sensor.m2_override_raw", "sensor.m2_override_2_raw"],
    "4060": ["sensor.m1_override_raw", "sensor.m1_override_2_raw"],
    "4076": ["sensor.m1_override_raw", "sensor.m1_override_2_raw"],
    "4067": ["sensor.p2_override_raw"],
    "4066": ["sensor.p1_override_raw"],
    "4069": ["sensor.a1_override_raw"],
}
VALVES = {"M2": ("sensor.m2_opening", "sensor.m2_closing"),
          "M1": ("sensor.m1_opening", "sensor.m1_closing")}
PUMPS = {"P2": "sensor.p2_circulation_pump_heating_raw",
         "P1": "sensor.p1_circulation_pump_dhw_raw"}
ALARM = "sensor.a1_alarm_raw"


def _cells(svg):
    """Yield (attrs, start, end) for each top-level drawio cell group."""
    heads = list(re.finditer(r'<g id="cell-[^"]+"([^>]*)>', svg))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(svg)
        yield dict(re.findall(r'data-([a-z_]+)="([^"]*)"', m.group(1))), m.end(), end


def _uri(svg_root, body):
    doc = svg_root + body + "</svg>"
    return "data:image/svg+xml;base64," + base64.b64encode(doc.encode()).decode()


def _overlay(uri, conditions):
    return {"type": "conditional", "conditions": conditions, "elements": [{
        "type": "image", "image": uri, "tap_action": {"action": "none"},
        "style": {"left": "50%", "top": "50%", "width": "100%", "pointer-events": "none"}}]}


def build(svg):
    """Return (background_svg, overlay_elements)."""
    root = re.search(r"<svg [^>]*>", svg).group(0)
    root = re.sub(r'\sstyle="[^"]*"', "", root)
    root = re.sub(r'\swidth="[^"]*"|\sheight="[^"]*"', "", root)
    cut = []          # (start, end) spans to remove from the background
    overlays = []

    def take(m, offset):
        cut.append((offset + m.start(), offset + m.end()))
        return m.group(0)

    for a, start, end in _cells(svg):
        seg = svg[start:end]
        comp, pnu, title = a.get("component"), a.get("pnu"), a.get("title")

        if comp == "ecl_mode" and pnu in CIRCUITS:
            mode_e, status_e = CIRCUITS[pnu]
            for m in re.finditer(r'<image data-type="(mode|status)" data-state="([a-z_]+)"[^>]*/>', seg):
                el = take(m, start)
                kind, state = m.group(1), m.group(2)
                if kind == "mode":
                    for code, name in MODES.items():
                        if name == state:
                            overlays.append(_overlay(_uri(root, el), [{"entity": mode_e, "state": code}]))
                else:  # status only shown while the circuit runs on its schedule
                    for code, name in STATUSES.items():
                        if name == state:
                            overlays.append(_overlay(_uri(root, el), [
                                {"entity": mode_e, "state": "1"}, {"entity": status_e, "state": code}]))

        elif comp == "manual_override":
            for m in re.finditer(r"<image [^>]*/>", seg):
                el = take(m, start)
                # 4077/4076 sit on the same spot as 4062/4060, so one hand per spot is enough
                if pnu in OVERRIDES and pnu not in ("4077", "4076"):
                    overlays.append(_overlay(_uri(root, el), [{"condition": "or", "conditions": [
                        {"condition": "numeric_state", "entity": e, "above": 0} for e in OVERRIDES[pnu]]}]))

        elif title == "A1":
            bell = take(re.search(r'<image data-type="status" data-state="on"[^>]*/>', seg), start)
            overlays.append(_overlay(_uri(root, bell), [
                {"entity": ALARM, "state_not": "0"}, {"entity": ALARM, "state_not": "unavailable"}]))
            dash = take(re.search(r'<path data-type="status" data-state="off"[^>]*/>', seg), start)
            overlays.append(_overlay(_uri(root, dash), [{"entity": ALARM, "state": "0"}]))

        elif title in VALVES:
            opening, closing = VALVES[title]
            for m in re.finditer(r'<path data-type="status" data-state="(neutral|open|closed)"[^>]*/>', seg):
                el = take(m, start)
                state = m.group(1)
                if state == "open":
                    el = re.sub(r'stroke="#[0-9a-f]{8}"', f'stroke="{OPEN_RED}"', el)
                    conds = [{"entity": opening, "state": "1"}]
                elif state == "closed":
                    el = re.sub(r'stroke="#[0-9a-f]{8}"', f'stroke="{CLOSE_BLUE}"', el)
                    conds = [{"entity": closing, "state": "1"}]
                else:
                    conds = [{"entity": opening, "state_not": "1"}, {"entity": closing, "state_not": "1"}]
                overlays.append(_overlay(_uri(root, el), conds))

        elif title in PUMPS:
            m = re.search(r'<path data-type="status"[^>]*/>', seg)
            tri = m.group(0).replace('fill="#808080"', f'fill="{GREEN}"')
            overlays.append(_overlay(_uri(root, tri), [{"entity": PUMPS[title], "state": "1"}]))

    background = svg
    for s, e in sorted(cut, reverse=True):
        background = background[:s] + background[e:]
    return background, overlays


# --- Valve opening rings (V1/V2 % = valve position, confirmed by eye on the real valves) ---
RING_R, RING_W = 26, 5
RING_STEP = 5  # one overlay per 5 %
VALVE_RINGS = {  # valve: (position sensor, ring centre under the valve symbol, motion sensor)
    "M2": ("sensor.v2_analog_valve_heating_circuit_1", (300, 374), "sensor.m2_motorized_control_valve_circuit_1"),
    "M1": ("sensor.v1_analog_valve_dhw_circuit_2", (300, 694), "sensor.m1_motorized_control_valve_circuit_2"),
}
# ring colour follows the valve motion, like the Danfoss ^ (red) / v (blue) indicator
RING_COLOURS = [("OPENING", OPEN_RED), ("CLOSING", CLOSE_BLUE), (None, "#546e7a")]


def _arc(cx, cy, r, fraction, colour=OPEN_RED):
    """SVG path for a clockwise arc from 12 o'clock covering `fraction` of the circle."""
    if fraction >= 0.999:
        return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colour}" '
                f'stroke-width="{RING_W}"/>')
    a = math.radians(-90 + 360 * fraction)
    x, y = cx + r * math.cos(a), cy + r * math.sin(a)
    large = 1 if fraction > 0.5 else 0
    return (f'<path d="M {cx} {cy - r} A {r} {r} 0 {large} 1 {x:.2f} {y:.2f}" fill="none" '
            f'stroke="{colour}" stroke-width="{RING_W}" stroke-linecap="round"/>')


def add_ring_tracks(svg):
    """Grey ring tracks under the valves, baked into the background."""
    tracks = "".join(f'<circle cx="{cx}" cy="{cy}" r="{RING_R}" fill="#fff" stroke="#d9d9d9" '
                     f'stroke-width="{RING_W}"/>' for _, (cx, cy), _ in VALVE_RINGS.values())
    i = svg.rindex("</svg>")
    return svg[:i] + tracks + svg[i:]


def ring_overlays(svg):
    """One full-canvas overlay per 5 % step; each shows while the position rounds to that step."""
    root = re.search(r"<svg [^>]*>", svg).group(0)
    root = re.sub(r'\sstyle="[^"]*"', "", root)
    root = re.sub(r'\swidth="[^"]*"|\sheight="[^"]*"', "", root)
    out = []
    for entity, (cx, cy), motion in VALVE_RINGS.values():
        for pct in range(RING_STEP, 101, RING_STEP):
            cond = {"condition": "numeric_state", "entity": entity, "above": pct - RING_STEP / 2}
            if pct < 100:
                cond["below"] = pct + RING_STEP / 2
            for state, colour in RING_COLOURS:
                if state:
                    m = [{"entity": motion, "state": state}]
                else:
                    m = [{"entity": motion, "state_not": s} for s, _ in RING_COLOURS if s]
                out.append(_overlay(_uri(root, _arc(cx, cy, RING_R, pct / 100, colour)), [cond] + m))
    return out


# --- Pump rotation arrows (SVG SMIL animation inside the overlay image) ---
PUMP_CENTRES = {"P2": (800, 160), "P1": (980, 640)}
SPIN_R = 27


def _spinner(cx, cy, seconds, colour="#1a7f1a"):
    """Two curved arrows around a pump circle, rotating clockwise."""
    def arrow(start_deg):
        a0, a1 = math.radians(start_deg), math.radians(start_deg + 70)
        x0, y0 = cx + SPIN_R * math.cos(a0), cy + SPIN_R * math.sin(a0)
        x1, y1 = cx + SPIN_R * math.cos(a1), cy + SPIN_R * math.sin(a1)
        # arrowhead at the leading end, pointing along the clockwise tangent
        t = a1 + math.pi / 2
        hx, hy = x1 + 7 * math.cos(t), y1 + 7 * math.sin(t)
        lx, ly = x1 + 5 * math.cos(a1), y1 + 5 * math.sin(a1)
        rx, ry = x1 - 5 * math.cos(a1), y1 - 5 * math.sin(a1)
        return (f'<path d="M {x0:.1f} {y0:.1f} A {SPIN_R} {SPIN_R} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" '
                f'stroke="{colour}" stroke-width="3" stroke-linecap="round"/>'
                f'<path d="M {lx:.1f} {ly:.1f} L {hx:.1f} {hy:.1f} L {rx:.1f} {ry:.1f} Z" fill="{colour}"/>')
    return (f'<g>{arrow(-60)}{arrow(120)}'
            f'<animateTransform attributeName="transform" type="rotate" from="0 {cx} {cy}" '
            f'to="360 {cx} {cy}" dur="{seconds}s" repeatCount="indefinite"/></g>')


SPIN_SECONDS = 8  # one slow, calm turn; the same for both pumps


def pump_spinners(svg):
    """Slowly rotating arrows on both pump symbols while the symbol's relay is ON (same rule as
    the green triangle); grey and still otherwise."""
    root = re.search(r"<svg [^>]*>", svg).group(0)
    root = re.sub(r'\sstyle="[^"]*"', "", root)
    root = re.sub(r'\swidth="[^"]*"|\sheight="[^"]*"', "", root)
    out = []
    for pump, entity in PUMPS.items():
        cx, cy = PUMP_CENTRES[pump]
        out.append(_overlay(_uri(root, _spinner(cx, cy, SPIN_SECONDS)), [{"entity": entity, "state": "1"}]))
        still = _spinner(cx, cy, SPIN_SECONDS, colour="#9e9e9e").replace("<animateTransform", "<!--").replace(
            'repeatCount="indefinite"/>', "-->")
        out.append(_overlay(_uri(root, still), [{"entity": entity, "state_not": "1"}]))
    return out


# --- Pipe colour by temperature, flow dashes, attention pulses ---
def _root(svg):
    root = re.search(r"<svg [^>]*>", svg).group(0)
    root = re.sub(r'\sstyle="[^"]*"', "", root)
    return re.sub(r'\swidth="[^"]*"|\sheight="[^"]*"', "", root)


# supply pipes (coordinates from the Danfoss drawing); gaps leave the pump/valve symbols uncovered
PIPES = {
    "district_supply": ("sensor.heat_meter_flow_temperature",
                        "M 40 160 L 480 160 M 240 160 L 240 310 M 240 330 L 240 480 L 480 480"),
    "heating_supply": ("sensor.s3_flow_temperature_sensor_circuit_1", "M 580 160 L 780 160 M 820 160 L 1200 160"),
    "dhw_supply": ("sensor.s4_dhw_flow_temperature_sensor_circuit_2", "M 580 480 L 1200 480"),
}
# (above, below, colour): orange when cool, deep red when hot
PIPE_BANDS = [(None, 30, "#ffb74d"), (30, 40, "#fb8c00"), (40, 50, "#f4511e"), (50, 60, "#e53935"), (60, None, "#b71c1c")]

import settings

# DHW circulation pump relay. If your pumps are wired to swapped terminals and you keep a binary_sensor for that
# (config pump_wiring_swapped_entity), relay 2 drives the DHW flow while it is on, else relay 1.
_SWAP = settings.get("pump_wiring_swapped_entity")
_DHW_FLOW = ([{"condition": "or", "conditions": [
    {"condition": "and", "conditions": [
        {"condition": "state", "entity": _SWAP, "state": "on"},
        {"condition": "state", "entity": "sensor.p2_circulation_pump_heating_raw", "state": "1"}]},
    {"condition": "and", "conditions": [
        {"condition": "state", "entity": _SWAP, "state_not": "on"},
        {"condition": "state", "entity": "sensor.p1_circulation_pump_dhw_raw", "state": "1"}]}]}]
    if _SWAP else [{"condition": "state", "entity": "sensor.p1_circulation_pump_dhw_raw", "state": "1"}])


FLOWS = {  # loop path (drawn in flow direction) and when it moves
    "district": ("M 40 160 L 480 160 M 240 160 L 240 310 M 240 330 L 240 480 L 480 480 "
                 "M 480 320 L 325 320 M 275 320 L 40 320 M 480 640 L 325 640 M 275 640 L 80 640 L 80 320",
                 [{"entity": "binary_sensor.heat_meter_flowing", "state": "on"}]),
    # radiator loop: the Grundfos is the only pump with a measured speed
    "heating": ("M 580 160 L 780 160 M 820 160 L 1200 160 M 1200 320 L 580 320",
                [{"condition": "numeric_state", "entity": "sensor.circulation_pump_speed", "above": 0}]),
    # DHW circulation: relay 2 while the pumps are wired swapped (config pump_wiring_swapped_entity), else relay 1
    # solid parts only (the dashed circulation return is not drawn with flow dashes)
    "dhw": ("M 580 480 L 1060 480 M 960 640 L 825 640 M 775 640 L 580 640", _DHW_FLOW),
}

PULSES = [  # (centre, radius, conditions): slow amber pulse around the alarm bell / override hands
    ((799.5, 23.5), 30, [{"condition": "numeric_state", "entity": "sensor.a1_alarm_raw", "above": 0}]),
    ((829.5, 59.5), 15, [{"condition": "numeric_state", "entity": "sensor.a1_override_raw", "above": 0}]),
    ((369.5, 279.5), 15, [{"condition": "or", "conditions": [
        {"condition": "numeric_state", "entity": e, "above": 0} for e in OVERRIDES["4062"]]}]),
    ((369.5, 599.5), 15, [{"condition": "or", "conditions": [
        {"condition": "numeric_state", "entity": e, "above": 0} for e in OVERRIDES["4060"]]}]),
    ((829.5, 129.5), 15, [{"condition": "numeric_state", "entity": "sensor.p2_override_raw", "above": 0}]),
    ((1009.5, 609.5), 15, [{"condition": "numeric_state", "entity": "sensor.p1_override_raw", "above": 0}]),
]


def pipe_overlays(svg):
    root, out = _root(svg), []
    for entity, d, *dash in PIPES.values():  # optional third item: stroke-dasharray (unshown pipe parts)
        dash_attr = f' stroke-dasharray="{dash[0]}"' if dash else ""
        for lo, hi, colour in PIPE_BANDS:
            cond = {"condition": "numeric_state", "entity": entity}
            if lo is not None: cond["above"] = lo
            if hi is not None: cond["below"] = hi
            out.append(_overlay(_uri(root, f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="5"{dash_attr}/>'),
                                [cond]))
    return out


def flow_overlays(svg):
    """Slow white dashes moving along a loop while water flows in it."""
    root, out = _root(svg), []
    for d, conds in FLOWS.values():
        # dark, semi-transparent dashes stay visible on every pipe colour (white vanished on pale steps)
        dash = (f'<path d="{d}" fill="none" stroke="#1a1a1a" stroke-opacity="0.45" stroke-width="2" '
                f'stroke-dasharray="3 17"><animate attributeName="stroke-dashoffset" from="20" to="0" '
                f'dur="4s" repeatCount="indefinite"/></path>')
        out.append(_overlay(_uri(root, dash), conds))
    return out


def pulse_overlays(svg):
    root, out = _root(svg), []
    for (cx, cy), r, conds in PULSES:
        ring = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#f59e0b" stroke-width="3">'
                f'<animate attributeName="stroke-opacity" values="0.15;0.9;0.15" dur="3s" '
                f'repeatCount="indefinite"/></circle>')
        out.append(_overlay(_uri(root, ring), conds))
    return out


def decorations(svg):
    """Pipe colours under the flow dashes, then pulses; all drawn below the labels."""
    return pipe_overlays(svg) + flow_overlays(svg) + pulse_overlays(svg)
