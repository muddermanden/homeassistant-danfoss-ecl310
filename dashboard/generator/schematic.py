"""Picture-elements card for the Danfoss A266.1 schematic (positions in SVG px, 1205x756)."""
import json
import re

import settings

W, H = 1205, 756
# Type scale (canvas units at the 1205-wide drawing; 1 unit ~ 0.065 vw on a typical desktop card):
#   L = section titles and the controller time, M = all values and their labels, S = supporting text.
TYPE_L, TYPE_M, TYPE_S = 20, 15, 12
FONT = "Roboto, Arial, Helvetica, sans-serif"


def fs(units):
    """Font size that scales with the card: units of the drawing -> vw, with sane pixel limits."""
    return f"clamp({max(7, round(units * 0.5))}px, {units * 0.065:.3f}vw, {round(units * 1.4)}px)"


SIZE_L, SIZE_M, SIZE_S = fs(TYPE_L), fs(TYPE_M), fs(TYPE_S)
BLACK = {"color": "#000", "font-weight": "600", "font-size": SIZE_M}          # values
BLUE = {"color": "#1f5fa8", "font-size": SIZE_M}                              # setpoints, limits
ORANGE = {"color": "#e65100", "font-weight": "700", "font-size": SIZE_S}
RED = {"color": "#c00", "font-weight": "600", "font-size": SIZE_M}
BOLD_SMALL = {"color": "#000", "font-weight": "600", "font-size": SIZE_M}
SMALL = {"color": "#000", "font-size": SIZE_M}
RING_TEXT = {"color": "#000", "font-weight": "700", "font-size": SIZE_S, "letter-spacing": "-0.02em"}
CLOCK = {"color": "#000", "font-size": SIZE_L}
# state-label wraps its text in a div with 8px padding: the transforms cancel it so x/y hit the text itself
SHIFT = {"end": "calc(-100% + 8px)", "start": "-8px", "middle": "-50%"}
BASELINE = "calc(-8px - 0.92em)"  # moves the text baseline (Arial/Roboto ascent ~0.92em) onto y
# entity, x, baseline y, anchor, style, prefix, suffix, hide_when_unavailable
LABELS = [
    ("sensor.ecl_controller_time", 409.5, 43.5, "start", CLOCK, "", "", True),
    ("sensor.s1_outdoor_temperature_sensor", 119.5, 16.5, "end", BLACK, "", "", False),
    ("sensor.v2_analog_valve_heating_circuit_1", 300, 380, "middle", RING_TEXT, "", "", False),
    ("sensor.s5_return_temperature_sensor_circuit_1", 469.5, 264.5, "end", BLACK, "", "", True),
    ("sensor.desired_return_temperature_circuit_1", 469.5, 282.5, "end", BLUE, "limit ", "", False),
    ("sensor.s3_flow_temperature_sensor_circuit_1", 669.5, 104.5, "end", BLACK, "", "", False),
    ("sensor.desired_flow_temperature_circuit_1", 669.5, 122.5, "end", BLUE, "(", ")", False),
    ("sensor.s4_dhw_flow_temperature_sensor_circuit_2", 670.5, 424.5, "end", BLACK, "", "", False),
    ("sensor.desired_dhw_flow_temperature_circuit_2", 670.5, 442.5, "end", BLUE, "(", ")", False),
    ("sensor.s6_dhw_return_temperature_sensor_circuit_2", 469.5, 584.5, "end", BLACK, "", "", True),
    ("sensor.desired_dhw_return_temperature_circuit_2", 469.5, 602.5, "end", BLUE, "limit ", "", False),
    ("sensor.v1_analog_valve_dhw_circuit_2", 300, 700, "middle", RING_TEXT, "", "", False),
]

