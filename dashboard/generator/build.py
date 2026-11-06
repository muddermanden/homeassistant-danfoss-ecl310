"""Generate the heating dashboard (YAML + background SVGs) from your config and Danfoss drawing.

    python build.py --config ../config.local.yaml [--states states.json]

Writes into output_dir (default ../build): heating-dashboard.yaml / .json, a266-schematic.svg and
a266-schematic-tv.svg. Copy the SVGs to /config/www/heating/ and paste the YAML into the dashboard's raw
configuration editor. --states is an optional {"states": [...], "entities": [...]} dump used to check that
every referenced entity exists.
"""
import argparse, json, os, sys, yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings
import prune

_ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
_ap.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.local.yaml"))
_ap.add_argument("--states", help="optional states/entities dump for the entity check")
ARGS = _ap.parse_args()
settings.load(ARGS.config)
OUT_DIR = settings.path("output_dir", "build")
OUT_DIR.mkdir(parents=True, exist_ok=True)

from schematic import card as schematic_card, phone_card, unclamp
import live_symbols
from schematic import pad, add_static_text
# white margin around the Danfoss drawing so edge labels (S1 value at the top) stay clear of the card edge
MAIN_W, MAIN_H = 1265, 836
DRAWING = settings.path("drawing", "drawings/a266.svg")
if not DRAWING.is_file():
    sys.exit(f"Danfoss drawing not found: {DRAWING} (see dashboard/README.md, 'Get the drawing')")
drawing = add_static_text(DRAWING.read_text(encoding="utf-8"))
# pump titles a little higher so the rotating arrows (radius 27 around the pump circles) don't cover them
drawing = drawing.replace('<text x="799.5" y="134.5">P2</text>', '<text x="799.5" y="122">P2</text>', 1)
drawing = drawing.replace('<text x="979.5" y="614.5">P1</text>', '<text x="979.5" y="602">P1</text>', 1)
# variant.direct_heating: circuit 1 drawn as direct heating with a mixing loop (author's house, direct_heating.py).
# Off: the original Danfoss A266.1 drawing with heat exchanger 1.
DIRECT = bool(settings.get("variant.direct_heating", False))
SUFFIX = "" if DIRECT else "-indirect"
if DIRECT:
    import direct_heating, schematic
    drawing = direct_heating.transform(drawing)
    live_symbols.PIPES.update(direct_heating.PIPES)
    live_symbols.FLOWS["district"] = (direct_heating.FLOWS_DISTRICT, live_symbols.FLOWS["district"][1])
    live_symbols.FLOWS["heating"] = (direct_heating.FLOWS_HEATING, live_symbols.FLOWS["heating"][1])
    # variant.one_pipe: the radiators as a one-pipe (single-string) loop (see direct_heating.one_pipe)
    DYNAMIC_DEFAULT = bool(settings.get("variant.dynamic_colours", True))
    ONE_PIPE = bool(settings.get("variant.one_pipe", True))  # radiators as a one-pipe loop
    if ONE_PIPE:
        drawing = direct_heating.one_pipe(drawing)
        # the Danfoss reference label: this is no longer the textbook example a
        drawing = drawing.replace(">A266_1 ex. a<", ">A266.1 (direct, one-pipe)<", 1)
        if DYNAMIC_DEFAULT:
            drawing = direct_heating.neutral_underlay(drawing)
        live_symbols.PIPES["heating_supply"] = (live_symbols.PIPES["heating_supply"][0], direct_heating.ONE_PIPE_SUPPLY)
        live_symbols.PIPES["heating_loop_dashed"] = (live_symbols.PIPES["heating_supply"][0],
                                                     direct_heating.LOOP_DASHED_D, direct_heating.LOOP_DASH)
        live_symbols.FLOWS["heating"] = (direct_heating.FLOWS_HEATING_ONE_PIPE, live_symbols.FLOWS["heating"][1])
        schematic.NAV_HOTSPOTS[0] = (direct_heating.ONE_PIPE_MARKER, schematic.NAV_HOTSPOTS[0][1])
    # variant.dynamic_colours: pipe colours on a blue->red scale between district return and supply (colour_scale.py)
    DYNAMIC = ONE_PIPE and DYNAMIC_DEFAULT
    # variant.fixed_scale: a fixed 30-60 °C scale instead of return..supply (colour_scale.fixed_overlays)
    FIXED = DYNAMIC and bool(settings.get("variant.fixed_scale", True))
    _pipes = live_symbols.pipe_overlays
    def _direct_pipes(svg):
        if DYNAMIC:
            import colour_scale
            make = colour_scale.fixed_overlays if FIXED else colour_scale.overlays
            return make(svg, live_symbols._overlay, live_symbols._uri, live_symbols._root(svg))
        args = (svg, live_symbols.PIPE_BANDS, live_symbols._overlay, live_symbols._uri, live_symbols._root(svg))
        extra = direct_heating.loop_return_overlays(*args) if ONE_PIPE else []
        return _pipes(svg) + extra + direct_heating.bypass_overlays(*args)
    live_symbols.pipe_overlays = _direct_pipes
    if DYNAMIC:
        import colour_scale
        k = drawing.rindex("</svg>")
        drawing = drawing[:k] + colour_scale.legend_svg() + (colour_scale.fixed_legend_text() if FIXED else "") + drawing[k:]
        small = {"color": "#333", "font-size": schematic.SIZE_S}
        legend_live = not FIXED
        ly = colour_scale.LEGEND_Y + 4
        schematic.LABELS += ([
            (colour_scale.SUP, colour_scale.LEGEND_X0 - 6, ly, "end", small, "Supply ", "", False),
            (colour_scale.RET, colour_scale.LEGEND_X1 + 6, ly, "start", small, "Return ", "", False),
            (colour_scale.MID, (colour_scale.LEGEND_X0 + colour_scale.LEGEND_X1) / 2, ly + 16, "middle", small,
             "", "", True)] if legend_live else []) + [
            (colour_scale.EST, direct_heating.BYPASS_X + 10, 302, "start",
             {"color": "#333", "font-weight": "600", "font-size": schematic.SIZE_S}, "Loop return ≈", "", True),
        ]
        # phone: only the legend's end values, larger
        big = {"color": "#333", "font-weight": "700", "font-size": schematic.PHONE_S}
        if legend_live:
            schematic.PHONE_LABELS += [
                (colour_scale.SUP, colour_scale.LEGEND_X0 - 6, ly, "end", big, "", "", False),
                (colour_scale.RET, colour_scale.LEGEND_X1 + 6, ly, "start", big, "", "", False),
            ]
    dx = direct_heating.S3_SHIFT
    def _move(rows):
        out = []
        for r in rows:
            if r[0] in ("sensor.s3_flow_temperature_sensor_circuit_1", "sensor.desired_flow_temperature_circuit_1"):
                r = (r[0], r[1] + dx) + tuple(r[2:])
            if r[0] == "sensor.s5_return_temperature_sensor_circuit_1":
                continue  # no S5 symbol any more
            out.append(r)
        return out
    schematic.LABELS[:] = _move(schematic.LABELS)
    schematic.PHONE_LABELS[:] = _move(schematic.PHONE_LABELS)
