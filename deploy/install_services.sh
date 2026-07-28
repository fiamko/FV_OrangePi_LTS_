#!/bin/bash
# ===================================================================
# Instalacni skript pro FVE systemd sluzby
# Spustit na OPI/Armbianu:  sudo bash install_services.sh
# ===================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVICE_DIR="/etc/systemd/system"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)/systemd"

echo "============================================"
echo "  FVE Service Installer"
echo "============================================"

# --- 1. Kontrola root praci ---
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}CHYBA: Skript musi byt spusten jako root (sudo).${NC}"
    exit 1
fi

# --- 2. Kontrola, ze existuje uzivatel fiam ---
if ! id -u fiam >/dev/null 2>&1; then
    echo -e "${YELLOW}VAROVANI: Uzivatel 'fiam' neexistuje.${NC}"
    echo "Vytvarim uzivatele 'fiam'..."
    useradd -m -s /bin/bash fiam
    usermod -a -G dialout fiam   # pro pristup k /dev/ttyUSB0
    echo -e "${GREEN}Uzivatel fiam vytvoren a pridan do skupiny dialout.${NC}"
else
    echo -e "${GREEN}[OK]${NC} Uzivatel 'fiam' existuje."
    # Zajistime, ze je ve skupine dialout
    if ! groups fiam | grep -q dialout; then
        usermod -a -G dialout fiam
        echo -e "${YELLOW}Uzivatel fiam pridan do skupiny dialout (pro /dev/ttyUSB0).${NC}"
    fi
fi

# --- 3. Kontrola pracovni slozky ---
WORKDIR="/home/fiam/menic_web"
if [ ! -d "$WORKDIR" ]; then
    echo -e "${RED}CHYBA: Pracovni slozka $WORKDIR neexistuje.${NC}"
    echo "Nejprve tam nakopiruj projekt (vcetne fve-env virtualniho prostredi)."
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Pracovni slozka $WORKDIR existuje."

# --- 4. Kontrola Python venv ---
PYTHON_BIN="$WORKDIR/fve-env/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
    echo -e "${RED}CHYBA: Python virtualni prostredi nenalezeno: $PYTHON_BIN${NC}"
    echo "Vytvorte ho:  cd $WORKDIR && python3 -m venv fve-env && source fve-env/bin/activate && pip install -r requirements.txt"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Python venv: $PYTHON_BIN"

# --- 5. Kontrola Mosquitto ---
if ! systemctl is-active --quiet mosquitto; then
    echo -e "${YELLOW}VAROVANI: Mosquitto neni spusteny. Pokusim se ho zapnout...${NC}"
    systemctl enable --now mosquitto 2>/dev/null || {
        echo -e "${RED}Mosquitto se nepodarilo spustit. Nainstalujte ho: apt install mosquitto${NC}"
    }
else
    echo -e "${GREEN}[OK]${NC} Mosquitto bezi."
fi

# --- 6. Nakopirovani service souboru ---
SERVICES=("fve-menic-reader.service" "fve-dashboard.service")
for svc in "${SERVICES[@]}"; do
    src="$SOURCE_DIR/$svc"
    dst="$SERVICE_DIR/$svc"

    if [ ! -f "$src" ]; then
        echo -e "${RED}CHYBA: Zdrojovy soubor $src neexistuje!${NC}"
        exit 1
    fi

    cp "$src" "$dst"
    chmod 644 "$dst"
    echo -e "${GREEN}[OK]${NC} Nainstalovan: $dst"
done

# --- 7. Reload systemd ---
systemctl daemon-reload
echo -e "${GREEN}[OK]${NC} systemd daemon reloaded."

# --- 8. Enable + start sluzeb ---
for svc in "${SERVICES[@]}"; do
    echo "---"
    echo "Zapinam a spoustim: $svc"
    systemctl enable "$svc"
    systemctl restart "$svc"

    # Pockame chvili a zkontrolujeme status
    sleep 2
    if systemctl is-active --quiet "$svc"; then
        echo -e "${GREEN}[OK]${NC} $svc bezi."
    else
        echo -e "${RED}[FAIL]${NC} $svc se nepodarilo spustit."
        echo "Poslednich 20 radku logu:"
        journalctl -u "$svc" -n 20 --no-pager
    fi
done

echo ""
echo "============================================"
echo "  Instalace dokoncena!"
echo "============================================"
echo ""
echo "Uzitecne prikazy pro diagnostiku:"
echo "  systemctl status fve-menic-reader"
echo "  systemctl status fve-dashboard"
echo "  journalctl -u fve-menic-reader -f"
echo "  journalctl -u fve-dashboard -f"
echo ""
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):5000"
