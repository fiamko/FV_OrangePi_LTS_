# FV_OrangePi_LTS_

> Version: 2026-09-28

**FVE Dashboard for the OrangePi 3 LTS** — monitoring and control of a home photovoltaic power plant through a web interface.

---

## Motivation

The purchased SolarAssistant licence did not suit me — only one inverter, a closed system, no way to modify it. So I built my own monitoring and control system that reads multiple inverters and manages surplus harvesting the way I want.

### How it works
- I manage harvesting by **battery voltage** — the thresholds are set in the OPI web UI to hundredths of a volt.
- The OPI evaluates the threshold and sends commands over MQTT to the ESP power devices (boiler, floor heating, hot tub).
- The ESPs have **time hysteresis** (no flickering like with analog switching) and **their own safety features** — when household consumption rises they disconnect harvesting immediately, without waiting for the OPI.
- The household (dishwasher, washing machine, oven…) always has priority.

### Hot tub
I modified an inflatable supermarket hot tub: it has two 1 kW coils, so heating power can be controlled in steps. I interrupted each coil with an NC relay contact in an ESP32 module. ⚠️ **Copy this modification at your own risk.**

### Web
The whole system is visible at fv-peter.cz. Grey icon = component disconnected, black = connected and working. The number under the icon greys out on an OFF command and blackens on ON. The animated line turns blue and flows to the appliance when the relay closes. The floor heating shows the boiler input/output temperature, the hot tub shows temperature and real consumption.

The system is still in development — features are being added (among others, firmware for a Sonoff on the circulation pump).

## What it is

A web application written in Python (Flask) that:
- Displays live data from the Voltronic inverter (over serial)
- Measures battery voltage/current via INA226 (I²C)
- Controls appliances (boiler, floor heating, hot tub) based on battery voltage
- Communicates with ESP32 power devices over MQTT
- Provides a responsive dashboard optimised for tablet and mobile

---

## Hardware

| Device | Model | IP |
|--------|-------|-----|
| **OrangePi 3 LTS** | Armbian (Bookworm) | `192.168.0.191` |
| **Inverter 1** | Voltronic Axpert 3.6kW | `/dev/ttyUSB0` |
| **Inverter 2** | Voltronic Axpert 3.0kW | `/dev/ttyUSB1` |
| **INA226** | I²C battery current/voltage sensor | I²C bus |
| **ESP32 hot tub** | ESP32-32E N4 + 2× relay + SCT013 + DS18B20 | `192.168.0.106` |
| **ESP32 floor heating 2200W** | ESP32 + relay | `192.168.0.151` |
| **ESP32 floor heatings** | ESP32 + 2× relay (future) | `192.168.0.???` |
| **Sonoff Basic R1** | eWeLink firmware — circulation pump | `192.168.0.132` |

---

## Project structure

```
menic_web/
├── app01.py                  # Flask server (port 5000), starts the MQTT worker
├── config.json               # Appliance switching thresholds, seasonal profiles
├── mqtt_menic1.py            # Inverter reader over /dev/ttyUSB0 → MQTT
├── ina226_mqtt.py            # INA226 reader over I²C → MQTT
├── ewelink_mqtt.py           # eWeLink bridge (Sonoff) → MQTT
├── ewelink_config.example.json  # Bridge config template (device key)
├── EWELINK.md                # eWeLink bridge documentation
├── voltronic.py              # Library for inverter communication
├── requirements.txt          # Python dependencies
├── models/
│   └── state.py              # current_data dict + data_lock
├── services/
│   ├── mqtt_service.py        # MQTT worker: data, INA, controller
│   ├── controller_service.py  # ControllerEngine: thresholds, commands
│   ├── dashboard_service.py   # Data transformation for the frontend
│   ├── history_service.py     # SQLite history recording
│   ├── settings_service.py    # config.json read/write
│   └── statistics_service.py  # Aggregation for statistics
├── routes/
│   ├── dashboard.py           # / and /data
│   ├── settings.py            # /nastaveni (password from secrets.py)
│   └── statistics.py          # /statistiky
├── static/
│   ├── dashboard.js           # Frontend logic (2s refresh)
│   ├── settings.js            # Settings validation
│   ├── style.css              # Styles (responsive)
│   ├── sw.js                  # Service Worker (PWA)
│   └── icons/                 # PNG appliance icons
├── templates/
│   ├── index.html             # Main dashboard
│   ├── settings.html          # Threshold settings
│   ├── statistics.html        # Statistics
│   └── statistics_detail.html # Statistics detail
└── deploy/
    ├── install_services.sh    # Installation script
    ├── systemd/               # systemd services
    │   ├── fve-dashboard.service
    │   ├── fve-menic-reader.service
    │   ├── fve-ewelink.service
    │   └── tigervnc@.service
    └── caddy/                 # Reverse proxy + HTTPS
        ├── Caddyfile
        ├── get-cert.sh
        └── renew-cert.sh
```