import schematic as _sch
drawing = _sch.typeset_svg(live_symbols.add_ring_tracks(drawing))
main_svg = pad(drawing, MAIN_W, MAIN_H)
background, overlays = live_symbols.build(main_svg)
overlays = live_symbols.decorations(main_svg) + overlays
overlays += live_symbols.ring_overlays(main_svg) + live_symbols.pump_spinners(main_svg)
(OUT_DIR / "a266-schematic.svg").write_text(background, encoding="utf-8")
# 16:9 canvas with ~6 % margin on every side for TV overscan: the drawing uses 88 % of the height
TV_H = 860
TV_W = round(TV_H * 16 / 9)  # 1529
tv_svg = pad(drawing, TV_W, TV_H)
tv_background, tv_overlays = live_symbols.build(tv_svg)
tv_overlays = live_symbols.decorations(tv_svg) + tv_overlays
tv_overlays += live_symbols.ring_overlays(tv_svg) + live_symbols.pump_spinners(tv_svg)
(OUT_DIR / "a266-schematic-tv.svg").write_text(tv_background, encoding="utf-8")
TV = settings.get("tv.media_player")  # optional: cast the TV view to this media player
TV_VIEW = bool(settings.get("tv.view", True))
DASH = settings.get("dashboard_path", "dashboard-heating")
IMAGE = settings.get("image_url", "/local/heating/a266-schematic.svg")
TV_IMAGE = settings.get("tv_image_url", "/local/heating/a266-schematic-tv.svg")
WEATHER = settings.get("weather")

def tile(e, name=None, **kw):
    c = {"type": "tile", "entity": e}
    if name: c["name"] = name
    c.update(kw)
    return c

def heading(text, icon):
    return {"type": "heading", "heading": text, "icon": icon}

def entities(title, rows):
    """Rows are (entity, name); name None shows the entity's own friendly name."""
    return {"type": "entities", "title": title,
            "entities": [{"entity": e, "name": n} if n else {"entity": e} for e, n in rows]}

def apex(title, gspan, series, yaxis=None, height=280, cols=12, **kw):
    c = {"type": "custom:apexcharts-card", "graph_span": gspan,
         "header": {"show": True, "title": title, "show_states": True, "colorize_states": True},
         "apex_config": {"chart": {"height": height}, "legend": {"show": True}},
         "series": series, "grid_options": {"columns": cols}}
    if yaxis: c["yaxis"] = yaxis
    c.update(kw)
    return c

def s(e, name, **kw):
    d = {"entity": e, "name": name, "stroke_width": 2}
    d.update(kw)
    return d

HALF = {"grid_options": {"columns": 6}}

overview_md = """\
**District heating** supply **{{ states('sensor.heat_meter_flow_temperature') }} °C** → heat exchanger
→ **V2** valve {{ states('sensor.v2_analog_valve_heating_circuit_1') }} %
→ circuit 1 flow **S3 {{ states('sensor.s3_flow_temperature_sensor_circuit_1') }} °C** (desired {{ states('sensor.desired_flow_temperature_circuit_1') }} °C)
→ pump {{ states('sensor.circulation_pump_flow') | float(0) | round(2) }} m³/h / {{ states('sensor.circulation_pump_power') | float(0) | round(1) }} W
→ """ + settings.get("overview.radiators", "radiators") + """
→ district return **{{ states('sensor.heat_meter_return_temperature') }} °C** (ΔT {{ states('sensor.heat_meter_temperature_difference') }} K)

**DHW branch:** V1 valve {{ states('sensor.v1_analog_valve_dhw_circuit_2') }} % → **S4 {{ states('sensor.s4_dhw_flow_temperature_sensor_circuit_2') }} °C** (desired {{ states('sensor.desired_dhw_flow_temperature_circuit_2') }} °C)

**Outdoor** S1 {{ states('sensor.s1_outdoor_temperature_sensor') }} °C""" + (
    f" (met.no {{{{ state_attr('{WEATHER}', 'temperature') }}}} °C)" if WEATHER else "") + """ ·
**Heating** {{ states('sensor.mode_heating_circuit_1') }} / {{ states('sensor.status_heating_circuit_1') }} ·
**DHW** mode {{ states('sensor.mode_dhw_raw') }} / status {{ states('sensor.status_dhw_raw') }} (raw) ·
**Heat power** {{ states('sensor.heat_meter_power') }} kW"""

