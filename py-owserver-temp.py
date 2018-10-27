#!/usr/bin/python
import datetime
import sys
import time

import pyownet
from influxdb import InfluxDBClient


###
# writing to a logfile with a given strftime() formatted
# name, and a dummy version used for a fixed filedescriptor
###

# dummy
class NonTSLogfile:
    def __init__(self, f_or_fn):
        if type(f_or_fn) == str:
            self.fn = f_or_fn
            self.f = open(f_or_fn, 'at')
        else:
            self.fn = 'Unknown'
            self.f = f_or_fn
        self.ts = None
        self.fresh = True

    def update(self, ts=None):
        self.ts = ts

    def write(self, *args, **kwargs):
        self.fresh = False
        self.f.write(*args, **kwargs)


# filename given as strftime format
class TimestampLogfile:
    def __init__(self, filefmt):
        self.filefmt = filefmt
        self.ts = None

        self.fn = None
        self.f = None
        self.fresh = None

    def update(self, ts=None):
        if ts is None:
            ts = datetime.datetime.now()
        self.ts = ts
        newfn = ts.strftime(self.filefmt)
        if newfn != self.fn:
            if self.f:
                self.f.close()

            print('New logfile', newfn)
            sys.stdout.flush()

            self.fn = newfn
            self.f = open(newfn, 'at')
            self.fresh = True

    def write(self, *args, **kwargs):
        if self.f is None:
            self.update()

        self.fresh = False
        self.f.write(*args, **kwargs)


# read text file with two columns
def read_list_of_tuples(fn, ncol):
    ret = list()
    for n, line in enumerate(open(fn, 'rt'), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        arr = line.split()
        if len(arr) != ncol:
            raise RuntimeError('%s:%d Need %d items per line.' % (fn, n, ncol))
        ret.append(tuple(arr))
    return ret


# format float from value dict
def format_sensorline(sensors_and_names, value_dict):
    arr = list()
    for ow, name in sensors_and_names:
        if not name in value_dict:
            arr.append('-       ')
        else:
            arr.append('%+7.2f' % value_dict[name])
    return ' '.join(arr)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--filefmt', metavar='FMT',
                        default='temp_@Y-@m-@d.log',
                        help='logfile format, like strftime, but with @ [def: temp_@Y-@m-@d.log]')
    parser.add_argument('-s', '--stdout', action='store_true', default=False,
                        help='Output log to stdout (e.g. for debugging).')
    parser.add_argument('-t', '--time', type=float, metavar='SEC', default=15,
                        help='Time to sleep between updates, in seconds. [def: 15]')
    parser.add_argument('sensorlist',
                        help='''File with temperature sensor list, one sensor
per line, comments starting with # allowed, empty lines allowed. First column
is onewire address (28.ABCD...), second column is short name.''')

    args = parser.parse_args()

    sensors = read_list_of_tuples(args.sensorlist, 2)
    print('Read %d sensors from %s.' % (len(sensors), args.sensorlist))

    args.filefmt = args.filefmt.replace('@', '%')

    # logfile
    lf = NonTSLogfile(sys.stdout) if args.stdout else TimestampLogfile(args.filefmt)

    # influxdb
    iflxdb = InfluxDBClient('localhost', 8086)

    ownet = pyownet.protocol.proxy()  # default to localhst, that's fine for us

    while True:
        ###
        # read thermometers
        ###
        post_data = dict()
        for ow, name in sensors:
            try:
                t_degC_str = ownet.read(ow + '/temperature')
                t_degC = float(t_degC_str)
                post_data[name] = t_degC
            except Exception as e:
                print('Cannot read ow sensor %s (%s): %s' % (name, ow, e))
                continue

        now = datetime.datetime.now()
        lf.update(now)
        if lf.fresh:
            print('#', ' '.join([name for ow, name in sensors]))

        ts = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        print(ts, format_sensorline(sensors, post_data), file=lf)
        lf.f.flush()

        try:
            influxdb_json_body = [{
                'measurement': 'heating',
                'time': ts,
                'fields': post_data
            }]
            iflxdb.write_points(influxdb_json_body, database='heating')
        except Exception as e:
            print('Cannot write data to influxdb: %s' % (e))

        time.sleep(args.time)


if __name__ == '__main__':
    main()
