#!/usr/bin/env python3
"""Overi, jestli desec.io publikuje domenu fiam-opi.dedyn.io."""
import socket

print("Test 1: verejne DNS...")
try:
    ip = socket.gethostbyname("fiam-opi.dedyn.io")
    print(f"  OK -> {ip}")
except socket.gaierror:
    print("  FAIL - domena neni v DNS")

print()

print("Test 2: primo ns1.desec.io...")
try:
    ns_ip = socket.gethostbyname("ns1.desec.io")
    print(f"  ns1 IP: {ns_ip}")

    # DNS dotaz: A fiam-opi.dedyn.io
    parts = "fiam-opi.dedyn.io".split(".")
    q = b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
    for p in parts:
        q += bytes([len(p)]) + p.encode("ascii")
    q += b"\x00\x00\x01\x00\x01"

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(5)
    s.sendto(q, (ns_ip, 53))
    r = s.recv(512)
    s.close()

    rcode = r[3] & 15
    codes = {0: "OK", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN"}
    print(f"  Desec rcode: {rcode} ({codes.get(rcode, 'neznamy')})")

    if rcode == 0:
        # Hledej A record v odpovedi
        anc = (r[6] << 8) + r[7]
        print(f"  Odpovedi: {anc}")
        if anc > 0:
            pos = 12
            while pos < len(r) and r[pos] != 0:
                pos += r[pos] + 1
            pos += 5
            import struct
            for _ in range(anc):
                pos += 2
                rtype = struct.unpack("!H", r[pos:pos+2])[0]
                pos += 6
                rdlen = struct.unpack("!H", r[pos:pos+2])[0]
                pos += 2
                if rtype == 1 and rdlen == 4:
                    ip = ".".join(str(b) for b in r[pos:pos+rdlen])
                    print(f"  A zaznam: {ip}")
                pos += rdlen
except Exception as e:
    print(f"  ERROR: {e}")

print()
print("Hotovo.")
