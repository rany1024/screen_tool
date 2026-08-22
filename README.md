# screen_tool

# 1. 安装/卸载screen_tool
```
source screen_tool.sh install
source screen_tool.sh uninstall
```

# 2. 基础命令
```
st : 列出当前会话的窗口
st -a : 列出全部会话
st <id> : cd 到指定窗口的路径
st -load : 按 conf 恢复会话, 并 screen -rd 进最近一次工作的会话
```

# 3. 基本功能
    3.1 记录各会话/窗口, 保存到 `[<SSH目标IP>-<端口>/conf.json]`
    3.2 跟着窗口增删、切路径、`env.` / `vi` 更新 conf
    3.3 断电后 `st -load` 恢复会话, 并进入最近一次工作的会话
