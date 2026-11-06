# Heating dashboards

**Two ways to see your ECL 310 at a glance: a ready-made starter dashboard, or the full schematic dashboard built
from the Danfoss drawing of your own system.**

![Schematic dashboard, overview](screenshots/overview-desktop.png)

| Space heating view | Phone | TV view |
|---|---|---|
| ![Space heating view](screenshots/space-heating-desktop.png) | ![Overview on a phone](screenshots/overview-phone.png) | ![TV view](screenshots/tv.png) |

<sub>The author's schematic dashboard, with every option on (heat meter, circulation pump, rooms, direct heating).
Drawing © Danfoss; values live from the author's ECL 310.</sub>

| | Starter | Schematic |
|---|---|---|
| What | Tiles, history and a simple schematic | The Danfoss A266 diagram with live values, coloured pipes, turning pumps, warnings, trend charts, views per circuit and a TV view |
| How | A ready-made file you paste in | **Generated**: a script builds it from your copy of the drawing and a config file |
| Needs | [`packages/ecl310.yaml`](../packages/ecl310.yaml) | That package, [`packages/heating_rooms.yaml`](../packages/heating_rooms.yaml), Python 3.10+, three HACS cards and your copy of the Danfoss drawing |

## Starter dashboard

1. Install [`packages/ecl310.yaml`](../packages/ecl310.yaml) (see the [main README](../README.md#quick-start)) and
   check that its entities have values.
2. Settings → Dashboards → **Add dashboard** → *New dashboard from scratch*, and give it a name.
3. Open it, then ⋮ → **Edit dashboard** → ⋮ → **Raw configuration editor**. Replace the contents with
   [`starter-dashboard.yaml`](starter-dashboard.yaml) and save.

The first card shows the Danfoss drawing from `/config/www/ecl310/a266.svg`. If you don't have it (see
[Get the drawing](#2-get-the-drawing)), delete that card.

## Schematic dashboard

The schematic dashboard isn't shipped as a finished file, for two reasons. Its pump, valve and pipe overlays are
cut from the Danfoss drawing, which is Danfoss's copyright. And a finished file only fits one house. Instead, the
[`generator/`](generator/) builds it for you. The author's own dashboard is built the same way.

All commands below run in the `dashboard/` folder of a clone of this repository.

### 1. Set up Python

You need Python 3.10 or newer.

```bash
git clone https://github.com/muddermanden/homeassistant-danfoss-ecl310.git
cd homeassistant-danfoss-ecl310/dashboard
python3 -m venv .venv
.venv/bin/pip install -r generator/requirements.txt
cp config.example.yaml config.local.yaml
```

`config.local.yaml` is yours and git-ignored. The defaults work for an ECL with nothing extra attached.

### 2. Get the drawing

The drawing isn't in this repository. Save your own copy from the Danfoss **Leanheat Monitor** web app, which
shows the diagram of your controller:

1. Open Leanheat Monitor in a desktop browser and go to your ECL 310's schematic (system diagram).
2. Press **F12** to open the developer tools, and select the **Network** tab.
3. Reload the page (Cmd/Ctrl + R), so the browser records the requests.
4. Type `svg` in the filter box. Click the request with the diagram, for example `A266_1…svg`, and save the
   response: right-click → *Open in new tab*, then save the page.
5. Save it as `drawings/A266.1a.svg`. The `drawings/` folder is git-ignored.
6. Clean it. This removes the empty value fields (`--,-- °C`, `1st Jan 1970`) where Home Assistant will show live
   values, and names the two circuits:

   ```bash
   .venv/bin/python generator/clean_drawing.py drawings/A266.1a.svg drawings/a266.svg --config config.local.yaml
   ```

   It should say `placeholders left: 0`.

Keep the drawing for your own use, and don't publish it.

The generator is made for the 1205 × 756 px **A266.1 "ex. a"** drawing. Another A266 variant draws things in other
places; see [Adapting to another drawing](#adapting-to-another-drawing).

### 3. Prepare Home Assistant

- **Packages:** install [`packages/ecl310.yaml`](../packages/ecl310.yaml) and
  [`packages/heating_rooms.yaml`](../packages/heating_rooms.yaml) in `/config/packages/`. `heating_rooms.yaml` is a
  small helper package, not a dashboard. The schematic uses its *Heating Dashboard Text* sensor for fixed labels, and
  its room statistics when `features.rooms` is on.
  [`packages/ecl310_extras.yaml`](../packages/ecl310_extras.yaml) is only needed with a heat meter.
- **HACS cards:** install these from HACS → Frontend:
  [apexcharts-card](https://github.com/RomRider/apexcharts-card) (charts),
  [gauge-card-pro](https://github.com/benjamin-dcs/gauge-card-pro) (valve gauges) and, only with `features.rooms`,
  [config-template-card](https://github.com/iantrich/config-template-card).
- **Rooms (optional):** to include room temperatures, create the label *Heated room* (Settings → Areas, labels &
  zones → Labels) and add it to the temperature sensor of each heated room.

Restart Home Assistant after adding packages.

### 4. Configure

Open `config.local.yaml`. Every setting is explained in the file; these are the ones you're most likely to change:

| Setting | What it does |
|---|---|
| `features.heat_meter`, `features.circulation_pump`, `features.rooms` | Turn on the parts you have. Off leaves out every card, value and colour rule that needs them |
| `entities` | Map the generator's entity ids to yours (see below) |
| `variant.direct_heating` | Redraws circuit 1 as direct heating with a mixing loop, as in the author's house. Off keeps the original drawing |
| `tv.view`, `tv.media_player` | A full-screen TV view, and *Cast to TV* buttons for that media player |
| `weather`, `network_tracker`, `other_rooms` | Optional extras for the overview, diagnostics and rooms views |
| `heat_cut_out_c` | Your ECL *heat cut-out* temperature. Above it, the schematic says space heating is off for summer |

The generator uses the package's ids for the ECL, and generic ids for the optional hardware:
`sensor.heat_meter_*` for the heat meter and `sensor.circulation_pump_*` for the pump. If your ids differ, map
them:

```yaml
entities:
  exact:
    binary_sensor.heat_meter_flowing: binary_sensor.my_meter_flowing
  prefixes:
    sensor.heat_meter_: sensor.my_meter_          # sensor.heat_meter_power -> sensor.my_meter_power
    sensor.circulation_pump_: sensor.grundfos_
```

### 5. Build

```bash
.venv/bin/python generator/build.py --config config.local.yaml
```

It writes three files to `build/` (git-ignored):

| File | What |
|---|---|
| `heating-dashboard.yaml` | The dashboard (a `.json` copy is written too) |
| `a266-schematic.svg` | Background drawing for desktop and phone |
| `a266-schematic-tv.svg` | Background drawing for the TV view |

To check that every entity exists, add `--states states.json`: a JSON object with `states` (the list from
`/api/states`) and, optionally, `entities` (the entity registry).

### 6. Load it into Home Assistant

1. Copy both SVG files to `/config/www/heating/`. Home Assistant serves that folder as `/local/heating/`.
2. Settings → Dashboards → **Add dashboard** → *New dashboard from scratch*, with the URL `dashboard-heating` (or
   whatever you set as `dashboard_path`).
3. Open it, then ⋮ → **Edit dashboard** → ⋮ → **Raw configuration editor**. Replace the contents with
   `build/heating-dashboard.yaml` and save.

After changing the config or the drawing, build again and repeat steps 1 and 3.

## How the schematic works

Everything is core Home Assistant, except the charts and gauges:

1. A **`picture-elements` card** shows the drawing.
2. **`state-label` elements** sit on each symbol, placed in percent of the image so the card scales. Font sizes
   use CSS `clamp(…, vw, …)`, so text stays readable from phone to TV. Phones get a sparser set of labels.
3. **Conditional layers.** The generator cuts each live symbol (pumps, valves, pipes, the alarm bell) out of the
   drawing as a small SVG. It then adds one `conditional` overlay per state and colour: a pump running, a valve
   opening or closing, a pipe at a given temperature. That's several hundred overlays, which is why a script
   writes the dashboard instead of a person.
4. **Animation.** Pump arrows turn slowly (8 s per turn) while the relay is on, and dashes move along a pipe while
   water flows.
5. **Stale values turn grey** while a value is `unavailable` or `unknown`, or while its source is offline
   (`binary_sensor.ecl_modbus_online` for ECL values, the pump's link sensor for pump values).
6. **Navigation.** The circled 1 and 2 on the drawing open the Space heating and Hot water views.

### Colour rules

| Cue | Driven by | Rule |
|---|---|---|
| S3 heating flow | `sensor.heating_flow_deviation` (S3 − desired) | green within ±2 K, amber otherwise |
| S4 hot water | `sensor.dhw_flow_deviation` (S4 − desired) | green within ±2 K, amber otherwise |
| Valve rings M1, M2 | valve motor | red while opening, blue while closing, grey otherwise; the fill shows the position |
| Pump arrows P1, P2 | relay registers 4006, 4007 | turning while on, grey and still while off |
| Amber pulse | alarm and override registers | shown only while active |
| Pipe colour | the pipe's own temperature | fixed scale: 30 °C blue → 45 °C orange → 60 °C red |
| Grey value | value unavailable, or source offline | `#9e9e9e` |
| Summer cut-out label | S1 outdoor temperature | shown above `heat_cut_out_c` |
| District return *(heat meter)* | return temperature | green < 35 °C, amber 35–45 °C, red > 45 °C, red whenever above the ECL return limit |
| ΔT *(heat meter)* | supply − return | green ≥ 25 K, amber < 15 K |
| Rooms *(rooms)* | room − desired room temperature | green within ±1 K, blue when colder, orange when warmer |

### Code map

| File in `generator/` | Does |
|---|---|
| `build.py` | Reads the config, builds the views, writes the output |
| `clean_drawing.py` | Prepares the drawing saved from Leanheat Monitor |
| `schematic.py` | Label positions (`LABELS`, `STACKS`, `PHONE_LABELS`), colour rules, the picture card |
| `live_symbols.py` | Cuts the live symbols out of the drawing; overlays, pump arrows, flow dashes |
| `direct_heating.py` | The direct-heating and one-pipe redraw of circuit 1 (`variant.direct_heating`) |
| `colour_scale.py` | Pipe colours by temperature |
| `settings.py`, `prune.py` | Config loading, entity mapping, leaving out features that are off |

### Adapting to another drawing

All positions are pixel coordinates in the drawing (1205 × 756 for A266.1):

- Value labels: `LABELS`, `STACKS` and `PHONE_LABELS` in `schematic.py`
- Pipes and flow paths: `PIPES` and `FLOWS` in `live_symbols.py`, as SVG path data along the pipes
- Pump centres: `PUMP_CENTRES` in `live_symbols.py`; alarm and override pulses: `PULSES`

Open the SVG in a browser or Inkscape to read off coordinates, then build and compare.

## Troubleshooting

**`Danfoss drawing not found`** means `drawing` in `config.local.yaml` doesn't point at your cleaned SVG. Do
[step 2](#2-get-the-drawing) first.

**The schematic is a blank or broken image.** Home Assistant can't find the background. Check that both SVGs are in
`/config/www/heating/`. Then reload the page with Cmd/Ctrl + Shift + R, because browsers cache `/local/` files.

**Cards say "Custom element doesn't exist".** A HACS card is missing. Install it (see
[step 3](#3-prepare-home-assistant)) and reload the page.

**Values are in the wrong place.** Your drawing isn't the A266.1 "ex. a" drawing. See
[Adapting to another drawing](#adapting-to-another-drawing).

**Static labels such as "Heating" and "Status" are missing.** `packages/heating_rooms.yaml` isn't installed, so
`sensor.heating_dashboard_text` doesn't exist.

## Limits

- Tested with one installation: ECL Comfort 310, A266.1, Leanheat drawing "A266_1 ex. a", Home Assistant 2026.11.
- The overview's text summary needs `heat_meter` and `circulation_pump` on, because it describes that flow.
- The Danfoss drawing and ECL Comfort are Danfoss material. This project is not affiliated with Danfoss.
