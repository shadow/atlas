#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
from functools import lru_cache
from statistics import median
import maxminddb
import os
import csv
import json


log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=True)
#log = PastlyLogger(info='/dev/stdout', overwrite=['info'], log_threads=True)
#log = PastlyLogger(notice='/dev/stdout', overwrite=['notice'], log_threads=True)
mmdb = None


def fail_hard(*s):
    if s: log.error(*s)
    exit(1)


def load_results(args):
    log('loading results from', args.results)
    with open(args.results, 'rt') as fd:
        return json.load(fd)


@lru_cache(maxsize=4096)
def _get_cc_for_ip(ip_str):
    cc = None
    data = mmdb.get(ip_str)
    if data and 'country' in data:
        cc = data['country']['iso_code']
    return cc


@lru_cache(maxsize=4096)
def _get_city_name_for_ip(ip_str):
    name = None
    data = mmdb.get(ip_str)
    if data and 'city' in data and 'names' in data['city'] \
            and 'en' in data['city']['names']:
        name = data['city']['names']['en']
    return name


@lru_cache(maxsize=4096)
def _get_city_code_for_ip(ip_str):
    cc = None
    data = mmdb.get(ip_str)
    if data and 'city' in data:
        cc = data['city']['geoname_id']
    return cc

def _calc_avg_rtt(res):
    assert 'result' in res
    rtts = []
    for rtt in res['result']:
        if 'rtt' not in rtt: continue
        rtts.append(rtt['rtt'])
    if len(rtts) < 1: return -1
    return median(rtts)


def main(args):
    global mmdb
    mmdb = maxminddb.open_database(args.mmdb)
    results = load_results(args)
    counter = 0
    total_count = 0
    with open(args.output, 'wt') as fd:
        fieldnames = ['id', 'src', 'src_city', 'src_city_name', 'src_country',
                      'dst', 'dst_city', 'dst_city_name', 'dst_country',
                      'latency']
        writer = csv.DictWriter(fd, fieldnames=fieldnames)
        writer.writeheader()
        for msm_id in results:
            for result in results[msm_id]:
                total_count += 1
                rtt = _calc_avg_rtt(result)
                if rtt < 0: continue
                src_ip = result['from']
                dst_ip = result['dst_addr']
                writer.writerow({
                    'id': counter,
                    'src': src_ip,
                    'src_city': _get_city_code_for_ip(src_ip),
                    'src_city_name': _get_city_name_for_ip(src_ip),
                    'src_country': _get_cc_for_ip(src_ip),
                    'dst': dst_ip,
                    'dst_city': _get_city_code_for_ip(dst_ip),
                    'dst_city_name': _get_city_name_for_ip(dst_ip),
                    'dst_country': _get_cc_for_ip(dst_ip),
                    'latency': rtt/2
                })
                counter += 1
    log('Got {}/{} ({}%) good ping measurements written to'
        .format(counter, total_count, int(100*counter/total_count)), args.output)
    log('country', _get_cc_for_ip.cache_info())
    log('city', _get_city_code_for_ip.cache_info())



if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('--mmdb', type=str, help='Path to MaxMind DB',
                        default='data/GeoLite2-City.mmdb')
    parser.add_argument(
        '--results', type=str, default='cache/all-pairs-results.json',
        help='Output from 04-fetch-all-pairs-results.py')
    parser.add_argument('--output', type=str, default='data/all-pairs.csv')
    args = parser.parse_args()
    for fname in [args.mmdb, args.results]:
        if not os.path.isfile(fname):
            fail_hard(fname, 'must exist')
    try: main(args)
    except KeyboardInterrupt: pass
