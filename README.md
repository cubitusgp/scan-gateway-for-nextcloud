# scan-gateway for Nextcloud

A lightweight Docker container that acts as an **SMB receiver for network scanners** (Brother, OKI, Ricoh, etc.) and automatically uploads scanned documents to a **WebDAV destination** such as Nextcloud, ownCloud, or any WebDAV-compatible server.

## How it works

```
Scanner (Brother, OKI…) ──► SMB share ──► scan-gateway ──► WebDAV (Nextcloud…)
```

1. Your scanner sends scanned files to an SMB share exposed by this container
2. The container detects new files and uploads them via WebDAV to your destination
3. Files appear instantly in Nextcloud (or any WebDAV server) without any manual action

## Why this exists

Most entry-level and mid-range network scanners (Brother MFC, OKI MB…) support SMB but **not WebDAV natively**. This container bridges the gap, allowing you to send scans directly to Nextcloud or any WebDAV server without exposing your Nextcloud data folder over SMB.

## Requirements

- Docker & Docker Compose
- A network scanner with SMB/CIFS scan-to-folder support
- A WebDAV destination (Nextcloud, ownCloud, Apache, etc.)

## Quick start

### 1. Create the macvlan network

The container needs its own IP on your LAN to avoid port 445 conflicts with the host (e.g. TrueNAS).

```bash
docker network create -d macvlan \
  --subnet=192.168.1.0/24 \
  --gateway=192.168.1.1 \
  -o parent=br0 \
  scan-gateway-net
```

> Replace `subnet`, `gateway` and `parent` interface (`br0`, `eth0`…) to match your network.  
> Use `ip link show` to find your network interface.

### 2. Build the image

```bash
git clone https://github.com/YOUR_USERNAME/scan-gateway-for-nextcloud.git
cd scan-gateway-for-nextcloud
docker build -t scan-gateway:latest .
```

### 3. Configure and start

Copy the example compose file and edit it:

```bash
cp docker-compose.yml.example docker-compose.yml
```

Edit `docker-compose.yml`:

| Variable | Description |
|---|---|
| `SMB_USER` | Username for the SMB share (used by the scanner) |
| `SMB_PASSWORD` | Password for the SMB share |
| `POLL_INTERVAL` | How often (seconds) to check for new files (default: 3) |
| `DESTINATIONS` | Comma-separated list of destinations (see format below) |
| `ipv4_address` | A free IP address on your LAN for the container |

#### DESTINATIONS format

```
smb_folder|webdav_url|webdav_user|webdav_password
```

Multiple destinations (one SMB share per destination):
```
office|https://nextcloud.example.com/remote.php/dav/files/admin/Scans/Office/|admin|app-password,
reception|https://nextcloud.example.com/remote.php/dav/files/admin/Scans/Reception/|admin|app-password2
```

> **Tip:** Use a Nextcloud [app password](https://docs.nextcloud.com/server/latest/user_manual/en/session_management.html#managing-devices) instead of your main password.

#### Nextcloud WebDAV URL format

```
https://YOUR_NEXTCLOUD/remote.php/dav/files/USERNAME/Path/To/Folder/
```

For **Group Folders**, the path is:
```
https://YOUR_NEXTCLOUD/remote.php/dav/files/USERNAME/__groupfolders/FOLDER_NAME/
```

### 4. Start

```bash
docker compose up -d
docker logs -f scan-gateway
```

### 5. Configure your scanner

| Field | Value |
|---|---|
| **Server / Host** | IP address of the container (e.g. `192.168.1.250`) |
| **Share name** | The `smb_folder` name from your `DESTINATIONS` |
| **Username** | Value of `SMB_USER` |
| **Password** | Value of `SMB_PASSWORD` |
| **Authentication** | NTLMv2 |

## TrueNAS SCALE notes

On TrueNAS SCALE, the physical interface is typically bridged (`br0`). Use `br0` as the `parent` interface for the macvlan network.

If TrueNAS already uses SMB on port 445, the macvlan approach gives the container its own dedicated IP — no port conflict.

## Tested with

- Brother MFC-J5345DW
- OKI MB492
- Nextcloud AIO (Docker)
- TrueNAS SCALE 24.10 (Electric Eel)

## Contributing

Pull requests welcome! Feel free to open an issue if you have tested with other scanner models or WebDAV servers.

## License

MIT
