# MANUAL — FVE Dashboard for the OrangePi 3 LTS

> Version: 2026-09-28 | Operation and understanding of the whole system

---

## What it is

The FVE Dashboard is a web application that monitors and controls a home photovoltaic
power plant. It runs on the OrangePi 3 LTS (Armbian) and communicates with:

- **Voltronic Axpert inverter** over the serial line `/dev/ttyUSB0`
- **INA226** — I²C battery voltage/current sensor
- **ESP32 power devices** — hot tub, floor heating (over MQTT)

---

## Dashboard (`/`)

The main page shows live data refreshed every 2 seconds:

| Element | Shows |
|---------|-------|
| **PV panels** | Current PV panel power (W) |
| **Inverter 1** | Inverter power (VA), load (%) |
| **Battery** | Voltage (V), state (% capacity), discharge current (A) |
| **Boiler** | ON/OFF, green = heating |
| **Floor 300W** | ON/OFF |
| **Floor 2000W** | ON/OFF |
| **Floor 2200W** | ON/OFF + boiler input/output temperatures |
| **Hot tub** | ON/OFF + **real measured power (W)** + water temperature |

### Status indicators

- **Coloured icon** = device online
- **Greyed icon** = device offline (ESP32 unreachable)
- **Value under the icon** = real measured power (hot tub), or a constant (boiler, floor heating)

### Clicking a device

Clicking the hot tub or the 2200 W floor heating opens the web page of the given
ESP32 (e.g. `http://192.168.0.106`), where detailed diagnostics are available.

---

## Settings (`/nastaveni`)

**Access:** `http://192.168.0.191:5000/nastaveni` — password from `secrets.py`

### What can be set

| Parameter | Description |
|-----------|-------------|
| **zapni_XXX / vypni_XXX** | Voltage thresholds for appliance on/off |
| **rizeni_podle** | Metric: `batteryVoltage` (battery voltage), `batteryFlow` (% capacity), `inaB_V` (INA226) |
| **hystereze_s** | Minimum time between state changes (prevents oscillation) |
| **power_XXX** | Rated appliance power — for total load calculation |
| **battery_capacity_ah** | Battery capacity in Ah |
| **sample_interval_s** | History sampling interval (s) |
| **cerpadlo_vypni_deltaT** | Pump-off ΔT (°C) |
| **cerpadlo_max_min** | Cumulative heating minutes before the pump switches on |
| **cerpadlo_min_beh_min** | Minimum pump runtime after switch-on (minutes) |
| **cerpadlo_off_persist_min** | How long ΔT must stay below the threshold before the pump stops (minutes) |

### Seasonal profiles

The dashboard supports 4 profiles (spring/summer/autumn/winter). The thresholds can be set
for each profile separately — the dashboard automatically uses the profile for the current date.

---

## Statistics (`/statistiky`)

Shows historical data stored in the SQLite database `fve_history.db`:

- Consumption (house, boiler, floor heating, hot tub) in kWh
- PV production in kWh
- Surplus utilisation (%)

Data is stored every `sample_interval_s` seconds. Aggregation by hours/days.

---

## ControllerEngine — how appliance control works

File: `services/controller_service.py`

The ControllerEngine evaluates the current battery state every few seconds and decides
which appliances to switch on/off:

1. Reads `battery_voltage` (or `inaB_V`/`batteryFlow`) from `current_data`
2. For each appliance compares with the `zapni_*` / `vypni_*` thresholds in `config.json`
3. Respects `hystereze_s` — doesn't change state before the interval elapses
4. Publishes the command over MQTT (e.g. `fve/spotrebice/virivka/set`)

### MQTT command format

```json
{
  "device": "virivka",
  "label": "Vířivka",
  "state": "ON",
  "enabled": true,
  "source": "batteryVoltage",
  "source_value": 27.1,
  "on_threshold": 27.0,
  "off_threshold": 26.9,
  "hystereze_s": 20.0,
  "updated_at": 1721234567
}
```

---

## Circulation pump automation (Sonoff)

File: `services/controller_service.py`, method `_tick_cerpadlo`. Details in [EWELINK.md](EWELINK.md).

