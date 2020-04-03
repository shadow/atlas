#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
import csv
import re
import os
import json
log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=False)


def fail_hard(*a):
    log.error(*a)
    exit(1)


def expand_path(path, user=True, vars=True, norm=True, abs=True):
    ''' Optionally expand path using the various os.path functions.
    I could explain each of these, or I could just point to
    https://docs.python.org/3.4/library/os.path.html (fix for your version of
    python as necessary) '''
    if user:
        path = os.path.expanduser(path)
    if vars:
        path = os.path.expandvars(path)
    if norm:
        path = os.path.normpath(path)
    if abs:
        path = os.path.abspath(path)
    return path


def find_files(d, ext=None):
    ''' Recursively find all files in the specified dir, optionally limited
    to files with the specified extension '''
    files = set()
    for root, subdirs, subfiles in os.walk(d):
        for fname in subfiles:
            fname = os.path.join(root, fname)
            if not ext:
                files.add(fname)
            else:
                fbase, fext = os.path.splitext(fname)
                if fext == ext:
                    files.add(fname)
    return files


def _trim_global_index_data(args, data):
    best_upload = None
    best_download = None
    country_name = None
    country_id = None
    # The data coming is is essentially two lists: fixed and mobile.
    # Each list has dictionaries of monthly summaries.
    # Find the highest upload and download rates and return them as the
    # up/download rates for the country.
    # Country ID is an integer. Not sure what it maps to yet. It would be nice
    # if it was an ID MaxMind understood, but I'm not getting my hopes up.
    for connection_type in ['fixed', 'mobile']:
        data_list = data[connection_type]
        for item in data_list:
            if best_upload is None:
                best_upload = float(item['upload_mbps'])
            elif float(item['upload_mbps']) > best_upload:
                best_upload = float(item['upload_mbps'])
            if best_download is None:
                best_download = float(item['download_mbps'])
            elif float(item['download_mbps']) > best_download:
                best_download = float(item['download_mbps'])
            if country_name is None:
                country_name = item['country']['country_name']
            if country_id is None:
                country_id = item['country']['country_id']
    return {'up_mbits': best_upload,
            'down_mbits': best_download,
            'country_name': country_name,
            'country_id': country_id, }


def load_global_index(args, gicc):
    directory = os.path.join(args.dir, 'global-index')
    if not os.path.exists(directory) and not os.path.isdir(directory):
        log.warn('Could not find global-index data')
        return {}
    data = {}
    log.notice('Loading global-index data from', directory)
    reg = r'^ *var data = ({.+});$'
    fnames = find_files(directory)
    for fname in fnames:
        fbase, _ = os.path.splitext(fname)
        fbase = os.path.basename(fbase)
        with open(fname, 'rt') as fd:
            for line in fd:
                match = re.search(reg, line)
                if not match:
                    continue
                log.debug('Found data for', fbase)
                if fbase in data:
                    log.warn('Already had data for', fbase, 'overwriting it')
                if fbase not in gicc:
                    log.warn(fbase, 'not found in global index country code '
                             'data so skipping this country')
                    continue
                cc = gicc[fbase]
                data[cc] = json.loads(match.group(1))
                data[cc] = _trim_global_index_data(args, data[cc])
    return data


def load_city_reports(args):
    assert os.path.exists(args.city_csv) and os.path.isfile(args.city_csv)
    log.notice('Loading city data from', args.city_csv)
    out_data = {}
    required_columns = ['Country', 'City', 'Upload', 'Download', 'geoname_id']
    with open(args.city_csv, 'rt') as fd:
        in_data = csv.DictReader(fd)
        for row in in_data:
            for col in required_columns:
                assert col in row
            if not row['geoname_id']:
                continue
            log.debug('Found data for', row['City'])
            out_data[row['geoname_id']] = {
                'country_name': row['Country'],
                'city_name': row['City'],
                'up_mbits': float(row['Upload']),
                'down_mbits': float(row['Download']),
                'city_id': int(row['geoname_id'])
            }
    return out_data


def load_global_index_country_codes(args):
    assert os.path.isfile(args.gicc)
    d = {}
    with open(args.gicc, 'rt') as fd:
        for line in fd:
            line = line.strip()
            name, code = line.split(' ')
            d[name] = code.upper()
    return d


def main(args):
    # mmdb = maxminddb.open_database(args.mmdb)
    gicc = load_global_index_country_codes(args)
    global_index = load_global_index(args, gicc)
    city_reports = load_city_reports(args)
    with open(args.output, 'wt') as fd:
        json.dump({'countries': global_index, 'cities': city_reports},
                  fd, indent=2)


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--dir', type=str, default='www.speedtest.net',
                        help='Path to speedtest.net wget dump directory')
    parser.add_argument('-o', '--output', type=str, default='speed-data.json')
    parser.add_argument('--gicc', type=str,
                        default='data/country-codes.txt',
                        help='Path to file storing country names and codes '
                        'as used in the speedtest.net/global-index webpages')
    parser.add_argument('--city-csv', type=str, default='data/maxminddb-cities.csv',
                        help='Path to semi-hand-montified Maxmind GeoLite2 '
                        'cities CSV file')
    args = parser.parse_args()
    # args.dir = expand_path(args.dir)
    # args.gicc = expand_path(args.gicc)
    if not os.path.exists(args.dir) and not os.path.isdir(args.dir):
        fail_hard(args.dir, 'doesn\'t exist')
    if not os.path.exists(args.gicc) and not os.path.isfile(args.gicc):
        fail_hard(args.gicc, 'doesn\'t exist')
    if not os.path.exists(args.city_csv) and not os.path.isfile(args.city_csv):
        fail_hard(args.city_csv, 'doesn\'t exist')
    exit(main(args))
