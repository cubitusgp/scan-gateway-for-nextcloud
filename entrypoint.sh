#!/bin/bash
set -e

CONFIG_FILE="/config/config.json"

# If no config.json exists yet, bootstrap from environment variables
if [ ! -f "$CONFIG_FILE" ]; then
    mkdir -p /config
    echo "No config.json found, bootstrapping from environment..."

    DESTINATIONS_JSON="[]"
    if [ -n "$DESTINATIONS" ]; then
        DESTINATIONS_JSON="["
        IFS=',' read -ra ENTRIES <<< "$DESTINATIONS"
        FIRST=1
        for entry in "${ENTRIES[@]}"; do
            NAME=$(echo "$entry" | cut -d'|' -f1 | tr -d ' ')
            URL=$(echo "$entry" | cut -d'|' -f2 | tr -d ' ')
            USER=$(echo "$entry" | cut -d'|' -f3 | tr -d ' ')
            PASS=$(echo "$entry" | cut -d'|' -f4 | tr -d ' ')
            [ -z "$NAME" ] && continue
            [ $FIRST -eq 0 ] && DESTINATIONS_JSON="$DESTINATIONS_JSON,"
            DESTINATIONS_JSON="$DESTINATIONS_JSON{\"name\":\"$NAME\",\"url\":\"$URL\",\"webdav_user\":\"$USER\",\"webdav_password\":\"$PASS\"}"
            FIRST=0
        done
        DESTINATIONS_JSON="$DESTINATIONS_JSON]"
    fi

    cat > "$CONFIG_FILE" << EOF
{
  "smb_user": "${SMB_USER:-scanner}",
  "smb_password": "${SMB_PASSWORD:-changeme}",
  "destinations": $DESTINATIONS_JSON
}
EOF
    echo "Config bootstrapped: $CONFIG_FILE"
fi

# Load config and apply Samba
apply_samba() {
    SMB_USER=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c['smb_user'])")
    SMB_PASSWORD=$(python3 -c "import json; c=json.load(open('$CONFIG_FILE')); print(c['smb_password'])")

    cat > /etc/samba/smb.conf << SMBEOF
[global]
workgroup = WORKGROUP
server string = ScanGateway
security = user
passdb backend = tdbsam
log level = 1
SMBEOF

    python3 - << PYEOF
import json
config = json.load(open("$CONFIG_FILE"))
for dest in config.get("destinations", []):
    name = dest["name"]
    user = config["smb_user"]
    with open("/etc/samba/smb.conf", "a") as f:
        f.write(f"""
[{name}]
path = /drop/{name}
writable = yes
guest ok = no
valid users = {user}
create mask = 0664
""")
    import os, subprocess
    os.makedirs(f"/drop/{name}", exist_ok=True)
    subprocess.run(["chown", f"{user}:{user}", f"/drop/{name}"], capture_output=True)
    subprocess.run(["chmod", "755", f"/drop/{name}"], capture_output=True)
    print(f"SMB share created: {name}")
PYEOF

    useradd -M "$SMB_USER" 2>/dev/null || true
    (echo "$SMB_PASSWORD"; echo "$SMB_PASSWORD") | smbpasswd -a "$SMB_USER" -s
    echo "SMB user ready: $SMB_USER"
}

apply_samba

# Start Samba
nmbd -D
smbd -D
echo "Samba started"

# Start admin UI in background
python3 /admin.py &
echo "Admin UI started on port 4380"

# Start watcher
exec python3 /watch.py
