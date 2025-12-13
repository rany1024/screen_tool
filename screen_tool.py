#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import os
import tempfile
from datetime import datetime
import time
import copy


CONF_PATH = "~/screen_tool/"

def load_conf(path: Path) -> dict:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def atomic_write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, encoding="utf-8",
        dir=str(path.parent), prefix=path.name + ".tmp."
    ) as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        tmp = tf.name
    os.replace(tmp, str(path))

def print_ss(ss_name, ss_obj, is_selected):
    curr = ss_obj.get("curr_win", "")
    wins = ss_obj.get("wins", {}) or {}
    print(f" {ss_name}")
    for win_name, p in wins.items():

#        if not isinstance(p, dict):
#            pstr = p
#            p = wins[win_name] = {}
#            p["pwd"] = pstr

        if is_selected :
            if curr == win_name:
                print(f"    => {win_name:>2}  {p}")
            else:
                print(f"       {win_name:>2}  {p}")
        else :
            print(f"       {win_name:>2}  {p}")
    print(" ")



def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <show | show_all | load | get | set | del>")
        return

    ssh_parts = os.environ.get('SSH_CONNECTION').split()
    conf_name = CONF_PATH + f"conf_{ssh_parts[2]}-{ssh_parts[3]}.json"
    conf_path = Path(conf_name).expanduser()

    win_name = os.environ.get('WINDOW')
    pwd = os.environ.get('PWD')
    ss_name = (os.environ.get('STY') or '').split('.', 1)[-1]

    cmd = sys.argv[1].lower()

    if cmd == "show" or cmd == "show_all":
        if len(sys.argv) != 2:
            print(f"Usage: {sys.argv[0]} {cmd}", file=sys.stderr)
            return

        screen_conf = load_conf(conf_path)

        for __ss_name, ss_obj in screen_conf.items():
            if __ss_name == ss_name :
                print("=>", end="")
                print_ss(__ss_name, ss_obj, __ss_name == ss_name)
            elif cmd == "show_all":
                print("  ", end="")
                print_ss(__ss_name, ss_obj, __ss_name == ss_name)


        #print(f"{ss_name} 1.not find!")
        return

    if cmd == "load":
        screen_conf = load_conf(conf_path)
        for ss_name, ss_obj in screen_conf.items():
            print_ss(ss_name, ss_obj)
        return

    if cmd == "get":
        if len(sys.argv) != 3:
            print(f"Usage: {sys.argv[0]} {cmd} <switch_id>", file=sys.stderr)
            return

        switch_id = sys.argv[2]
        screen_conf = load_conf(conf_path)

        switch_path = screen_conf[ss_name]["wins"][switch_id]["pwd"];

        print(f"{switch_path}", file=sys.stdout)

        return

    if cmd == "set":
        if len(sys.argv) != 3:
            print(f"Usage: {sys.argv[0]} {cmd} <bash_cmd>", file=sys.stderr)
            return

        bash_cmd = sys.argv[2]

        screen_conf = load_conf(conf_path)
        screen_conf_ori = copy.deepcopy(screen_conf)

        ss_obj = screen_conf.setdefault(ss_name, {})
        ss_obj["curr_win"] = win_name
        wins = ss_obj.setdefault("wins", {})
        curr_win = wins.setdefault(win_name, {})
#        if not isinstance(curr_win, dict):
#            __type = type(curr_win)
#            print(f"curr_win({__type}) not dict!, reset it!")
#            curr_win = wins[win_name] = {}
        
        curr_win["pwd"] = pwd

        if not bash_cmd.startswith('python3 $tool_path/screen_tool.py'):
            BOLD  = "\033[1;48;5;97m"
            RESET = "\033[0m"
            print(f"._EXEC_: {BOLD}{bash_cmd}{RESET}")

        if bash_cmd[:2] == "vi" :
            print(f"Enter vi: [{BOLD}{bash_cmd}{RESET}]")
            curr_win["vi"] = bash_cmd
        elif "vi" in curr_win :
            del curr_win["vi"]

        if bash_cmd[:4] == "env.":
            print(f"Enter env: [{BOLD}{bash_cmd}{RESET}]")
            curr_win["env"] = bash_cmd

        #wins[str(win_name)] = pwd

        if (screen_conf == screen_conf_ori):
            return

        ss_obj["last_ts"] = datetime.now().strftime("%Y%m%d-%H:%M:%S")

        ss_obj["wins"] = dict(sorted(wins.items(), key=lambda x: int(x[0])))

        atomic_write_json(conf_path, screen_conf)
        return

    if cmd == "del":
        if len(sys.argv) != 2:
            print(f"Usage: {sys.argv[0]} {cmd} ", file=sys.stderr)
            return

        screen_conf = load_conf(conf_path)
        if not ss_name in screen_conf:
            print(f"session {ss_name} 2.not find!")
            return

        if not win_name in screen_conf[ss_name]["wins"]:
            print(f"in{ss_name}, win {win_name} 3.not find!")
            return

        del screen_conf[ss_name]["wins"][win_name]

        if not screen_conf[ss_name]["wins"] :
            del screen_conf[ss_name]

        atomic_write_json(conf_path, screen_conf)

        return

    print(f"Unknown cmd: {cmd}\nAllowed: load | set | del", file=sys.stderr)

if __name__ == "__main__":
    main()

