#!/usr/bin/env python3
"""一次性脚本: 把 2026-07-31 关机时被 del 掉的 5 个 session 补回 conf.json。

pwd / env / vi 全部由 historys/<session>/<win>.history 反推, 已逐条核验目录存在;
原目录已被删除的, 回落到最近的存在祖先。执行前会强制备份。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/home/rany/screen_tool")
from screen_tool import conf_lock, load_conf, save_conf, backup_conf  # noqa: E402

CONF = Path("/home/rany/screen_tool/192.168.1.5-2227/conf.json")
HIST = CONF.parent / "historys"

UP2 = "/home/rany/fastwork/ci/s3160/UP2PTX02"
H1T4 = "/home/rany/fastwork/ci/s3160/H1T4RTX01H"
WIFI = "/home/rany/tmp/tmp/wifi-driver"

LOST = {
    "a2_s3160_UP2PTX02-DT08": {
        "curr_win": "4",
        "wins": {
            "0": {"pwd": UP2},
            "1": {"pwd": f"{UP2}/sdk/smp/a7_linux/source/mpp"},
            "2": {"pwd": f"{UP2}/deps/atbm6062cu", "env": "env.hi3516"},
            "3": {"pwd": f"{UP2}/sdk/smp/a7_linux/source/mpp/apps",
                  "env": "env.hi3516", "vi": "vi tx_task.c "},
            "4": {"pwd": f"{UP2}/sdk/smp/a7_linux/source/mpp/apps"},
            "5": {"pwd": f"{UP2}/sdk/TuTuLink/include/libttcommon", "env": "env.hi3516"},
            "6": {"pwd": f"{UP2}/sdk/TuTuLink/lib/modules"},
            # 原 backtrace_v2.0/simple 已删除, 回落到上级
            "7": {"pwd": "/home/rany/tmp/backtrace/backtrace_v2.0"},
        },
    },
    "a4_s3160_1t4rtx": {
        "curr_win": "1",
        "wins": {
            "0": {"pwd": H1T4},
            "1": {"pwd": f"{H1T4}/deps/seekwave_4h135/out", "env": "env.hi3516"},
            "2": {"pwd": f"{H1T4}/sdk/TuTuLink/etc"},
            "3": {"pwd": f"{H1T4}/sdk/smp/a7_linux/source/mpp/apps",
                  "env": "env.hi3516", "vi": "vi tx_task.c"},
            "4": {"pwd": f"{WIFI}/swt6621"},
        },
    },
    "b_swt6652x": {
        "curr_win": "5",
        "wins": {
            "0": {"pwd": f"{WIFI}/swt6652x"},
            "1": {"pwd": f"{WIFI}/swt6652x", "env": "env.hi3516"},
            "2": {"pwd": f"{WIFI}/swt6652x"},
            # 原 SWT6652_H26.16.5.1_F26.20.2.4/swt6652x 已删除, 回落到同名工作副本
            "3": {"pwd": f"{WIFI}/swt6652x", "env": "env.hi3516"},
            "4": {"pwd": f"{WIFI}/atbm6062cu", "vi": "vi Makefile"},
            "5": {"pwd": "/home/rany/fastwork/ubuntu_vm_enc/wifi/ap_sta/hostapd",
                  "vi": "vi start_hostapd.sh "},
        },
    },
    "b_wpa_nl": {
        "curr_win": "0",
        "wins": {
            # 原 deps/wifi-driver/hostapd 已删除, 回落到 deps
            "0": {"pwd": "/home/rany/fastwork/ci/s3160/HP2PTX08/deps", "env": "env.t32"},
            "1": {"pwd": "/home/rany/fastwork/ci/s23xx/H1T4RTX01_ori/sdk/opensource",
                  "env": "env.hi3516"},
            "2": {"pwd": "/home/rany/fastwork/ci/s3160/HP2PTX08/deps", "env": "env.hi3516"},
            "3": {"pwd": "/home/public/env", "vi": "vi env.hi3516 "},
            "4": {"pwd": "/home/rany/tmp/test_c/test_printf", "env": "env.hi3516"},
            "5": {"pwd": "/home/rany/wifi8272/am8270/sdk/output/build/iperf-2.0.5",
                  "env": "env.t23"},
        },
    },
    "c_libttbp": {
        "curr_win": "4",
        "wins": {
            "0": {"pwd": "/home/rany/tmp/tmp/libttbp/trunk/libttmirror"},
            "1": {"pwd": "/home/rany/tmp/tmp/libttbp/trunk", "vi": "vi libttbp.h "},
            "2": {"pwd": "/home/rany/tmp/tmp/libttbp/trunk", "vi": "vi ttbp_io.h "},
            "3": {"pwd": "/home/rany/tmp/tmp/libttmp/branches/typeAC"},
            "4": {"pwd": f"{H1T4}/deps/ttmirror", "vi": "vi libttmirror_tx.h "},
            "5": {"pwd": "/home/rany/fastwork/ci/s13xx/H1T4RRX01/deps/ttmirror",
                  "vi": "vi ttmulti.c "},
        },
    },
}


def newest_history_ts(ss_name: str) -> str:
    files = list((HIST / ss_name).glob("*.history"))
    newest = max(f.stat().st_mtime for f in files)
    return datetime.fromtimestamp(newest).strftime("%Y%m%d-%H:%M:%S")


def main():
    missing = [p["pwd"] for ss in LOST.values() for p in ss["wins"].values()
               if not Path(p["pwd"]).is_dir()]
    if missing:
        print("以下目录不存在, 中止:", *missing, sep="\n  ")
        return 1

    with conf_lock(CONF):
        conf = load_conf(CONF)
        before = json.loads(json.dumps(conf))
        backup_conf(CONF, force=True)

        for ss_name, spec in LOST.items():
            if ss_name in conf:
                print(f"skip {ss_name}: 已存在")
                continue
            conf[ss_name] = {
                "wins": spec["wins"],
                "last_win": "",
                "curr_win": spec["curr_win"],
                "last_ts": newest_history_ts(ss_name),
            }
            print(f"add  {ss_name}: {len(spec['wins'])} wins, "
                  f"last_ts={conf[ss_name]['last_ts']}")

        conf = dict(sorted(conf.items(), key=lambda x: x[0]))
        save_conf(CONF, conf, before)

    print(f"\n现在共 {len(load_conf(CONF))} 个 session")
    return 0


if __name__ == "__main__":
    sys.exit(main())
