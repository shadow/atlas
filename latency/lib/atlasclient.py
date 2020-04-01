from datetime import datetime
import time
from ripe.atlas.cousteau import (
        AtlasSource,
        AtlasStream,
        AtlasCreateRequest,
        AtlasLatestRequest,
#        Measurement,
        Ping
)
import urllib.request
from urllib.error import HTTPError, URLError
import json


class AtlasClient:
    def __init__(self, args, log, results_manager):
        self._args = args
        self._log = log
        self._results_manager = results_manager

    def _create_measurement_impl(self, target_probe):
        args = self._args
        log = self._log
        probe = target_probe
        if 'address_v4' not in probe:
            log.error('probe has no ipv4 addr')
            return None
        target_id = probe['id']
        target_ip = probe['address_v4']
        log.notice('Creating measurement to probe', target_id, target_ip)
        desc = '{} {} to {}'.format(args.test_name_prefix, args.src_probe, target_id)
        ping = Ping(af=4, target=target_ip, description=desc)
        source = AtlasSource(type='probes', value='{}'.format(args.src_probe),
                             requested=1)
        req = AtlasCreateRequest(
            start_time=datetime.utcnow(),
            key=args.api,
            measurements=[ping],
            sources=[source],
            is_oneoff=True
        )
        is_success, resp = req.create()
        if not is_success:
            log.warn('Error creating measurement:', str(resp))
            return None
        else:
            msm_id = resp['measurements'][0]
            return msm_id
        log(is_success, resp)

    def _get_measurement_status(self, msm_id):
        assert msm_id
        req = AtlasLatestRequest(msm_id=msm_id)
        is_success, results = req.create()
        if not is_success:
            self._log.warn('Fetching status of', msm_id, 'was not successful.',
                           results)
            return None
        return results

    def do(self, item):
        rm = self._results_manager
        log = self._log
        had_to_create_msm = False
        probe = item['probe']
        if 'id' not in probe:
            log.error('probe without ID???')
            return None
        if 'address_v4' not in probe:
            log.error('probe without ipv4 address???')
            return None
        if not rm.have_measurement_for_probe(probe['id']):
            log('No measurement for probe', probe['id'], 'yet')
            msm_id = self._create_measurement(probe)
            had_to_create_msm = True
        if not rm.have_measurement_for_probe(probe['id']):
            log.warn('Unable to make measurement to probe', probe['id'])
            return
        msm_id = int(rm.get_measurement_for_probe(probe['id']))
        log.info('Have msm', msm_id, 'for probe', probe['id'])
        if not rm.have_result_for_probe(probe['id']):
            log.debug('Fetching result for msm', msm_id)
            self._wait_for_result(probe, msm_id)
        if not rm.have_result_for_probe(probe['id']):
            log.warn('Unable to fetch result for probe', probe['id'])
            return
        log.notice('Have result for msm', msm_id)
        if had_to_create_msm:
            self._wait_for_measurement_to_complete(msm_id)

    def _create_measurement(self, probe):
        self._log.debug('Called with probe', probe['id'])
        args = self._args
        log = self._log
        prb_id = probe['id']
        for _ in range(0, self._args.msm_attempts):
            msm_id = self._create_measurement_impl(probe)
            if not msm_id:
                time.sleep(60)
                continue
            self._results_manager.recv_measurement(prb_id, msm_id)
            return msm_id
        return None

    def _wait_for_result(self, probe, msm_id):
        args = self._args
        log = self._log
        prb_id = probe['id']
        result = None
        timeout = time.time() + args.msm_result_timeout
        while time.time() < timeout:
            result = self._get_measurement_status(msm_id)
            if result: break
            log.debug('Waiting for result for msm', msm_id, '...')
            time.sleep(10)
        if not result:
            log.warn('Didn\'t get a result')
        else:
            log.debug('Got result for msm', msm_id)
            self._results_manager.recv_result(prb_id, msm_id, result)
        return result

    def _wait_for_measurement_to_complete(self, msm_id):
        log = self._log
        atlas_url = 'https://atlas.ripe.net/api/v2/measurements/{}/'.format(msm_id)
        while True:
            try: req = urllib.request.urlopen(atlas_url)
            except HTTPError:
                log.warn('Got an HTTP error trying to fetch msm', msm_id,
                         'so we aren\'t going to wait for it to finish')
                break
            except URLError as e:
                log.warn(e, 'but will try again to wait until msm is stopped')
                time.sleep(10)
            else:
                j = json.loads(req.read().decode('utf-8'))
                if j['stop_time']:
                    log.info('msm', msm_id, 'is considered done')
                    break
            log.debug('Still waiting on msm', msm_id, 'to be done ...')
            time.sleep(30)
        return