# Two-column stacks: label and value are both state-labels with the same font size and line height,
# vertically centred on the same row line. Labels show only their prefix: they point at an empty
# attribute of sensor.heating_dashboard_text (packages/heating_rooms.yaml).
TEXT_ENTITY, TEXT_ATTR = "sensor.heating_dashboard_text", "blank"
STACK_SIZE = SIZE_M
INK, RED_INK, BLUE_INK = "#000", "#c00", "#1f5fa8"
# (label x, value x, [(label, colour, entity, row centre y)])
STACKS = [
    # district heating inlet: supply above the pipe, power and flow below it
    (40, 100, [("Supply", RED_INK, "sensor.heat_meter_flow_temperature", 146),
               ("Power", INK, "sensor.heat_meter_power", 184),
               ("Flow", INK, "sensor.heat_meter_volume_flow", 204)]),
    # district heating return
    (95, 158, [("Return", BLUE_INK, "sensor.heat_meter_return_temperature", 344),
               ("ΔT", INK, "sensor.heat_meter_temperature_difference", 364)]),
    # circulation pump P2: under the pipe, left of P2 so it stays clear of the mode block
    (626, 680, [("Speed", INK, "sensor.circulation_pump_speed", 182),
                ("Flow", INK, "sensor.circulation_pump_flow", 202),
                ("Head", INK, "sensor.circulation_pump_head", 222),
                ("Power", INK, "sensor.circulation_pump_power", 242),
                ("Temp", INK, "sensor.circulation_pump_medium_temperature", 262)]),
    # circuit 1 mode/status, centred on the ECL mode box (277–301), right edge left of the box
    (784, 846, [("Heating", INK, "sensor.mode_heating_circuit_1", 280),
                ("Status", INK, "sensor.status_heating_circuit_1", 300)]),
    # S2 spot (no ECL room sensor fitted): heated-room statistics, above the S2 house icon
    (1062, 1130, [("Rooms", INK, "sensor.heated_rooms_average_temperature", 12),
                  ("min", INK, "sensor.heated_rooms_minimum_temperature", 32),
                  ("max", INK, "sensor.heated_rooms_maximum_temperature", 52),
                  ("desired", BLUE_INK, "sensor.desired_room_temperature_circuit_1", 72)]),
]


# Phone layout: a true miniature of the desktop text would be ~4 px on a 343 px card, below the browser's
# minimum font size (~6 px), so it renders larger and collides. Phones get one key value per spot instead
# (the detail is in the sections below), sized in vw: the card is the full width minus 32 px of gutters.
PHONE_M, PHONE_S = "2.2vw", "1.5vw"  # phone has its own two-step scale: values, supporting text
PHONE = {"color": "#000", "font-weight": "700", "font-size": PHONE_M}
PHONE_RED = {**PHONE, "color": "#c00"}
PHONE_BLUE = {**PHONE, "color": "#1f5fa8"}
PHONE_LABELS = [
    ("sensor.s1_outdoor_temperature_sensor", 119.5, 14, "end", PHONE, "", "", False),
    ("sensor.heated_rooms_average_temperature", 1199.5, 70, "end", PHONE, "Rooms ", "", False),
    ("sensor.heat_meter_flow_temperature", 40, 148, "start", PHONE_RED, "", "", False),
    ("sensor.heat_meter_power", 40, 196, "start", PHONE, "", "", False),
    ("sensor.heat_meter_return_temperature", 92, 360, "start", PHONE_BLUE, "", "", False),
    ("sensor.v2_analog_valve_heating_circuit_1", 334, 384, "start", PHONE, "", "", False),
    ("sensor.s3_flow_temperature_sensor_circuit_1", 625, 112, "start", PHONE, "", "", False),
    ("sensor.circulation_pump_power", 800, 214, "middle", PHONE, "", "", False),
    ("sensor.circulation_pump_speed", 800, 252, "middle", PHONE, "", "", False),
    ("sensor.s4_dhw_flow_temperature_sensor_circuit_2", 625, 432, "start", PHONE, "", "", False),
    ("sensor.ecl_controller_time", 409.5, 64, "start", {**PHONE, "font-weight": "400", "font-size": PHONE_S}, "", "", True),
    ("sensor.v1_analog_valve_dhw_circuit_2", 334, 704, "start", PHONE, "", "", False),
]


def phone_card(image, overlays=(), width=W, height=H):
    """Same drawing and live symbols as card(), with the phone label set."""
    return {"type": "picture-elements", "image": image, "grid_options": {"columns": "full"},
            "elements": list(overlays) + [x for l in PHONE_LABELS
                                          for x in colour_banded(element(*l, width=width, height=height))]
                        + [x for x in (swap_note(width, height, size=PHONE_S), cut_out_label(width, height, size=PHONE_S)) if x]
                        + nav_hotspots(width, height)}


def unclamp(card_cfg):
    """Panel/TV view: the card is the full viewport width, so plain vw is already exact."""
    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("font-size"), str):
                o["font-size"] = re.sub(r"clamp\([^,]+,\s*([\d.]+vw),[^)]+\)", r"\1", o["font-size"])
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(card_cfg)
    return card_cfg


