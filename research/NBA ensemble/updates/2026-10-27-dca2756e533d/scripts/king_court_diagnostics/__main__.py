import argparse
from .experiment import lock_code,run


def main():
    parser=argparse.ArgumentParser(description='Frozen-plan King of the Court distribution diagnostics; v1 unchanged')
    sub=parser.add_subparsers(dest='command',required=True)
    lock=sub.add_parser('lock-code');lock.add_argument('--output',required=True)
    compare=sub.add_parser('compare')
    compare.add_argument('--history',required=True)
    compare.add_argument('--code-lock',required=True)
    compare.add_argument('--event-audit',required=True)
    compare.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='lock-code':
        lock_code(args.output)
    else:
        result=run(args.history,args.code_lock,args.output,args.event_audit)
        print(result['overall_predictive_verdict'])


if __name__=='__main__':
    main()
