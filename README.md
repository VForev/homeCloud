# HomeCloud ☁️

HomeCloud is a self-hosted file and image storage web application built with **Flask**.  
It is designed to run locally on a **Raspberry Pi** (or any Linux server) and be exposed securely to the internet using **Nginx**, **Gunicorn**, and **Let’s Encrypt SSL**.

This repository documents **exactly** how to rebuild the full environment from scratch.

---

## Features

- Upload and store files/images
- Web-based UI
- Runs locally on your own hardware
- Production-ready setup using Gunicorn + Nginx
- Free HTTPS using Let’s Encrypt
- Secrets managed safely using environment variables

---

## Tech Stack

- **Python 3**
- **Flask**
- **Gunicorn** (WSGI server)
- **Nginx** (reverse proxy + SSL)
- **Let’s Encrypt / Certbot**
- **systemd** (process management)
- **Namecheap DNS**
- **Raspberry Pi (Linux)**

---

## Directory Structure

```

homeCloud/
├── app.py
├── templates/
├── static/
├── data/                 # Uploaded files/images
├── .venv/                # Python virtual environment
├── .env                  # Secrets (NOT committed)
├── .gitignore
└── README.md

````

---

## Requirements

- Linux (Raspberry Pi OS / Ubuntu recommended)
- Python 3.10+
- Public domain name
- Router with port forwarding access
- Internet connection that allows ports 80 & 443

---

## 1. Clone the Repository

```bash
git clone https://github.com/VForev/homeCloud.git
cd homeCloud
````

---

## 2. Create Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install flask gunicorn python-dotenv
```

---

## 3. Create the Secrets File (`.env`)

Create a `.env` file **in the project root**:

```bash
nano .env
```

Example:

```env
SECRET_KEY=replace_with_a_long_random_string
UPLOAD_FOLDER=/home/base/homeCloud/data
MAX_CONTENT_LENGTH=524288000
```

⚠️ **Important**

* `.env` must NOT be committed to GitHub
* Make sure `.gitignore` contains:

```
.env
```

---

## 4. Run Locally (Development Test)

```bash
source .venv/bin/activate
python app.py
```

Open:

```
http://127.0.0.1:8080
```

---

## 5. Run with Gunicorn (Production)

From the project directory:

```bash
gunicorn -w 2 -b 127.0.0.1:8080 app:app
```

Test:

```bash
curl http://127.0.0.1:8080
```

---

## 6. Run Gunicorn as a systemd Service

Create service file:

```bash
sudo nano /etc/systemd/system/homecloud.service
```

```ini
[Unit]
Description=HomeCloud (Gunicorn)
After=network.target

[Service]
User=base
WorkingDirectory=/home/base/homeCloud
EnvironmentFile=/home/base/homeCloud/.env
Environment="PATH=/home/base/homeCloud/.venv/bin"
ExecStart=/home/base/homeCloud/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8080 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable & start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now homecloud
sudo systemctl status homecloud
```

Logs:

```bash
sudo journalctl -u homecloud -f
```

---

## 7. Install & Configure Nginx

```bash
sudo apt install nginx -y
```

Create site config:

```bash
sudo nano /etc/nginx/sites-available/homecloud
```

```nginx
server {
    listen 80;
    server_name vforeproductions.com www.vforeproductions.com;

    client_max_body_size 500M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable:

```bash
sudo ln -s /etc/nginx/sites-available/homecloud /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 8. Domain & DNS (Namecheap)

In **Namecheap → Advanced DNS**:

```
A Record   @     → YOUR_PUBLIC_IP
A Record   www   → YOUR_PUBLIC_IP
```

Ports required:

* **80 (HTTP)**
* **443 (HTTPS)**

---

## 9. Enable Free SSL (Let’s Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d vforeproductions.com -d www.vforeproductions.com
```

Choose:
✅ Redirect HTTP → HTTPS

Test:

```bash
curl -I https://vforeproductions.com
```

Auto-renew test:

```bash
sudo certbot renew --dry-run
```

---

## 10. Router Configuration (Required)

* Assign Raspberry Pi a **static LAN IP**
* Forward ports:

  * TCP 80 → Pi
  * TCP 443 → Pi

---

## 11. Local Network Access (Inside the House)

Some routers don’t support NAT loopback.

Recommended solution:

* Run **Pi-hole**
* Add local DNS records:

```
vforeproductions.com → 192.168.x.x
www.vforeproductions.com → 192.168.x.x
```

---

## Common Errors & Fixes

### 502 Bad Gateway

* Gunicorn not running
* Wrong systemd path or user
* Wrong Gunicorn target (`app:app`)
* Missing dependencies

Check:

```bash
sudo systemctl status homecloud
sudo journalctl -u homecloud
sudo tail /var/log/nginx/error.log
```

---

## Security Notes ⚠️

* This app exposes file uploads to the internet
* Add authentication before public use
* Consider VPN-only or IP restrictions for private deployments

---

## License

MIT License

---

## Author

**VFore Productions**
Self-hosted infrastructure & software experimentation

---

https://chatgpt.com/share/697b2200-a5b0-800e-b105-36f67d818fd2