# Value colours (thresholds documented in dashboard/README.md, Colour rules).
GOOD, WARN, BAD, COLD, WARM = "#2e7d32", "#b26a00", "#c62828", "#1565c0", "#e65100"
# shown entity: (entity the bands test, [(above, below, colour or None = keep the normal colour)])
COLOUR_RULES = {
    "sensor.heat_meter_return_temperature": ("sensor.heat_meter_return_temperature",
                                           [(None, 35, GOOD), (35, 45, WARN), (45, None, BAD)]),
    "sensor.heat_meter_temperature_difference": ("sensor.heat_meter_temperature_difference",
                                      [(25, None, GOOD), (15, 25, None), (None, 15, WARN)]),
    "sensor.s3_flow_temperature_sensor_circuit_1": ("sensor.heating_flow_deviation",
                                                    [(-2, 2, GOOD), (2, None, WARN), (None, -2, WARN)]),
    "sensor.s4_dhw_flow_temperature_sensor_circuit_2": ("sensor.dhw_flow_deviation",
                                                        [(-2, 2, GOOD), (2, None, WARN), (None, -2, WARN)]),
}
for _avg in ("average", "minimum", "maximum"):
    COLOUR_RULES[f"sensor.heated_rooms_{_avg}_temperature"] = (
        f"sensor.heated_rooms_{_avg}_deviation", [(-1, 1, GOOD), (1, None, WARM), (None, -1, COLD)])


# Return above the ECL return limit always shows red, whatever the traffic light says.
OVERRIDE_RED = {"sensor.heat_meter_return_temperature": "sensor.return_limit_deviation"}

STALE = "#9e9e9e"
NEUTRAL = "#333"
UNAVAILABLE = ["unavailable", "unknown"]
# group "online" signals: a value is shown grey while its source is offline or the value itself is unavailable
ECL_PREFIXES = ("sensor.s1_", "sensor.s3_", "sensor.s4_", "sensor.s5_", "sensor.s6_", "sensor.desired_",
                "sensor.v1_", "sensor.v2_", "sensor.mode_", "sensor.status_", "sensor.ecl_")
# Stale-data groups: (entity prefixes, condition while the source is live, condition while it is stale).
# The heat meter (wmbusmeters) sends nothing while there is no flow, so its temperatures freeze at the last values.
METER_FLOW = "sensor.heat_meter_volume_flow"
GROUPS = [
    (ECL_PREFIXES, {"condition": "state", "entity": "binary_sensor.ecl_modbus_online", "state": "on"},
     {"condition": "state", "entity": "binary_sensor.ecl_modbus_online", "state_not": "on"}),
    (("sensor.circulation_pump_",), {"condition": "state", "entity": "binary_sensor.circulation_pump_pump_connected", "state": "on"},
     {"condition": "state", "entity": "binary_sensor.circulation_pump_pump_connected", "state_not": "on"}),
]
# NOFLOW_GREY (default on): grey the meter temperatures while it reports no flow (its values are frozen then)
if settings.get("variant.noflow_grey", True) and settings.feature("heat_meter"):
    GROUPS.append((("sensor.heat_meter_flow_temperature", "sensor.heat_meter_return_temperature",
                    "sensor.heat_meter_temperature_difference"),
                   {"condition": "numeric_state", "entity": METER_FLOW, "above": 0},
                   {"condition": "numeric_state", "entity": METER_FLOW, "below": 0.0005}))


def _fresh_stale(entity):
    """(conditions while the value is live, condition while it is stale)."""
    fresh = [{"condition": "state", "entity": entity, "state_not": s} for s in UNAVAILABLE]
    stale = [{"condition": "state", "entity": entity, "state": UNAVAILABLE}]
    for prefixes, online, offline in GROUPS:
        if entity.startswith(prefixes):
            fresh.append(online)
            stale.append(offline)
    return fresh, {"condition": "or", "conditions": stale}


