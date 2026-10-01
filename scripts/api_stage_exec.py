"""Linux exec wrapper: terminate the stage if its API parent dies."""
import ctypes
import os
import signal
import sys

parent = os.getppid()
if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0):
    raise OSError(ctypes.get_errno(), 'PR_SET_PDEATHSIG failed')
if parent == 1 or os.getppid() != parent:
    raise SystemExit('API parent disappeared')
os.execvpe(sys.argv[1], sys.argv[1:], os.environ)
