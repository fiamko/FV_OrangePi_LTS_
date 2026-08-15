# FV_OrangePi_LTS_

> Verze: 2026-08-12

**FVE Dashboard pro OrangePi 3 LTS** — monitorování a řízení domácí fotovoltaické elektrárny přes webové rozhraní.

---
## Motivace k vývoji vlastního systému monitoringu FV elektrárny
Vlastní ostrovní elektrárna s využitím veřejné elektrické sítě jako záložního zdroje s automatickým třífázovým přepínačem sítí a blokádou v přepnutí na tuto síť. 
Zakoupená licence na SolarAsisstant nevyhovovala funkcemi, omezením na jeden měnič a uzavřením systému bez možnosti úprav dle potřeby. Rozhodnutí vytvořit systém vlastní bez podobných omezení, hlavně s možností načítat data z více měničů, nebo řídit vytěžování i do zakoupené vířivky s vlastní regulací a neznámým kódem pro dálkové vyp/zap topení. Ostatní spotřebiče jsou běžné odporové spirály jednak jako topné tělesa v kotli pro vodní podlahové topení, ohřev teplé vody, nebo jako elektrické podlahové topení s vlastní regulaci.
Vířivka a její úpravy: Po odkrytování pohonné jednotky běžné nafukovací vířivky ze supermarketu jsem zjistil dvě samostatné topné spirály, každá příkon 1kW, tedy stupňovité řízení výkonu topení. Tohle je výborně využitelné na vytěžování zbytkového výkonu mojí FV. Jeden vývod každé spirály jsem přerušil NC kontakty dvou relé v modulu ESP32 z Aliexpressu. Pokud mě budete kopírovat v této úpravě vířivky, konáte tak na vlastní nebezpečí!
Ráno, ve dni kdy chci mít ohřátou vířivku tuto normálně zapojím a nastavím ohřev, čím se zapne oběhové čerpadlo, ale spirály se po cca 1 minutě odpojí a čeká se příkaz z nadřazeného OPI LTS pro zapnutí ohřevu. 
Vytěžování řídím primitivně podle napětí baterie a toto je nastavitelné v setup OPI LTS - náhled živého a fungujícího systému je na adrese mého webu, kde je vidět nastavení OPI i jednotlivých ESP. Možnost měnit nastavení je bezpečně zaheslovaná.
OPI vyhodnotí podle napětí baterie nastavený práh zapnutí, všechny ESP mají hysterezi časovou pro zamezení blikání jako u analogového řízení dosud používaného, uloží do MQTT povel na zapnutí jednotlivých spotřebičů a takto řídí v reálném čase vytěžování tak, aby byla energie z panelů maximálně využita pro užitečné uložení a využití. 
Tím jsem eliminoval blikání jednoduchého analogového spínání napěťovým prahem, zvýšil přesnost nastavení na stotiny voltu a zajistil tak vždy dostatek energie v baterii pro noční provoz elektrárny.
Jednotlivé ESP32, uložené v samostatných repo jsou jedno i dvou reléové moduly běžně k zakoupení na Aliexpres, Amazon či jiných, podobných tržištích a přibude i možnost změny firmwaru v Sonoff - u mně na spínání oběhového čerpadla ve vodním okruhu podlahového topení.
Systém je pořád ve vývoji, přibývají další funkce a možnosti rozšíření. Vše neustále sleduji a nastavuji, ale z větší bezpečností jako u původního analogového systému, navíc mám kdekoli a kdykoli kontrolu co se v domácnosti děje, samotná domácnost (myčka, pračka, pečící trouby a pod) mají absolutní přednost a bezpečnostní funkce v samotných ESP urychlují reakci na zvýšený odběr domácnosti odpojením vytěžování bez čekání na povel od OPI.
Na webu FV-peter.cz jsou některé komponenty šedé a tedy nepřipojené do systému či už pro jejich vypnutí, poruchu nebo servis. U měniče číslo 2 mám poruchu na sériovém portu a INA není dokončená pro citlivost na rušení ve strojovně. Bojler není připojen (zatím) vůbec. 
Signalizace jednotlivých funkcí na webu: Šedá ikona je komponenta nepřipojena k MQTT, černá signalizuje připojení a funkci. Výkon (číslice) pod ikonou je šedý, pokud je příkaz z OPI off, zčerná po příkazu ON. animované čáry ke komponentům jsou šedé pokud ESP hlásí svůj stav jako OFF, když se relé zapne, čára zmodrá a animuje tok energie k spotřebiči. U kotle podlahovky se zobrazuje nad ikonou teplota vstupní a výstupní do/z kotle, která se občas změní podle hlášení stavů z ESP, ale po 10 sec se vrátí na teplotu. Vířivka podobně signalizuje teplotu a pod ikonou i reálný odběr výkonu z FV. Ostatní je jasné a není potřeba vysvětlovat.

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
