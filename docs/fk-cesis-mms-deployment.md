# FK Cēsis MMS Deployment

This repository owns deployed runtime for the FK Cēsis MMS application image.

## Image source

- Image: `codeberg.org/linards-kalvans/fk-cesis-mms`
- Dev floating tag: `dev`
- Prod floating tag: `main`
- Immutable rollback tags: `<major>.<minor>`

The application repository owns image builds and tag generation.

## Runtime layout

Server directory:

```text
/opt/fk-cesis-mms/
  compose.yaml
  .env
  bin/
    fk-deploy-listener.py
    deploy-fk-cesis-mms.sh
  data/
    uploads/
    private-uploads/
```

## Provision host

```bash
apt-get update
apt-get install -y docker.io docker-compose-plugin caddy openssl python3
systemctl enable --now docker
systemctl enable --now caddy

useradd --system --uid 10001 --create-home --home-dir /opt/fk-cesis-mms --shell /usr/sbin/nologin fkmms
usermod -aG docker fkmms

install -o fkmms -g fkmms -m 0750 -d /opt/fk-cesis-mms
install -o fkmms -g fkmms -m 0750 -d /opt/fk-cesis-mms/bin
install -o fkmms -g fkmms -m 0750 -d /opt/fk-cesis-mms/data/uploads
install -o fkmms -g fkmms -m 0700 -d /opt/fk-cesis-mms/data/private-uploads
```

## Install runtime files

Copy:

- `deploy/fk-cesis-mms/compose.yaml` to `/opt/fk-cesis-mms/compose.yaml`
- `deploy/fk-cesis-mms/.env.example` to `/opt/fk-cesis-mms/.env`, then replace placeholder values
- `deploy/fk-cesis-mms/bin/*` to `/opt/fk-cesis-mms/bin/`
- `deploy/fk-cesis-mms/systemd/fk-cesis-mms-deploy-listener.service` to `/etc/systemd/system/`
- listener env file to `/etc/fk-cesis-mms-deploy-listener.env`
- Caddy example into the host Caddyfile, with real domain and port

## Channel config

Dev server:

```ini
IMAGE_TAG=dev
SITE_URL=https://dev-mms.example.lv
DJANGO_ALLOWED_HOSTS=dev-mms.example.lv
```

Prod server:

```ini
IMAGE_TAG=main
SITE_URL=https://mms.example.lv
DJANGO_ALLOWED_HOSTS=mms.example.lv
```

Prod rollback:

```ini
IMAGE_TAG=0.42
```

## Start stack

```bash
su -s /bin/bash fkmms -c 'cd /opt/fk-cesis-mms && docker login codeberg.org'
su -s /bin/bash fkmms -c 'cd /opt/fk-cesis-mms && docker compose pull'
su -s /bin/bash fkmms -c 'cd /opt/fk-cesis-mms && docker compose up -d'
su -s /bin/bash fkmms -c 'cd /opt/fk-cesis-mms && docker compose ps'
```

## Verify

```bash
curl -fsS https://mms.example.lv/healthz
su -s /bin/bash fkmms -c 'cd /opt/fk-cesis-mms && docker compose logs --tail=100 web qcluster'
```

## Deploy listener

```bash
systemctl daemon-reload
systemctl enable --now fk-cesis-mms-deploy-listener
systemctl status fk-cesis-mms-deploy-listener
```

## Rollback

1. Edit `/opt/fk-cesis-mms/.env`.
2. Set `IMAGE_TAG=<known-good-version>`, for example `IMAGE_TAG=0.42`.
3. Run:

```bash
su -s /bin/bash fkmms -c 'cd /opt/fk-cesis-mms && docker compose pull web qcluster && docker compose up -d web qcluster'
```

4. Verify `/healthz`.

Set `IMAGE_TAG=main` to resume floating prod updates.

## Secrets rule

Never commit real `.env` values, deploy webhook secrets, API keys, SMTP passwords, OCR keys, DocuSeal keys, or Invoice Ninja keys.
