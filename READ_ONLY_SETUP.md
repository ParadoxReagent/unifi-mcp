# Read-only UniFi Network MCP: local setup for Claude Code

This fork keeps only the UniFi Network MCP server and makes it read-only in code:

- Tools that create, update, delete, block, reboot or otherwise change the controller are **never registered**. They cannot be listed, discovered, or reached through `unifi_execute` / `unifi_batch`.
- The policy gate denies every non-read action, and no `UNIFI_POLICY_*`, `UNIFI_READ_ONLY`, settings file or permission-mode value can turn writes back on.
- Secrets are always redacted. WiFi passphrases, private PSKs, VPN private/pre-shared keys and config files, RADIUS and SNMP secrets, and device SSH credentials come back as `***REDACTED***`. `UNIFI_*REDACT_SENSITIVE_FIELDS` is ignored, and every tool result also passes through a final redaction pass in `main.py`.
- `apps/network/tests/unit/test_read_only_build.py` checks these guarantees.

The Protect, Access, API and relay servers, the Cloudflare worker, and the Claude/Codex plugins (which install the published PyPI package rather than this code) have been removed.

## 1. Create a View Only account on the console (recommended)

Defense in depth: even if this code had a bug, the controller itself refuses writes.

1. UniFi console → **Admins & Users** → **Create New Admin**.
2. Choose **Restrict to local access only**, set a username and password.
3. Give it the **View Only** role for Network (no other apps).

Some reads that are sent as controller commands (for example speed-test status) may be refused for a View Only account. Everything else works.

## 2. Install and check the server from this checkout

```bash
git clone https://github.com/ParadoxReagent/unifi-mcp.git
cd unifi-mcp
uv sync --package unifi-network-mcp
make network-test   # optional
```

Running from this checkout (`uv run --directory …`) uses the code in this repository, not a package from PyPI.

## 3. Store the settings outside the repo

The server never loads a project `.env`. Put the settings in a private per-user file:

```bash
mkdir -p ~/.config/unifi-mcp && chmod 700 ~/.config/unifi-mcp
printf '%s' 'YOUR-VIEW-ONLY-PASSWORD' > ~/.config/unifi-mcp/password
chmod 600 ~/.config/unifi-mcp/password

# Pin the console's TLS certificate (UniFi consoles use self-signed certs):
openssl s_client -connect 192.168.1.1:443 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256

cat > ~/.config/unifi-mcp/network.env <<'EOF'
UNIFI_NETWORK_HOST=192.168.1.1
UNIFI_NETWORK_USERNAME=claude-readonly
UNIFI_NETWORK_PASSWORD_FILE=/home/YOU/.config/unifi-mcp/password
UNIFI_NETWORK_SITE=default
UNIFI_NETWORK_SSL_FINGERPRINT=AB:CD:...from the openssl command...
UNIFI_TOOL_REGISTRATION_MODE=eager
EOF
chmod 600 ~/.config/unifi-mcp/network.env
```

`eager` registers the read tools directly (about 100), so Claude Code calls them as normal tools instead of through the `unifi_execute` wrapper.

## 4. Add it to Claude Code

```bash
claude mcp add unifi-network --scope user \
  -e UNIFI_SETTINGS_FILE=$HOME/.config/unifi-mcp/network.env \
  -- uv run --directory /absolute/path/to/unifi-mcp --package unifi-network-mcp unifi-network-mcp
```

Start Claude Code and run `/mcp` to confirm `unifi-network` is connected. Ask "list my UniFi devices" as a first check.

## Privacy note

Tool results (client names, IPs, MACs, SSIDs, nearby networks) go into your Claude conversation. Text that other people control, such as a neighbor's SSID or a client hostname, also lands in the model's context. Treat it as data; read-only mode is what keeps a prompt-injection attempt in that text harmless.

## Useful read tools for WiFi troubleshooting

| Question | Tools |
|----------|-------|
| AP radio channel, width, DFS, TX power, utilization | `unifi_get_device_radio`, `unifi_get_device_details`, `unifi_list_available_channels` |
| A client's signal, PHY rate, retries, band, AP | `unifi_get_client_wifi_details`, `unifi_get_client_details`, `unifi_get_client_stats` |
| WLAN settings: band steering, minimum RSSI, BSS transition, min data rates, WiFi 6/7 | `unifi_list_wlans`, `unifi_get_wlan_details`, `unifi_list_ap_groups` |
| Rate limits that cap throughput | `unifi_list_usergroups` (bandwidth profiles), `unifi_list_qos_rules`, `unifi_get_gateway_settings` (Smart Queues) |
| IPS / threat management | `unifi_get_threat_management_settings`, `unifi_get_threat_posture`, `unifi_get_ips_events` |
| AP uplink speed and errors | `unifi_get_switch_ports`, `unifi_get_port_stats`, `unifi_get_lldp_neighbors` |
| Interference and roaming | `unifi_get_rf_scan_results`, `unifi_list_rogue_aps`, `unifi_list_events`, `unifi_get_network_health` |
| WAN baseline | `unifi_get_speedtest_results`, `unifi_get_gateway_stats` |
