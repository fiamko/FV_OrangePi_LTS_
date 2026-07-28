# Nastavení HTTPS pro FVE dashboard — krok za krokem

> **Doména:** `fiam-opi.dedyn.io`  
> **Token (desec.io):** už je v `renew-cert.sh`  
> **Backend:** Flask na `localhost:5000`  

## 0. Předpoklady

- OPI běží na Armbianu, IP `192.168.0.191`
- Flask už běží jako systemd služba (`fve-dashboard.service`), port 5000
- Caddy už je nainstalované (asi přes `apt install caddy`)

Ověř, kde Caddy je:

```bash
which caddy
systemctl status caddy
```

Pokud neběží jako služba, zjisti jak jsi ho spouštěl.

---

## 1. Nainstalovat lego (ACME klient)

Lego je statická binárka, žádné závislosti. OPI má ARM64:

```bash
# Stažení
cd /tmp
wget https://github.com/go-acme/lego/releases/download/v4.22.2/lego_v4.22.2_linux_arm64.tar.gz

# Rozbalení
tar -xzf lego_v4.22.2_linux_arm64.tar.gz

# Instalace
sudo mv lego /usr/local/bin/
sudo chmod +x /usr/local/bin/lego

# Ověření
lego --version
```

---

## 2. Získat certifikát přes DNS-01

```bash
# Token je uložen v /home/fiam/.desec_token (chmod 600)
# Pokud ještě neexistuje, vytvoř ho:
#   echo 'tvuj-token' | sudo tee /home/fiam/.desec_token
#   sudo chmod 600 /home/fiam/.desec_token

# Spusť lego (běž jako uživatel fiam, ne root!)
sudo -u fiam bash -c "
  export DESEC_TOKEN=\$(cat /home/fiam/.desec_token)
  /usr/local/bin/lego \
    --email tvuj@email.cz \
    --dns desec \
    --domains fiam-opi.dedyn.io \
    --accept-tos \
    --path /home/fiam/.lego \
    run
"
```

> **Nahraď `tvuj@email.cz` svým emailem!**
> Let's Encrypt na něj pošle varování, když certifikát bude expirovat.

Po úspěchu uvidíš:

```
[INFO] [fiam-opi.dedyn.io] Server responded with a certificate.
```

Certifikáty budou v:
- `/home/fiam/.lego/certificates/fiam-opi.dedyn.io.crt`
- `/home/fiam/.lego/certificates/fiam-opi.dedyn.io.key`

---

## 3. Zastavit staré Caddy a nasadit novou konfiguraci

```bash
# Záloha stávajícího Caddyfile
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak 2>/dev/null || true

# Nakopírovat nový Caddyfile
sudo cp /home/fiam/menic_web/deploy/caddy/Caddyfile /etc/caddy/Caddyfile

# Vytvořit adresář pro logy
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy

# Ověřit syntaxi
caddy validate --config /etc/caddy/Caddyfile

# Restartovat Caddy
sudo systemctl restart caddy
sudo systemctl status caddy
```

---

## 4. Ověřit na PC/telefonu

Otevři v prohlížeči:

```
https://fiam-opi.dedyn.io
```

Pokud se stránka nenačte, přidej do `/etc/hosts` na počítači:

```
192.168.0.191   fiam-opi.dedyn.io
```

A znovu načti `https://fiam-opi.dedyn.io`. **Měl bys vidět ZELENÝ ZÁMEK.**

---

## 5. Tablet: lokální DNS přes OPI

Tablety na stejné WiFi musí `fiam-opi.dedyn.io` překládat na `192.168.0.191`.

### Varianta A: DNS server na OPI (doporučeno)

```bash
# Nainstalovat dnsmasq
sudo apt install dnsmasq

# Konfigurace
sudo tee /etc/dnsmasq.d/fve.conf << 'EOF'
# Poslouchej jen na lokální síti
interface=wlan0
bind-interfaces

# Doménu přelož na lokální IP OPI
address=/fiam-opi.dedyn.io/192.168.0.191

# Ostatní dotazy přepošli na Google DNS
server=8.8.8.8
server=8.8.4.4
EOF

# Restart
sudo systemctl restart dnsmasq
sudo systemctl enable dnsmasq
```

Potom na **každém tabletu**:
- Jdi do WiFi nastavení → dlouze podrž připojenou síť → Upravit síť → Rozšířené možnosti
- **Nastavení IP:** Statické (nebo DHCP)
- **DNS 1:** `192.168.0.191`
- Uložit

### Varianta B: Upravit hosts na tabletu (Android)

Na Androidu lze `/etc/hosts` upravit jen s rootem. Pokud tablety nemají root, viz varianta A.

---

## 6. Automatické obnovení certifikátu

Certifikát od Let's Encrypt platí 90 dní. Obnovujeme týdně (stačí):

```bash
# Nakopírovat obnovovací skript
sudo cp /home/fiam/menic_web/deploy/caddy/renew-cert.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/renew-cert.sh

# Upravit email v renew-cert.sh!
sudo nano /usr/local/bin/renew-cert.sh
#   Najdi tvuj-email@example.com → napiš svůj email

# Přidat do cronu (spustí se každou neděli ve 3:00)
sudo crontab -e
# Přidej řádek:
# 0 3 * * 0 /usr/local/bin/renew-cert.sh
```

---

## 7. Závěrečné ověření

- [ ] `https://fiam-opi.dedyn.io` — zelený zámek na PC
- [ ] `https://fiam-opi.dedyn.io` — zelený zámek na Android telefonu
- [ ] `https://fiam-opi.dedyn.io` — zelený zámek na obou tabletech
- [ ] WakeLock tlačítko funguje (displej nezhasne)
- [ ] Dashboard se obnovuje (`/data` endpoint vrací JSON)
- [ ] Nastavení a Statistiky fungují

---

## Diagnostika — co když nefunguje

**Certifikát se nezíská:**
```bash
sudo -u fiam bash -c 'export DESEC_TOKEN=$(cat /home/fiam/.desec_token); \
  /usr/local/bin/lego --email tvuj@email.cz --dns desec \
  --domains fiam-opi.dedyn.io --accept-tos --path /home/fiam/.lego run
```

**Caddy se nespustí:**
```bash
sudo journalctl -u caddy -n 50
```

**Tablet nenačte stránku:**
- Zkontroluj, že tablet používá DNS `192.168.0.191`
- Na tabletu: `ping fiam-opi.dedyn.io` — musí vrátit `192.168.0.191`

**Certifikát expiruje:**
```bash
sudo /usr/local/bin/renew-cert.sh
```
