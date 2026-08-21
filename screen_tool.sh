#!/bin/bash

tool_path="`cd $(dirname $BASH_SOURCE);pwd;cd - > /dev/null`"


# Regist __log_screen_path
__log_screen_path() {
    if [ -z "$STY" ] || [ -n "$__st_killed_by_signal" ]; then
        return
    fi

    win_id=$WINDOW
    ss_name=${STY#*.}

    if [[ "$PROMPT_COMMAND;" == *"$BASH_COMMAND;"* ]]; then
        return 
    fi

    if [[ "${BASH_COMMAND:0:6}" == "python" ]]; then
        return
    fi

    #printf "%-16s %-6s %s\n" "$ss_name" "$win_id" "$PWD"
    #python3.8 $tool_path/screen_tool.py "set" "$ss_name" "$win_id" "$PWD" "$BASH_COMMAND"
    python3.8 $tool_path/screen_tool.py "set" "$BASH_COMMAND"

    history -a
}

if [[ -z "$PROMPT_COMMAND" ]]; then
    PROMPT_COMMAND="__log_screen_path"
else
    PROMPT_COMMAND="$(echo $PROMPT_COMMAND | sed 's/;__log_screen_path//g' )"
    PROMPT_COMMAND="${PROMPT_COMMAND%%+([[:space:];])};__log_screen_path"
fi
trap __log_screen_path DEBUG


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
        python3.8 $tool_path/screen_tool.py "load" $2
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

    if [ -z $SGARCH ]; then
        last=$(screen_tool -last)
        if [ -n $last]; then
            echo "cd to last $last"
            cd "$last"
        fi
    fi

    __set_history_param

    echo "$script_name load completed!"

else
    echo "$script_name [install | uninstall]"

fi
