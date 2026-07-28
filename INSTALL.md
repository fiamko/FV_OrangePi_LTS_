# INSTALL — Kompletní instalační průvodce FVE systému

> Verze: 2026-07-11 | Od holého Armbianu po plně funkční HTTPS dashboard

**Legenda značek:**
- ⚠️ **PRE-AI** — Tento krok byl hotov před asistencí CodeWhale. Příkazy jsou
  ověřené
  zpětnou analýzou běžícího systému, ale neprocházely jsme je spolu krok za
  krokem.
  V případě nejasností konzultuj.
- ✅ **AI-FIX** — Tento krok jsme dělali spolu, příkazy jsou odladěné a ověřené.

---

## Krok 1: Armbian na Orange Pi ⚠️ PRE-AI

### 1.1 Stáhnout a nahrát Armbian

Stáhni Armbian pro Orange Pi PC2 (nebo jiný model) z
  https://www.armbian.com/orange-pi-pc2/
Použij **Armbian Imager** nebo Rufus. Nahrát na microSD kartu (doporučeno 16+
  GB).

### 1.2 První spuštění

- Vlož kartu do OPI, připoj LAN kabel, HDMI monitor (pro první boot), napájení.
- Po nabootování se přihlas jako **root** (heslo: 1234).
- Systém tě vyzve ke změně hesla a vytvoření uživatele.
- Nastav IP na statickou `192.168.0.191` (přes `armbian-config` → Network → IP →
  Static).

### 1.3 Základní aktualizace

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget python3 python3-pip python3-venv vim nano

# I²C nástroje pro INA226
sudo apt install -y i2c-tools python3-smbus

# Povolení I²C
sudo armbian-config   # → System → Hardware → i2c0/i2c1 → Enable
```

### 1.4 Ověření I²C (INA226)

```bash
sudo i2cdetect -y 1
# Měla by se objevit adresa 0x40 (INA226)
```

---

## Krok 2: Vytvoření uživatele `fiam` ⚠️ PRE-AI

```bash
sudo useradd -m -s /bin/bash fiam
sudo usermod -a -G dialout fiam     # přístup k /dev/ttyUSB0
sudo usermod -a -G i2c fiam         # přístup k I²C (pokud skupina existuje)
```

Nastav heslo:
```bash
sudo passwd fiam
```

---

## Krok 3: Mosquitto MQTT broker ⚠️ PRE-AI

```bash
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

Ověření:
```bash
systemctl status mosquitto
mosquitto_sub -t "test" &
mosquitto_pub -t "test" -m "ahoj"
# Mělo by vypsat "ahoj"
```

---

## Krok 4: Nakopírování projektu na OPI ⚠️ PRE-AI

### 4.1 Vytvoření pracovního adresáře

```bash
sudo mkdir -p /home/fiam/menic_web
sudo chown -R fiam:fiam /home/fiam/menic_web
```

### 4.2 Přenesení souborů z Windows PC

Na **Windows PC** (PowerShell, z adresáře projektu):

```powershell
scp -r templates static routes services models __pycache__ fiam@192.168.0.191:/home/fiam/menic_web/
scp app01.py config.json config.json requirements.txt fiam@192.168.0.191:/home/fiam/menic_web/
scp voltronic.py ina226_mqtt.py mqtt_menic1.py fiam@192.168.0.191:/home/fiam/menic_web/
scp check_dns.py MANUAL.md INSTALL.md fiam@192.168.0.191:/home/fiam/menic_web/
scp -r deploy fiam@192.168.0.191:/home/fiam/menic_web/
```

### 4.3 Ověření přenosu

```bash
ls -la /home/fiam/menic_web/
# Měly by tam být: app01.py, config.json, static/, templates/, routes/, services/, models/, deploy/
```

---

## Krok 5: Python virtuální prostředí ⚠️ PRE-AI

```bash
cd /home/fiam/menic_web
python3 -m venv fve-env
source fve-env/bin/activate
pip install --upgrade pip
pip install Flask paho-mqtt smbus2
deactivate
```