---

## MQTT topics

### Inverter data
| Topic | Direction | Content |
|-------|-----------|---------|
| `menic/1/data` | OPI → MQTT | JSON: voltage, current, power, temperature, etc. |

### INA226 data
| Topic | Direction | Content |
|-------|-----------|---------|
| `baterie/data` | OPI → MQTT | JSON: `inaB_V`, `inaB_A` |

### Appliance control (ControllerEngine → ESP)
| Topic | Device |
|-------|--------|
| `fve/spotrebice/podlaha300/set` | Floor 300W |
| `fve/spotrebice/podlaha2000/set` | Floor 2000W |
| `fve/spotrebice/podlaha2200/set` | Floor 2200W |
| `fve/spotrebice/bojler/set` | Boiler |
| `fve/spotrebice/virivka/set` | Hot tub |
| `fve/spotrebice/cerpadlo/set` | Circulation pump (eWeLink) |

### State from ESP32
| Topic | Direction | Content |
|-------|-----------|---------|
| `fve/spotrebice/virivka/stav` | ESP → MQTT | JSON: `status`, `vystup1/2`, `proud0`, `teplota` |
| `fve/spotrebice/virivka/status` | ESP → MQTT | Last Will: `{"status":"online"/"offline"}` |
| `fve/spotrebice/podlaha2200/stav` | ESP → MQTT | JSON: `status`, `vystup`, `duvod` |
| `fve/spotrebice/podlaha2200/status` | ESP → MQTT | Last Will: `{"status":"online"/"offline"}` |

---

## Installation on the OrangePi 3 LTS

### Requirements
- Armbian (Bookworm), Python 3.12+
- Mosquitto MQTT broker
- Access to the I²C bus (for INA226)
- Serial port `/dev/ttyUSB0` (for the inverter)

### Quick install
```bash
# 1. Clone the repository
git clone https://github.com/fiamko/FV_OrangePi_LTS_.git
cd FV_OrangePi_LTS_

# 2. Create a virtualenv and install dependencies
python3 -m venv fve-env
source fve-env/bin/activate
pip install -r requirements.txt

# 3. Copy and edit config.json
cp config.json config.local.json
nano config.json   # set thresholds for your battery

# 4. Install the systemd services
sudo bash deploy/install_services.sh

# 5. Start
sudo systemctl enable fve-menic-reader fve-dashboard
sudo systemctl start fve-menic-reader fve-dashboard
```

The dashboard runs at `http://192.168.0.191:5000`.

### Access
- **Dashboard:** `http://192.168.0.191:5000`
- **Settings:** `http://192.168.0.191:5000/nastaveni` (password: see `secrets.py`)
- **Statistics:** `http://192.168.0.191:5000/statistiky`

---

## Configuration

All appliance switching thresholds are in `config.json`. The dashboard supports 4 seasonal profiles (spring/summer/autumn/winter).

