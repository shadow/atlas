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
import random


class AtlasClient:
    def __init__(self, args, log, results_manager):
        self._log = log
        self._args = args
        self._rm = results_manager

    def _create_measurement_impl(self, inmsm):
        args = self._args
        log = self._log
        target_ip = inmsm.target
        probes = [str(p) for p in inmsm.probes]
        desc = '[real02] all-pairs ping {} (nonce={})'.format(target_ip, random.randint(0,1000000000))
        log(desc)
        ping = Ping(af=4, target=target_ip, description=desc)
        source = AtlasSource(
            type='probes', requested=len(probes),
            value='{}'.format(','.join(probes)))
        req = AtlasCreateRequest(
            start_time=datetime.utcnow(),
            key=args.api,
            measurements=[ping],
            sources=[source],
            is_oneoff=True
        )
        success, resp = req.create()
        if not success:
            log.warn('Error creating measurement:', str(resp))
            return None
        msm_id = resp['measurements'][0]
        return msm_id


    def _create_measurement(self, inmsm):
        args = self._args
        log = self._log
        for _ in range(0, args.msm_attempts):
            msm_id = self._create_measurement_impl(inmsm)
            if not msm_id:
                time.sleep(60)
                continue
            return msm_id

    def _wait_for_msm(self, msm_id):
        log = self._log
        atlas_url = 'https://atlas.ripe.net/api/v2/measurements/{}/'.format(msm_id)
        while True:
            try: req = urllib.request.urlopen(atlas_url)
            except HTTPError as e:
                log.warn(e, 'Got from msm', msm_id, 'but will keep waiting')
                time.sleep(10)
            except URLError as e:
                log.warn(e, 'Got from msm', msm_id, 'but will keep waiting')
                time.sleep(10)
            else:
                j = json.loads(req.read().decode('utf-8'))
                if j['stop_time']:
                    log.info('msm', msm_id, 'is considered done')
                    return
            log.debug('Still waiting on msm', msm_id, 'to be done ...')
            time.sleep(30)


    def do(self, inmsm):
        log = self._log
        rm = self._rm
        log.debug('Got', inmsm)
        msm_id = self._create_measurement(inmsm)
        if msm_id is not None:
            rm.recv({'msm_id': int(msm_id), 'inmsm': inmsm})
            self._wait_for_msm(msm_id)