meter_flags = ["binary_sensor.heat_meter_alarm", "binary_sensor.heat_meter_error",
               "binary_sensor.heat_meter_permanent_error", "binary_sensor.heat_meter_temporary_error",
               "binary_sensor.heat_meter_power_low"]

# Heated rooms are not listed here: membership is the HA label "Heated room" (label_id heated_room),
# so labelling a new sensor adds it to the statistics, the room table and the room chart.
HEATED_LABEL = settings.get("rooms_label", "heated_room")
heated_rooms_md = """\
{%- set target = states('sensor.desired_room_temperature_circuit_1') | float(0) -%}
{%- set ns = namespace(rows=[]) -%}
{%- for e in label_entities('""" + HEATED_LABEL + """') | select('match', 'sensor[.]') -%}
  {%- set ns.rows = ns.rows + [[area_name(e) or state_attr(e, 'friendly_name'), e]] -%}
{%- endfor %}
| Room | °C | vs. desired |
|---|---:|---:|
{%- for name, e in ns.rows | sort(attribute='0') %}
{%- if states(e) | is_number %}
{%- set d = states(e) | float - target %}
| {{ name }} | {{ states(e) | float | round(1) }} | {{ '%+.1f' | format(d) }} K {{ '▲' if d > 1 else ('▼' if d < -1 else '') }} |
{%- else %}
| {{ name }} | – | |
{%- endif %}
{%- endfor %}

Included: sensors labelled *Heated room* ({{ ns.rows | count }}). ▲▼ = more than 1 K from the desired {{ target }} °C."""

# Room chart series are built in the browser from the entity registry labels (config-template-card
# evals the ${...} body inside the card, where only this.hass, states and user are in scope).
rooms_series_js = (
    "${Object.values(this.hass.entities)"
    ".filter(e => (e.labels || []).includes('" + HEATED_LABEL + "') && e.entity_id.startsWith('sensor.'))"
    ".map(e => { const a = e.area_id || (this.hass.devices[e.device_id] || {}).area_id;"
    " return {entity: e.entity_id, name: (this.hass.areas[a] || {}).name"
    " || (this.hass.states[e.entity_id] || {attributes: {}}).attributes.friendly_name || e.entity_id,"
    " stroke_width: 1, opacity: 0.6, yaxis_id: 'room'}; })"
    ".sort((x, y) => x.name.localeCompare(y.name))"
    ".concat(["
    "{entity: 'sensor.heated_rooms_average_temperature', name: 'Average', stroke_width: 4, yaxis_id: 'room'},"
    "{entity: 'sensor.heated_rooms_minimum_temperature', name: 'Minimum', stroke_width: 3, yaxis_id: 'room'},"
    "{entity: 'sensor.heated_rooms_maximum_temperature', name: 'Maximum', stroke_width: 3, yaxis_id: 'room'},"
    "{entity: 'sensor.s1_outdoor_temperature_sensor', name: 'Outdoor S1', stroke_width: 2, yaxis_id: 'out'}])}"
)
rooms_chart = {
    "type": "custom:config-template-card",
    # re-render when the room set can have changed (the average's 'rooms' count follows the label)
    "entities": ["sensor.heated_rooms_average_temperature"],
    "grid_options": {"columns": 12},
    "card": {
        "type": "custom:apexcharts-card", "graph_span": "48h",
        "header": {"show": True, "title": "Heated rooms vs. outdoor – 48 h", "show_states": False},
        "apex_config": {"chart": {"height": 300}, "legend": {"show": True}},
        "yaxis": [{"id": "room", "decimals": 0}, {"id": "out", "opposite": True, "decimals": 0}],
        "series": rooms_series_js,
    },
}

# Shown, but left out of the statistics: network gear heats the storage, the glass house is half outdoors.
# config other_rooms: [{name: ..., entity: ...}]
OTHER_ROOMS = [(r["name"], r["entity"]) for r in settings.get("other_rooms", [])]


def valve_gauge(entity, title, motion, override, signal_override, hot):
    """Valve opening as a needle gauge: 0 % closed (grey) to 100 % fully open (hot colour)."""
    return {
        "type": "custom:gauge-card-pro", "entity": entity, "min": 0, "max": 100,
        "needle": True, "gradient": True,
        "segments": [{"from": 0, "color": "#9e9e9e"}, {"from": 50, "color": "#ffb74d"}, {"from": 100, "color": hot}],
        "value_texts": {"primary": {"unit_of_measurement": " %"},
                        "secondary": {"value": "{{ states('" + motion + "') }}", "unit_of_measurement": ""}},
        "titles": {"primary": {"value": title},
                   "secondary": {"value": "Override {{ states('" + override + "') }} · signal {{ states('" + signal_override + "') }}"}},
        "grid_options": {"columns": 6, "rows": 3},
    }