1. The boiler heats (`heating1_state_actual == 1`) → heating time is accumulated.
2. After `cerpadlo_max_min` (4) minutes → pump on.
3. The pump runs at least `cerpadlo_min_beh_min` (60) minutes.
4. After the minimum time + ΔT (input − output) < `cerpadlo_vypni_deltaT` (3 °C) held
   continuously for `cerpadlo_off_persist_min` (2) minutes → off + accumulation reset.
5. At midnight the accumulation resets.

Only **valid** temperatures switch the pump off (ESP online + temperatures > 0) — a
transient `0/0` reading cannot falsely stop the pump.

---

## ESP32 devices

### Hot tub (ESP32-32E N4)

- **IP:** `192.168.0.106`
- **Sensors:** SCT013 (current), DS18B20 (temperature)
- **Relay:** 2×10A, NC wiring (on failure relay = heats)
- **MQTT command:** `fve/spotrebice/virivka/set` — `{"enabled": true/false}`
- **MQTT state:** `fve/spotrebice/virivka/stav` — `{"status":"ZAP"/"OFF","vystup1":0/1,"vystup2":0/1,"proud0":12.5,"teplota":28.3}`
- **Last Will:** `fve/spotrebice/virivka/status` — `{"status":"online"/"offline"}`
- **Web:** `http://192.168.0.106` (password — default in the ESP firmware)
- **Serial commands:** `scan` (DS18B20 scan), `status` (state printout)

### Floor heating 2200W

- **IP:** `192.168.0.151`
- **Sensors:** 2× DS18B20 (boiler input/output)
- **Relay:** 1×30A
- **MQTT command:** `fve/spotrebice/podlaha2200/set` — `{"enabled": true/false}`
- **MQTT temperatures:** `fve/spotrebice/podlaha2200/teplota` — `{"vstup":42.5,"vystup":35.1,"valid":true}`
- **Web:** `http://192.168.0.151` (password — default in the ESP firmware)

### Floor heatings (300W + 2000W, 2-channel ESP32)

- **MQTT command 300W:** `fve/spotrebice/podlaha300/set` — `{"enabled": true/false}`
- **MQTT command 2000W:** `fve/spotrebice/podlaha2000/set` — `{"enabled": true/false}`

---

## File structure on the OPI

Everything runs from `/home/fiam/menic_web/`. Key files:

| File | Purpose |
|------|---------|
| `app01.py` | Flask server (port 5000) + MQTT worker daemon |
| `config.json` | All thresholds and powers — **single source of truth** |
| `mqtt_menic1.py` | Inverter reader over `/dev/ttyUSB0` → MQTT |
| `ina226_mqtt.py` | INA226 reader over I²C → MQTT |
| `voltronic.py` | Library for inverter communication |
| `services/mqtt_service.py` | MQTT worker — listens to data, calls the controller |
| `services/controller_service.py` | ControllerEngine — evaluates thresholds |
| `services/dashboard_service.py` | Data transformation for the frontend |
| `services/history_service.py` | SQLite history recording |

---

## Inverter data filtering

`mqtt_menic1.py` contains a filter (`filtruj()`) that cleans inverter data:

1. **Subnormal values** (abs < 1e-10) → zeroed
2. **Absolute limits** — values above the limit (e.g. voltage > 65V) → discarded
3. **±20% jump limit** — only for voltages (`battery_voltage`, `battery_voltage_scc`, `pv_voltage`)
4. **Power keys** — no jump limit (PV power fluctuates naturally)

Only the keys the dashboard actually uses are filtered. The rest (grid voltage,
frequency, bus voltage) are published raw without filtering.

---

## Network and access

| Address | What |
|---------|------|
| `http://192.168.0.191:5000` | Local dashboard (LAN) |
| `https://fiam-opi.dedyn.io` | HTTPS via Caddy (LAN) |
| `https://fv-peter.cz` | HTTPS via Cloudflare Tunnel (internet) |
| `http://192.168.0.191:5000/nastaveni` | Settings (password from `secrets.py`) |

SSH: `ssh fiam@192.168.0.191`

---

## Services