| Parameter | Description |
|-----------|-------------|
| `zapni_*` / `vypni_*` | Voltage thresholds for appliance on/off |
| `rizeni_podle` | Metric: `batteryVoltage`, `batteryFlow`, `inaB_V` |
| `hystereze_s` | Minimum time between state changes |
| `power_*` | Rated appliance power (for load calculation) |
| `ochrana_odberu` | Block harvesting when no consumption flows from the inverter (`true`/`false`) |
| `odber_limit_w` | Inverter consumption threshold (W) below which harvesting is blocked |
| `cerpadlo_vypni_deltaT` | Pump-off ΔT (°C) |
| `cerpadlo_max_min` | Cumulative heating minutes before the pump switches on |
| `cerpadlo_min_beh_min` | Minimum pump runtime after switch-on (minutes) |
| `cerpadlo_off_persist_min` | How long ΔT must stay below the threshold before the pump stops (minutes) |

---

## ESP32 power devices

Each ESP32:
- Listens to MQTT commands from the ControllerEngine
- Reports state (`fve/.../stav`) and online/offline (`fve/.../status` Last Will)
- On the dashboard:
  - **Online** = coloured icon, clicking opens the ESP web
  - **Offline** = greyed icon

---

## eWeLink bridge (Sonoff circulation pump)

Control of a Sonoff (original eWeLink firmware) over LAN **without Tasmota and without a cloud account** — detailed guide in [EWELINK.md](EWELINK.md).

- The bridge `ewelink_mqtt.py` (service `fve-ewelink`) controls the relay over HTTP `/zeroconf/*` (AES-128-CBC, key = MD5(devicekey)).
- State is read from the **mDNS broadcast** (`_ewelink._tcp.local.`) — works both ways (command and manual change from the app/button).
- Pump automation in the ControllerEngine: boiler heats → accumulation → on after 4 min → min. 60 min runtime → off at ΔT < 3 °C (held continuously 2 min, valid data only) → reset at midnight.
- **Required iptables rule** for UDP 5353 (mDNS) — see EWELINK.md.
- The device key is obtained over the device's AP mode (`http://10.10.7.1/device`) and stored in `ewelink_config.json` (in `.gitignore`, **never commit**).

## Security

- MQTT broker only on LAN (`iptables` restricted to `192.168.0.0/24`)
- Settings password in `secrets.py` (`SETTINGS_PASSWORD`) — **change before deployment!**
- External access via Caddy + Cloudflare Tunnel (optional)

---

## Version history

### 2026-09-28 — Pump false-shutdown protection
- The circulation pump controller (`_tick_cerpadlo`) now ignores invalid temperatures (ESP offline / temperature 0) and only switches the pump off when ΔT stays below the threshold continuously for `cerpadlo_off_persist_min` (2 min). A transient `0/0` reading no longer falsely stops the pump.
- New parameter `cerpadlo_off_persist_min` in `config.json` and the web settings.

### 2026-09-25 — Harvesting protection without inverter consumption
- New safety in harvesting control: when no consumption flows from the inverter (the household is switched to the public grid), harvesting is immediately stopped so appliances don't heat from the grid.
- Consumption is read from the MQTT key `output_active_power` (W). Below the limit (default 10 W) all harvesting appliances are forced OFF.
- Inverter 2 is **exempt** from this protection — controlled manually / by mechanical switching.
- New parameters in `config.json` and the web settings:
  - `ochrana_odberu` (bool, default `true`) — enable/disable the safety.
  - `odber_limit_w` (W, default `10.0`) — consumption threshold for blocking.

---

## Licence

MIT — do whatever you want with it.

---

# FV_OrangePi_LTS_

> Verze: 2026-09-28

**FVE Dashboard pro OrangePi 3 LTS** — monitorování a řízení domácí fotovoltaické elektrárny přes webové rozhraní.

---

## Motivace

Koupená licence na SolarAssistant mi nevyhovovala — jen jeden měnič, uzavřený systém, bez možnosti úprav. Proto jsem si postavil vlastní monitorovací a řídicí systém, který načítá více měničů a řídí vytěžování přebytků podle sebe.

### Jak to funguje
- Vytěžování řídím podle **napětí baterie** — meze se nastavují ve webu OPI s přesností na setiny voltu.
- OPI vyhodnotí práh a přes MQTT posílá povely ESP výkonovým členům (bojler, podlahovky, vířivka).
- ESP mají **časovou hysterezi** (žádné blikání jako u analogového spínání) a **vlastní bezpečnostní funkce** — při zvýšeném odběru domácnosti odpojí vytěžování okamžitě, bez čekání na OPI.
- Domácnost (myčka, pračka, trouba…) má vždy přednost.