CAST_BUTTONS = [] if not (TV and TV_VIEW) else [
        {"type": "button", "name": "Cast to TV", "icon": "mdi:cast", "show_state": False,
         "grid_options": {"columns": 3, "rows": 1},
         "tap_action": {"action": "perform-action", "perform_action": "cast.show_lovelace_view",
                        "data": {"entity_id": TV, "dashboard_path": DASH, "view_path": "tv"}}},
        {"type": "button", "name": "Open full screen", "icon": "mdi:fullscreen", "show_state": False,
         "grid_options": {"columns": 3, "rows": 1},
         "tap_action": {"action": "navigate", "navigation_path": f"/{DASH}/tv"}},
        {"type": "button", "name": "Stop casting", "icon": "mdi:cast-off", "show_state": False,
         "grid_options": {"columns": 3, "rows": 1},
         "tap_action": {"action": "perform-action", "perform_action": "media_player.turn_off",
                        "target": {"entity_id": TV}}}
]
if TV_VIEW and not TV:
    CAST_BUTTONS = [{"type": "button", "name": "Open full screen", "icon": "mdi:fullscreen", "show_state": False,
                     "grid_options": {"columns": 3, "rows": 1},
                     "tap_action": {"action": "navigate", "navigation_path": f"/{DASH}/tv"}}]


