#!/usr/bin/env sh

killall -q polybar

while pgrep -x polybar >/dev/null; do sleep 1; done

nohup polybar -c /home/joao/.config/polybar/config.ini > /dev/null 2>&1 &
