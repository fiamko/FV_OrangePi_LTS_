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
2. Po `cerpadlo_max_min` (45) minutách → **zapnutí čerpadla**.
3. Čerpadlo běží minimálně `cerpadlo_min_beh_min` (60) minut — ochrana proti cyklu
   (po zapnutí se ΔT teprve vytváří).
4. Po min. době + **ΔT (vstup−výstup) < `cerpadlo_vypni_deltaT` (10 °C)** → vypnutí + reset akumulace.
5. **O půlnoci** se akumulace resetuje.

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
