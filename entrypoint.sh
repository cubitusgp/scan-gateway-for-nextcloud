#!/bin/bash
set -e

# Base Samba config
cat > /etc/samba/smb.conf << SMBEOF
[global]
workgroup = WORKGROUP
server string = ScanGateway
security = user
passdb backend = tdbsam
log level = 1
SMBEOF

# Create SMB user first
useradd -M "$SMB_USER" 2>/dev/null || true
(echo "$SMB_PASSWORD"; echo "$SMB_PASSWORD") | smbpasswd -a "$SMB_USER" -s
echo "SMB user created: $SMB_USER"

# Create SMB shares from DESTINATIONS
IFS=',' read -ra ENTRIES <<< "$DESTINATIONS"
for entry in "${ENTRIES[@]}"; do
    NAME=$(echo "$entry" | cut -d'|' -f1 | tr -d ' ')
    [ -z "$NAME" ] && continue
    mkdir -p "/drop/$NAME"
    chown "$SMB_USER:$SMB_USER" "/drop/$NAME"
    chmod 755 "/drop/$NAME"
    cat >> /etc/samba/smb.conf << SMBEOF

[$NAME]
path = /drop/$NAME
writable = yes
guest ok = no
valid users = $SMB_USER
create mask = 0664
SMBEOF
    echo "SMB share created: $NAME"
done

# Start Samba
nmbd -D
smbd -D
echo "Samba started"

# Start watcher
exec python3 /watch.py
