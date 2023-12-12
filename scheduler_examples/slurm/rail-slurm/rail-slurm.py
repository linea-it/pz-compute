#!/usr/bin/env python3
from os import execvp, sched_getaffinity, sched_setaffinity
from sys import argv, stderr

THREAD_SIBLINGS_LIST = \
        '/sys/devices/system/cpu/cpu%d/topology/thread_siblings_list'

OOM_ADJUST = '/proc/self/oom_score_adj'

def increase_oom_score():
    with open(OOM_ADJUST) as f:
        score = int(f.read())

    score = min(1000, score + 500)

    with open(OOM_ADJUST, 'w') as f:
        print('%d' % (score), file=f)

def bind(my_id):
    curr_mask = list(sorted(sched_getaffinity(0)))
    my_hart = curr_mask[my_id % len(curr_mask)]

    with open(THREAD_SIBLINGS_LIST % my_hart) as f:
        harts = [int(x) for x in f.read().split(',')]

    sched_setaffinity(0, harts)
    print(sched_getaffinity(0), flush=True)

def main():
    try:
        my_id = int(argv[1])
    except (IndexError, ValueError):
        print('Usage: %s <cpu_id> <prog> [<args>...]' % argv[0], file=stderr, flush=True)
        raise SystemExit(1)

    bind(my_id)
    increase_oom_score()
    execvp(argv[2], argv[2:])

if __name__ == '__main__': main()
