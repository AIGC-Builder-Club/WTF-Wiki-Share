---
name: clash-verge-chain-proxy
description: Configure a reusable, sanitized Clash Verge Rev/Mihomo chained proxy override. Use when adding a SOCKS5/HTTP/Trojan/VMess/Shadowsocks landing proxy behind an existing upstream node with dialer-proxy, editing Clash Verge profile enhancement files, or validating that a chained outbound appears in proxy groups without leaking secrets.
---

# Clash Verge Chain Proxy

Use this skill when a user wants to add a chained proxy in Clash Verge Rev or Mihomo, especially when the final exit should be a SOCKS5 landing proxy reached through an existing subscription node.

## Safety Rules

- Never expose real proxy credentials, subscription URLs, tokens, UUIDs, passwords, or private IPs in final answers.
- Treat all proxy files under `~/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/` as sensitive.
- Prefer reading structure with parsed YAML or targeted `rg`; avoid printing entire `proxies:` blocks because they often contain passwords.
- Before editing, back up files under `profiles/.codex-backup/`.
- Prefer profile enhancement files over editing remote subscription YAML directly; subscriptions are overwritten on update.

## Chain Direction

For “landing IP is SOCKS5, upstream is HK11” use this direction:

```text
local client -> existing upstream node -> SOCKS5 landing proxy -> target site
```

In Mihomo config, the final landing proxy gets `dialer-proxy`:

```yaml
- name: "<CHAINED_PROXY_NAME>"
  type: socks5
  server: "<SOCKS5_HOST>"
  port: <SOCKS5_PORT>
  username: "<SOCKS5_USERNAME>"
  password: "<SOCKS5_PASSWORD>"
  udp: true
  dialer-proxy: "<UPSTREAM_NODE_NAME>"
```

This means the SOCKS5 proxy is dialed through the upstream node. The target website should see the SOCKS5 landing IP.

## Discover Current Profile

Use the Clash Verge config directory:

```bash
APP_DIR="$HOME/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev"
PROFILES_DIR="$APP_DIR/profiles"
sed -n '1,140p' "$APP_DIR/profiles.yaml"
```

Find the current remote profile and its enhancement files:

```yaml
current: <REMOTE_UID>
items:
  - uid: <REMOTE_UID>
    type: remote
    option:
      merge: <MERGE_UID>
      script: <SCRIPT_UID>
      proxies: <PROXIES_UID>
      groups: <GROUPS_UID>
      rules: <RULES_UID>
```

Map UIDs to files in `profiles.yaml`, for example:

```yaml
- uid: <PROXIES_UID>
  type: proxies
  file: <PROXIES_UID>.yaml
- uid: <GROUPS_UID>
  type: groups
  file: <GROUPS_UID>.yaml
- uid: <SCRIPT_UID>
  type: script
  file: <SCRIPT_UID>.js
```

## Minimal Override Pattern

Edit the current profile's `type: proxies` enhancement file:

```yaml
# Profile Enhancement Proxies Template for Clash Verge

prepend:
  - name: "<CHAINED_PROXY_NAME>"
    type: socks5
    server: "<SOCKS5_HOST>"
    port: <SOCKS5_PORT>
    username: "<SOCKS5_USERNAME>"
    password: "<SOCKS5_PASSWORD>"
    udp: true
    dialer-proxy: "<UPSTREAM_NODE_NAME>"

append: []

delete: []
```

Edit the current profile's `type: groups` enhancement file:

```yaml
# Profile Enhancement Groups Template for Clash Verge

prepend:
  - name: "<CHAIN_GROUP_NAME>"
    type: select
    proxies:
      - "<CHAINED_PROXY_NAME>"
      - "<UPSTREAM_NODE_NAME>"
      - DIRECT

append: []

delete: []
```

If the user wants the node to appear inside an existing group such as `🔰 选择节点`, use the current profile's script enhancement file:

```js
function main(config, profileName) {
  const chainedProxy = "<CHAINED_PROXY_NAME>";
  const chainedGroup = "<CHAIN_GROUP_NAME>";
  const upstreamNode = "<UPSTREAM_NODE_NAME>";

  config.proxies = config.proxies || [];
  if (!config.proxies.some((proxy) => proxy.name === chainedProxy)) {
    config.proxies.unshift({
      name: chainedProxy,
      type: "socks5",
      server: "<SOCKS5_HOST>",
      port: <SOCKS5_PORT>,
      username: "<SOCKS5_USERNAME>",
      password: "<SOCKS5_PASSWORD>",
      udp: true,
      "dialer-proxy": upstreamNode,
    });
  }

  config["proxy-groups"] = config["proxy-groups"] || [];
  if (!config["proxy-groups"].some((group) => group.name === chainedGroup)) {
    config["proxy-groups"].unshift({
      name: chainedGroup,
      type: "select",
      proxies: [chainedProxy, upstreamNode, "DIRECT"],
    });
  }

  const addProxyToGroup = (groupName) => {
    const group = config["proxy-groups"].find((item) => item.name === groupName);
    if (!group) return;
    group.proxies = group.proxies || [];
    if (!group.proxies.includes(chainedProxy)) {
      group.proxies.unshift(chainedProxy);
    }
  };

  addProxyToGroup("🔰 选择节点");
  addProxyToGroup("🐟 漏网之鱼");

  return config;
}
```

Keep the script idempotent so repeated profile reloads do not duplicate nodes.

## Optional Merge Template

If the user explicitly asks to edit `Merge.yaml`, add the same intent there, but explain that the current remote profile may use a different merge UID.

```yaml
profile:
  store-selected: true

prepend-proxies:
  - name: "<CHAINED_PROXY_NAME>"
    type: socks5
    server: "<SOCKS5_HOST>"
    port: <SOCKS5_PORT>
    username: "<SOCKS5_USERNAME>"
    password: "<SOCKS5_PASSWORD>"
    udp: true
    dialer-proxy: "<UPSTREAM_NODE_NAME>"

prepend-proxy-groups:
  - name: "<CHAIN_GROUP_NAME>"
    type: select
    proxies:
      - "<CHAINED_PROXY_NAME>"
      - "<UPSTREAM_NODE_NAME>"
      - DIRECT
```

Do not rely only on `Merge.yaml` unless `profiles.yaml` shows the current remote profile is actually bound to it.

## Validation

Validate YAML and JS syntax:

```bash
ruby -ryaml -e 'ARGV.each { |path| YAML.load_file(path); puts "ok #{File.basename(path)}" }' \
  "$PROFILES_DIR/<MERGE_FILE>" \
  "$PROFILES_DIR/<PROXIES_FILE>" \
  "$PROFILES_DIR/<GROUPS_FILE>"

node --check "$PROFILES_DIR/<SCRIPT_FILE>"
```

Create a temporary synthesized config and test with the bundled core:

```bash
tmp="$(mktemp -t chained-proxy).yaml"

ruby -ryaml -e '
base_path, proxies_path, groups_path, out = ARGV
doc = YAML.load_file(base_path)
proxy_enhancement = YAML.load_file(proxies_path)
group_enhancement = YAML.load_file(groups_path)

doc["proxies"] ||= []
doc["proxy-groups"] ||= []

proxy_names = doc["proxies"].map { |proxy| proxy["name"] }
(proxy_enhancement["prepend"] || []).reverse_each do |proxy|
  next if proxy_names.include?(proxy["name"])
  doc["proxies"].unshift(proxy)
  proxy_names.unshift(proxy["name"])
end

group_names = doc["proxy-groups"].map { |group| group["name"] }
(group_enhancement["prepend"] || []).reverse_each do |group|
  next if group_names.include?(group["name"])
  doc["proxy-groups"].unshift(group)
  group_names.unshift(group["name"])
end

File.write(out, doc.to_yaml)
' "$PROFILES_DIR/<REMOTE_PROFILE_FILE>" "$PROFILES_DIR/<PROXIES_FILE>" "$PROFILES_DIR/<GROUPS_FILE>" "$tmp"

"/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo" -t -f "$tmp"
```

Success signal:

```text
configuration file <temp-file> test is successful
```

## User Handoff

Tell the user:

- Which enhancement files were edited.
- Which node/group names to select in Clash Verge.
- Whether `verge-mihomo -t` passed.
- That Clash Verge may need a profile reload or core restart before `clash-verge.yaml` reflects the override.

Do not include real credentials in the final answer.
