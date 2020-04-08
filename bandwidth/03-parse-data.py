#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
import csv
import re
import os
import json
import glob
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
        log.warn('Could not find country data')
        return {}
    data = {}
    log.notice('Loading country data from', directory)
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


def sets_of_n(lst, n):
    out = []
    work = []
    for item in lst:
        work.append(item)
        if len(work) == n:
            out.append(work)
            work = []
    assert not len(work)
    return out


def rows_with_city(csv_dict, city_name):
    rows = []
    city_name = city_name.lower()
    for row in csv_dict:
        if row['city_name'].lower() == city_name:
            rows.append(row)
    return rows


def get_best_match(rows, city_name, country_name):
    assert len(rows)
    if len(rows) == 1:
        return rows[0]
    # if the city name has a comma in it, try treating the part after the comma
    # as a "subdivision" (state, in the US) name. There's two levels of
    # subdivisions in maxmind's db. This part tries subdiv level 1
    if ',' in city_name:
        log.debug(
            f'Trying to find best match for {city_name} from {len(rows)} '
            f'rows with subdiv level 1')
        city, subdiv = city_name.split(',', maxsplit=1)
        city = city.lower()
        subdiv = subdiv.strip().lower().replace('é', 'e')
        filtered = []
        for row in rows:
            if row['city_name'].lower() != city:
                continue
            if row['subdivision_1_name'].lower() == subdiv:
                filtered.append(row)
        if len(filtered) == 1:
            return filtered[0]
        if len(filtered) > 1:
            log.info(
                f'Still {len(filtered)} matches for "{city}" city in subdiv '
                f'"{subdiv}" in country {country_name}. Arbitrarily picking '
                'first of the following')
            for row in filtered:
                log.debug(dict(row))
            return filtered[0]
    # if no comma in city_name, try filtering on country name matches
    if ',' not in city_name:
        country = country_name.lower().replace('-', ' ')
        log.debug(
            f'There exists {len(rows)} matches for "{city_name}" city. '
            f'Trying to filter down with "{country}" country')
        filtered = []
        for row in rows:
            if row['country_name'].lower() == country:
                filtered.append(row)
        if len(filtered) == 1:
            return filtered[0]
        if len(filtered) > 1:
            log.info(
                f'More than one match for "{city_name}" city with "{country}" '
                f'country name. Arbitrarily picking the first item of the '
                f'following {len(filtered)}')
            for row in filtered:
                log.debug(dict(row))
            return filtered[0]
    return None


def try_alt_name(mmdb_csv, city):
    alt_name_map = {
        'Buraydah': 'Buraidah',
        'Yekaterinburg': 'Ekaterinburg',
        'Saint Petersburg': 'St Petersburg',
        'Nizhny Novgorod': 'Nizhniy Novgorod',
        'Al Khobar': 'Khobar',
        'Al Hofuf': 'Al Hufuf',
        'Taif': 'Ta\'if',
        'Shubra al Khaymah': 'Shubra',
        'Al Mahalla El Kubra': 'Al Mahallah al Kubra',
        'Saint Petersburg, Florida': 'St Petersburg',
        'Québec City, Québec': 'Québec',
        'Sha Tin District': 'Shatin',
        'Wan Chai District': 'Wanchai',
        # there are three "cities" in this district, this is one of them
        'Yau Tsim Mong District': 'Yau Ma Tei',
        # there are ~eight "cities" in this district, this is one of them
        'Central and Western District': 'Tai Hang',
        'Kowloon City District': 'Kowloon',
        # there are ~ten "cities" in this district, this is one of them
        'Southern District': 'Deep Water Bay',
        # there are ~nine "cities" in this district, this is one of them
        'Eastern District': 'Sai Wan Ho',
        'Las Palmas': 'Las Palmas de Gran Canaria',
    }
    if city in alt_name_map:
        return rows_with_city(mmdb_csv, alt_name_map[city])
    return []



def load_city_reports(args, gicc, mmdb_csv):
    directory = os.path.join(args.dir, 'reports-parsed')
    if not os.path.exists(directory) and not os.path.isdir(directory):
        log.warn('Could not find reports-parsed directory with city data')
        return {}
    assert os.path.exists(directory) and os.path.isdir(directory)
    log.notice('Loading city data from', directory)
    out_data = {}
    for fname in glob.iglob(f'{directory}/**', recursive=True):
        if not os.path.isfile(fname):
            continue
        country = os.path.splitext(os.path.basename(fname))[0]
        if country not in gicc:
            log.warn(country, 'not found in global index country code data '
                     'so skipping', fname)
            continue
        lines = iter([line.strip() for line in open(fname, 'rt')])
        for city, down, up in sets_of_n(lines, 3):
            rows = rows_with_city(mmdb_csv, city)
            # special case attempt for city names like 'Wichita, Kansas'
            if not len(rows) and ',' in city:
                city_ = city.split(',')[0]
                rows = rows_with_city(mmdb_csv, city_)
            # special case attempt for city names like 'Sham Shui Po District'
            if not len(rows) and city.endswith(' District'):
                city_ = city[:-1*len(' District')]
                rows = rows_with_city(mmdb_csv, city_)
            # special case for different spellings
            if not len(rows):
                rows = try_alt_name(mmdb_csv, city)
            # give up if after all that we still don't have any idea
            if not len(rows):
                log.warn(f'Did not find city "{city}" (country {country}) '
                         f'in GeoLite2 CSV DB. Ignoring it.')
                continue
            # we have 1 or more rows. if we have more than one, pick the best
            if len(rows) > 1:
                best_match = get_best_match(rows, city, country)
                if best_match is None:
                    log.warn(
                        f'{len(rows)} matches for "{city}" (country '
                        f'{country}) and couldn\'t pick best, so ignoring.')
                    for r in rows:
                        log(dict(r))
                    continue
                rows = [best_match]
            assert len(rows) == 1
            row = rows[0]
            out_data[row['geoname_id']] = {
                'country_name': country,
                'country_id': gicc[country],
                'city_name': row['city_name'],
                'up_mbits': up,
                'down_mbits': down,
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


def load_mmdb_csv(args):
    return [row for row in csv.DictReader(open(args.mmdb_csv, 'rt'))]


def main(args):
    gicc = load_global_index_country_codes(args)
    mmdb_csv = load_mmdb_csv(args)
    global_index = load_global_index(args, gicc)
    city_reports = load_city_reports(args, gicc, mmdb_csv)
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
    parser.add_argument('--mmdb-csv', type=str,
                        default='data/GeoLite2-City-Locations-en.csv',
                        help='Path to the GeoLite2 City database in CSV '
                        'format that you downloaded.')
    args = parser.parse_args()
    if not os.path.exists(args.gicc) and not os.path.isfile(args.gicc):
        fail_hard(args.gicc, 'doesn\'t exist')
    exit(main(args))
