#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import os
import tempfile
from datetime import datetime
import time
import copy
import subprocess



CONF_PATH = "~/screen_tool/"

def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        if r.stderr:
            print(r.stderr)
        sys.exit(1)
    return r

def session_exists(name: str) -> bool:
    r = subprocess.run(["screen", "-list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return f".{name}" in r.stdout

def stuff(ss_name: str, window_index: int, text: str):
    run(["screen", "-S", ss_name, "-p", str(window_index), "-X", "stuff", text])

def send_cmd(ss_name: str, win_name: str, cmd: str, delay: float = 0.01):
    stuff(ss_name, win_name, cmd + "\n")
    time.sleep(delay)

def create_window(ss_name: str, win_name: str, win_obj):
    if session_exists(ss_name):
        run(["screen", "-S", ss_name, "-X", "screen", "-t", ""])
    else:
        run(["screen", "-dmS", ss_name, "-t", ""])

def create_session(ss_name: str, ss_obj):
    print(f"++ {ss_name}")

    #if session_exists(ss_name):
    #    run(["screen", "-X", "-S", ss_name, "quit"])

    last = ss_obj.get("last_win", "")
    curr = ss_obj.get("curr_win", "")
    wins = ss_obj.get("wins", {}) or {}
    for win_name, win_obj in wins.items():
        print(f" +   {win_name}")
        create_window(ss_name, win_name, win_obj)

        pwd = win_obj.get("pwd", "")
        env = win_obj.get("env", "")
        vi = win_obj.get("vi", "")

        if env:
            send_cmd(ss_name, win_name, env)
            print(f"       env:{env}")
        if pwd:
            send_cmd(ss_name, win_name, "cd " + pwd)
            print(f"       pwd:{pwd}")
        if vi:
            send_cmd(ss_name, win_name, vi)
            print(f"       vi:{vi}")

    run(["screen", "-S", ss_name, "-X", "select", last])
    run(["screen", "-S", ss_name, "-X", "select", curr])



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


def get_wins_len_dict(wins):
    len_dict = {}
    
    for win_name, p in wins.items():
        for key, val in p.items():
            current_len = len(val)
            if key not in len_dict or len_dict[key] < current_len:
                len_dict[key] = current_len
    
    #wins = copy.deepcopy(wins)
    #
    #for win_name, p in wins.items():
    #    for key, val in p.items():
    #        p[key] = val.ljust(len_dict[key])
    
    return len_dict
        

def print_ss(ss_name, ss_obj, is_selected):
    last = ss_obj.get("last_win", "")
    curr = ss_obj.get("curr_win", "")
    wins = ss_obj.get("wins", {}) or {}
    len_dict = get_wins_len_dict(wins)

    print(f" {ss_name}")
    for win_name, p in wins.items():

#        if not isinstance(p, dict):
#            pstr = p
#            p = wins[win_name] = {}
#            p["pwd"] = pstr

        #p_str = "   |   ".join(f"{v:<90}" for k, v in p.items() if v)
        #pwd =  p["pwd"].ljust(len_dict["pwd"] if "pwd" in p else ""
        #env = p["env"] if "env" in p else ""
        #vi = p["vi"] if "vi" in p else ""
        #p_str = " | ".join(item for item in (pwd, env, vi))
        p_str = p

        if is_selected :
            if curr == win_name:
                print(f"    => {win_name:>2}  {p_str}")
            elif last == win_name:
                print(f"    -- {win_name:>2}  {p_str}")
            else:
                print(f"       {win_name:>2}  {p_str}")
        else :
            print(f"       {win_name:>2}  {p_str}")
    print(" ")

def reset_screen(screen_conf):

    # kill all session
    run(["bash", "-c", "screen -ls | awk '/\\t/ {print $1}' | xargs -r -I {} screen -X -S {} quit"])

    for ss_name, ss_obj in screen_conf.items():
        create_session(ss_name, ss_obj)
        time.sleep(0.2)


    return

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

    #print(f"cmd:[{cmd}]")

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

    if cmd == "get_last_pwd":
        if len(sys.argv) != 2:
            print(f"Usage: {sys.argv[0]} {cmd}", file=sys.stderr)
            return

        screen_conf = load_conf(conf_path)

        for __ss_name, ss_obj in screen_conf.items():
            if __ss_name == ss_name :
                last_win_name = ss_obj.get("last_win")
                pwd = ss_obj["wins"][last_win_name]["pwd"]
                print(f"{pwd}")
                return
                
        return

    if cmd == "load":
        print(f"conf_path:[{conf_path}]")
        screen_conf = load_conf(conf_path)
        reset_screen(screen_conf)
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
        wins = ss_obj.setdefault("wins", {})
        last_win_name = ss_obj.get("curr_win", "")
        if last_win_name != win_name :
            ss_obj["last_win"] = last_win_name

        if not last_win_name in wins:
            ss_obj["last_win"] = ""

        ss_obj["curr_win"] = win_name
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

        screen_conf = dict(sorted(screen_conf.items(), key=lambda x: x[0]))

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

        if screen_conf[ss_name]["last_win"] == win_name:
            screen_conf[ss_name]["last_win"] = ""

        if not screen_conf[ss_name]["wins"] :
            del screen_conf[ss_name]

        atomic_write_json(conf_path, screen_conf)

        return

    print(f"Unknown cmd: {cmd}\nAllowed: load | set | del", file=sys.stderr)

if __name__ == "__main__":
    main()

