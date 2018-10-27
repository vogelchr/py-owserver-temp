#!/bin/sh

install -v -m755 -o0 -g0 py-owserver-temp.py /usr/local/sbin
install -v -m644 -o0 -g0 ow_temp_sensors.txt /usr/local/share

if [ -d /etc/systemd/system ] ; then
	do_reload=0
	if [ -f "/etc/systemd/system/log_ow_temp.service" ] ; then
		do_reload=1
		systemctl stop log_ow_temp
	fi
	install -v -m644 -o0 -g0 log_ow_temp.service /etc/systemd/system/log_ow_temp.service

	if [ "$do_reload" = 1 ] ; then
		systemctl daemon-reload
	fi

	systemctl enable log_ow_temp
	systemctl start log_ow_temp
fi
