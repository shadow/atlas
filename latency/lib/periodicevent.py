import time
from threading import Thread, Event


class PeriodicEvent():
    def __init__(self, func, *args, _run_interval=60.0, _end_event=None,
            _log_func=print, _thread_name=None, _resolution=0.1,
            _run_at_end=True, **kwargs):
        self._func = func
        self._args, self._kwargs = args, kwargs

        self._run_interval = _run_interval
        self._end_event = _end_event
        self._log = _log_func
        self._resolution = _resolution
        self._run_at_end = _run_at_end

        self._last_run = time.time()
        self._thread = Thread(target=self._enter)
        if _thread_name:
            self._thread.name = _thread_name
        self._name = self._thread.name

        self._log('Starting PeriodicEvent', self._name, 'that runs roughly every',
                self._run_interval,'seconds')
        if not self._end_event:
            self._log('Warning: No _end_event so this thread will never die')
        self._thread.start()

    def _runit(self):
        self._func(*self._args, **self._kwargs)

    def _enter(self):
        while not self._end_event or not self._end_event.is_set():
            now = time.time()
            if self._last_run + self._run_interval <= now:
                self._runit()
                self._last_run = now
            else: time.sleep(self._resolution)
        if self._run_at_end: self._runit()
        self._log('Ending PeriodicEvent', self._name)

