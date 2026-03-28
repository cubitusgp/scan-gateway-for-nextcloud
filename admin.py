#!/usr/bin/env python3
"""
scan-gateway - admin.py
Web administration interface for managing SMB shares and WebDAV destinations.
"""

import json
import os
import signal
import subprocess
import time
from functools import wraps

from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("ADMIN_SECRET", "changeme-secret-key")

CONFIG_FILE = "/config/config.json"
ADMIN_USER  = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS  = os.environ.get("ADMIN_PASSWORD", "admin")

# ─── Config helpers ──────────────────────────────────────────────────────────

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"smb_user": "scanner", "smb_password": "changeme", "destinations": []}
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# ─── Auth ────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─── Samba reload ────────────────────────────────────────────────────────────

def apply_config(config):
    """Rewrite smb.conf and restart Samba based on current config."""
    smb_user = config["smb_user"]
    smb_pass = config["smb_password"]

    # Rewrite smb.conf
    smb_conf = f"""[global]
workgroup = WORKGROUP
server string = ScanGateway
security = user
passdb backend = tdbsam
log level = 1
"""
    for dest in config["destinations"]:
        name = dest["name"]
        drop = f"/drop/{name}"
        os.makedirs(drop, exist_ok=True)
        subprocess.run(["chown", f"{smb_user}:{smb_user}", drop], capture_output=True)
        subprocess.run(["chmod", "755", drop], capture_output=True)
        smb_conf += f"""
[{name}]
path = {drop}
writable = yes
guest ok = no
valid users = {smb_user}
create mask = 0664
"""

    with open("/etc/samba/smb.conf", "w") as f:
        f.write(smb_conf)

    # Update SMB user password
    subprocess.run(["useradd", "-M", smb_user], capture_output=True)
    subprocess.run(
        ["smbpasswd", "-a", smb_user, "-s"],
        input=f"{smb_pass}\n{smb_pass}\n".encode(),
        capture_output=True
    )

    # Restart Samba
    subprocess.run(["pkill", "smbd"], capture_output=True)
    subprocess.run(["pkill", "nmbd"], capture_output=True)
    time.sleep(1)
    subprocess.Popen(["nmbd", "-D"])
    subprocess.Popen(["smbd", "-D"])

    # Signal watcher to reload config
    try:
        with open("/tmp/watcher.pid") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
    except Exception:
        pass

