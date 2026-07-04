#!/usr/bin/env python3
"""Compara dois estados do DroidBot e mostra as views que diferem.

Uso:
    python diff_states.py <dir_states_A> <prefixo_state_str_A> <dir_states_B> <prefixo_state_str_B>

Exemplo:
    python diff_states.py ^
        output_dir_SAD_Mobile_18.3_APKPure\\default\\states ff5076c8 ^
        output_dir_SAD_Mobile_18.3_APKPure\\atf_replay_run\\states f1cc7520
"""

import glob
import json
import os
import sys


def find_state(states_dir, prefix):
    for path in glob.glob(os.path.join(states_dir, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        if str(data.get("state_str", "")).startswith(prefix):
            return path, data
    return None, None


def view_signature(view):
    return (
        view.get("class"),
        view.get("resource_id"),
        (view.get("text") or "").strip(),
        (view.get("content_description") or "").strip(),
    )


def summarize(sig):
    cls, rid, text, desc = sig
    parts = [cls or "?"]
    if rid:
        parts.append(f"id={rid}")
    if text:
        parts.append(f"text={text[:40]!r}")
    if desc:
        parts.append(f"desc={desc[:40]!r}")
    return " | ".join(parts)


def list_states(states_dir):
    found = []
    for path in glob.glob(os.path.join(states_dir, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            found.append((str(data.get("state_str", "?"))[:12],
                          os.path.basename(path)))
        except Exception:
            found.append(("<ilegivel>", os.path.basename(path)))
    return found


def main():
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    dir_a, prefix_a, dir_b, prefix_b = sys.argv[1:5]

    path_a, state_a = find_state(dir_a, prefix_a)
    path_b, state_b = find_state(dir_b, prefix_b)
    for label, path, d, prefix in (("A", path_a, dir_a, prefix_a),
                                   ("B", path_b, dir_b, prefix_b)):
        if path is None:
            print(f"[ERRO] Estado {prefix}* nao encontrado em {label} ({d})")
            if not os.path.isdir(d):
                print(f"       O diretorio nao existe.")
            else:
                states = list_states(d)
                print(f"       {len(states)} arquivos JSON no diretorio:")
                for sid, fname in sorted(states):
                    print(f"         {sid}  {fname}")
            sys.exit(1)
        print(f"{label}: {path}")

    print(f"\nforeground A: {state_a.get('foreground_activity')}")
    print(f"foreground B: {state_b.get('foreground_activity')}")

    sigs_a = {view_signature(v) for v in state_a.get("views", [])}
    sigs_b = {view_signature(v) for v in state_b.get("views", [])}

    only_a = sigs_a - sigs_b
    only_b = sigs_b - sigs_a
    print(f"\nviews: {len(sigs_a)} em A, {len(sigs_b)} em B, "
          f"{len(sigs_a & sigs_b)} em comum")

    print(f"\n=== Somente em A ({len(only_a)}) ===")
    for sig in sorted(only_a, key=str):
        print("  " + summarize(sig))

    print(f"\n=== Somente em B ({len(only_b)}) ===")
    for sig in sorted(only_b, key=str):
        print("  " + summarize(sig))


if __name__ == "__main__":
    main()