def colour_banded(el):
    """Value element -> conditional copies: grey while stale, otherwise coloured by its bands (if any)."""
    if el.get("type") != "state-label" or el.get("entity") == TEXT_ENTITY or el["style"].get("color") == NEUTRAL:
        return [el]  # static text and neutral annotations (legend values, loop return estimate) keep their colour
    entity = el["entity"]
    fresh, stale = _fresh_stale(entity)
    grey = json.loads(json.dumps(el)); grey["style"]["color"] = STALE
    out = [{"type": "conditional", "conditions": [stale], "elements": [grey]}]
    if entity not in COLOUR_RULES:
        return out + [{"type": "conditional", "conditions": fresh, "elements": [el]}]
    test, bands = COLOUR_RULES[entity]
    extra = []
    if entity in OVERRIDE_RED:
        limit = OVERRIDE_RED[entity]
        red = json.loads(json.dumps(el)); red["style"]["color"] = BAD
        out.append({"type": "conditional", "conditions": fresh + [
            {"condition": "numeric_state", "entity": limit, "above": 0}], "elements": [red]})
        extra = [{"condition": "or", "conditions": [
            {"condition": "numeric_state", "entity": limit, "below": 0.001},
            {"condition": "state", "entity": limit, "state": UNAVAILABLE}]}]
    # band test entity unavailable: plain colour
    out.append({"type": "conditional", "conditions": fresh + extra + [
        {"condition": "state", "entity": test, "state": UNAVAILABLE}], "elements": [el]})
    for lo, hi, colour in bands:
        cond = {"condition": "numeric_state", "entity": test}
        if lo is not None: cond["above"] = lo - 0.001  # bands meet without a gap
        if hi is not None: cond["below"] = hi
        copy = json.loads(json.dumps(el))
        if colour: copy["style"]["color"] = colour
        out.append({"type": "conditional", "conditions": fresh + extra + [cond], "elements": [copy]})
    return out


# Summer cut-out: the ECL stops space heating above its "Heat cut-out" setting (PNU 11179). That register is
# not polled in HA; it read 20 °C in the danfoss-ecl dump on 2026-10-28, so the limit is fixed here.
HEAT_CUT_OUT_C = settings.get("heat_cut_out_c", 20)


def cut_out_label(width=W, height=H, size=SIZE_S):
    dx, dy = (width - W) / 2, (height - H) / 2
    label = {"type": "state-label", "entity": TEXT_ENTITY, "attribute": TEXT_ATTR,
             "prefix": f"Summer cut-out (> {HEAT_CUT_OUT_C} °C)", "tap_action": {"action": "none"},
             "style": {"left": f"{(40 + dx) / width * 100:.2f}%", "top": f"{(74 + dy) / height * 100:.2f}%",
                       "transform": "translate(-8px, -50%)", "white-space": "nowrap", "padding": "0",
                       "line-height": "1.15", "color": WARN, "font-weight": "600", "font-size": size}}
    return {"type": "conditional", "conditions": [
        {"condition": "numeric_state", "entity": "sensor.s1_outdoor_temperature_sensor", "above": HEAT_CUT_OUT_C}],
        "elements": [label]}


# The circled 1 and 2 in the Danfoss drawing open the Space heating and Hot water views.
_DASH = "/" + settings.get("dashboard_path", "dashboard-heating")
NAV_HOTSPOTS = [((1180, 240), _DASH + "/space-heating"), ((530, 430), _DASH + "/hot-water")]
_CLEAR = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxIDEiLz4="


def nav_hotspots(width=W, height=H):
    dx, dy = (width - W) / 2, (height - H) / 2
    return [{"type": "image", "image": _CLEAR, "tap_action": {"action": "navigate", "navigation_path": path},
             "style": {"left": f"{(x + dx) / width * 100:.2f}%", "top": f"{(y + dy) / height * 100:.2f}%",
                       "width": f"{52 / width * 100:.2f}%", "cursor": "pointer"}}
            for (x, y), path in NAV_HOTSPOTS]


def add_static_text(svg):
    """Kept for the build pipeline; all text is HTML now."""
    return svg


# Temporary note while the pumps are wired swapped (config pump_wiring_swapped_entity).
# Optional (config pump_wiring_swapped_entity): a note on the schematic while that binary_sensor is on.
SWAP_NOTE = (settings.get("pump_wiring_swapped_entity"), "P1/P2 wired swapped (terminals 11/12) - pending fix")


def swap_note(width=W, height=H, size=SIZE_S):
    dx, dy = (width - W) / 2, (height - H) / 2
    entity, text = SWAP_NOTE
    if not entity:
        return None
    label = {"type": "state-label", "entity": TEXT_ENTITY, "attribute": TEXT_ATTR, "prefix": "⚠ " + text,
             "tap_action": {"action": "none"},
             "style": {"left": f"{(40 + dx) / width * 100:.2f}%", "top": f"{(740 + dy) / height * 100:.2f}%",
                       "transform": "translate(-8px, -50%)", "white-space": "nowrap", "padding": "0",
                       "line-height": "1.15", "color": "#b45309", "font-weight": "600", "font-size": size}}
    return {"type": "conditional", "conditions": [{"entity": entity, "state": "on"}], "elements": [label]}