| Service | What it does | Restart |
|---------|--------------|---------|
| `fve-dashboard` | Flask + MQTT worker | `sudo systemctl restart fve-dashboard` |
| `fve-menic-reader` | Inverter reader | `sudo systemctl restart fve-menic-reader` |
| `fve-ewelink` | eWeLink bridge (pump) | `sudo systemctl restart fve-ewelink` |
| `mosquitto` | MQTT broker | `sudo systemctl restart mosquitto` |
| `caddy` | HTTPS proxy | `sudo systemctl restart caddy` |
| `dnsmasq` | Local DNS | `sudo systemctl restart dnsmasq` |
| `cloudflared-tunnel` | Cloudflare tunnel | `sudo systemctl restart cloudflared-tunnel` |

---

## Troubleshooting

### Dashboard shows old data / zeros

```bash
# Restart both main services
sudo systemctl restart fve-menic-reader fve-dashboard
```

### Hot tub shows power even when offline

After restarting `fve-dashboard` — fix from 12.8.2026: in the offline state
`virivka_actual_w` and `virivka_current` are zeroed.

### Inverter supplies no data

```bash
# Check the serial line
ls -la /dev/ttyUSB0
# Check MQTT data
mosquitto_sub -t "menic/1/data" -C 1 | python3 -m json.tool
```

### HTTPS does not work (certificate)

```bash
sudo bash /home/fiam/menic_web/deploy/caddy/fix-caddy.sh
```

### INA226 does not read

```bash
sudo i2cdetect -y 1
# Address 0x40 should be visible
sudo chmod a+rw /dev/i2c-1  # emergency permission
```

---

## Updating the code from GitHub

```bash
cd /home/fiam/menic_web
git pull
sudo systemctl restart fve-menic-reader fve-dashboard
```

---

*Last updated: 28. 9. 2026*

---

# MANUÁL — FVE Dashboard pro OrangePi 3 LTS

> Verze: 2026-09-28 | Obsluha a pochopení celého systému

---

## Co to je

FVE Dashboard je webová aplikace, která monitoruje a řídí domácí fotovoltaickou
elektrárnu. Běží na OrangePi 3 LTS (Armbian) a komunikuje s:

- **Měničem Voltronic Axpert** přes sériovou linku `/dev/ttyUSB0`
- **INA226** — I²C senzor napětí a proudu baterie
- **ESP32 výkonovými členy** — vířivka, podlahovky (přes MQTT)

---

## Dashboard (`/`)

Hlavní stránka zobrazuje živá data obnovovaná každé 2 sekundy:

| Prvek | Co ukazuje |
|-------|-----------|
| **PV panely** | Aktuální výkon FV panelů (W) |
| **Měnič 1** | Výkon měniče (VA), zátěž (%) |
| **Baterie** | Napětí (V), stav (% kapacity), vybíjecí proud (A) |
| **Bojler** | ON/OFF, zelená = topí |
| **Podlaha 300W** | ON/OFF |
| **Podlaha 2000W** | ON/OFF |
| **Podlaha 2200W** | ON/OFF + teploty vstup/výstup kotle |
| **Vířivka** | ON/OFF + **skutečný změřený výkon (W)** + teplota vody |

### Indikátory stavu

- **Barevná ikona** = zařízení online
- **Zašedlá ikona** = zařízení offline (ESP32 nedostupné)
- **Hodnota pod ikonou** = reálný změřený výkon (vířivka), nebo konstanta (bojler, podlahovky)

### Kliknutí na zařízení

Kliknutí na vířivku nebo podlahovku 2200W otevře webovou stránku daného
ESP32 (např. `http://192.168.0.106`), kde je detailní diagnostika.

---

## Nastavení (`/nastaveni`)

**Přístup:** `http://192.168.0.191:5000/nastaveni` — heslo ze `secrets.py`

### Co se dá nastavit

| Parametr | Popis |
|----------|-------|
| **zapni_XXX / vypni_XXX** | Napěťové meze pro sepnutí/vypnutí spotřebiče |
| **rizeni_podle** | Metrika: `batteryVoltage` (napětí bat.), `batteryFlow` (% kapacity), `inaB_V` (INA226) |
| **hystereze_s** | Minimální doba mezi změnami stavu (zabraňuje kmitání) |
| **power_XXX** | Jmenovitý výkon spotřebiče — pro výpočet celkové zátěže |
| **battery_capacity_ah** | Kapacita baterie v Ah |
| **sample_interval_s** | Interval vzorkování pro historii (s) |
| **cerpadlo_vypni_deltaT** | ΔT pro vypnutí čerpadla (°C) |
| **cerpadlo_max_min** | Kumulativní minuty ohřevu před zapnutím čerpadla |
| **cerpadlo_min_beh_min** | Minimální doba běhu čerpadla po zapnutí (minuty) |
| **cerpadlo_off_persist_min** | Jak dlouho musí ΔT držet pod mezí, než se čerpadlo vypne (minuty) |