# ─── HTML template ───────────────────────────────────────────────────────────

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Scan Gateway Admin</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, sans-serif; background: #f0f2f5; color: #1a1a2e; }
    header { background: #1a1a2e; color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
    header h1 { font-size: 1.2rem; font-weight: 600; }
    header a { color: #aaa; text-decoration: none; font-size: 0.85rem; }
    header a:hover { color: white; }
    main { max-width: 860px; margin: 2rem auto; padding: 0 1rem; }
    .card { background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.07); margin-bottom: 1.5rem; overflow: hidden; }
    .card-header { padding: 1rem 1.5rem; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
    .card-header h2 { font-size: 1rem; font-weight: 600; }
    .card-body { padding: 1.5rem; }
    .dest-item { display: flex; justify-content: space-between; align-items: center; padding: .75rem 1rem; border: 1px solid #eee; border-radius: 8px; margin-bottom: .5rem; }
    .dest-info strong { font-size: .95rem; }
    .dest-info small { display: block; color: #666; font-size: .8rem; margin-top: 2px; word-break: break-all; }
    .actions { display: flex; gap: .5rem; flex-shrink: 0; }
    .btn { padding: .4rem .9rem; border: none; border-radius: 6px; cursor: pointer; font-size: .85rem; text-decoration: none; display: inline-block; }
    .btn-primary { background: #1a1a2e; color: white; }
    .btn-primary:hover { background: #2d2d4e; }
    .btn-danger { background: #fee2e2; color: #dc2626; }
    .btn-danger:hover { background: #fecaca; }
    .btn-secondary { background: #f1f5f9; color: #334155; }
    .btn-secondary:hover { background: #e2e8f0; }
    form.inline { display: inline; }
    .form-group { margin-bottom: 1rem; }
    .form-group label { display: block; font-size: .85rem; font-weight: 500; margin-bottom: .3rem; color: #444; }
    .form-group input { width: 100%; padding: .5rem .75rem; border: 1px solid #ddd; border-radius: 6px; font-size: .9rem; }
    .form-group input:focus { outline: none; border-color: #1a1a2e; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .alert { padding: .75rem 1rem; border-radius: 6px; margin-bottom: 1rem; font-size: .9rem; }
    .alert-success { background: #dcfce7; color: #166534; }
    .alert-error { background: #fee2e2; color: #dc2626; }
    .empty { text-align: center; color: #999; padding: 2rem; font-size: .9rem; }
    .login-wrap { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
    .login-card { background: white; border-radius: 12px; padding: 2.5rem; width: 100%; max-width: 380px; box-shadow: 0 4px 20px rgba(0,0,0,.1); }
    .login-card h1 { font-size: 1.3rem; margin-bottom: 1.5rem; text-align: center; }
    .login-card .btn { width: 100%; padding: .7rem; font-size: 1rem; margin-top: .5rem; }
    .badge { background: #e0f2fe; color: #0369a1; padding: .2rem .6rem; border-radius: 20px; font-size: .75rem; font-weight: 600; }
  </style>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>
"""

LOGIN_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="login-wrap">
  <div class="login-card">
    <h1>🖨️ Scan Gateway</h1>
    {% if error %}<div class="alert alert-error">{{ error }}</div>{% endif %}
    <form method="post">
      <div class="form-group">
        <label>Username</label>
        <input name="username" type="text" autofocus required>
      </div>
      <div class="form-group">
        <label>Password</label>
        <input name="password" type="password" required>
      </div>
      <button class="btn btn-primary" type="submit">Sign in</button>
    </form>
  </div>
</div>
""")

MAIN_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<header>
  <h1>🖨️ Scan Gateway Admin</h1>
  <a href="/logout">Logout</a>
</header>
<main>
  {% if flash_msg %}
  <div class="alert alert-{{ flash_type }}">{{ flash_msg }}</div>
  {% endif %}

  <!-- SMB Shares -->
  <div class="card">
    <div class="card-header">
      <h2>SMB Shares <span class="badge">{{ destinations|length }}</span></h2>
      <a href="/add" class="btn btn-primary">+ Add share</a>
    </div>
    <div class="card-body">
      {% if destinations %}
        {% for dest in destinations %}
        <div class="dest-item">
          <div class="dest-info">
            <strong>📁 {{ dest.name }}</strong>
            <small>→ {{ dest.url }}</small>
            <small>User: {{ dest.webdav_user }}</small>
          </div>
          <div class="actions">
            <a href="/edit/{{ loop.index0 }}" class="btn btn-secondary">Edit</a>
            <form class="inline" method="post" action="/delete/{{ loop.index0 }}"
                  onsubmit="return confirm('Delete share {{ dest.name }}?')">
              <button class="btn btn-danger" type="submit">Delete</button>
            </form>
          </div>
        </div>
        {% endfor %}
      {% else %}
        <div class="empty">No shares configured yet. Click "+ Add share" to get started.</div>
      {% endif %}
    </div>
  </div>

  <!-- SMB Credentials -->
  <div class="card">
    <div class="card-header">
      <h2>SMB Credentials</h2>
    </div>
    <div class="card-body">
      <form method="post" action="/credentials">
        <div class="form-row">
          <div class="form-group">
            <label>SMB Username</label>
            <input name="smb_user" value="{{ smb_user }}" required>
          </div>
          <div class="form-group">
            <label>SMB Password</label>
            <input name="smb_password" type="password" placeholder="Leave empty to keep current">
          </div>
        </div>
        <button class="btn btn-primary" type="submit">Save credentials</button>
      </form>
    </div>
  </div>
</main>
""")

FORM_HTML = BASE_HTML.replace("{% block content %}{% endblock %}", """
<header>
  <h1>🖨️ Scan Gateway Admin</h1>
  <a href="/">← Back</a>
</header>
<main>
  <div class="card">
    <div class="card-header"><h2>{{ title }}</h2></div>
    <div class="card-body">
      <form method="post">
        <div class="form-group">
          <label>SMB Share name (used by the scanner, no spaces)</label>
          <input name="name" value="{{ dest.name }}" placeholder="e.g. office" required {% if edit %}readonly{% endif %}>
        </div>
        <div class="form-group">
          <label>WebDAV URL</label>
          <input name="url" value="{{ dest.url }}" placeholder="https://nextcloud.example.com/remote.php/dav/files/user/Scans/Office/" required>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>WebDAV Username</label>
            <input name="webdav_user" value="{{ dest.webdav_user }}" required>
          </div>
          <div class="form-group">
            <label>WebDAV Password (app password)</label>
            <input name="webdav_password" type="password" placeholder="{% if edit %}Leave empty to keep current{% else %}App password{% endif %}">
          </div>
        </div>
        <div style="display:flex;gap:.5rem">
          <button class="btn btn-primary" type="submit">Save</button>
          <a href="/" class="btn btn-secondary">Cancel</a>
        </div>
      </form>
    </div>
  </div>
</main>
""")

# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form["username"] == ADMIN_USER and request.form["password"] == ADMIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Invalid username or password"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    config = load_config()
    flash_msg = session.pop("flash_msg", None)
    flash_type = session.pop("flash_type", "success")
    return render_template_string(MAIN_HTML,
        destinations=config["destinations"],
        smb_user=config["smb_user"],
        flash_msg=flash_msg,
        flash_type=flash_type
    )

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method == "POST":
        config = load_config()
        name = request.form["name"].strip().replace(" ", "_")
        if any(d["name"] == name for d in config["destinations"]):
            return render_template_string(FORM_HTML, title="Add share",
                dest=request.form, edit=False,
                error=f"Share '{name}' already exists")
        config["destinations"].append({
            "name": name,
            "url": request.form["url"].strip(),
            "webdav_user": request.form["webdav_user"].strip(),
            "webdav_password": request.form["webdav_password"].strip()
        })
        save_config(config)
        apply_config(config)
        session["flash_msg"] = f"Share '{name}' added and Samba reloaded."
        session["flash_type"] = "success"
        return redirect(url_for("index"))
    return render_template_string(FORM_HTML, title="Add share",
        dest={"name":"","url":"","webdav_user":"","webdav_password":""}, edit=False)

@app.route("/edit/<int:idx>", methods=["GET", "POST"])
@login_required
def edit(idx):
    config = load_config()
    dest = config["destinations"][idx]
    if request.method == "POST":
        dest["url"] = request.form["url"].strip()
        dest["webdav_user"] = request.form["webdav_user"].strip()
        if request.form["webdav_password"].strip():
            dest["webdav_password"] = request.form["webdav_password"].strip()
        config["destinations"][idx] = dest
        save_config(config)
        apply_config(config)
        session["flash_msg"] = f"Share '{dest['name']}' updated and Samba reloaded."
        session["flash_type"] = "success"
        return redirect(url_for("index"))
    return render_template_string(FORM_HTML, title=f"Edit share — {dest['name']}",
        dest=dest, edit=True)

@app.route("/delete/<int:idx>", methods=["POST"])
@login_required
def delete(idx):
    config = load_config()
    name = config["destinations"][idx]["name"]
    config["destinations"].pop(idx)
    save_config(config)
    apply_config(config)
    session["flash_msg"] = f"Share '{name}' deleted and Samba reloaded."
    session["flash_type"] = "success"
    return redirect(url_for("index"))

@app.route("/credentials", methods=["POST"])
@login_required
def credentials():
    config = load_config()
    config["smb_user"] = request.form["smb_user"].strip()
    if request.form["smb_password"].strip():
        config["smb_password"] = request.form["smb_password"].strip()
    save_config(config)
    apply_config(config)
    session["flash_msg"] = "SMB credentials updated and Samba reloaded."
    session["flash_type"] = "success"
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4380, debug=False)
