# Danfoss ECL Comfort 310 (A266.x) — Home Assistant YAML package

A plain Home Assistant [package](https://www.home-assistant.io/docs/configuration/packages/) that reads a
**Danfoss ECL Comfort 310** running application **A266.x** (weather-compensated heating + DHW) over **Modbus TCP**,
using the core [`modbus`](https://www.home-assistant.io/integrations/modbus/) integration. No custom component needed.

## Two repositories, one controller

The ECL Comfort 310 work is split into two independent repositories:

| Repository | What it is | Use it when |
|---|---|---|
| [danfoss-ecl](https://github.com/muddermanden/danfoss-ecl) | Python register catalog + `ecl-dump` CLI. Reads every A266.x register over Modbus, writes a CSV and compares settings with factory values | You want to analyse or document a controller, check which registers it really has, or find a register before using it elsewhere |
| [homeassistant-danfoss-ecl310](https://github.com/muddermanden/homeassistant-danfoss-ecl310) | Ready-to-use Home Assistant YAML package: a `modbus:` hub plus template sensors | You want the ECL in Home Assistant for daily monitoring, history and dashboards |

**How they relate:** the Home Assistant package's register addresses, scales and decoding were taken from the
danfoss-ecl catalog (Home Assistant `address` = PNU − 1). Use danfoss-ecl to verify your controller, or to look up
a register before adding it to the package.

**Independent:** you can use either one on its own. They share no code, neither needs the other at runtime, and
each is versioned separately. The package needs no Python. The tool needs no Home Assistant.

## Requirements

- Danfoss ECL Comfort 310 with application **A266.x**. Other applications (A247, A260, …) map registers differently.
- Modbus TCP enabled and reachable from Home Assistant: port **502**, unit id **1**.
- A fixed IP address for the controller (DHCP reservation).
- Packages enabled in `configuration.yaml`:

  ```yaml
  homeassistant:
    packages: !include_dir_named packages
  ```

## Install

1. Copy `packages/ecl310.yaml` to `/config/packages/ecl310.yaml`.
2. Change `host: 192.168.1.100` to your controller's IP address.
3. **Developer tools → Check configuration**, then restart Home Assistant.
4. Hide the `*_raw` diagnostic sensors you don't need in the UI. Don't delete them: the template sensors use them.

The Home Assistant `address` is **PNU − 1** (Danfoss parameter number minus one).

## What you get (`packages/ecl310.yaml`)

All entities are **read-only**. The package only reads holding registers and never writes to the controller.

| Group | Entities |
|---|---|
| Temperatures | S1 outdoor, S2 room, S3 flow (circuit 1), S4 DHW flow (circuit 2), S5/S6 return (circuits 1/2) |
| Setpoints | Desired room / flow / return (circuit 1), desired DHW flow / return (circuit 2), comfort and setback temperature |
| Outputs | M1/M2 3-point valve opening/closing, P1/P2 pump relays, A1 alarm relay, V1/V2 analog valve position (%), triacs 5/6 |
| Overrides | M1/M2/P1/P2/A1/V1/V2 override state (AUTO / manual) + `Manual Override` problem sensors |
| Mode / status | Mode and status for heating circuit 1 and DHW circuit 2 |
| Diagnostics | `ECL Modbus Online`, `ECL Alarm`, controller clock, firmware version, application (e.g. `A266.1`) |
| Derived | Heating / DHW flow deviation (actual − desired) |

Raw registers have a `*_raw` suffix. Template sensors decode them into readable states (e.g. `OPENING` / `CLOSING` /
`STOPPED`, `AUTO`, `COMFORT`).

## Optional extras (`packages/ecl310_extras.yaml`)

These template sensors combine the ECL with hardware that is **not** part of the controller. Only install them if
you have equivalents, and rename the entity ids to match your devices.

| Sensor | Needs |
|---|---|
| Heat Meter Faults | Heat meter fault flags (alarm, error, permanent/temporary error, power low, busy) |
| Return Limit Deviation | Heat meter return temperature |
| Radiator Loop Return Estimated | Heat meter supply/return temperature and volume flow + circulation pump flow |

In the author's setup:

- **District-heating heat meter** read over wireless M-Bus with the
  [wmbusmeters add-on](https://github.com/wmbusmeters/wmbusmeters-ha-addon) → MQTT
  (`sensor.varme_c5_*`).
- **Grundfos ALPHA2 GO** circulation pump bridged with an ESP32 running ESPHome (`sensor.heating_pump_flow`).

A heating dashboard built on this package also uses room temperature sensors (Hue, Zigbee, Matter) aggregated
into average / min / max / coldest / warmest room, plus a weather forecast. Those parts aren't in this repo.

## Dashboard

[`dashboard/`](dashboard/) has two options:

- a **starter dashboard** (ready-made YAML) that uses only `ecl310.yaml` entities and core cards;
- a **generator** that builds the full schematic dashboard: the Danfoss A266 diagram with live values, coloured
  pipes and animated pumps. The dashboard YAML is generated from your copy of the drawing and one config file;
  it isn't committed. The Danfoss drawing isn't included either: the README explains how to save your own copy
  from Leanheat Monitor.

[`packages/heating_rooms.yaml`](packages/heating_rooms.yaml) is the helper package the schematic dashboard needs:
room statistics and a text helper. It is not the dashboard itself.

## Disclaimer

Not affiliated with or endorsed by Danfoss. Tested on one ECL Comfort 310 with A266.1. Use at your own risk. Check
values against the controller display or Danfoss Leanheat / ECL Tool before relying on them.

## License

MIT — see [LICENSE](LICENSE).
