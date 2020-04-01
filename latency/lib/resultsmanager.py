import json
import os
from threading import RLock
import fcntl
import urllib
from ripe.atlas.cousteau import AtlasLatestRequest
import time

class ResultsManager:
    def __init__(self, args, log):
        self._args = args
        self._log = log
        self._measurements = {}
        self._lock = RLock()
        if os.path.isfile(args.measurements_file):
            with open(args.measurements_file, 'rt') as fd:
                log.info('Loading existing measurements from', args.measurements_file)
                ResultsManager.lock_fd(fd)
                try: self._measurements = json.load(fd)
                finally: ResultsManager.unlock_fd(fd)
        self._fetch_more_from_ripe()

    def __del__(self):
        args = self._args
        msms = self._measurements
        with self._lock:
            with open(args.measurements_file, 'wt') as fd:
                ResultsManager.lock_fd(fd)
                try: json.dump(msms, fd, indent=2)
                finally: ResultsManager.unlock_fd(fd)

    def _fetch_more_from_ripe(self):
        log = self._log
        measurements = []
        last_msm_id = -1
        log.debug('Fetching measurements after id', last_msm_id)
        url = 'https://atlas.ripe.net/api/v2/measurements/?page_size=500&description__startswith=%5Btest%5D%20reachability&mine=true'
        msm_resp = urllib.request.urlopen(url+'&id__gt='+str(last_msm_id))
        j = json.loads(msm_resp.read().decode('utf-8'))
        while len(j['results']):
            old_len = len(measurements)
            log.debug('found', len(j['results']), 'measurements')
            for measurement in j['results']:
                last_msm_id = measurement['id']
                prb_id = str(measurement['description'].split()[-1])
                #log.debug(prb_id,
                #          'yes' if self.have_measurement_for_probe(prb_id) else 'no', 'msm ...',
                #          'yes' if self.have_result_for_probe(prb_id) else 'no', 'result')
                if not self.have_measurement_for_probe(prb_id):
                    log.debug('Adding msm', last_msm_id, 'for probe', prb_id)
                    self.recv_measurement(prb_id, last_msm_id)
                msm_id = self.get_measurement_for_probe(prb_id)
                assert msm_id
                if not self.have_result_for_probe(prb_id):
                    req = AtlasLatestRequest(msm_id=last_msm_id)
                    is_success, results = req.create()
                    log.debug('Requesting results for msm', msm_id, 'probe', prb_id)
                    if not is_success: continue
                    self.recv_result(prb_id, msm_id, results)
                    time.sleep(1)
                measurements.append(measurement)
            new_len = len(measurements)
            msm_resp = urllib.request.urlopen(url+'&id__gt='+str(last_msm_id))
            j = json.loads(msm_resp.read().decode('utf-8'))


    @staticmethod
    def lock_fd(fd):
        fcntl.flock(fd, fcntl.LOCK_EX)

    @staticmethod
    def unlock_fd(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)

    def have_measurement_for_probe(self, prb_id):
        with self._lock:
            return str(prb_id) in self._measurements

    def have_result_for_probe(self, prb_id):
        with self._lock:
            return str(prb_id) in self._measurements and 'result' in self._measurements[str(prb_id)]

    def get_measurement_for_probe(self, prb_id):
        with self._lock:
            assert self.have_measurement_for_probe(prb_id)
            return self._measurements[str(prb_id)]['msm_id']

    def get_result_for_probe(self, prb_id):
        with self._lock:
            assert self.have_result_for_probe(prb_id)
            return self._measurements[str(prb_id)]['result']

    def recv_measurement(self, prb_id, msm_id):
        with self._lock:
            msms = self._measurements
            log = self._log
            args = self._args
            assert not self.have_measurement_for_probe(prb_id)
            msms[str(prb_id)] = {'msm_id': str(msm_id)}
            #with open(args.measurements_file, 'wt') as fd:
            #    ResultsManager.lock_fd(fd)
            #    try: json.dump(msms, fd, indent=2)
            #    finally: ResultsManager.unlock_fd(fd)

    def recv_result(self, prb_id, msm_id, result):
        with self._lock:
            msms = self._measurements
            log = self._log
            args = self._args
            assert self.have_measurement_for_probe(prb_id)
            assert str(msms[str(prb_id)]['msm_id']) == str(msm_id)
            msms[str(prb_id)]['result'] = result
            #with open(args.measurements_file, 'wt') as fd:
            #    ResultsManager.lock_fd(fd)
            #    try: json.dump(msms, fd, indent=2)
            #    finally: ResultsManager.unlock_fd(fd)