### Sezónní profily

Dashboard podporuje 4 profily (jaro/léto/podzim/zima). Meze se dají nastavit
pro každý profil zvlášť — dashboard automaticky použije profil podle aktuálního
data.

---

## Statistiky (`/statistiky`)

Zobrazují historická data uložená v SQLite databázi `fve_history.db`:

- Spotřeba (dům, bojler, podlahovky, vířivka) v kWh
- Výroba FV v kWh
- Využití přebytků (%)

Data se ukládají každých `sample_interval_s` sekund. Agregace po hodinách/dnech.

---

## ControllerEngine — jak funguje řízení spotřebičů

Soubor: `services/controller_service.py`

ControllerEngine každých pár sekund vyhodnotí aktuální stav baterie a rozhodne,
které spotřebiče zapnout/vypnout:

1. Přečte `battery_voltage` (nebo `inaB_V`/`batteryFlow`) z `current_data`
2. Pro každý spotřebič porovná s mezemi `zapni_*` / `vypni_*` v `config.json`
3. Respektuje `hystereze_s` — nezmění stav dřív než po uplynutí intervalu
4. Publikuje příkaz přes MQTT (např. `fve/spotrebice/virivka/set`)

### Formát MQTT příkazu

```json
{
  "device": "virivka",
  "label": "Vířivka",
  "state": "ON",
  "enabled": true,
  "source": "batteryVoltage",
  "source_value": 27.1,
  "on_threshold": 27.0,
  "off_threshold": 26.9,
  "hystereze_s": 20.0,
  "updated_at": 1721234567
}
```

---

## Automatika oběhového čerpadla (Sonoff)

Soubor: `services/controller_service.py`, metoda `_tick_cerpadlo`. Podrobnosti v [EWELINK.md](EWELINK.md).

1. Kotel topí (`heating1_state_actual == 1`) → akumuluje se čas ohřevu.
2. Po `cerpadlo_max_min` (4) minutách → zapnutí čerpadla.
3. Čerpadlo běží minimálně `cerpadlo_min_beh_min` (60) minut.
4. Po min. době + ΔT (vstup−výstup) < `cerpadlo_vypni_deltaT` (3 °C) držící souvisle
   `cerpadlo_off_persist_min` (2) minuty → vypnutí + reset akumulace.
5. O půlnoci se akumulace resetuje.

Čerpadlo vypne jen při **platných** teplotách (ESP online + teploty > 0) — přechodné
čtení `0/0` nemůže čerpadlo falešně zastavit.

---

## ESP32 zařízení

### Vířivka (ESP32-32E N4)

- **IP:** `192.168.0.106`
- **Čidla:** SCT013 (proud), DS18B20 (teplota)
- **Relé:** 2×10A, NC zapojení (při výpadku relé = topí)
- **MQTT příkaz:** `fve/spotrebice/virivka/set` — `{"enabled": true/false}`
- **MQTT stav:** `fve/spotrebice/virivka/stav` — `{"status":"ZAP"/"OFF","vystup1":0/1,"vystup2":0/1,"proud0":12.5,"teplota":28.3}`
- **Last Will:** `fve/spotrebice/virivka/status` — `{"status":"online"/"offline"}`
- **Web:** `http://192.168.0.106` (heslo — výchozí v ESP firmwaru)
- **Sériové příkazy:** `scan` (sken DS18B20), `status` (výpis stavu)

### Podlahovka 2200W

- **IP:** `192.168.0.151`
- **Čidla:** 2× DS18B20 (vstup/výstup kotle)
- **Relé:** 1×30A
- **MQTT příkaz:** `fve/spotrebice/podlaha2200/set` — `{"enabled": true/false}`
- **MQTT teploty:** `fve/spotrebice/podlaha2200/teplota` — `{"vstup":42.5,"vystup":35.1,"valid":true}`
- **Web:** `http://192.168.0.151` (heslo — výchozí v ESP firmwaru)

### Podlahovky (300W + 2000W, 2-kanálový ESP32)

