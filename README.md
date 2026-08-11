# FV_OrangePi_LTS_

> Verze: 2026-08-12

**FVE Dashboard pro OrangePi 3 LTS** — monitorování a řízení domácí fotovoltaické elektrárny přes webové rozhraní.

---

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

---

## Struktura projektu

```
menic_web/
├── app01.py                  # Flask server (port 5000), spouští MQTT worker
├── config.json               # Meze pro spínání spotřebičů, sezónní profily
├── mqtt_menic1.py            # Čtečka měniče přes /dev/ttyUSB0 → MQTT
├── ina226_mqtt.py            # Čtečka INA226 přes I²C → MQTT
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
- **Nastavení:** `http://192.168.0.191:5000/nastaveni` (heslo: **změňte v app01.py!**)
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

---

## ESP32 výkonové členy

Každý ESP32:
- Poslouchá MQTT povely z ControllerEngine
- Hlásí stav (`fve/.../stav`) a online/offline (`fve/.../status` Last Will)
- Na dashboardu se zobrazuje:
  - **Online** = barevná ikona, kliknutí otevře web ESP
  - **Offline** = zašedlá ikona

---

## Zabezpečení

- MQTT broker pouze na LAN (`iptables` omezení na `192.168.0.0/24`)
- Heslo pro nastavení v `app01.py` (`SETTINGS_PASSWORD`) — **před nasazením změnit!**
- Externí přístup přes Caddy + Cloudflare Tunnel (volitelné)

---

## Licence

MIT — dělej si s tím co chceš.
