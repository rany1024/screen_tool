#!/usr/bin/env python3
import json
import sys


from pathlib import Path
import os
import shutil
import tempfile
import fcntl
import errno
from contextlib import contextmanager
from datetime import datetime
import time
import copy
import subprocess

import getpass
username = getpass.getuser()
lock_path = f"/tmp/{username}_lock"

# 单个 reload 最长允许持有的时间, 超过则认为是崩溃遗留的死锁
LOAD_LOCK_TTL = 120

# conf.json 读-改-写 互斥锁最长等待时间, 等不到就放弃本次写入而不是卡住提示符
CONF_LOCK_TIMEOUT = 5.0

# 滚动备份: 最多保留份数, 以及两次常规备份之间的最小间隔(秒)
BACKUP_KEEP = 20
BACKUP_MIN_INTERVAL = 300

BOLD = "\033[1;48;5;97m"
RESET = "\033[0m"

CONF_PATH = "~/screen_tool/"


class ConfCorrupt(Exception):
    pass

def run(cmd):
    print(f"run: {' '.join(cmd)}")
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        if r.stderr:
            print(r.stderr)
        #sys.exit(1)
        return r
    return r

def session_exists(name: str) -> bool:
    r = subprocess.run(["screen", "-list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return f".{name}" in r.stdout

def stuff(ss_name: str, win_idx, text: str, max_retry: int = 20) -> bool:
    if not text.endswith("\n"):
        text = text + "\n"

    for attempt in range(1, max_retry + 1):
        r = subprocess.run(
            ["screen", "-S", ss_name, "-p", str(win_idx), "-X", "stuff", text],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if r.returncode == 0:
            return True

        time.sleep(0.05)

    return False
    
def send_cmd(ss_name: str, win_name: str, cmd: str):
    stuff(ss_name, win_name, cmd)

def create_window(ss_name: str, win_name: str, win_obj):
    if session_exists(ss_name):
        print(f" new win {win_name}")
        run(["screen", "-S", ss_name, "-X", "screen", "-t", win_name])
    else:
        print(f" new sess:{ss_name} win:{win_name}")
        run(["screen", "-dmS", ss_name, "-t", win_name])

def create_session(ss_name: str, ss_obj):
    print(f"++ {ss_name}")

    #if session_exists(ss_name):
    #    run(["screen", "-X", "-S", ss_name, "quit"])

    last = ss_obj.get("last_win", "")
    curr = ss_obj.get("curr_win", "")
    wins = ss_obj.get("wins", {}) or {}

    win_nums = sorted((int(k) for k in wins.keys()))
    max_num = win_nums[-1]

    run(["screen", "-dmS", ss_name]) # create session

    for _ in range(max_num):
        run(["screen", "-S", ss_name, "-X", "screen"]) # add max_num wins

    want = set(win_nums)
    for i in range(max_num, -1, -1):
        if i not in want:
            run(["screen", "-S", ss_name, "-p", str(i), "-X", "kill"]) # remove win if not existed

    # fill win data
    for win_name, win_obj in wins.items():
        print(f" +   {win_name}")
        #create_window(ss_name, win_name, win_obj)

        pwd = win_obj.get("pwd", "")
        env = win_obj.get("env", "")
        vi = win_obj.get("vi", "")

        if env:
            send_cmd(ss_name, win_name, " " + env)
            print(f"       env:{env}")
        if pwd:
            send_cmd(ss_name, win_name, " cd " + pwd)
            print(f"       pwd:{pwd}")

        send_cmd(ss_name, win_name, " history -c;history -r")

        if vi:
            send_cmd(ss_name, win_name, " " + vi)
            print(f"       vi:{vi}")

    #run(["screen", "-S", ss_name, "-X", "select", last])
    #run(["screen", "-S", ss_name, "-X", "select", curr])



def load_conf(path: Path) -> dict:
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise ConfCorrupt(f"{path} is empty")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ConfCorrupt(f"{path}: {e}") from None

@contextmanager
def conf_lock(path: Path):
    """把 conf.json 的读-改-写整段串行化, 避免并发进程互相覆盖。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path.parent / (path.name + ".lock")), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + CONF_LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"conf lock busy: {path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

def backup_conf(path: Path, force: bool = False):
    if not path.exists():
        return

    bdir = path.parent / "backups"
    bdir.mkdir(parents=True, exist_ok=True)

    snaps = sorted(bdir.glob("conf-*.json"))
    if not force and snaps:
        if time.time() - snaps[-1].stat().st_mtime < BACKUP_MIN_INTERVAL:
            return

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    shutil.copy2(str(path), str(bdir / f"conf-{stamp}.json"))

    for old in sorted(bdir.glob("conf-*.json"))[:-BACKUP_KEEP]:
        old.unlink()

def count_wins(conf: dict) -> int:
    return sum(len(ss.get("wins", {}) or {}) for ss in conf.values())

def atomic_write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tf:
            json.dump(data, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
        os.replace(tmp, str(path))
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)

    dfd = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)

def save_conf(path: Path, data: dict, before: dict):
    """写回前先滚动备份, 条目变少时强制留一份快照。"""
    backup_conf(path, force=count_wins(data) < count_wins(before))
    atomic_write_json(path, data)


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
        time.sleep(1)


    return

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <show | show_all | load | get | set | del>")
        return

    ssh_conn = os.environ.get('SSH_CONNECTION')
    if not ssh_conn:
        print("SSH_CONNECTION not set", file=sys.stderr)
        return

    ssh_parts = ssh_conn.split()
    conf_name = CONF_PATH + f"{ssh_parts[2]}-{ssh_parts[3]}/conf.json"
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
        backup_conf(conf_path, force=True)

        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))

        try:
            reset_screen(screen_conf)
            time.sleep(2.5)
        finally:
            if os.path.exists(lock_path):
                os.remove(lock_path)

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

        with conf_lock(conf_path):
            set_win(conf_path, ss_name, win_name, pwd, bash_cmd)

        return

    if cmd == "del":
        if len(sys.argv) != 2:
            print(f"Usage: {sys.argv[0]} {cmd} ", file=sys.stderr)
            return

        with conf_lock(conf_path):
            del_win(conf_path, ss_name, win_name)

        return

    print(f"Unknown cmd: {cmd}\nAllowed: load | set | del", file=sys.stderr)


def set_win(conf_path: Path, ss_name, win_name, pwd, bash_cmd):
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

    curr_win["pwd"] = pwd

    if not bash_cmd.startswith('python3 $tool_path/screen_tool.py'):
        print(f"._EXEC_: {BOLD}{bash_cmd}{RESET}")

    if bash_cmd[:2] == "vi" :
        print(f"Enter vi: [{BOLD}{bash_cmd}{RESET}]")
        curr_win["vi"] = bash_cmd
    elif "vi" in curr_win :
        del curr_win["vi"]

    if bash_cmd[:4] == "env.":
        print(f"Enter env: [{BOLD}{bash_cmd}{RESET}]")
        curr_win["env"] = bash_cmd

    if (screen_conf == screen_conf_ori):
        return

    ss_obj["last_ts"] = datetime.now().strftime("%Y%m%d-%H:%M:%S")

    ss_obj["wins"] = dict(sorted(wins.items(), key=lambda x: int(x[0])))

    screen_conf = dict(sorted(screen_conf.items(), key=lambda x: x[0]))

    save_conf(conf_path, screen_conf, screen_conf_ori)


def del_win(conf_path: Path, ss_name, win_name):
    screen_conf = load_conf(conf_path)
    screen_conf_ori = copy.deepcopy(screen_conf)

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

    save_conf(conf_path, screen_conf, screen_conf_ori)


def load_lock_active() -> bool:
    """判断 reload 锁是否有效, 顺手清掉崩溃遗留的死锁。"""
    try:
        st = os.stat(lock_path)
    except FileNotFoundError:
        return False

    stale = time.time() - st.st_mtime > LOAD_LOCK_TTL
    if not stale:
        try:
            os.kill(int(Path(lock_path).read_text().strip()), 0)
        except (ValueError, ProcessLookupError):
            stale = True
        except PermissionError:
            pass

    if stale:
        try:
            os.remove(lock_path)
        except FileNotFoundError:
            pass
        return False

    return True


if __name__ == "__main__":

    if load_lock_active():
        exit(0)

    try:
        main()
    except ConfCorrupt as e:
        print(f"conf.json unreadable, refusing to write: {e}", file=sys.stderr)
        exit(1)
    except TimeoutError as e:
        print(f"skip write: {e}", file=sys.stderr)
        exit(1)
