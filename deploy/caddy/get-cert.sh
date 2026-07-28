#!/bin/bash
# =============================================================================
# Jednorazove ziskani certifikatu od Let's Encrypt pres lego (DNS-01 desec)
# Spustit na OPI:  sudo -u fiam bash /home/fiam/menic_web/deploy/caddy/get-cert.sh
# =============================================================================
set -euo pipefail

TOKEN_FILE="/home/fiam/.desec_token"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "CHYBA: Token soubor $TOKEN_FILE neexistuje." >&2
    echo "Vytvor ho: echo 'tvuj-token' > $TOKEN_FILE && chmod 600 $TOKEN_FILE" >&2
    exit 1
fi
export DESEC_TOKEN=$(cat "$TOKEN_FILE")

# E-mail pro Let's Encrypt — ze souboru nebo promenne prostredi
EMAIL_FILE="/home/fiam/.cert_email"
if [ -f "$EMAIL_FILE" ]; then
    CERT_EMAIL=$(cat "$EMAIL_FILE")
elif [ -n "${CERT_EMAIL:-}" ]; then
    true  # uz nastaveno pres promennou prostredi
else
    echo "CHYBA: E-mail nenastaven. Vytvor $EMAIL_FILE nebo nastav CERT_EMAIL." >&2
    exit 1
fi

/usr/local/bin/lego \
    --email "$CERT_EMAIL" \
    --dns desec \
    --domains fiam-opi.dedyn.io \
    --accept-tos \
    --path /home/fiam/.lego \
    run
