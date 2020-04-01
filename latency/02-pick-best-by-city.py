#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
from lib.probelist import ProbeList
import maxminddb
import os
log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=True)
#log = PastlyLogger(info='/dev/stdout', overwrite=['info'], log_threads=True)
#log = PastlyLogger(notice='/dev/stdout', overwrite=['notice'], log_threads=True)
def fail_hard(*s):
    if s: log.error(*s)
    exit(1)


def main(args):
    mmdb = maxminddb.open_database(args.mmdb)
    probe_list = ProbeList(args, log, mmdb)
    probe_list.add_reachability_info()
    probe_list.trim_unreachable()
    probe_list.group_probes_by_city()
    probe_list.keep_only_best()
    probe_list.assert_all_probes_have_city()
    probe_list.generate_all_pairs()


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--probe-list', type=str, default='cache/all-probes.json',
        help='File in which we have a list of all current RIPE probes')
    parser.add_argument(
        '--probe-list-age', type=float, default=1000000,
        help='Max age in hours of the probe list before redownloading it')
    parser.add_argument(
        '--measurements-file', type=str, default='cache/reachability-measurements.json',
        help='File with reachability measurements from 01-test-reachability.py')
    parser.add_argument(
        '--mmdb', type=str, default='data/GeoLite2-City.mmdb', help='Path to '
        'MaxMind City DB')
    parser.add_argument(
        '--out-selected-probes', type=str, default='data/selected-probes.json',
        help='File to store the best probes for future scripts')
    parser.add_argument(
        '--out-all-pairs-list', type=str, default='cache/all-pairs.txt',
        help='File to store the necessary all-pairs ping measurement info '
        'for 03-*.py to use')
    parser.add_argument(
        '--max-probes-per-measurement', type=int, default=950,
        help='Max number of source probes that can be used in a measurement')
    args = parser.parse_args()
    for fname in [args.measurements_file, args.mmdb, args.probe_list]:
        if not os.path.isfile(fname): fail_hard(fname, 'must exist as a file')
    exit(main(args))
