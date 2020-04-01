#!/usr/bin/env python3
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from lib.pastlylogger import PastlyLogger
from lib.periodicevent import PeriodicEvent
from lib.atlasclient03 import AtlasClient
from lib.resultsmanager03 import ResultsManager
from threading import Thread, Event
from queue import Empty, Queue
import time, os, json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
log = PastlyLogger(debug='/dev/stdout', overwrite=['debug'], log_threads=True)
#log = PastlyLogger(info='/dev/stdout', overwrite=['info'], log_threads=True)
#log = PastlyLogger(notice='/dev/stdout', overwrite=['notice'], log_threads=True)

def fail_hard(*s):
    if s: log.error(*s)
    exit(1)

kill_worker_threads = Event()
kill_stats_thread = Event()
kill_results_thread = Event()
start_time = time.time()
progress = None
progress_end = None
workers = []

class Worker:
    def __init__(self, args, log, results_manager, end_event, name):
        self._args = args
        self._log = log
        self._name = name
        self._rm = results_manager
        self._end_event = end_event
        self._input = Queue(maxsize=1)
        self._thread = Thread(target=self._enter)
        self._thread.name = self._name
        self._thread.start()

    def wait(self):
        assert self._thread != None
        self._thread.join()

    def give(self, item):
        self._input.put(item)

    @property
    def name(self): return self._name
    @property
    def is_ready(self): return not self._input.full()

    def _enter(self):
        log = self._log
        log('Starting Worker', self._name)
        atlas_client = AtlasClient(self._args, self._log, self._rm)
        while not self._input.empty() or not self._end_event.is_set():
            item = None
            try: item = self._input.get(timeout=0.5)
            except Empty: continue
            if item:
                atlas_client.do(item)
        log('Ending Worker', self._name)

class InMeasurement:
    def __init__(self, target_ip, probe_ids):
        self._target = target_ip
        self._probes = [int(p) for p in probe_ids]
    @property
    def target(self): return self._target
    @property
    def probes(self): return self._probes

    def __str__(self): return '{} <-- ({} probes)'.format(self.target, len(self.probes))


def read_in_measurements(args):
    m = []
    with open(args.measurement_list, 'rt') as fd:
        for line in fd:
            words = line.split()
            ip, prbs = words[0], words[1:]
            m.append(InMeasurement(ip, prbs))
    return m


def get_next_worker_thread(workers):
    while True:
        for w in workers:
            if w.is_ready:
                return w
        time.sleep(0.1)


def remaining_time(current_item, total_items, current_runtime):
    if current_item < 1:
        VERY_BIG_NUMBER = 60*60*24*365*10
        return VERY_BIG_NUMBER
    rem = ((current_runtime * total_items) / current_item) - current_runtime
    return rem


def seconds_to_duration(secs):
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    d, h, m, s = int(d), int(h), int(m), int(round(s,0))
    if d > 0: return '{}d{}h{}m{}s'.format(d,h,m,s)
    elif h > 0: return '{}h{}m{}s'.format(h,m,s)
    elif m > 0: return '{}m{}s'.format(m,s)
    else: return '{}s'.format(s)


def log_stats():
    now = time.time()
    dur = seconds_to_duration(now - start_time)
    rem = seconds_to_duration(remaining_time(progress, progress_end, now - start_time))
    log.notice('We\'ve been running for', dur, 'have handled',
            '{}/{}'.format(progress, progress_end), 'measurements, and expect to be done in', rem)


def probably_can_create_measurement(args):
    now = time.time()
    if now - 10 < probably_can_create_measurement.last_check:
        log.debug('Returning cached answer',
                  probably_can_create_measurement.last_answer)
        return probably_can_create_measurement.last_answer
    log.debug('Checking again if we can create measurements')
    probably_can_create_measurement.last_check = now
    atlas_url = 'https://atlas.ripe.net/api/v2/credits/'
    req = Request(atlas_url)
    req.add_header('Authorization', 'Key {}'.format(args.api))
    try: resp = urlopen(req)
    except HTTPError as e:
        log.warn('Couldn\'t fetch credit information. Assuming (probably '
                'incorrectly) that we can create more measurements')
        probably_can_create_measurement.last_answer = True
        return True
    j = json.loads(resp.read().decode('utf-8'))
    previous_results = j['past_day_measurement_results']
    previous_spent = j['past_day_credits_spent']
    log.debug('Got', previous_results, 'previous results and', previous_spent, 'previous spent')
    if previous_results > args.results_per_day:
        log.info('Previous day had',previous_results,'results. Wait till '
                'that goes down.')
        probably_can_create_measurement.last_answer = False
        return False
    if previous_spent > args.spend_per_day:
        log.info('Previous day had', previous_spent, 'credits spent. Wait '
                 'till that goes down.')
        probably_can_create_measurement.last_answer = False
        return False
    probably_can_create_measurement.last_answer = True
    return True
probably_can_create_measurement.last_check = 0
probably_can_create_measurement.last_answer = None


def main(args):
    global workers
    global progress
    global progress_end
    in_measurements = read_in_measurements(args)
    stats_thread = PeriodicEvent(
        log_stats, _run_interval=args.stats_interval,
        _end_event=kill_stats_thread, _thread_name='stats')
    results_manager = ResultsManager(args, log, kill_results_thread)
    workers = [ Worker(args, log, results_manager, kill_worker_threads, 'worker-{}'.format(i))
               for i in range(0, args.threads) ]
    progress = 0
    progress_end = len(in_measurements)
    for in_msm in in_measurements:
        if results_manager.have_inmsm(in_msm):
            log.debug('Already have', in_msm)
            progress_end -= 1
            continue
        while not probably_can_create_measurement(args):
            time.sleep(15*60)
        worker = get_next_worker_thread(workers)
        log.debug('Giving', worker.name, in_msm)
        worker.give(in_msm)
        progress += 1
        time.sleep(60)

if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--measurement-list', type=str, default='cache/all-pairs.txt',
        help='File with list of all-pairs ping measurements from 02-pick-best-by-city.py')
    parser.add_argument(
        '--threads', type=int, default=1,
        help='Number of threads/measurements to do at once')
    parser.add_argument(
        '--msm-attempts', type=int, default=3,
        help='Number of times to attempt to create a measurement')
    parser.add_argument('--api', type=str, required=True)
    parser.add_argument(
        '--results-per-day', type=int, default=95000,
        help='Maximum results RIPE will let you get per day')
    parser.add_argument(
        '--spend-per-day', type=int, default=990000,
        help='Maximum results RIPE will let you get per day')
    parser.add_argument('--all-pairs-measurements', type=str, default='cache/all-pairs-measurements.txt',
        help='Place to cache list of measurements we\'ve made')
    parser.add_argument(
        '--stats-interval', type=float, default=300, help='Log progress stats '
        'every this many seconds')
    args = parser.parse_args()
    for fname in [args.measurement_list]:
        if not os.path.isfile(fname): fail_hard(fname, 'must exist')
    if len(args.api) != 36:
        fail_hard(args.api, 'doesn\'t look like an API key')
    try: main(args)
    except KeyboardInterrupt: pass
    finally:
        kill_worker_threads.set()
        for worker in workers:
            worker.wait()
        kill_results_thread.set()
        kill_stats_thread.set()


