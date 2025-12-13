# screen_tool

# 1. 安装/卸载screen_tool
```
source screen_tool.sh install
source screen_tool.sh uninstall
```

# 2. 基础命令
```
st : 相当于screen_tool show
st -a : 相当于 screen_tool show_all
st <id> : cd 到指定id的路径去
```

# 3. 基本功能
3.1 记录screen各会话,窗口信息, 保存到[conf_服务地址-端口号.json]中
3.2 会根窗口的增/删, 切换路径而更新conf...json的内容
3.3 断电后调用screen_tool load 恢复会话 (暂未实现)
