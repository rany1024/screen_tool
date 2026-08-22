#!/bin/bash

tool_path="`cd $(dirname $BASH_SOURCE);pwd;cd - > /dev/null`"


# DEBUG 只记下即将执行的命令; 真正写 conf 放到 PROMPT_COMMAND,
# 这时 cd 已经完成, PWD 才是对的。source 本脚本期间 __st_ready 为空, 不会入账。
__st_ready=""
__st_pending_cmd=""

__st_on_debug() {
    if [ -z "$__st_ready" ] || [ -z "$STY" ] || [ -n "$__st_killed_by_signal" ]; then
        return
    fi
    if [[ "$PROMPT_COMMAND;" == *"$BASH_COMMAND;"* ]]; then
        return
    fi
    case "$BASH_COMMAND" in
        python*|__st_*|__log_screen_path*|__set_history_param*|__on_bash_exit*)
            return
            ;;
    esac
    __st_pending_cmd="$BASH_COMMAND"
    printf '._EXEC_: \033[1;48;5;97m%s\033[0m\n' "$BASH_COMMAND"
}

__log_screen_path() {
    if [ -z "$__st_ready" ] || [ -z "$STY" ] || [ -n "$__st_killed_by_signal" ]; then
        return
    fi

    trap - DEBUG
    python3.8 $tool_path/screen_tool.py "set" "$__st_pending_cmd"
    __st_pending_cmd=""
    history -a
    trap __st_on_debug DEBUG
}

if [[ -z "$PROMPT_COMMAND" ]]; then
    PROMPT_COMMAND="__log_screen_path"
else
    PROMPT_COMMAND="$(echo $PROMPT_COMMAND | sed 's/;__log_screen_path//g' )"
    PROMPT_COMMAND="${PROMPT_COMMAND%%+([[:space:];])};__log_screen_path"
fi


# Regist __on_bash_exit
#
# 只有用户主动 exit 才把窗口从 conf.json 里摘掉。被 SIGHUP/SIGTERM 干掉时
# (关机、screen -X quit、ssh 断链) 保留记录, 否则一次关机就会让所有窗口
# 同时自删, 把整个 conf.json 清空。
__st_killed_by_signal=""
__st_on_signal() {
    __st_killed_by_signal=$1
    trap - DEBUG
    PROMPT_COMMAND=
    exit $2
}
trap '__st_on_signal HUP 129' HUP
trap '__st_on_signal TERM 143' TERM

__on_bash_exit() {
    if [ -z "$STY" ] || [ -n "$__st_killed_by_signal" ]; then
        return
    fi

    win_id=$WINDOW
    ss_name=${STY#*.}

    python3.8 $tool_path/screen_tool.py "del"
}
trap __on_bash_exit EXIT

__set_history_param() {
    if [ -z "$STY" ]; then
        return
    fi

    local_name=$(echo $SSH_CONNECTION | awk '{ print($3"-"$4) }')
    win_id=$WINDOW
    ss_name=${STY#*.}

    if [ -n "$ss_name" ] && [ -n "$win_id" ]; then
        export HISTFILE="$tool_path/$local_name/historys/$ss_name/${win_id}.history"

        mkdir -p "$(dirname "$HISTFILE")"

        export HISTSIZE=500
        export HISTFILESIZE=1000

        #shopt -s histappend

        #history -c
        #history -r

        echo "HISTFILE=$HISTFILE"
        echo "HISTSIZE=$HISTSIZE"
        echo "history set complet!"
    fi
}


screen_tool() {
    ss_name=${STY#*.}
    switch_id=$1
    if [ -z "$switch_id" ]; then
        python3.8 $tool_path/screen_tool.py "show"
    elif [ x"$switch_id" == x"-a" ]; then
        python3.8 $tool_path/screen_tool.py "show_all"
    elif [ x"$switch_id" == x"-last" ]; then
        python3.8 $tool_path/screen_tool.py "get_last_pwd"
    elif [ x"$switch_id" == x"-load" ]; then
        python3.8 $tool_path/screen_tool.py "load" $2 || return
        if [ -n "$STY" ]; then
            return
        fi
        target=$(python3.8 $tool_path/screen_tool.py "get_last_target")
        last=${target%% *}
        win=${target#* }
        if [ -z "$last" ]; then
            return
        fi
        if [ -n "$win" ] && [ "$win" != "$last" ]; then
            echo "screen -rd $last -p $win"
            screen -rd "$last" -p "$win"
        else
            echo "screen -rd $last"
            screen -rd "$last"
        fi
    else
        path=$(python3.8 $tool_path/screen_tool.py "get" $switch_id)
        cd "$path"
    fi
}


# install / uninstall / normal exec ##########################################
script_name=$(basename "$BASH_SOURCE")
line=$(awk "/source .*$script_name/ {print FNR}" ~/.bashrc)
if [ x"$1" = x"install" ];  then
    if [ -z "$line" ]; then
        echo "source $tool_path/$script_name" >> ~/.bashrc
        echo "$script_name install success"
        bash
    else
        echo "$script_name has been installed!"
    fi

elif [ x"$1" = x"uninstall" ];then
    if [ "a$line" = "a" ]; then
        echo "Can't find $script_name!"
    else
        sed -i "$line d" ~/.bashrc
        echo "$script_name has been uninstalled!"

        alias st='st'
    fi

elif [ x"$1" = x"" ]; then #normal exec
    alias st='screen_tool'

    if [ -z "$SGARCH" ]; then
        last=$(screen_tool -last)
        if [ -n "$last" ]; then
            echo "cd to last $last"
            cd "$last"
        fi
    fi

    __set_history_param

    echo "$script_name load completed!"
    __st_ready=1

else
    echo "$script_name [install | uninstall]"

fi
