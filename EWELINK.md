# eWeLink bridge — Sonoff circulation pump

Control of a Sonoff (original eWeLink firmware) over LAN — **no Tasmota, no cloud account**.

## What it is

`ewelink_mqtt.py` is a standalone bridge (systemd service `fve-ewelink`) that:

- **controls the relay** of the Sonoff over the eWeLink LAN protocol (HTTP POST `/zeroconf/<command>`),
- **reads the actual relay state** over the mDNS broadcast (`_ewelink._tcp.local.`),
- **connects everything to MQTT** (command, state, online/offline).

## Protocol

- **Control**: `POST http://<ip>:8081/zeroconf/switch` with JSON `{"data":{"switch":"on"/"off"}}`.
  Data encrypted with **AES-128-CBC** (key = `MD5(devicekey)`, random IV, PKCS7 padding).
- **State read**: the device broadcasts mDNS `_ewelink._tcp.local.` every ~2 s with TXT records
  `data1..data4` (base64-encrypted state) + `iv` + `encrypt`. The bridge decrypts it and gets `switch`.
- The device **does not return the state in the HTTP response** (`getState`/`info` return only
  `{"error":0}`) — hence reading the state over mDNS is necessary.

Reference implementation: [AlexxIT/SonoffLAN](https://github.com/AlexxIT/SonoffLAN) (`core/ewelink/local.py`).

## Getting the device key (no cloud account)

1. Hold the Sonoff button (~5–7 s) until the LED blinks fast (AP/pairing mode).
2. Connect to WiFi `ITEAD-10000`, password `12345678`.
3. Open `http://10.10.7.1/device` → copy `deviceid` and `apikey` (apikey = device key).
4. The Sonoff returns to the normal WiFi (restart or wait).

> The device key is a permanent device property, it never changes. LAN mode is enabled in the
> eWeLink app (device settings → "LAN Control").

## Configuration

File `ewelink_config.json` (next to the bridge, **NEVER commit** — it contains the device key).
Template: `ewelink_config.example.json`.

| Key | Meaning |
|-----|---------|
| `deviceid` | Device ID (10 chars, e.g. `100036a7a1`) |
| `devicekey` | Device key (UUID, from AP mode) |
| `host` / `port` | Device IP and port (LAN mode = 8081) |
| `mqtt_broker` / `mqtt_port` | MQTT broker (on OPI `localhost:1883`) |
| `cmd_topic` | MQTT command (from ControllerEngine) |
| `state_topic` | MQTT actual state |
| `status_topic` | MQTT online/offline (Last Will) |
| `poll_interval_s` | Health-check interval (getState) |

## MQTT topics

| Topic | Direction | Content |
|-------|-----------|---------|
| `fve/spotrebice/cerpadlo/set` | OPI → bridge | `{"enabled": true/false, ...}` |
| `fve/spotrebice/cerpadlo/stav` | bridge → OPI | `{"status":"ZAP"/"OFF","vystup":0/1,"duvod":"..."}` |
| `fve/spotrebice/cerpadlo/status` | bridge → MQTT | `{"status":"online"/"offline"}` (Last Will) |

## Pump automation (ControllerEngine)

Logic in `services/controller_service.py` (method `_tick_cerpadlo`):

1. The boiler heats (`heating1_state_actual == 1`) → **heating time is accumulated**.
2. After `cerpadlo_max_min` (4) minutes → **pump on**.
3. The pump runs at least `cerpadlo_min_beh_min` (60) minutes — cycle protection
   (ΔT only forms after switch-on).
4. After the minimum time + **ΔT (input − output) < `cerpadlo_vypni_deltaT` (3 °C)** held
   continuously for `cerpadlo_off_persist_min` (2) minutes → **off + accumulation reset**.
5. **At midnight** the accumulation resets.

**Data-validity guard:** the pump is only switched off on **valid** temperatures — the ESP32
must be online (`podlahovka2200_online`) and both temperatures must be > 0. A transient
`0/0` reading (ESP boot / brief dropout) therefore cannot falsely switch the pump off; the
ΔT condition must also persist for `cerpadlo_off_persist_min` before the pump stops.

Parameters are changed on `/nastaveni` (section "Čerpadlo (eWeLink)") — they take effect
immediately, without restart.

## Manual control

- **Dashboard**: click the pump icon (next to the 2200 W floor heating) + password → toggle
  (60 min override).
- **eWeLink app / button**: works; the bridge catches it over mDNS and the dashboard shows it.
- Icon: grey = off, black = running, red = offline.

## Installation

```bash
# 1. dependencies (into venv)
pip install -r requirements.txt        # paho-mqtt, pycryptodome, zeroconf

# 2. config
cp ewelink_config.example.json ewelink_config.json
nano ewelink_config.json               # deviceid + devicekey + host

# 3. systemd service
sudo cp deploy/systemd/fve-ewelink.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fve-ewelink

# 4. test (without MQTT)
./fve-env/bin/python ewelink_mqtt.py --test state   # read (returns "online", not state)
./fve-env/bin/python ewelink_mqtt.py --test on      # switch relay on
./fve-env/bin/python ewelink_mqtt.py --test off     # switch relay off
```

## Important: iptables (mDNS)

The OPI has a firewall with default policy `INPUT DROP`. To read the state over mDNS you must
allow UDP 5353 from the LAN, otherwise the bridge controls the device but does not read the state back:

```bash
sudo iptables -A INPUT -s 192.168.0.0/24 -p udp --dport 5353 -j ACCEPT
sudo netfilter-persistent save
```

## Troubleshooting

| Symptom | Cause / solution |
|---------|------------------|
| `--test state` → `switch = None` | normal — the device does not return state in HTTP, state is read from mDNS |
| State not read (no `stav ze zarizeni (mDNS)`) | missing iptables rule for UDP 5353 |
| `spojeni: timed out` | device offline / LAN mode off / wrong device key |
| `error=400` for `switch` without param | the `switch` command requires `{"switch":"on"/"off"}` |
| LED blinks fast (AP mode) | device in pairing mode → restart or re-pair in the app |

---

# eWeLink bridge — Sonoff oběhové čerpadlo

Ovládání Sonoffu (originální eWeLink firmware) přes LAN — **bez Tasmoty, bez cloud účtu**.

## Co to je

`ewelink_mqtt.py` je samostatný bridge (systemd služba `fve-ewelink`), který:

- **ovládá relé** Sonoffu přes eWeLink LAN protokol (HTTP POST `/zeroconf/<command>`),
- **čte skutečný stav** relé přes mDNS broadcast (`_ewelink._tcp.local.`),
- **propojuje vše s MQTT** (příkaz, stav, online/offline).

## Protokol

- **Ovládání**: `POST http://<ip>:8081/zeroconf/switch` s JSON `{"data":{"switch":"on"/"off"}}`.
  Data šifrována **AES-128-CBC** (klíč = `MD5(devicekey)`, náhodné IV, PKCS7 padding).
- **Čtení stavu**: zařízení každé ~2 s vysílá mDNS `_ewelink._tcp.local.` s TXT záznamy
  `data1..data4` (base64 šifrovaný stav) + `iv` + `encrypt`. Bridge to dešifruje a získá `switch`.
- Zařízení **nevrací stav v HTTP odpovědi** (`getState`/`info` vrátí jen `{"error":0}`) —
  proto je čtení stavu přes mDNS nutné.

Referenční implementace: [AlexxIT/SonoffLAN](https://github.com/AlexxIT/SonoffLAN) (`core/ewelink/local.py`).

## Získání device key (bez cloud účtu)

1. Dlouze podrž tlačítko na Sonoffu (~5–7 s), až LED začne rychle blikat (AP/párovací mód).
2. Připoj se k WiFi `ITEAD-10000`, heslo `12345678`.
3. Otevři `http://10.10.7.1/device` → opiš `deviceid` a `apikey` (apikey = device key).
4. Sonoff se vrátí do normální WiFi (restart nebo počkej).

> Device key je trvalá vlastnost zařízení, nemění se. LAN mód se nastavuje v appce eWeLink
> (nastavení zařízení → „LAN Control").

## Konfigurace

Soubor `ewelink_config.json` (vedle bridge, **NIKDY necommitovat** — obsahuje device key).
Šablona: `ewelink_config.example.json`.

| Klíč | Význam |
|------|--------|
| `deviceid` | ID zařízení (10 znaků, např. `100036a7a1`) |
| `devicekey` | Device key (UUID, z AP módu) |
| `host` / `port` | IP a port zařízení (LAN mód = 8081) |
| `mqtt_broker` / `mqtt_port` | MQTT broker (na OPI `localhost:1883`) |
| `cmd_topic` | MQTT příkaz (z ControllerEngine) |
| `state_topic` | MQTT skutečný stav |
| `status_topic` | MQTT online/offline (Last Will) |
| `poll_interval_s` | Interval health-checku (getState) |

## MQTT topicy

| Topic | Směr | Obsah |
|-------|------|-------|
| `fve/spotrebice/cerpadlo/set` | OPI → bridge | `{"enabled": true/false, ...}` |
| `fve/spotrebice/cerpadlo/stav` | bridge → OPI | `{"status":"ZAP"/"OFF","vystup":0/1,"duvod":"..."}` |
| `fve/spotrebice/cerpadlo/status` | bridge → MQTT | `{"status":"online"/"offline"}` (Last Will) |

## Automatika čerpadla (ControllerEngine)

Logika v `services/controller_service.py` (metoda `_tick_cerpadlo`):

1. Kotel topí (`heating1_state_actual == 1`) → **akumuluje se čas ohřevu**.
2. Po `cerpadlo_max_min` (4) minutách → **zapnutí čerpadla**.
3. Čerpadlo běží minimálně `cerpadlo_min_beh_min` (60) minut — ochrana proti cyklu
   (po zapnutí se ΔT teprve vytváří).
4. Po min. době + **ΔT (vstup−výstup) < `cerpadlo_vypni_deltaT` (3 °C)** držící souvisle
   `cerpadlo_off_persist_min` (2) minuty → **vypnutí + reset akumulace**.
5. **O půlnoci** se akumulace resetuje.

**Hlídání platnosti dat:** čerpadlo se vypne jen při **platných** teplotách — ESP32 musí
být online (`podlahovka2200_online`) a obě teploty musí být > 0. Přechodné čtení `0/0`
(start ESP / krátký výpadek) tak nemůže čerpadlo falešně vypnout; podmínka ΔT navíc musí
trvat `cerpadlo_off_persist_min`, než se čerpadlo zastaví.

Parametry se mění na `/nastaveni` (sekce „Čerpadlo (eWeLink)") — platí okamžitě, bez restartu.

## Ruční ovládání

- **Dashboard**: klik na ikonu čerpadla (vedle podlahovky 2200) + heslo → přepnutí (override 60 min).
- **Appka eWeLink / tlačítko**: funguje; bridge to zachytí přes mDNS a dashboard zobrazí.
- Ikona: šedá = vypnuto, černá = běží, červená = offline.

## Instalace

```bash
# 1. závislosti (do venv)
pip install -r requirements.txt        # paho-mqtt, pycryptodome, zeroconf

# 2. config
cp ewelink_config.example.json ewelink_config.json
nano ewelink_config.json               # deviceid + devicekey + host

# 3. systemd služba
sudo cp deploy/systemd/fve-ewelink.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fve-ewelink

# 4. test (bez MQTT)
./fve-env/bin/python ewelink_mqtt.py --test state   # čtení (vrací "online", ne stav)
./fve-env/bin/python ewelink_mqtt.py --test on      # sepnout relé
./fve-env/bin/python ewelink_mqtt.py --test off     # vypnout relé
```

## Důležité: iptables (mDNS)

OPI má firewall s výchozí politikou `INPUT DROP`. Pro čtení stavu přes mDNS je nutné povolit
UDP 5353 z LAN, jinak bridge zařízení ovládá, ale nečte stav zpětně:

```bash
sudo iptables -A INPUT -s 192.168.0.0/24 -p udp --dport 5353 -j ACCEPT
sudo netfilter-persistent save
```

## Troubleshooting

| Symptom | Příčina / řešení |
|---------|------------------|
| `--test state` → `switch = None` | normální — zařízení nevrací stav v HTTP odpovědi, stav se čte z mDNS |
| Nečte se stav (žádný `stav ze zarizeni (mDNS)`) | chybí iptables pravidlo pro UDP 5353 |
| `spojeni: timed out` | zařízení offline / LAN mód vypnutý / špatný device key |
| `error=400` u `switch` bez parametru | příkaz `switch` vyžaduje `{"switch":"on"/"off"}` |
| LED rychle bliká (AP mód) | zařízení v párovacím módu → restart nebo přepárování v appce |