sections = [
    # 1. System overview
    {"type": "grid", "column_span": 4, "cards": [
        heading("System overview", "mdi:sitemap"),
        *CAST_BUTTONS,
        {**schematic_card(IMAGE, overlays, width=MAIN_W, height=MAIN_H),
         "visibility": [{"condition": "screen", "media_query": "(min-width: 768px)"}]},
        {**phone_card(IMAGE, overlays, width=MAIN_W, height=MAIN_H),
         "visibility": [{"condition": "screen", "media_query": "(max-width: 767px)"}]},
        {"type": "markdown", "content": overview_md, "grid_options": {"columns": "full"}},
        tile("sensor.s1_outdoor_temperature_sensor", "Outdoor S1", **HALF) | {"grid_options": {"columns": 3}},
        tile("sensor.mode_heating_circuit_1", "Heating mode", grid_options={"columns": 3}),
        tile("sensor.status_heating_circuit_1", "Heating status", grid_options={"columns": 3}),
        tile("sensor.p2_circulation_pump_heating_circuit_1", grid_options={"columns": 3}),
        tile("binary_sensor.circulation_pump_pump_connected", "Pump link", grid_options={"columns": 3}),
        tile("sensor.heat_meter_status_text", "Meter status", grid_options={"columns": 3}),
        tile("binary_sensor.heat_meter_flowing", "District heating flowing", grid_options={"columns": 3}),
        tile("sensor.heat_meter_power", "Heat power", grid_options={"columns": 3}),
        {"type": "conditional",
         "conditions": [{"condition": "or", "conditions": [
             {"condition": "state", "entity": f, "state": "on"} for f in meter_flags]}],
         "card": {"type": "markdown", "grid_options": {"columns": "full"},
                  "content": "⚠️ **Heat meter reports a fault:** {{ "
                      + json.dumps(meter_flags)
                      + " | select('is_state', 'on') | map('replace', 'binary_sensor.heat_meter_', '')"
                        " | map('replace', '_', ' ') | join(', ') }}"}},
    ]},
    # 2. District heating
    {"type": "grid", "cards": [
        heading("District heating (primary)", "mdi:transmission-tower-import"),
        tile("sensor.heat_meter_flow_temperature", "Supply", **HALF),
        tile("sensor.heat_meter_return_temperature", "Return", **HALF),
        tile("sensor.heat_meter_temperature_difference", "ΔT supply–return", **HALF),
        tile("sensor.heat_meter_power", "Power", **HALF),
        tile("sensor.heat_meter_volume_flow", "Volume flow", **HALF),
        tile("binary_sensor.heat_meter_flowing", "Flowing", **HALF),
        entities("Energy & volume", [
            ("sensor.heat_meter_energy_daily", "Energy today"),
            ("sensor.heat_meter_energy_yearly", "Energy this year"),
            ("sensor.heat_meter_total_energy_consumption", "Energy total (meter)"),
            ("sensor.heat_meter_total_energy_consumption_last_month", "Energy last month"),
            ("sensor.heat_meter_prev_1_month", "Previous month (stored)"),
            ("sensor.heat_meter_prev_1_month_date", "Previous month date"),
            ("sensor.heat_meter_max_power_last_month", "Peak power last month"),
            ("sensor.heat_meter_due_energy_consumption", "Annual reading energy"),
            ("sensor.heat_meter_due_date", "Annual reading date"),
            ("sensor.heat_meter_volume_daily", "Volume today"),
            ("sensor.heat_meter_volume_yearly", "Volume this year"),
            ("sensor.heat_meter_total_volume", "Volume total (meter)"),
        ]),
        {"type": "entities", "title": "Meter health", "entities": [
            {"entity": "sensor.heat_meter_status_text", "name": "Meter status"},
            {"entity": "sensor.heat_meter_faults", "name": "Heat meter faults"},
            {"entity": "sensor.heat_meter_timestamp", "name": "Last telegram"},
            {"entity": "sensor.heat_meter_rssi", "name": "Signal (RSSI)"},
            {"entity": "binary_sensor.heat_meter_receiver_running", "name": "wmbusmeters add-on"},
            {"type": "section", "label": "Fault flags (OK = not active)"},
            {"entity": "binary_sensor.heat_meter_error", "name": "Error"},
            {"entity": "binary_sensor.heat_meter_temporary_error", "name": "Temporary error"},
            {"entity": "binary_sensor.heat_meter_permanent_error", "name": "Permanent error"},
            {"entity": "binary_sensor.heat_meter_alarm", "name": "Alarm"},
            {"entity": "binary_sensor.heat_meter_power_low", "name": "Power low"},
            {"entity": "binary_sensor.heat_meter_busy", "name": "Busy"},
        ]},
        apex("Supply, return & ΔT – 7 days", "7d", [
            s("sensor.heat_meter_flow_temperature", "Supply", group_by={"func": "avg", "duration": "30min"}),
            s("sensor.heat_meter_return_temperature", "Return", group_by={"func": "avg", "duration": "30min"}),
            s("sensor.heat_meter_temperature_difference", "ΔT", stroke_width=1, group_by={"func": "avg", "duration": "30min"}),
        ], yaxis=[{"min": 0, "decimals": 0}]),
    ]},
    # 3. Heating circuit 1
    {"type": "grid", "cards": [
        heading("Heating circuit 1 (ECL 310)", "mdi:heating-coil"),
        tile("sensor.s1_outdoor_temperature_sensor", "Outdoor S1", **HALF),
        tile("sensor.s3_flow_temperature_sensor_circuit_1", "Flow S3", **HALF),
        tile("sensor.desired_flow_temperature_circuit_1", "Desired flow", **HALF),
        valve_gauge("sensor.v2_analog_valve_heating_circuit_1", "M2 heating valve",
                    "sensor.m2_motorized_control_valve_circuit_1", "sensor.m2_override", "sensor.v2_override", "#e2000f"),
        tile("sensor.desired_return_temperature_circuit_1", "Return limit", **HALF),
        tile("sensor.desired_room_temperature_circuit_1", "Desired room", **HALF),
        tile("sensor.comfort_temperature", "Comfort", **HALF),
        tile("sensor.setback_temperature", "Setback", **HALF),
        entities("Control & actuators", [
            ("sensor.mode_heating_circuit_1", "Mode"),
            ("sensor.status_heating_circuit_1", "Status"),
            ("sensor.p2_circulation_pump_heating_circuit_1", None),
            ("sensor.p2_override", None),
            ("sensor.m2_motorized_control_valve_circuit_1", "M2 valve"),
            ("sensor.m2_override", "M2 override"),
            ("sensor.v2_override", "V2 signal override"),
            ("sensor.a1_alarm", "ECL alarm"),
        ]),
        apex("Heat curve – 48 h", "48h", [
            s("sensor.desired_flow_temperature_circuit_1", "Desired flow", yaxis_id="t", curve="stepline"),
            s("sensor.s3_flow_temperature_sensor_circuit_1", "Flow S3", yaxis_id="t"),
            s("sensor.circulation_pump_medium_temperature", "Pump medium", yaxis_id="t", stroke_width=1),
            s("sensor.heat_meter_flow_temperature", "Primary supply", yaxis_id="t", stroke_width=1),
            s("sensor.heat_meter_return_temperature", "Primary return", yaxis_id="t", stroke_width=1),
            s("sensor.s1_outdoor_temperature_sensor", "Outdoor", yaxis_id="out", stroke_width=1),
        ], yaxis=[{"id": "t", "decimals": 0, "min": 0},
                  {"id": "out", "opposite": True, "decimals": 0}]),
    ]},
    # 4. Circulation pump
    {"type": "grid", "cards": [
        heading("Circulation pump", "mdi:pump"),
        tile("sensor.circulation_pump_power", "Power", **HALF),
        tile("sensor.circulation_pump_flow", "Flow", **HALF),
        tile("sensor.circulation_pump_head", "Head", **HALF),
        tile("sensor.circulation_pump_speed", "Speed", **HALF),
        tile("sensor.circulation_pump_medium_temperature", "Medium temperature", **HALF),
        tile("binary_sensor.circulation_pump_pump_connected", "Pump link", **HALF),
        entities("Pump details", [
            ("sensor.circulation_pump_temperature_2", "Temperature 2 (unknown)"),
            ("sensor.circulation_pump_temperature_3", "Temperature 3 (unknown)"),
            ("sensor.circulation_pump_energy", "Energy"),
            ("sensor.circulation_pump_operating_time", "Operating time"),
                    ("binary_sensor.circulation_pump_status", "ESP online"),
            ("sensor.circulation_pump_product_type", "Product type"),
            ("sensor.circulation_pump_starts", "Starts"),
    ("sensor.circulation_pump_uptime", "ESP uptime"),
            ("button.circulation_pump_restart", "Restart ESP"),
        ]),
        apex("Pump – 48 h", "48h", [
            s("sensor.circulation_pump_flow", "Flow", yaxis_id="flow"),
            s("sensor.circulation_pump_power", "Power", yaxis_id="w"),
            s("sensor.circulation_pump_medium_temperature", "Medium temp", yaxis_id="t", stroke_width=1),
        ], yaxis=[{"id": "flow", "min": 0, "decimals": 2},
                  {"id": "w", "opposite": True, "min": 0, "decimals": 0},
                  {"id": "t", "opposite": True, "decimals": 0}]),
    ]},
    # 5. DHW
    {"type": "grid", "cards": [
        heading("Domestic hot water (circuit 2)", "mdi:water-boiler"),
        tile("sensor.s4_dhw_flow_temperature_sensor_circuit_2", "DHW S4", **HALF),
        tile("sensor.desired_dhw_flow_temperature_circuit_2", "Desired DHW", **HALF),
        tile("sensor.desired_dhw_return_temperature_circuit_2", "DHW return limit", **HALF),
        valve_gauge("sensor.v1_analog_valve_dhw_circuit_2", "M1 hot water valve",
                    "sensor.m1_motorized_control_valve_circuit_2", "sensor.m1_override", "sensor.v1_override", "#ff6d00"),
        entities("DHW control", [
            ("sensor.mode_dhw_circuit_2", "Mode"),
            ("sensor.status_dhw_circuit_2", "Status"),
            ("sensor.p1_circulation_pump_dhw_circuit_2", None),
            ("sensor.p1_override", None),
            ("sensor.m1_motorized_control_valve_circuit_2", "M1 valve"),
            ("sensor.m1_override", "M1 override"),
            ("sensor.v1_override", "V1 signal override"),
        ]),
        apex("Hot water vs. heat load – 48 h", "48h", [
            s("sensor.s4_dhw_flow_temperature_sensor_circuit_2", "DHW S4", yaxis_id="t"),
            s("sensor.desired_dhw_flow_temperature_circuit_2", "Desired DHW", yaxis_id="t", curve="stepline", stroke_width=1),
            s("sensor.v1_analog_valve_dhw_circuit_2", "M1 valve", yaxis_id="pct", curve="stepline", stroke_width=1),
            s("sensor.heat_meter_power", "Heat power", yaxis_id="kw", type="area", opacity=0.2, stroke_width=1),
        ], yaxis=[{"id": "t", "decimals": 0},
                  {"id": "pct", "min": 0, "max": 100, "decimals": 0, "show": False},
                  {"id": "kw", "opposite": True, "min": 0, "decimals": 1}]),
    ]},
    # 6. Rooms
    {"type": "grid", "cards": [heading("Rooms", "mdi:home-thermometer"),
        tile("sensor.heated_rooms_average_temperature", "Heated rooms, average", **HALF),
        tile("sensor.desired_room_temperature_circuit_1", "Desired room (ECL)", **HALF),
        tile("sensor.heated_rooms_minimum_temperature", "Minimum", **HALF),
        tile("sensor.coldest_heated_room", "Coldest room", **HALF),
        tile("sensor.heated_rooms_maximum_temperature", "Maximum", **HALF),
        tile("sensor.warmest_heated_room", "Warmest room", **HALF),
        {"type": "markdown", "title": "Heated rooms", "content": heated_rooms_md}]
        + ([{"type": "heading", "heading": "Not heated (not in the statistics)", "heading_style": "subtitle"}]
           if OTHER_ROOMS else [])
        + [tile(e, n, **HALF) for n, e in OTHER_ROOMS]
        + [rooms_chart]},
    # 7. Energy history
    {"type": "grid", "column_span": 2, "cards": [
        heading("Energy history", "mdi:chart-bar"),
        apex("Daily heat energy vs. outdoor – 30 days", "30d", [
            {"entity": "sensor.heat_meter_total_energy_consumption", "name": "Heat energy",
             "type": "column", "yaxis_id": "kwh",
             "statistics": {"type": "change", "period": "day", "align": "start"},
             "show": {"in_header": False}},
            {"entity": "sensor.s1_outdoor_temperature_sensor", "name": "Outdoor mean",
             "type": "line", "yaxis_id": "c", "stroke_width": 2,
             "statistics": {"type": "mean", "period": "day", "align": "start"},
             "show": {"in_header": False}},
        ], yaxis=[{"id": "kwh", "min": 0, "decimals": 0},
                  {"id": "c", "opposite": True, "decimals": 0}],
            height=300, span={"end": "day"},
            header={"show": True, "title": "Daily heat energy vs. outdoor – 30 days"}),
        apex("Pump energy per day – 30 days", "30d", [
            {"entity": "sensor.circulation_pump_energy", "name": "Pump energy", "type": "column",
             "float_precision": 3,
             "statistics": {"type": "change", "period": "day", "align": "start"},
             "show": {"in_header": False}},
        ], yaxis=[{"min": 0, "decimals": 2}], height=220, span={"end": "day"},
            header={"show": True, "title": "Pump energy per day – 30 days"}),
    ]},
]

