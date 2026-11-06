"""Dynamic pipe colours on a scale between the district return (min, blue) and supply (max, red).

Card conditions can't interpolate, so HA template helpers (HA_TEMPLATES, to go into ecl310.yaml) give the coloured
temperatures their position on the scale in 10 % steps; every pipe overlay is shown for one combination of steps.
"""
import direct_heating as dh

# Ramp (red -> orange -> blue). Re-balanced after a full-open test ("too much blue,
# red/orange too late"): 0-15 % Danfoss blue, 15-30 % light blue, then warm from 30 %: peach -> orange at 50 % ->
# red-orange at 75 % -> Danfoss red. Blue never blends into orange (that passes through grey, reserved for stale data).
SPLIT = 0.3
COLD = [(0.0, (31, 97, 163)), (0.15, (31, 97, 163)), (SPLIT, (156, 196, 228))]
WARM = [(SPLIT, (246, 184, 112)), (0.5, (239, 112, 35)), (0.75, (232, 64, 26)), (1.0, (226, 0, 15))]
GREY = "#9e9e9e"


def colour_at(p):
    """Colour for scale position p (0 = return, 1 = supply)."""
    p = min(max(p, 0.0), 1.0)
    anchors = COLD if p < SPLIT else WARM
    for (p0, c0), (p1, c1) in zip(anchors, anchors[1:]):
        if p <= p1:
            f = (p - p0) / (p1 - p0) if p1 > p0 else 0
            return "#%02x%02x%02x" % tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return "#%02x%02x%02x" % anchors[-1][1]


STEPS = list(range(0, 101, 10))
RAMP = [colour_at(s / 100) for s in STEPS]

RET, SUP = "sensor.heat_meter_return_temperature", "sensor.heat_meter_flow_temperature"
# Cold end of the scale. Default: district return. variant.scale_min: room uses the heated-room average instead, so radiator
# water a little above the return still shows warm.
import settings as _settings
if _settings.get("variant.scale_min") == "room":
    RET = "sensor.heated_rooms_average_temperature"
S3 = "sensor.s3_flow_temperature_sensor_circuit_1"
Q_PUMP, Q_IN = "sensor.circulation_pump_flow", "sensor.heat_meter_volume_flow"
V1 = "sensor.v1_analog_valve_dhw_circuit_2"
EST = "sensor.radiator_loop_return_estimated"
MID = "sensor.pipe_scale_mid_temperature"
POS = {S3: "sensor.pipe_scale_s3", EST: "sensor.pipe_scale_loop_return"}
MIN_SPAN = 10  # K: a narrower supply-return span is widened around its midpoint

_SCALE = (f"{{% set r, s = states('{RET}') | float(none), states('{SUP}') | float(none) %}}"
          "{% if r is not none and s is not none %}{% set m = (r + s) / 2 %}"
          f"{{% set h = ([s - r, {MIN_SPAN}] | max) / 2 %}}{{% set lo, hi = m - h, m + h %}}{{% endif %}}")


def _pos_template(src):
    return (_SCALE + f"{{% set v = states('{src}') | float(none) %}}"
            "{{ ((([[v, lo] | max, hi] | min) - lo) / (hi - lo) * 10) | round(0) | int * 10 "
            "if v is not none and r is not none and s is not none else none }}")


