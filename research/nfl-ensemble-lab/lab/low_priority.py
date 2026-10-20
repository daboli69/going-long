"""Run a lab Python command at idle priority, leaving two logical cores free."""
import os
import subprocess
import sys
import psutil


def main():
    if len(sys.argv)<3 or sys.argv[1]!="-m" or not (sys.argv[2].startswith("lab.") or sys.argv[2]=="streamlit"):
        raise SystemExit("Usage: python -m lab.low_priority -m lab.<module> [arguments]")
    n=max(1,psutil.cpu_count()-2)
    p=psutil.Process();p.nice(psutil.IDLE_PRIORITY_CLASS);p.cpu_affinity(list(range(n)))
    os.environ.update(OMP_NUM_THREADS=str(n),MKL_NUM_THREADS=str(n),OPENBLAS_NUM_THREADS=str(n))
    return subprocess.call([sys.executable]+sys.argv[1:])


if __name__=="__main__":
    raise SystemExit(main())
