#!/bin/sh
# Local key math stays in the container. Interface and NAT operations
# become structured helper calls. iptables text is refused.
cmd=$(basename "$0")
case "$cmd" in
  iptables|ip6tables|iptables-nft|ip6tables-nft|iptables-legacy|ip6tables-legacy)
    echo "wg-helper: rejected command" >&2
    exit 127
    ;;
esac
if [ "$cmd" = wg ]; then
  case "$1" in
    genkey|genpsk|pubkey) exec /usr/bin/wg "$@" ;;
  esac
fi
if [ "$cmd" = wg-quick ] && [ "$1" = strip ]; then
  exec /usr/bin/wg-quick "$@"
fi
exec node /opt/wg-handoff/handoff.mjs "$cmd" "$@"