# config network_tracker: a device_tracker for the controller (e.g. from UniFi) adds network rows.
TRACKER = settings.get("network_tracker")
controller_md = ("""\
{%- set t = '""" + TRACKER + """' -%}
""" if TRACKER else "") + """| | |
|---|---|
""" + ("""| Network (UniFi) | {{ 'Connected' if is_state(t, 'home') else 'Not connected' }} |
| IP address | {{ state_attr(t, 'ip') }} (VLAN {{ state_attr(t, 'vlan') }}) |
| MAC address | {{ state_attr(t, 'mac') }} ({{ state_attr(t, 'oui') }}) |
""" if TRACKER else "") + """| Modbus TCP | """ + ("{{ state_attr('binary_sensor.ecl_modbus_online', 'host') }}: " if settings.get("modbus_host_attribute") else "") + """**{{ 'online' if is_state('binary_sensor.ecl_modbus_online', 'on') else 'offline' }}** |
| Controller time | {{ states('sensor.ecl_controller_time') }} |
| Application | {{ states('sensor.ecl_application') }} |
| Firmware | {{ states('sensor.ecl_firmware_version') }} |"""
controller_card = {"type": "markdown", "title": "ECL 310 controller", "content": controller_md}

tv_view = {"title": "TV", "path": "tv", "icon": "mdi:television", "type": "panel", "subview": True,
           "cards": [unclamp(schematic_card(TV_IMAGE, tv_overlays, width=TV_W, height=TV_H, boost=1.1))]}


