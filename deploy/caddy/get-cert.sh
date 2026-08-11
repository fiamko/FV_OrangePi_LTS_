#!/bin/bash
# =============================================================================
# Jednorazove ziskani certifikatu od Let's Encrypt pres lego (DNS-01 desec)
# Spustit na OPI:  sudo -u fiam bash /home/fiam/menic_web/deploy/caddy/get-cert.sh
# =============================================================================
set -euo pipefail

# DESEC_TOKEN a CERT_EMAIL se ctou z gitignorovanych souboru:
#   ~/.desec_token  — desec.io API token (nikdy necommitovat!)
#   ~/.cert_email   — e-mail pro Let's Encrypt
export DESEC_TOKEN="$(cat "$HOME/.desec_token")"
CERT_EMAIL="$(cat "$HOME/.cert_email")"

/usr/local/bin/lego \
    --email "$CERT_EMAIL" \
    --dns desec \
    --domains fiam-opi.dedyn.io \
    --accept-tos \
    --path /home/fiam/.lego \
    run