- **MQTT příkaz 300W:** `fve/spotrebice/podlaha300/set` — `{"enabled": true/false}`
- **MQTT příkaz 2000W:** `fve/spotrebice/podlaha2000/set` — `{"enabled": true/false}`

---

## Struktura souborů na OPI

Vše běží z `/home/fiam/menic_web/`. Klíčové soubory:

| Soubor | Účel |
|--------|------|
| `app01.py` | Flask server (port 5000) + MQTT worker daemon |
| `config.json` | Veškeré meze a výkony — **jediný zdroj pravdy** |
| `mqtt_menic1.py` | Čtečka měniče přes `/dev/ttyUSB0` → MQTT |
| `ina226_mqtt.py` | Čtečka INA226 přes I²C → MQTT |
| `voltronic.py` | Knihovna pro komunikaci s měničem |
| `services/mqtt_service.py` | MQTT worker — poslouchá data, volá controller |
| `services/controller_service.py` | ControllerEngine — vyhodnocuje meze |
| `services/dashboard_service.py` | Transformace dat pro frontend |
| `services/history_service.py` | SQLite záznam historie |

---

## Filtrování dat z měniče

`mqtt_menic1.py` obsahuje filtr (`filtruj()`), který čistí data z měniče:

1. **Subnormální hodnoty** (abs < 1e-10) → vynulovat
2. **Absolutní limity** — hodnoty nad limit (např. napětí > 65V) → zahodit
3. **±20% omezení skoků** — jen pro napětí (`battery_voltage`, `battery_voltage_scc`, `pv_voltage`)
4. **Výkonové klíče** — bez omezení skoků (výkon FV lítá přirozeně)

Filtrují se jen klíče, které dashboard skutečně používá. Ostatní (grid voltage,
frekvence, bus voltage) se publikují surové bez filtrování.

---

## Síť a přístup

| Adresa | Co |
|--------|-----|
| `http://192.168.0.191:5000` | Lokální dashboard (LAN) |
| `https://fiam-opi.dedyn.io` | HTTPS přes Caddy (LAN) |
| `https://fv-peter.cz` | HTTPS přes Cloudflare Tunnel (internet) |
| `http://192.168.0.191:5000/nastaveni` | Nastavení (heslo ze `secrets.py`) |

SSH: `ssh fiam@192.168.0.191`

---

## Služby

| Služba | Co dělá | Restart |
|--------|---------|---------|
| `fve-dashboard` | Flask + MQTT worker | `sudo systemctl restart fve-dashboard` |
| `fve-menic-reader` | Čtečka měniče | `sudo systemctl restart fve-menic-reader` |
| `fve-ewelink` | eWeLink bridge (čerpadlo) | `sudo systemctl restart fve-ewelink` |
| `mosquitto` | MQTT broker | `sudo systemctl restart mosquitto` |
| `caddy` | HTTPS proxy | `sudo systemctl restart caddy` |
| `dnsmasq` | Lokální DNS | `sudo systemctl restart dnsmasq` |
| `cloudflared-tunnel` | Cloudflare tunel | `sudo systemctl restart cloudflared-tunnel` |

---

## Řešení problémů

### Dashboard ukazuje stará data / nuly

```bash
# Restartuj obě hlavní služby
sudo systemctl restart fve-menic-reader fve-dashboard
```

### Vířivka ukazuje výkon i když je offline

Po restartu `fve-dashboard` — oprava z 12.8.2026: při offline stavu se
`virivka_actual_w` a `virivka_current` nulují.

### Měnič nedodává data

```bash
# Ověř sériovou linku
ls -la /dev/ttyUSB0
# Ověř MQTT data
mosquitto_sub -t "menic/1/data" -C 1 | python3 -m json.tool
```

### HTTPS nefunguje (certifikát)

```bash
sudo bash /home/fiam/menic_web/deploy/caddy/fix-caddy.sh
```

### INA226 nečte

```bash
sudo i2cdetect -y 1
# Měla by být vidět adresa 0x40
sudo chmod a+rw /dev/i2c-1  # nouzové oprávnění
```

---

## Aktualizace kódu z GitHubu

```bash
cd /home/fiam/menic_web
git pull
sudo systemctl restart fve-menic-reader fve-dashboard
```

---

*Poslední aktualizace: 28. 9. 2026*