Ověření:
```bash
/home/fiam/menic_web/fve-env/bin/python -c "import flask; import paho.mqtt.client; print('OK')"
```

---

## Krok 6: Systemd služby ⚠️ PRE-AI

### 6.1 Nakopírovat service soubory

Service soubory už jsou v `/home/fiam/menic_web/deploy/systemd/`. Zkopíruj je:

```bash
sudo cp /home/fiam/menic_web/deploy/systemd/fve-menic-reader.service /etc/systemd/system/
sudo cp /home/fiam/menic_web/deploy/systemd/fve-dashboard.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/fve-menic-reader.service
sudo chmod 644 /etc/systemd/system/fve-dashboard.service
sudo systemctl daemon-reload
```

### 6.2 Spuštění

```bash
sudo systemctl enable fve-menic-reader
sudo systemctl enable fve-dashboard
sudo systemctl start fve-menic-reader
sudo systemctl start fve-dashboard
```

### 6.3 Ověření

```bash
systemctl status fve-menic-reader
systemctl status fve-dashboard

# Dashboard by měl běžet:
curl -s http://localhost:5000 | head -5
# Měl by vrátit HTML stránku
```

---

## Krok 7: Doména desec.io ⚠️ PRE-AI

### 7.1 Registrace domény

1. Jdi na https://desec.io
2. Vytvoř doménu `fiam-opi.dedyn.io`
3. V nastavení domény vygeneruj API token (Token management → Create Token)
4. Ulož token — budeš ho potřebovat pro Lego certifikát

### 7.2 ddclient (aktualizace dynamické IP)

Na OPI:
```bash
sudo apt install -y ddclient
```

Konfigurace `/etc/ddclient.conf`:
```
protocol=dyndns2
use=web
server=update.dedyn.io
login=fiam-opi.dedyn.io
password='TvujDesecToken'
fiam-opi.dedyn.io
```

```bash
sudo chmod 600 /etc/ddclient.conf
sudo systemctl enable --now ddclient
```

### 7.3 Ověření DNS

```bash
python3 /home/fiam/menic_web/check_dns.py
```

---

## Krok 8: Lego — Let's Encrypt certifikát ⚠️ PRE-AI

### 8.1 Instalace Lego

```bash
cd /tmp
wget https://github.com/go-acme/lego/releases/download/v4.22.2/lego_v4.22.2_linux_arm64.tar.gz
tar -xzf lego_v4.22.2_linux_arm64.tar.gz
sudo mv lego /usr/local/bin/
sudo chmod +x /usr/local/bin/lego
lego --version   # mělo by vypsat verzi
```

### 8.2 Spuštění get-cert.sh

Skript je v projektu:

```bash
sudo -u fiam bash /home/fiam/menic_web/deploy/caddy/get-cert.sh
```

Před spuštěním se ujisti, že skript obsahuje správný **DESEC_TOKEN** a
  **e-mail**.
Po úspěchu by certifikáty měly být v:

```bash
ls -la /home/fiam/.lego/certificates/
# fiam-opi.dedyn.io.crt, fiam-opi.dedyn.io.key, fiam-opi.dedyn.io.issuer.crt
```

---

## Krok 9: Caddy — HTTPS reverzní proxy ⚠️ PRE-AI

### 9.1 Instalace Caddy

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

### 9.2 Vytvoření bundle a nasazení konfigurace

Použij `fix-caddy.sh` — ten udělá všechno: bundle, Caddyfile, restart:

```bash
sudo bash /home/fiam/menic_web/deploy/caddy/fix-caddy.sh
```

Pokud bys potřeboval Caddy nasadit ručně:

