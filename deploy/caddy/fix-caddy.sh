#!/bin/bash
# Opravi Caddy: vytvori bundle, nakopiruje klic, zapise Caddyfile, restartuje
set -e

# 1. Vytvor bundle (cert + chain)
sudo cat /home/fiam/.lego/certificates/fiam-opi.dedyn.io.crt \
        /home/fiam/.lego/certificates/fiam-opi.dedyn.io.issuer.crt \
    | sudo tee /etc/caddy/fve-bundle.crt > /dev/null

# 2. Nakopiruj klic
sudo cp /home/fiam/.lego/certificates/fiam-opi.dedyn.io.key /etc/caddy/fve-bundle.key
sudo chmod 644 /etc/caddy/fve-bundle.crt /etc/caddy/fve-bundle.key

# 3. Novy Caddyfile
sudo tee /etc/caddy/Caddyfile > /dev/null << 'CEOF'
fiam-opi.dedyn.io {
    tls /etc/caddy/fve-bundle.crt /etc/caddy/fve-bundle.key

    reverse_proxy localhost:5000

    log {
        output file /var/log/caddy/fve-access.log
        level INFO
    }
}

http://fiam-opi.dedyn.io {
    redir https://{host}{uri} permanent
}
CEOF

# 4. Restart
sudo systemctl restart caddy
systemctl status caddy --no-pager
echo ""
echo "Pocet certifikatu v retezci (ma byt 2+):"
openssl s_client -connect localhost:443 -servername fiam-opi.dedyn.io </dev/null 2>/dev/null | grep -c "BEGIN CERTIFICATE"