# --- Views: the sections above are regrouped into perspectives -------------------------------------
def title_of(c):
    return (c.get("heading") or c.get("title") or c.get("name") or (c.get("header") or {}).get("title")
            or ((c.get("card") or {}).get("header") or {}).get("title") or "")


def take(sec, *titles):
    """Cards of a section whose title starts with any of `titles` (order kept)."""
    return [c for c in sections[sec]["cards"] if any(title_of(c).startswith(x) for x in titles)]


def drop(sec, *titles):
    return [c for c in sections[sec]["cards"] if not any(title_of(c).startswith(x) for x in titles)]


def view(title, path, icon, secs, max_columns=3):
    return {"title": title, "path": path, "icon": icon, "type": "sections", "max_columns": max_columns,
            "sections": secs}


def grid(*cards, span=None):
    s = {"type": "grid", "cards": list(cards)}
    if span: s["column_span"] = span
    return s


# warnings: anything that needs a look, shown on the overview only while it is true
# warnings: anything that needs a look, shown on the overview only while it is true
PROBLEMS = ["binary_sensor.ecl_alarm", "binary_sensor.m1_manual_override", "binary_sensor.m2_manual_override",
            "binary_sensor.p1_manual_override", "binary_sensor.p2_manual_override",
            "binary_sensor.a1_manual_override"] + [f for f in meter_flags if settings.enabled(f)]
warn_conditions = (
    [{"condition": "state", "entity": e, "state": "on"} for e in PROBLEMS]
    + [c for c in [{"condition": "state", "entity": "binary_sensor.ecl_modbus_online", "state": "off"},
       {"condition": "state", "entity": "binary_sensor.circulation_pump_pump_connected", "state": "off"},
       {"condition": "state", "entity": "sensor.heat_meter_status_text", "state_not": "OK"}] if settings.enabled(c["entity"])])
warn_md = """\
⚠️ **Heating system needs attention**
{%- for e in """ + json.dumps(PROBLEMS) + """ if is_state(e, 'on') %}
- {{ state_attr(e, 'friendly_name') }}
{%- endfor %}
{%- if is_state('binary_sensor.ecl_modbus_online', 'off') %}
- ECL 310 is not answering on Modbus
{%- endif %}""" + ("""
{%- if is_state('binary_sensor.circulation_pump_pump_connected', 'off') %}
- Circulation pump link (ESPHome) is down
{%- endif %}""" if settings.feature("circulation_pump") else "") + ("""
{%- if not is_state('sensor.heat_meter_status_text', 'OK') %}
- Heat meter status: {{ states('sensor.heat_meter_status_text') }}
{%- endif %}""" if settings.feature("heat_meter") else "")
warning_card = {"type": "conditional", "conditions": [{"condition": "or", "conditions": warn_conditions}],
                "card": {"type": "markdown", "content": warn_md}}

overview_cards = [c for c in sections[0]["cards"]
                  if c["type"] in ("heading", "button", "picture-elements")]
headline = [
    tile("sensor.s1_outdoor_temperature_sensor", "Outdoor"),
    tile("sensor.heated_rooms_average_temperature", "Rooms average"),
    tile("sensor.heat_meter_power", "Heat power"),
    tile("sensor.heat_meter_energy_daily", "Heat energy today"),
    tile("sensor.mode_heating_circuit_1", "Heating mode"),
    tile("sensor.status_heating_circuit_1", "Heating status"),
    tile("sensor.circulation_pump_power", "Pump power"),
    tile("sensor.s4_dhw_flow_temperature_sensor_circuit_2", "Hot water"),
]
for c in headline:
    c["grid_options"] = {"columns": 3}

pump_extra = [tile("sensor.circulation_pump_energy", "Energy", **HALF),
              tile("sensor.circulation_pump_operating_time", "Operating time", **HALF)]
