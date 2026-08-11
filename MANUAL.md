# MANUÁL — FVE Dashboard pro OrangePi 3 LTS

> Verze: 2026-08-12 | Obsluha a pochopení celého systému

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
- **MQTT teploty:** `fve/spotrebice/podlaha2200/teplota` — `{"vstup":42.5,"vystup":35.1}`
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

*Poslední aktualizace: 12. 8. 2026*