def stack_elements(width=W, height=H):
    dx, dy = (width - W) / 2, (height - H) / 2
    out = []
    for lx, vx, rows in STACKS:
        if not all(settings.enabled(r[2]) for r in rows):
            continue  # a stack that needs an optional feature that is off is left out whole
        for label, colour, entity, y in rows:
            for x, weight, el in ((lx, "400", {"entity": TEXT_ENTITY, "attribute": TEXT_ATTR, "prefix": label,
                                               "tap_action": {"action": "none"}}),
                                  (vx, "600", {"entity": entity})):
                el = {"type": "state-label", **el, "style": {
                    "left": f"{(x + dx) / width * 100:.2f}%", "top": f"{(y + dy) / height * 100:.2f}%",
                    "transform": "translate(-8px, -50%)", "white-space": "nowrap", "padding": "0",
                    "line-height": "1.15", "color": colour, "font-weight": weight, "font-size": STACK_SIZE,
                    "font-family": FONT}}
                out.append(el)
    return out


def element(e, x, y, anchor, style, prefix, suffix, hide, width=W, height=H):
    dx, dy = (width - W) / 2, (height - H) / 2
    st = {"left": f"{(x + dx) / width * 100:.2f}%", "top": f"{(y + dy) / height * 100:.2f}%",
          "transform": f"translate({SHIFT[anchor]}, {BASELINE})",
          "white-space": "nowrap", "padding": "0", "line-height": "1.15", "font-family": FONT, **style}
    el = {"type": "state-label", "entity": e, "style": st}
    if prefix: el["prefix"] = prefix
    if suffix: el["suffix"] = suffix
    if hide:
        conds = [{"entity": e, "state_not": "unavailable"}]
        if hide == "override":
            conds.append({"entity": e, "state_not": "0"})
        return {"type": "conditional", "conditions": conds, "elements": [el]}
    return el

def card(image, overlays=(), width=W, height=H, boost=1.0):
    """overlays: live Danfoss symbols from live_symbols.build(), drawn under the labels.

    A canvas larger than W x H centres the drawing on it (see pad()), e.g. 16:9 with a TV safe area.
    """
    labels = ([element(*l, width=width, height=height) for l in LABELS] + stack_elements(width, height)
              + [x for x in (swap_note(width, height), cut_out_label(width, height)) if x] + nav_hotspots(width, height))
    k = W / width * boost  # the drawing is narrower on a padded canvas: scale vw font sizes to match
    if k != 1:
        for el in labels:
            st = (el.get("elements") or [el])[0]["style"]
            if "font-size" in st:  # navigation hotspots have no text
                st["font-size"] = re.sub(r"([\d.]+)vw", lambda m: f"{float(m.group(1)) * k:.2f}vw", st["font-size"])
    labels = [x for el in labels for x in colour_banded(el)]
    return {"type": "picture-elements", "image": image,
            "grid_options": {"columns": "full"},
            "elements": list(overlays) + labels}


def pad(svg, width, height):
    """Pad the SVG canvas to width x height, keeping the drawing centred on white."""
    dx, dy = (width - W) / 2, (height - H) / 2
    x0, y0 = -0.5 - dx, -0.5 - dy
    svg = svg.replace('viewBox="-0.5 -0.5 1205 756"', f'viewBox="{x0} {y0} {width} {height}"', 1)
    svg = svg.replace('width="1205px" height="756px"', f'width="{width}px" height="{height}px"', 1)
    # white backdrop across the padded canvas (style background only covers the element box)
    return svg.replace("<g>", f'<rect x="{x0}" y="{y0}" width="{width}" height="{height}" fill="#fff"/><g>', 1)


def typeset_svg(svg):
    """Bring the drawing's own text onto the same scale and font: symbol tags (S1, M2, P1 ...) M bold,
    section titles and "Controller time:" L, the reference label S. The circled 1/2 stay at circle size."""
    svg = svg.replace('font-family="Arial,Helvetica"', f'font-family="{FONT}"')
    svg = re.sub(r'font-size="15px"(>\s*<text[^>]*>A266)', rf'font-size="{TYPE_S}px"\1', svg)
    svg = re.sub(r'font-size="(?:18|17\.5)px"', f'font-size="{TYPE_M}px"', svg)
    svg = re.sub(r'font-size="(?:20|20\.25)px"', f'font-size="{TYPE_L}px"', svg)
    return svg