raw_registers = entities("ECL raw registers (7-day history)", [
    ("sensor.m2_opening", "M2 opening (PNU 4002)"), ("sensor.m2_closing", "M2 closing (PNU 4003)"),
    ("sensor.m1_opening", "M1 opening (PNU 4000)"), ("sensor.m1_closing", "M1 closing (PNU 4001)"),
    ("sensor.p2_circulation_pump_heating_raw", "P2 relay (PNU 4007)"),
    ("sensor.p1_circulation_pump_dhw_raw", "P1 relay (PNU 4006)"),
    ("sensor.a1_alarm_raw", "A1 alarm (PNU 4009)"),
    ("sensor.m2_override_raw", "M2 override (PNU 4062)"), ("sensor.m2_override_2_raw", "V2 override (PNU 4077)"),
    ("sensor.m1_override_raw", "M1 override (PNU 4060)"), ("sensor.m1_override_2_raw", "V1 override (PNU 4076)"),
    ("sensor.p2_override_raw", "P2 override (PNU 4067)"), ("sensor.p1_override_raw", "P1 override (PNU 4066)"),
    ("sensor.a1_override_raw", "A1 override (PNU 4069)"),
    ("sensor.mode_heating_raw", "Mode circuit 1 (PNU 4201)"), ("sensor.status_heating_raw", "Status circuit 1 (PNU 4211)"),
    ("sensor.mode_dhw_raw", "Mode circuit 2 (PNU 4202)"), ("sensor.status_dhw_raw", "Status circuit 2 (PNU 4212)"),
])
# starts/voltage/current exist but are disabled in the entity registry
pump_diag = entities("Circulation pump (ESPHome)", [
    ("binary_sensor.circulation_pump_status", "ESP online"),
    ("binary_sensor.circulation_pump_pump_connected", "Pump link"),
    ("sensor.circulation_pump_speed", "Speed"),
    ("sensor.circulation_pump_temperature_2", "Temperature 2 (unknown)"),
    ("sensor.circulation_pump_temperature_3", "Temperature 3 (unknown)"),
    ("sensor.circulation_pump_starts", "Starts"),
    ("sensor.circulation_pump_product_type", "Product type"),
    ("sensor.circulation_pump_starts", "Starts"),
    ("sensor.circulation_pump_uptime", "ESP uptime"),
    ("button.circulation_pump_restart", "Restart ESP"),
])

views = [
    view("Overview", "overview", "mdi:view-dashboard",
         [grid(*overview_cards, warning_card, span=4), grid(*headline, span=4)], max_columns=4),
    view("Space heating", "space-heating", "mdi:radiator",
         [grid(*drop(2, "ECL 310 controller")),
          grid(*[c for c in drop(3, "Pump details")
                 if not (c["type"] == "tile" and c.get("name") == "Pump link")][:6], *pump_extra,
               *[c for c in drop(3, "Pump details") if c["type"] != "tile" and c["type"] != "heading"])]),
] + ([view("Rooms", "rooms", "mdi:home-thermometer", [grid(*sections[5]["cards"], span=2)], max_columns=2)]
       if settings.feature("rooms") else []) + [
    view("Hot water", "hot-water", "mdi:water-boiler", [grid(*sections[4]["cards"], span=2)], max_columns=2),
] + ([view("District heating", "district-heating", "mdi:transmission-tower-import",
         [grid(*drop(1, "Meter health")), grid(*[c for c in sections[6]["cards"]], span=2)])]
       if settings.feature("heat_meter") else []) + [
    view("Diagnostics", "diagnostics", "mdi:wrench",
         [grid(heading("ECL 310", "mdi:chip"), controller_card, raw_registers),
          *([grid(heading("Heat meter", "mdi:meter-electric"), *take(1, "Meter health"))]
            if settings.feature("heat_meter") else []),
          grid(heading("Circulation pump", "mdi:pump"), pump_diag)]),
] + ([tv_view] if TV_VIEW else [])
config = {"title": "Heating", "views": views}

config = prune.prune(config)
config = json.loads(settings.rename(json.dumps(config, ensure_ascii=False)))

# entity check (optional --states dump)
if ARGS.states:
    ha = json.load(open(ARGS.states))
    known = {e["entity_id"] for e in ha.get("entities", [])} | {s["entity_id"] for s in ha.get("states", [])}
else:
    ha, known = {"entities": []}, None
found, missing = set(), set()
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "entity" and isinstance(v, str): (found if known is None or v in known else missing).add(v)
            walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(config)
import re
for e in set(re.findall(r"(?:sensor|binary_sensor|weather)\.[a-z0-9_]+", json.dumps(config))):
    (found if known is None or e in known else missing).add(e)
print("entities referenced:", len(found | missing), "missing:", sorted(missing) if known is not None else "(not checked, no --states)")
disabled = {e["entity_id"] for e in ha["entities"] if e.get("disabled_by")}
if disabled:
    print("disabled (will show unavailable):", sorted(found & disabled))
cards = 0
def count(o):
    global cards
    if isinstance(o, dict):
        if "type" in o and isinstance(o["type"], str) and (o["type"] in ("tile","heading","markdown","entities","conditional") or o["type"].startswith("custom:")): cards += 1
        for v in o.values(): count(v)
    elif isinstance(o, list):
        for v in o: count(v)
count(config)
print("cards:", cards)

class D(yaml.SafeDumper): pass
D.add_representer(str, lambda d, v: d.represent_scalar("tag:yaml.org,2002:str", v, style="|" if "\n" in v else None))
with open(OUT_DIR / "heating-dashboard.yaml", "w") as f:
    f.write(f"# Heating dashboard (url_path {DASH}), storage mode.\n# Generated by dashboard/generator/build.py.\n")
    yaml.dump(config, f, Dumper=D, sort_keys=False, allow_unicode=True, width=120)
json.dump(config, open(OUT_DIR / "heating-dashboard.json", "w"))
print("written to", OUT_DIR)
if missing: sys.exit(1)
