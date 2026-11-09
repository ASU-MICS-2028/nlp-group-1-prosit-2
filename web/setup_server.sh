#!/bin/bash
# Set up the hosting server from nothing, or update it. Run on the server (Ubuntu 24.04) by someone with sudo: bash setup_server.sh
# The Claude key is not here: put one line, LLM_API_KEY=..., in /home/platform/.env, readable only by the platform user.
set -euo pipefail
HOST=34-78-38-126.sslip.io
BRANCH=${1:-main}
export DEBIAN_FRONTEND=noninteractive
sudo apt-get -qq update
sudo apt-get -qq install -y docker.io caddy git curl >/dev/null
# Bernard's sandbox makes one private network per backend. Docker's default allows only about 30: small blocks allow 256.
echo '{"default-address-pools":[{"base":"10.200.0.0/16","size":24}]}' | sudo tee /etc/docker/daemon.json >/dev/null
sudo systemctl restart docker
sudo useradd --system --create-home --shell /bin/bash platform 2>/dev/null || true
sudo usermod -aG docker platform
sudo mkdir -p /srv/deployed /etc/caddy/backends
sudo chown platform /srv/deployed /etc/caddy/backends
sudo tee /etc/caddy/Caddyfile >/dev/null <<CADDY
$HOST {
	request_body {
		max_size 1MB
	}
	import /etc/caddy/backends/*.caddy
	reverse_proxy 127.0.0.1:8080
}
CADDY
sudo -u platform -H bash -lc "
  test -x ~/.local/bin/uv || curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
  cd ~ && (test -d repo || git clone -q https://github.com/ASU-MICS-2028/nlp-group-1-prosit-2 repo)
  cd repo && git fetch -q && git switch -q $BRANCH && git pull -q
  ~/.local/bin/uv sync -q
  docker build -q -t w2-sandbox runtime/sandbox >/dev/null && docker pull -q alpine/socat:1.8.0.3 >/dev/null
  mkdir -p ~/builds"
sudo tee /etc/systemd/system/platform.service >/dev/null <<SERVICE
[Unit]
Description=Prosit 2 platform
After=docker.service network-online.target
Requires=docker.service

[Service]
User=platform
WorkingDirectory=/home/platform/repo
EnvironmentFile=/home/platform/.env
# Backends live in 10.200.x.x. They must not open connections to this server (ssh, Caddy). Replies to connections we opened still pass.
ExecStartPre=+/bin/sh -c 'iptables -C INPUT -s 10.200.0.0/16 -m conntrack --ctstate NEW -j REJECT 2>/dev/null || iptables -I INPUT -s 10.200.0.0/16 -m conntrack --ctstate NEW -j REJECT'
Environment=BUILDS_ROOT=/home/platform/builds PUBLIC_HOST=$HOST
ExecStart=/home/platform/.local/bin/uv run --with anthropic uvicorn web.app:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE
sudo systemctl daemon-reload
sudo systemctl enable -q platform
sudo systemctl restart platform
sudo systemctl reload-or-restart caddy