```bash
# 1. Vytvoř bundle
sudo mkdir -p /etc/caddy
cat /home/fiam/.lego/certificates/fiam-opi.dedyn.io.crt \
    /home/fiam/.lego/certificates/fiam-opi.dedyn.io.issuer.crt \
    | sudo tee /etc/caddy/fve-bundle.crt > /dev/null

# 2. Nakopíruj klíč
sudo cp /home/fiam/.lego/certificates/fiam-opi.dedyn.io.key /etc/caddy/fve-bundle.key
sudo chmod 644 /etc/caddy/fve-bundle.crt /etc/caddy/fve-bundle.key

# 3. Nakopíruj Caddyfile
sudo cp /home/fiam/menic_web/deploy/caddy/Caddyfile /etc/caddy/Caddyfile

# 4. Vytvoř log adresář
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy

# 5. Restart
sudo systemctl restart caddy
```

### 9.3 Ověření HTTPS

```bash
systemctl status caddy
curl -k https://localhost/ | head -5

# Z jiného zařízení:
# https://fiam-opi.dedyn.io
```

---

## Krok 9b: Cloudflare Tunnel — přístup z internetu ✅ AI-FIX

> **Poznámka:** Tento krok je potřeba jen pokud nemáš veřejnou IP adresu
>   (CGNAT).

Cloudflare Tunnel vytváří zabezpečený tunel z OPI na Cloudflare edge.
Doména `fv-peter.cz` (WEDOS → Cloudflare DNS) je přes něj dostupná z celého
světa.

### 9b.1 Instalace cloudflared

Cloudflared je binárka v `/home/fiam/.local/bin/cloudflared`.

```bash
# Stažení ARM64 binárky
curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 -o /home/fiam/.local/bin/cloudflared
chmod +x /home/fiam/.local/bin/cloudflared
echo 'export PATH=$HOME/.local/bin:$PATH' >> /home/fiam/.bashrc
```

### 9b.2 Autentizace s Cloudflare

```bash
/home/fiam/.local/bin/cloudflared tunnel login
# → otevři URL v prohlížeči, vyber doménu fv-peter.cz, Authorize
```

### 9b.3 Vytvoření tunelu

```bash
/home/fiam/.local/bin/cloudflared tunnel create fve-tunnel
```

Konfigurace je v `/home/fiam/.cloudflared/config.yml` a v repozitáři
(`deploy/cloudflared/config.yml`).

### 9b.4 DNS routing

```bash
/home/fiam/.local/bin/cloudflared tunnel route dns fve-tunnel fv-peter.cz
/home/fiam/.local/bin/cloudflared tunnel route dns fve-tunnel www.fv-peter.cz
```

### 9b.5 Systemd služba

```bash
sudo cp /home/fiam/menic_web/deploy/systemd/cloudflared-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-tunnel
```

Ověření:
```bash
systemctl status cloudflared-tunnel
curl -s https://fv-peter.cz | head -5
```

---

## Krok 10: Automatické obnovení certifikátu ✅ AI-FIX

Toto je naše společná oprava — **původní renew-cert.sh jen volal `lego renew`,
  ale nepřebaloval bundle pro Caddy**.

### 10.1 Opravený renew-cert.sh

Ujisti se, že `/home/fiam/menic_web/deploy/caddy/renew-cert.sh` obsahuje
po `lego renew` i kroky:
1. Ověření existence `.crt`, `.key`, `.issuer.crt`
2. Vytvoření bundle `cat cert issuer > /etc/caddy/fve-bundle.crt`
3. Kopírování klíče do `/etc/caddy/fve-bundle.key`
4. `systemctl reload caddy`

Správný soubor je ten, který je teď v repozitáři — vznikl při naší opravě.

### 10.2 Nakopírovat do `/usr/local/bin/` a cron

```bash
# Nakopírování (pokud /usr/local/bin neexistuje: sudo mkdir -p /usr/local/bin)
sudo cp /home/fiam/menic_web/deploy/caddy/renew-cert.sh /usr/local/bin/renew-cert.sh
sudo chmod +x /usr/local/bin/renew-cert.sh

# Nastavení cronu (jako root)
sudo crontab -e
# Přidat řádek:
# 0 3 * * 0 /usr/local/bin/renew-cert.sh
```