### Vířivka
Nafukovací vířivku ze supermarketu jsem upravil: má dvě spirály po 1 kW, takže výkon topení jde stupňovitě řídit. Každou spirálu jsem přerušil NC kontaktem relé v modulu ESP32. ⚠️ **Tuto úpravu kopírujete na vlastní nebezpečí.**

### Web
Na fv-peter.cz je vidět celý systém. Šedá ikona = komponenta nepřipojená, černá = připojená a funkční. Číslice pod ikonou šedne při příkazu OFF, zčerná při ON. Animovaná čára zmodrá a teče k spotřebiči, když relé sepne. U podlahovky se zobrazuje teplota vstup/výstup kotle, u vířivky teplota a reálný odběr.

Systém je stále ve vývoji — přibývají funkce (mj. firmware pro Sonoff na oběhové čerpadlo).

## Co to je

Webová aplikace napsaná v Pythonu (Flask), která:
- Zobrazuje živá data z Voltronic měniče (přes sériovou linku)
- Měří napětí/proud baterie přes INA226 (I²C)
- Řídí spotřebiče (bojler, podlahové topení, vířivka) podle napětí baterie
- Komunikuje s ESP32 výkonovými členy přes MQTT
- Nabízí responzivní dashboard optimalizovaný pro tablet i mobil

---

## Hardware

| Zařízení | Model | IP |
|----------|-------|-----|
| **OrangePi 3 LTS** | Armbian (Bookworm) | `192.168.0.191` |
| **Měnič 1** | Voltronic Axpert 3.6kW | `/dev/ttyUSB0` |
| **Měnič 2** | Voltronic Axpert 3.0kW | `/dev/ttyUSB1` |
| **INA226** | I²C senzor proudu/napětí baterie | I²C bus |
| **ESP32 vířivka** | ESP32-32E N4 + 2× relé + SCT013 + DS18B20 | `192.168.0.106` |
| **ESP32 podlahovka 2200W** | ESP32 + relé | `192.168.0.151` |
| **ESP32 podlahovky** | ESP32 + 2× relé (budoucí) | `192.168.0.???` |
| **Sonoff Basic R1** | eWeLink firmware — oběhové čerpadlo | `192.168.0.132` |

---

## Struktura projektu

```
menic_web/
├── app01.py                  # Flask server (port 5000), spouští MQTT worker
├── config.json               # Meze pro spínání spotřebičů, sezónní profily
├── mqtt_menic1.py            # Čtečka měniče přes /dev/ttyUSB0 → MQTT
├── ina226_mqtt.py            # Čtečka INA226 přes I²C → MQTT
├── ewelink_mqtt.py           # eWeLink bridge (Sonoff) → MQTT
├── ewelink_config.example.json  # Šablona configu bridge (device key)
├── EWELINK.md                # Dokumentace eWeLink bridge
├── voltronic.py              # Knihovna pro komunikaci s měničem
├── requirements.txt          # Python závislosti
├── models/
│   └── state.py              # current_data dict + data_lock
├── services/
│   ├── mqtt_service.py        # MQTT worker: data, INA, controller
│   ├── controller_service.py  # ControllerEngine: meze, povely
│   ├── dashboard_service.py   # Transformace dat pro frontend
│   ├── history_service.py     # SQLite záznam historie
│   ├── settings_service.py    # config.json čtení/zápis
│   └── statistics_service.py  # Agregace pro statistiky
├── routes/
│   ├── dashboard.py           # / a /data
│   ├── settings.py            # /nastaveni (heslo ze secrets.py)
│   └── statistics.py          # /statistiky
├── static/
│   ├── dashboard.js           # Frontend logika (aktualizace po 2s)
│   ├── settings.js            # Validace nastavení
│   ├── style.css              # Styly (responzivní)
│   ├── sw.js                  # Service Worker (PWA)
│   └── icons/                 # PNG ikony spotřebičů
├── templates/
│   ├── index.html             # Hlavní dashboard
│   ├── settings.html          # Nastavení mezí
│   ├── statistics.html        # Statistiky
│   └── statistics_detail.html # Detail statistik
└── deploy/
    ├── install_services.sh    # Instalační skript
    ├── systemd/               # Systemd služby
    │   ├── fve-dashboard.service
    │   ├── fve-menic-reader.service
    │   ├── fve-ewelink.service
    │   └── tigervnc@.service
    └── caddy/                 # Reverzní proxy + HTTPS
        ├── Caddyfile
        ├── get-cert.sh
        └── renew-cert.sh
```

