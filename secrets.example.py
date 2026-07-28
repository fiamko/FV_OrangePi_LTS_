"""
secrets.example.py — ŠABLONA pro secrets.py

Zkopíruj tento soubor jako `secrets.py` a vyplň skutečné hodnoty:
    cp secrets.example.py secrets.py

secrets.py NIKDY necommitovat do Gitu! Je v .gitignore.
"""

# === Přístupové údaje ===

# Heslo pro webové nastavení (http://192.168.0.191:5000/nastaveni)
SETTINGS_PASSWORD = "zmen-toto-heslo"

# MQTT broker
MQTT_BROKER = "localhost"   # "192.168.0.191" při přístupu zvenčí
MQTT_PORT = 1883

# === Síťová infrastruktura ===

# ESP32 zařízení — IP adresy v lokální síti
ESP_DEVICES = [
    {"name": "Vířivka",          "ip": "192.168.0.???", "subdomain": "virivka"},
    {"name": "Podlahovka 2200W", "ip": "192.168.0.???", "subdomain": "podlahovka2200"},
    {"name": "Podlahovky (budoucí)", "ip": "192.168.0.???", "subdomain": "podlahovky"},
]

# === Domény a certifikáty ===

# desec.io — token pro DNS-01 challenge (Let's Encrypt)
# Získáš na: https://desec.io/domains → vyber doménu → Token Management
DESEC_TOKEN = "tvuj-desec-token"

# E-mail pro Let's Encrypt notifikace (expirace certifikátu)
CERT_EMAIL = "tvuj@email.cz"

# === Cloudflare Tunnel (volitelné) ===

# ID tunelu (z výstupu: cloudflared tunnel create fve-tunnel)
CLOUDFLARE_TUNNEL_ID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# Doména pro Cloudflare Tunnel
CLOUDFLARE_DOMAIN = "tvoje-domena.cz"

# Interní IP subdomén (ESP zařízení přes Cloudflare Tunnel)
CLOUDFLARE_INGRESS_HOSTS = [
    {"hostname": "virivka.tvoje-domena.cz",        "service": "http://192.168.0.???:80"},
    {"hostname": "podlahovka2200.tvoje-domena.cz", "service": "http://192.168.0.???:80"},
]