Ověření:
```bash
sudo crontab -l | grep renew-cert
# Mělo by vypsat: 0 3 * * 0 /usr/local/bin/renew-cert.sh
```

### 10.3 Ruční test obnovení

```bash
sudo /usr/local/bin/renew-cert.sh
# Mělo by projít a na konci: "Pocet certifikatu v retezci (ma byt 2+): X"
```

---

## Krok 11: DNS resolv.conf oprava ✅ AI-FIX

Na OPI byl `systemd-resolved` deaktivovaný, ale symlink `/etc/resolv.conf`
stále mířil na jeho stub. **Toto musíš opravit na každé nové instalaci:**

```bash
# Zkontroluj aktuální stav
ls -la /etc/resolv.conf
# Pokud ukazuje: lrwxrwxrwx ... -> /run/systemd/resolve/stub-resolv.conf

# Oprava:
sudo rm /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf
```

Ověření:
```bash
cat /etc/resolv.conf
# nameserver 8.8.8.8
# nameserver 1.1.1.1

getent hosts acme-v02.api.letsencrypt.org
# Měla by se zobrazit IP adresa
```

---

## Krok 12: dnsmasq — lokální DNS pro tablety ⚠️ PRE-AI

Aby tablety v lokální síti našly `fiam-opi.dedyn.io` → `192.168.0.191`:

```bash
sudo apt install -y dnsmasq

sudo tee /etc/dnsmasq.d/fve.conf << 'EOF'
interface=wlan0
bind-interfaces
address=/fiam-opi.dedyn.io/192.168.0.191
server=8.8.8.8
server=8.8.4.4
EOF

sudo systemctl restart dnsmasq
sudo systemctl enable dnsmasq
```

### Nastavení na routeru

V DHCP nastavení routeru nastavit:
- **DNS1:** `192.168.0.191` (OPI — překládá lokální doménu)
- **DNS2:** `8.8.8.8` (Google — fallback pro internet)

**Poznámka:** OPI samo nesmí používat sebe jako DNS — proto jsme v kroku 11
  nastavili
`8.8.8.8` a `1.1.1.1` přímo.

---

## Krok 13: PWA — dynamický manifest, ikony a service worker ✅ AI-FIX

Aby šel dashboard "nainstalovat" na plochu jako fullscreen appku — a navíc
se **rozlišuje LAN vs. internet** přístup:

### 13.1 Dynamický manifest (`/manifest.json`)

Manifest **není statický soubor**, ale Flask routa v `app01.py`. Podle
`Host` headeru vrací jinou konfiguraci:

| Host | Název | Ikona | Barva |
|---|---|---|---|
| `fiam-opi.dedyn.io` | FIAM LAN 🟢 | `icon-lan-*.png` | zelená `#228B22` |
| `fv-peter.cz` | FIAM Web 🔵 | `icon-web-*.png` | modrá `#003366` |

### 13.2 PNG ikony (pro Windows)

Windows nepodporuje SVG ikony — proto jsou generované PNG skriptem
`generate_icons.py`:

```bash
python3 generate_icons.py
# Vytvoří 4 soubory v static/icons/:
#   icon-lan-192.png, icon-lan-512.png (zelené)
#   icon-web-192.png, icon-web-512.png (modré)
```

### 13.3 Ostatní PWA soubory

Aby šel dashboard "nainstalovat" na plochu jako fullscreen appku:

### 13.1 Soubory, které musí být v `/home/fiam/menic_web/static/`

**Dynamický manifest (`/manifest.json` routa v `app01.py` — viz 13.1):**
```json
{
    "name": "FIAM Elektrárna",
    "short_name": "FIAM",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#000000",
    "theme_color": "#000000",
    "icons": [{"src": "/static/icons/panely.png", "sizes": "any", "type": "image/png"}]
}
```

**`sw.js`:**
```javascript
self.addEventListener("install",function(e){self.skipWaiting()});
self.addEventListener("fetch",function(e){e.respondWith(fetch(e.request))});
```

**V `templates/index.html`** musí být v `<head>`:
```html
<link rel="manifest" href="/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
```