---

## MQTT topicy

### Data z měniče
| Topic | Směr | Obsah |
|-------|------|-------|
| `menic/1/data` | OPI → MQTT | JSON: napětí, proud, výkon, teplota atd. |

### Data z INA226
| Topic | Směr | Obsah |
|-------|------|-------|
| `baterie/data` | OPI → MQTT | JSON: `inaB_V`, `inaB_A` |

### Řízení spotřebičů (ControllerEngine → ESP)
| Topic | Zařízení |
|-------|----------|
| `fve/spotrebice/podlaha300/set` | Podlaha 300W |
| `fve/spotrebice/podlaha2000/set` | Podlaha 2000W |
| `fve/spotrebice/podlaha2200/set` | Podlaha 2200W |
| `fve/spotrebice/bojler/set` | Bojler |
| `fve/spotrebice/virivka/set` | Vířivka |
| `fve/spotrebice/cerpadlo/set` | Oběhové čerpadlo (eWeLink) |

### Stav z ESP32
| Topic | Směr | Obsah |
|-------|------|-------|
| `fve/spotrebice/virivka/stav` | ESP → MQTT | JSON: `status`, `vystup1/2`, `proud0`, `teplota` |
| `fve/spotrebice/virivka/status` | ESP → MQTT | Last Will: `{"status":"online"/"offline"}` |
| `fve/spotrebice/podlaha2200/stav` | ESP → MQTT | JSON: `status`, `vystup`, `duvod` |
| `fve/spotrebice/podlaha2200/status` | ESP → MQTT | Last Will: `{"status":"online"/"offline"}` |

---

## Instalace na OrangePi 3 LTS

### Požadavky
- Armbian (Bookworm), Python 3.12+
- Mosquitto MQTT broker
- Přístup k I²C sběrnici (pro INA226)
- Sériový port `/dev/ttyUSB0` (pro měnič)

### Rychlá instalace
```bash
# 1. Naklonovat repozitář
git clone https://github.com/fiamko/FV_OrangePi_LTS_.git
cd FV_OrangePi_LTS_

# 2. Vytvořit virtualenv a nainstalovat závislosti
python3 -m venv fve-env
source fve-env/bin/activate
pip install -r requirements.txt

# 3. Zkopírovat a upravit config.json
cp config.json config.local.json
nano config.json   # nastavit meze podle své baterie

# 4. Nainstalovat systemd služby
sudo bash deploy/install_services.sh

# 5. Spustit
sudo systemctl enable fve-menic-reader fve-dashboard
sudo systemctl start fve-menic-reader fve-dashboard
```

Dashboard běží na `http://192.168.0.191:5000`.

### Přístup
- **Dashboard:** `http://192.168.0.191:5000`
- **Nastavení:** `http://192.168.0.191:5000/nastaveni` (heslo: viz `secrets.py`)
- **Statistiky:** `http://192.168.0.191:5000/statistiky`

---

## Konfigurace

Veškeré meze pro spínání spotřebičů jsou v `config.json`. Dashboard podporuje 4 sezónní profily (jaro/léto/podzim/zima).