HA_TEMPLATES = f'''
      # Radiator loop return, estimated from the mixing balance at T1 (no sensor in the bypass):
      #   Q_pump * S3 = Q_in * T_supply + (Q_pump - Q_in) * T_bypass
      # Q_in is the heat meter flow, which also contains the DHW flow. With Q_in >= Q_pump the bypass carries no
      # flow, so the loop return is the measured district return; while hot water is drawn (V1 open) the last
      # value is held.
      - name: "Radiator Loop Return Estimated"
        unique_id: radiator_loop_return_estimated
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
        availability: >
          {{{{ [states('{Q_PUMP}'), states('{Q_IN}'), states('{S3}'), states('{SUP}'), states('{RET}')]
             | select('is_number') | list | count == 5 }}}}
        state: >
          {{% set qp, qi = states('{Q_PUMP}') | float, states('{Q_IN}') | float %}}
          {{% set s3, sup, ret = states('{S3}') | float, states('{SUP}') | float, states('{RET}') | float %}}
          {{% if states('{V1}') | float(0) > 0 %}}{{{{ this.state if this.state | is_number else none }}}}
          {{% elif qi >= qp %}}{{{{ ret | round(1) }}}}
          {{% else %}}{{{{ ([[ (qp * s3 - qi * sup) / (qp - qi), ret ] | max, s3] | min) | round(1) }}}}{{% endif %}}
        attributes:
          held: "{{{{ states('{V1}') | float(0) > 0 }}}}"
          mode: >
            {{{{ 'held' if states('{V1}') | float(0) > 0 else ('measured' if states('{Q_IN}') | float(0)
                 >= states('{Q_PUMP}') | float(0) else 'estimated') }}}}
          formula: "(Q_pump*S3 - Q_in*T_supply) / (Q_pump - Q_in), clamped to [return, S3]"
          note: >-
            Q_in is the heat meter flow (includes DHW). No bypass flow (Q_in >= Q_pump): the loop return is the
            measured district return. Held at the last value while hot water is drawn (V1 open).

      # Middle of the pipe colour scale (legend), and positions on it (return = 0, supply = 100) in 10 % steps.
      # Scale span at least {MIN_SPAN} K, widened around the midpoint.
      - name: "Pipe Scale Mid Temperature"
        unique_id: pipe_scale_mid_temperature
        unit_of_measurement: "°C"
        state: "{_SCALE}{{{{ m | round(1) if r is not none and s is not none else none }}}}"
''' + "".join(f'''
      - name: "Pipe Scale {name}"
        unique_id: pipe_scale_{key}
        state: "{_pos_template(src)}"
''' for src, name, key in [(S3, "S3", "s3"), (EST, "Loop Return", "loop_return")])


def mock_states(st, previous=None):
    """Same maths in Python, so previews can be rendered before the helpers exist in HA."""
    def f(e):
        try:
            return float(st[e])
        except (KeyError, ValueError):
            return None
    qp, qi, s3, sup, ret, v1 = f(Q_PUMP), f(Q_IN), f(S3), f(SUP), f(RET), f(V1) or 0
    out = {}
    if None not in (qp, qi, s3, sup, ret):
        if v1 > 0:
            if previous is not None:
                out[EST] = str(previous)  # held during a DHW draw
        elif qi >= qp:
            out[EST] = str(round(ret, 1))  # no bypass flow: measured return
        else:
            out[EST] = str(round(min(max((qp * s3 - qi * sup) / (qp - qi), ret), s3), 1))
    if None not in (sup, ret):
        m = (sup + ret) / 2
        h = max(sup - ret, MIN_SPAN) / 2
        lo, hi = m - h, m + h
        out[MID] = str(round(m, 1))
        for src, pos in POS.items():
            v = f(src) if src != EST else (float(out[EST]) if EST in out else None)
            if v is not None:
                out[pos] = str(int(round((min(max(v, lo), hi) - lo) / (hi - lo) * 10)) * 10)
    return out


def _cond(pos, step):
    return {"condition": "state", "entity": pos, "state": str(step)}


# Mixed water from T1 through S3 and P2 along the loop to the radiator outlet tee, incl. the radiator inlet stub.
LOOP_HOT = f"M {dh.BYPASS_X} 160 L 780 160 M 820 160 L {dh.LOOP_OUTLET_X} 160 M 920 160 L 920.5 207 L 950 207"
OUTLET_STUB = f"M 1130 275.71 L {dh.LOOP_OUTLET_X}.5 275.7 L {dh.LOOP_OUTLET_X} 160"
# After the radiator outlet the loop cools: dashed top + right side, dashed then solid bottom run back to T2.
_TOP = f"M {dh.LOOP_OUTLET_X} 160 L {dh.LOOP_RIGHT_X + 2.5} 160"  # overlaps the corner by half a stroke
_RIGHT = f"M {dh.LOOP_RIGHT_X} 157.5 L {dh.LOOP_RIGHT_X} 322.5"
_BOTTOM_DASHED = f"M {dh.LOOP_RIGHT_X + 2.5} 320 L {dh.LOOP_DASH_END_X} 320"
_BOTTOM_SOLID = dh.LOOP_RETURN_D  # LOOP_DASH_END_X -> T2
CIRCUIT_RETURN = f"M {dh.BYPASS_X} 320 L 325 320 M 275 320 L 80 320"  # T2 -> M2 -> DHW-return junction
RADIATORS = 8
_LEN_TOP = dh.LOOP_RIGHT_X - dh.LOOP_OUTLET_X
_LEN_RIGHT = 160
_LEN_BOTTOM = dh.LOOP_RIGHT_X - dh.BYPASS_X
_LEN = _LEN_TOP + _LEN_RIGHT + _LEN_BOTTOM


