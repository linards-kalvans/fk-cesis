#!/bin/sh
set -eu

# Host Caddy reaches the IPv4 loopback publication through this bridge's
# gateway, not necessarily Docker's default docker0/host-gateway address.
# Fail closed rather than falling back to trusting a whole subnet or all peers.
routes=$(ip -4 route show default)
case "$routes" in
  ''|*'
'*)
    printf '%s\n' 'Expected exactly one IPv4 default route for host Caddy ingress' >&2
    exit 1
    ;;
esac
set -- $routes
if [ "$#" -lt 3 ] || [ "$1" != default ] || [ "$2" != via ]; then
  printf '%s\n' 'Cannot determine the bridge gateway for host Caddy ingress' >&2
  exit 1
fi
gateway=$3
case "$gateway" in
  ''|*[!0-9.]*) exit 1 ;;
esac

cat > /tmp/football-club-host-proxy.conf <<EOF
set_real_ip_from $gateway;
real_ip_header X-Forwarded-For;
real_ip_recursive off;
map \$realip_remote_addr \$football_club_host_proxy {
    default 0;
    $gateway 1;
}
EOF

# Preserve the existing Debian PHP/shared-volume UID compatibility workaround.
addgroup -g 33 -S www-data 2>/dev/null || true
adduser -S -D -H -u 33 -G www-data www-data 2>/dev/null || true
sed -i 's/^user .*/user www-data www-data;/' /etc/nginx/nginx.conf
nginx -t
exec nginx -g 'daemon off;'