| Parametr | Popis |
|----------|-------|
| `zapni_*` / `vypni_*` | Napěťové meze pro sepnutí/vypnutí spotřebiče |
| `rizeni_podle` | Metrika: `batteryVoltage`, `batteryFlow`, `inaB_V` |
| `hystereze_s` | Minimální doba mezi změnami stavu |
| `power_*` | Jmenovitý výkon spotřebiče (pro dopočet zatížení) |
| `ochrana_odberu` | Blokovat vytěžování, když z měniče neteče žádný odběr (`true`/`false`) |
| `odber_limit_w` | Práh odběru z měniče (W), pod kterým se vytěžování zablokuje |
| `cerpadlo_vypni_deltaT` | ΔT pro vypnutí čerpadla (°C) |
| `cerpadlo_max_min` | Kumulativní minuty ohřevu před zapnutím čerpadla |
| `cerpadlo_min_beh_min` | Minimální doba běhu čerpadla po zapnutí (minuty) |
| `cerpadlo_off_persist_min` | Jak dlouho musí ΔT držet pod mezí, než se čerpadlo vypne (minuty) |

---

## ESP32 výkonové členy

Každý ESP32:
- Poslouchá MQTT povely z ControllerEngine
- Hlásí stav (`fve/.../stav`) a online/offline (`fve/.../status` Last Will)
- Na dashboardu se zobrazuje:
  - **Online** = barevná ikona, kliknutí otevře web ESP
  - **Offline** = zašedlá ikona

---

## eWeLink bridge (Sonoff oběhové čerpadlo)

Ovládání Sonoffu (originální eWeLink firmware) přes LAN **bez Tasmoty a bez cloud účtu** — podrobný postup viz [EWELINK.md](EWELINK.md).

- Bridge `ewelink_mqtt.py` (služba `fve-ewelink`) ovládá relé přes HTTP `/zeroconf/*` (AES-128-CBC, klíč = MD5(devicekey)).
- Stav se čte z **mDNS broadcast** (`_ewelink._tcp.local.`) — funguje obousměrně (příkaz i ruční změna z appky/tlačítka).
- Automatika čerpadla v ControllerEngine: kotel topí → akumulace → zapnutí po 4 min → min. 60 min běhu → vypnutí při ΔT < 3 °C (souvisle 2 min, jen platná data) → reset o půlnoci.
- **Nutné iptables pravidlo** pro UDP 5353 (mDNS) — viz EWELINK.md.
- Device key se získá přes AP mód zařízení (`http://10.10.7.1/device`), ukládá se do `ewelink_config.json` (v `.gitignore`, **nikdy necommitovat**).

## Zabezpečení

- MQTT broker pouze na LAN (`iptables` omezení na `192.168.0.0/24`)
- Heslo pro nastavení v `secrets.py` (`SETTINGS_PASSWORD`) — **před nasazením změnit!**
- Externí přístup přes Caddy + Cloudflare Tunnel (volitelné)

---

## Historie verzí

### 2026-09-28 — Ochrana proti falešnému vypnutí čerpadla
- Řízení oběhového čerpadla (`_tick_cerpadlo`) nově ignoruje neplatné teploty (ESP offline / teplota 0) a vypíná čerpadlo až když ΔT drží pod mezí souvisle `cerpadlo_off_persist_min` (2 min). Přechodné čtení `0/0` už čerpadlo falešně nezastaví.
- Nový parametr `cerpadlo_off_persist_min` v `config.json` a ve webovém nastavení.

### 2026-09-25 — Ochrana vytěžování bez odběru z měniče
- Nová pojistka v řízení vytěžování: když z měniče neteče žádný odběr (domácnost je přepnutá na veřejnou síť), vytěžování se okamžitě odstaví, aby spotřebiče netopily ze sítě.
- Odběr se čte z MQTT klíče `output_active_power` (W). Pod limitem (výchozí 10 W) se všechny vytěžovací spotřebiče vynutí do OFF.
- Měnič 2 je z této ochrany **vyjmutý** — ovládá se ručně / mechanickým přepojováním.
- Nové parametry v `config.json` a ve webovém nastavení:
  - `ochrana_odberu` (bool, výchozí `true`) — zapnutí/vypnutí pojistky.
  - `odber_limit_w` (W, výchozí `10.0`) — práh odběru pro blokaci.

---

## Licence

MIT — dělej si s tím co chceš.