DASHED_DARKEN = 0.25  # the dashed (unshown) loop part is drawn a bit darker so the light steps stay visible


def darker(hex_colour, amount):
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(c * (1 - amount)) for c in (r, g, b))


def _grad(gid, x1, y1, x2, y2, p1, p2, samples=12, darken=0.0):
    """Gradient from scale position p1 to p2, sampled so it follows the ramp (no straight RGB blend)."""
    stops = "".join(f'<stop offset="{k / samples:.3f}" '
                    f'stop-color="{darker(colour_at(p1 + (p2 - p1) * k / samples), darken)}"/>'
                    for k in range(samples + 1))
    return (f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
            f'{stops}</linearGradient>')


def _loop_svg(p_s3, p_est):
    """All circuit-1 pipe colours for S3 at p_s3 and the loop return estimate at p_est (0..1)."""
    at = lambda frac: p_s3 + (p_est - p_s3) * frac  # scale position; temperature falls linearly along the loop
    f0 = 1 / RADIATORS                                          # the drawn radiator is the first of eight
    f1 = f0 + (1 - f0) * _LEN_TOP / _LEN
    f2 = f0 + (1 - f0) * (_LEN_TOP + _LEN_RIGHT) / _LEN
    hot, est = colour_at(p_s3), colour_at(p_est)
    # the three dashed pieces continue one dash pattern (same as the single dashed path in the drawing);
    # the right and bottom pieces start half a stroke before their corner, hence the - 2.5
    dash = lambda offset: f'stroke-dasharray="{dh.LOOP_DASH}" stroke-dashoffset="{offset}"'
    return (
        "<defs>"
        + _grad("t", dh.LOOP_OUTLET_X, 0, dh.LOOP_RIGHT_X, 0, at(f0), at(f1), darken=DASHED_DARKEN)
        + _grad("v", 0, 160, 0, 320, at(f1), at(f2), darken=DASHED_DARKEN)
        + _grad("bd", dh.LOOP_RIGHT_X, 0, dh.BYPASS_X, 0, at(f2), p_est, darken=DASHED_DARKEN)
        + _grad("b", dh.LOOP_RIGHT_X, 0, dh.BYPASS_X, 0, at(f2), p_est)
        + _grad("y", 0, 320, 0, 160, p_est, p_s3)
        + "</defs>"
        f'<path d="{LOOP_HOT}" fill="none" stroke="{hot}" stroke-width="5"/>'
        f'<path d="{OUTLET_STUB}" fill="none" stroke="{colour_at(at(f0))}" stroke-width="5"/>'
        f'<path d="{_TOP}" fill="none" stroke="url(#t)" stroke-width="5" {dash(0)}/>'
        f'<path d="{_RIGHT}" fill="none" stroke="url(#v)" stroke-width="5" {dash(_LEN_TOP - 2.5)}/>'
        f'<path d="{_BOTTOM_DASHED}" fill="none" stroke="url(#bd)" stroke-width="5" {dash(_LEN_TOP + _LEN_RIGHT - 2.5)}/>'
        f'<path d="{_BOTTOM_SOLID}" fill="none" stroke="url(#b)" stroke-width="5"/>'
        f'<path d="{dh.BYPASS_D}" fill="none" stroke="url(#y)" stroke-width="5"/>'
        f'<path d="{CIRCUIT_RETURN}" fill="none" stroke="{est}" stroke-width="5"/>')


def overlays(svg, overlay, uri, root):
    s3p, estp = POS[S3], POS[EST]
    out = []
    for i in STEPS:
        for j in STEPS:
            if j > i:
                continue  # the estimate is clamped to <= S3
            out.append(overlay(uri(root, _loop_svg(i / 100, j / 100)), [_cond(s3p, i), _cond(estp, j)]))
    grey = (f'<path d="{LOOP_HOT} {OUTLET_STUB} {_TOP} {_RIGHT} {_BOTTOM_DASHED} {_BOTTOM_SOLID} '
            f'{dh.BYPASS_D} {CIRCUIT_RETURN}" fill="none" stroke="{GREY}" stroke-width="5"/>')
    out.append(overlay(uri(root, grey), [{"condition": "or", "conditions": [
        {"condition": "state", "entity": e, "state": ["unavailable", "unknown"]} for e in (s3p, estp)]}]))
    return out


LEGEND_X0, LEGEND_X1 = 280, 440  # empty area under the controller, above the district supply inlet
LEGEND_Y = 110


