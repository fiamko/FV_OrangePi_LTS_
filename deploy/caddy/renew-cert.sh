#!/bin/bash
# =============================================================================
# Obnoveni Let's Encrypt certifikatu pres lego + rebuild bundle + reload Caddy
#   Cron:  0 3 * * 0 /home/fiam/menic_web/deploy/caddy/renew-cert.sh
# =============================================================================
set -euo pipefail

export DESEC_TOKEN="$(cat "$HOME/.desec_token")"

LEGO_BIN="/usr/local/bin/lego"
CERT_DIR="/home/fiam/.lego/certificates"
CADDY_CERT="/etc/caddy/fve-bundle.crt"
CADDY_KEY="/etc/caddy/fve-bundle.key"
DOMAIN="fiam-opi.dedyn.io"
EMAIL="$(cat "$HOME/.cert_email")"
LOG_FILE="/var/log/fve-cert-renewal.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Zahajuji obnoveni certifikatu pro $DOMAIN ==="

if [ ! -x "$LEGO_BIN" ]; then
    log "CHYBA: lego nenalezeno na $LEGO_BIN"
    exit 1
fi

# 1. Obnoveni certifikatu (lego sam pozna, jestli je potreba)
"$LEGO_BIN" \
    --email "$EMAIL" \
    --dns desec \
    --domains "$DOMAIN" \
    --accept-tos \
    renew 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    log "VAROVANI: lego renew selhalo (exit code $EXIT_CODE)"
    exit 1
fi

log "OK: lego renew probehl uspesne"

# 2. Overeni, ze certifikaty existuji
CERT_FILE="$CERT_DIR/${DOMAIN}.crt"
KEY_FILE="$CERT_DIR/${DOMAIN}.key"
ISSUER_FILE="$CERT_DIR/${DOMAIN}.issuer.crt"

for f in "$CERT_FILE" "$KEY_FILE" "$ISSUER_FILE"; do
    if [ ! -f "$f" ]; then
        log "CHYBA: soubor $f neexistuje"
        exit 1
    fi
done

# 3. Vytvoreni bundle (cert + issuer cert = plny retezec)
cat "$CERT_FILE" "$ISSUER_FILE" > "$CADDY_CERT.tmp"
cp "$KEY_FILE" "$CADDY_KEY.tmp"
chmod 644 "$CADDY_CERT.tmp" "$CADDY_KEY.tmp"

# Atomicke prepsani (mv v ramci stejneho FS je atomicke)
mv "$CADDY_CERT.tmp" "$CADDY_CERT"
mv "$CADDY_KEY.tmp" "$CADDY_KEY"

log "OK: bundle vytvoren a nakopirovan do /etc/caddy/"

# 4. Reload Caddy (bez preruseni provozu)
if systemctl reload caddy 2>/dev/null; then
    log "OK: Caddy reloaded"
else
    log "VAROVANI: systemctl reload selhal, restartuji Caddy"
    systemctl restart caddy
fi

# 5. Rychle overeni
CERT_COUNT=$(openssl s_client -connect localhost:443 -servername "$DOMAIN" </dev/null 2>/dev/null | grep -c "BEGIN CERTIFICATE" || echo "0")
log "Pocet certifikatu v retezci (ma byt 2+): $CERT_COUNT"

log "=== Hotovo ==="