A před `</body>`:
```html
<script>
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/sw.js');
    }
</script>
```

Tyto soubory už jsou v repozitáři — stačí je přenést na OPI.

### 13.2 Instalace na zařízení

1. Otevři `https://fiam-opi.dedyn.io` (LAN) nebo `https://fv-peter.cz` (web) v Chrome/Kiwi
2. Menu → **Přidat na plochu** / **Install app**

---

## Krok 14: Spuštění a restart po migraci ⚠️ PRE-AI

Po dokončení všech kroků restartuj všechny služby:

```bash
sudo systemctl restart fve-menic-reader fve-dashboard cloudflared-tunnel
```

### Souhrn běžících služeb

| Služba | Port | Příkaz |
|---|---|---|
| Flask dashboard | 5000 (localhost) | `systemctl status fve-dashboard` |
| Čtečka měniče | sériový port | `systemctl status fve-menic-reader` |
| Mosquitto MQTT | 1883 (localhost) | `systemctl status mosquitto` |
| Caddy HTTPS | 80 + 443 | `systemctl status caddy` |
| dnsmasq DNS | 53 (lokálně) | `systemctl status dnsmasq` |
| ddclient DNS | — | `systemctl status ddclient` |
| Cloudflare Tunnel | tunel | `systemctl status cloudflared-tunnel` |

---

## Krok 15: Závěrečné ověření

### 15.1 Ověření na OPI

```bash
# Všechny služby běží?
systemctl status fve-dashboard fve-menic-reader caddy mosquitto dnsmasq cloudflared-tunnel

# Dashboard odpovídá?
curl -s http://localhost:5000 | head -5

# HTTPS odpovídá?
curl -k https://localhost/ | head -5

# Certifikát platný?
sudo openssl s_client -connect localhost:443 -servername fiam-opi.dedyn.io < /dev/null 2>/dev/null | openssl x509 -noout -dates

# MQTT data tečou?
mosquitto_sub -t "menic/1/data" -C 1 | python3 -m json.tool

# INA226 — I²C zařízení viditelné?
sudo i2cdetect -y 1
```

### 15.2 Ověření z jiného zařízení

1. Otevřít `https://fiam-opi.dedyn.io` — měl by se zobrazit dashboard
2. Zelený zámek v adresním řádku
3. Data se obnovují (hodnoty nejsou nuly)
4. "Přidat na plochu" funguje

---

## Krok 16: Migrace na nové OPI

Postup pro přechod na výkonnější OPI:

### 16.1 Na novém OPI

- Proveď kroky 1–15 (plná instalace)
- Ponech běžící Flask + Caddy + Mosquitto

### 16.2 Na starém OPI (bude jen čtečka 2. měniče)

Jakmile bude připojen druhý měnič:

1. Upravit (nebo vytvořit) `mqtt_menic2.py` — stejný princip jako
   `mqtt_menic1.py`,
   ale data publikuje pod `menic/2/data` a připojuje se k MQTT brokeru
   **nového** OPI
   (změnit `MQTT_BROKER = '192.168.0.191'` na IP nového OPI).

2. Vytvořit systemd službu pro druhý měnič, spouštět jen ji.

3. Nové OPI bude poslouchat MQTT témata `menic/2/data/#` a začlení je do
   dashboardu
   (to už je práce na rozšíření — viz MANUAL.md, kapitola 13).

---

## Rychlý tahák — oprava po havárii

Když po výpadku proudu/restartu web nejede:

```bash
# 1. Základní diagnostika
systemctl status fve-dashboard fve-menic-reader caddy mosquitto

# 2. Certifikát — okamžitá oprava
sudo bash /home/fiam/menic_web/deploy/caddy/fix-caddy.sh

# 3. DNS — ověření
cat /etc/resolv.conf

# 4. Kompletní restart
sudo systemctl restart fve-menic-reader fve-dashboard cloudflared-tunnel caddy
```

---

*Poslední aktualizace: 11. 7. 2026*