def legend_svg():
    """Colour bar baked into the drawing."""
    # hot (supply) on the left, cold (return) on the right
    stops = "".join(f'<stop offset="{k / 40:.3f}" stop-color="{colour_at(1 - k / 40)}"/>' for k in range(41))
    return (f'<defs><linearGradient id="legend" x1="0" y1="0" x2="1" y2="0">{stops}</linearGradient></defs>'
            f'<rect x="{LEGEND_X0}" y="{LEGEND_Y - 5}" width="{LEGEND_X1 - LEGEND_X0}" height="10" rx="2" '
            f'fill="url(#legend)"/>')


# --- Fixed scale (variant.fixed_scale): a colour always means the same temperature ---
FIXED_LO, FIXED_HI = 30.0, 60.0
_STEP_K = (FIXED_HI - FIXED_LO) / 10
DISTRICT_SUPPLY_D = (f"M 40 160 L {dh.BYPASS_X} 160 M 240 160 L 240 310 M 240 330 L 240 480 L 480 480")
DISTRICT_OUT_D = "M 80 320 L 40 320"  # after the DHW primary return has joined: the heat meter return
NOFLOW_GREY = bool(_settings.get("variant.noflow_grey", True))  # see schematic.py
METER_LIVE = {"condition": "numeric_state", "entity": "sensor.heat_meter_volume_flow", "above": 0}
METER_STALE = {"condition": "or", "conditions": [
    {"condition": "numeric_state", "entity": "sensor.heat_meter_volume_flow", "below": 0.0005},
    {"condition": "state", "entity": "sensor.heat_meter_volume_flow", "state": ["unavailable", "unknown"]}]}


def _band(entity, step):
    """Condition: entity's temperature rounds to this 10 % step of the fixed scale (ends open)."""
    c = {"condition": "numeric_state", "entity": entity}
    t = FIXED_LO + step / 10 * _STEP_K
    if step > 0:
        c["above"] = round(t - _STEP_K / 2, 2)
    if step < 100:
        c["below"] = round(t + _STEP_K / 2, 2)
    return c


def fixed_overlays(svg, overlay, uri, root):
    out = []
    for i in STEPS:
        for j in STEPS:
            if j > i:
                continue  # the estimate is clamped to <= S3
            out.append(overlay(uri(root, _loop_svg(i / 100, j / 100)), [_band(S3, i), _band(EST, j)]))
        c = colour_at(i / 100)
        out.append(overlay(uri(root, f'<path d="{DISTRICT_SUPPLY_D}" fill="none" stroke="{c}" stroke-width="5"/>'),
                           [_band(SUP, i)] + ([METER_LIVE] if NOFLOW_GREY else [])))
        out.append(overlay(uri(root, f'<path d="{DISTRICT_OUT_D}" fill="none" stroke="{c}" stroke-width="5"/>'),
                           [_band(RET, i)] + ([METER_LIVE] if NOFLOW_GREY else [])))
    # the heat meter sends nothing while there is no flow: its temperatures are frozen, so its pipes go grey
    if NOFLOW_GREY:
        out.append(overlay(uri(root, f'<path d="{DISTRICT_SUPPLY_D} {DISTRICT_OUT_D}" fill="none" stroke="{GREY}" '
                                     f'stroke-width="5"/>'), [METER_STALE]))
    grey = (f'<path d="{LOOP_HOT} {OUTLET_STUB} {_TOP} {_RIGHT} {_BOTTOM_DASHED} {_BOTTOM_SOLID} '
            f'{dh.BYPASS_D} {CIRCUIT_RETURN}" fill="none" stroke="{GREY}" stroke-width="5"/>')
    out.append(overlay(uri(root, grey), [{"condition": "or", "conditions": [
        {"condition": "state", "entity": e, "state": ["unavailable", "unknown"]} for e in (S3, EST)]}]))
    return out


def fixed_legend_text():
    """Static legend values (hot -> cold, left to right), baked into the drawing."""
    y = LEGEND_Y + 5
    mid = (FIXED_LO + FIXED_HI) / 2
    return (f'<g font-family="Roboto, Arial, Helvetica, sans-serif" font-size="12px" fill="#333">'
            f'<text x="{LEGEND_X0 - 6}" y="{y}" text-anchor="end">{FIXED_HI:.0f} °C</text>'
            f'<text x="{LEGEND_X1 + 6}" y="{y}" text-anchor="start">{FIXED_LO:.0f} °C</text>'
            f'<text x="{(LEGEND_X0 + LEGEND_X1) / 2}" y="{y + 16}" text-anchor="middle">{mid:.0f} °C</text></g>')
