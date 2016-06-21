from datetime import datetime, timedelta
import math
from os import environ

import psycopg2
import psycopg2.extras


def main():
    conn = psycopg2.connect("dbname=postgres")
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('select * from builds where job = %s order by timestamp_utc asc', ('dogweb-ci',))
    cis = cur.fetchall()
    cur.execute('select * from builds where job = %s order by timestamp_utc asc', ('build-dogweb-staging',))
    builds = cur.fetchall()
    cur.execute('select * from builds where job = %s order by timestamp_utc asc', ('deploy-dogweb-staging',))
    deploys = cur.fetchall()
    # for d in data:
    #     print d
    # data = filter(lambda d: len(d['triggers']) == 1 and d['triggers'][0].startswith('Started by GitHub push'), data)
    # for d in data:
        # print d

    # print_tree(make_tree(ci, builds, deploys))

    # for each push (dogweb-ci triggered by push)
    #     how long did it take for that code to get onto staging?
    #     ie what was the next builds that succeeded and what was the next deploys that succeeded

    iteration_times = []
    for ci in cis:
        # print dict(ci)
        if ci['result'] != 'SUCCESS':
            continue
        ci_end = ci['timestamp_utc'] + timedelta(seconds=ci['duration'])#, milliseconds=ci['duration'] / 1000 % 1000)
        bld = first_success_from(builds, ci_end)
        if not bld:
            print "Didn't find any successful builds after ci %r." % ci['id']
            continue
        bld_end = bld['timestamp_utc'] + timedelta(seconds=bld['duration'])#, milliseconds=ci['duration'] / 1000 % 1000)
        deploy = first_success_from(deploys, bld_end)
        if not deploy:
            print "Didn't find any successful deploys after build %r." % bld['id']
            continue
        deploy_end = deploy['timestamp_utc'] + timedelta(seconds=deploy['duration'])#, milliseconds=ci['duration'] / 1000 % 1000)
        total = deploy_end - ci['timestamp_utc']
        iteration_times.append(total.total_seconds())
        print "dogweb-ci %s at %sZ took %s to get onto staging." % (
            ci['jenkins_id'], ci['timestamp_utc'],
            pretty_elapsed(total.total_seconds()))

    print '\n-----------------------------\n'

    iteration_times.sort()
    print "%d builds counted" % len(iteration_times)
    print "Earliest: %s" % cis[0]['timestamp_utc']
    print "Most recent: %s" % cis[-1]['timestamp_utc']
    print "Median: %s" % pretty_elapsed(percentile(iteration_times,  0.5))
    print "p95: %s" % pretty_elapsed(percentile(iteration_times, 0.95))
    print "p99: %s" % pretty_elapsed(percentile(iteration_times, 0.99))


def first_success_from(sorted_builds, earliest):
    for b in sorted_builds:
        if b['timestamp_utc'] >= earliest and b['result'] == 'SUCCESS':
            return b


def pretty_elapsed(secs):
    secs = int(secs)  # TODO round
    mins = secs / 60
    secs %= 60
    hrs = mins / 60
    mins %= 60
    res = '%02ds' % secs
    if mins or hrs:
        res = '%02dm' % mins + res
    if hrs:
        res = '%dh' % hrs + res
    return res


def percentile(N, percent, key=lambda x:x):
    """
    Find the percentile of a list of values.

    http://code.activestate.com/recipes/511478/ (r1)

    @parameter N - is a list of values. Note N MUST BE already sorted.
    @parameter percent - a float value from 0.0 to 1.0.
    @parameter key - optional key function to compute value from each element of N.

    @return - the percentile of the values
    """
    if not N:
        return None
    k = (len(N)-1) * percent
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return key(N[int(k)])
    d0 = key(N[int(f)]) * (c-k)
    d1 = key(N[int(c)]) * (k-f)
    return d0+d1


# def make_tree(ci, build, deploy):
#     ci_by_id = by_id(ci)
#     build_by_id = by_id(build)
#     deploy_by_id = by_id(deploy)

#     link(build_by_id, ci_by_id, 'dogweb-ci')
#     link(deploy_by_id, build_by_id, 'build-dogweb-staging')

#     return ci_by_id.values()


# def link(children, parents, parent_proj):
#     trig_regex = r'Started by upstream project "%s" build number ([0-9,]+)' % parent_proj
#     for child in children.values():
#         for t in child['triggers']:
#             m = re.match(trig_regex, t)
#             if m:
#                 tid = int(m.groups()[0].replace(',', ''))
#                 if tid in parents:
#                     # Sometimes it's set to None.
#                     parents[tid]['triggered'] = (parents[tid].get('triggered') or []).append(child)
#                 else:
#                     print "Build %r was triggered by %r which isn't a known %s job." % (child['id'], tid, parent_proj)
#             else:
#                 print "Ignoring trigger %r on child %r" % (t, child['id'])


# def print_tree(lst, indent=0):
#     import pprint
#     pp = pprint.PrettyPrinter(indent=4)
#     pp.pprint(lst)
#     # for x in lst:
#     #     print ' ' * indent + x


# def by_id(lst):
#     res = {}
#     for x in lst:
#         res[x['id']] = x
#     return res


if __name__ == '__main__':
    main()
