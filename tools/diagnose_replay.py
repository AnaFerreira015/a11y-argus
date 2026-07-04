#!/usr/bin/env python3
"""Diagnostico do matching de replay: compara estados gravados (default/states)
com os estados ao vivo salvos pelo plugin (atf/*.state.json).

Uso:
    python diagnose_replay.py output_dir_SAD_Mobile_18.3_APKPure
"""

import glob
import json
import os
import sys
from collections import defaultdict


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sig_full(v):
    return (v.get("class"), v.get("resource_id"),
            (v.get("text") or "").strip(),
            (v.get("content_description") or "").strip())


def sig_struct(v):
    return (v.get("class"), v.get("resource_id"))


def show(sig):
    return " | ".join(str(p) for p in sig if p)


def main():
    output_root = sys.argv[1]
    recorded_dir = os.path.join(output_root, "default", "states")
    atf_dir = os.path.join(output_root, "atf")

    recorded, live = [], []
    for p in sorted(glob.glob(os.path.join(recorded_dir, "*.json"))):
        try:
            recorded.append(load(p))
        except Exception:
            pass
    for p in sorted(glob.glob(os.path.join(atf_dir, "*.state.json"))):
        try:
            live.append(load(p))
        except Exception:
            pass

    print(f"=== GRAVADOS ({len(recorded)}) ===")
    print(f"{'state_str':14s} {'structure':14s} foreground")
    for s in recorded:
        print(f"{str(s.get('state_str'))[:12]:14s} "
              f"{str(s.get('state_str_content_free'))[:12]:14s} "
              f"{s.get('foreground_activity')}")

    print(f"\n=== AO VIVO / replay ({len(live)}) ===")
    print(f"{'state_str':14s} {'structure':14s} foreground")
    for s in live:
        print(f"{str(s.get('state_str'))[:12]:14s} "
              f"{str(s.get('state_str_content_free'))[:12]:14s} "
              f"{s.get('foreground_activity')}")

    if not live:
        print("\n[!] Nenhum .state.json em atf/. O plugin esta salvando o estado?")
        return

    # Diff do estado ao vivo mais recente contra os gravados de mesma activity
    target = live[-1]
    fg = target.get("foreground_activity")
    peers = [s for s in recorded if s.get("foreground_activity") == fg]
    print(f"\n=== DIFF: ao vivo {str(target.get('state_str'))[:12]} vs "
          f"gravados com foreground {fg} ({len(peers)}) ===")
    if not peers:
        print("[!] Nenhum estado gravado com essa activity. As activities "
              "iniciais divergem entre captura e replay.")
        return

    tv_full = {sig_full(v) for v in target.get("views", [])}
    tv_struct = defaultdict(int)
    for v in target.get("views", []):
        tv_struct[sig_struct(v)] += 1

    for peer in peers:
        pv_full = {sig_full(v) for v in peer.get("views", [])}
        pv_struct = defaultdict(int)
        for v in peer.get("views", []):
            pv_struct[sig_struct(v)] += 1

        print(f"\n--- vs gravado {str(peer.get('state_str'))[:12]} "
              f"(structure {str(peer.get('state_str_content_free'))[:12]}) ---")

        only_live = tv_full - pv_full
        only_rec = pv_full - tv_full
        print(f"[nivel texto] so no ao vivo ({len(only_live)}):")
        for s in sorted(only_live, key=str):
            print("   " + show(s))
        print(f"[nivel texto] so no gravado ({len(only_rec)}):")
        for s in sorted(only_rec, key=str):
            print("   " + show(s))

        struct_diff = {k for k in set(tv_struct) | set(pv_struct)
                       if tv_struct.get(k, 0) != pv_struct.get(k, 0)}
        print(f"[nivel estrutura] classes/ids com contagem diferente "
              f"({len(struct_diff)}):")
        for s in sorted(struct_diff, key=str):
            print(f"   {show(s)}  (ao vivo={tv_struct.get(s, 0)}, "
                  f"gravado={pv_struct.get(s, 0)})")


if __name__ == "__main__":
    main()
