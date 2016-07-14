"""Calculates stats on dev iteration speed.

Looks at the previous weeks builds and assumes a 3 job workflow (test, build,
deploy).
"""
from datetime import datetime, timedelta
import math
from os import environ

import psycopg2
import psycopg2.extras


def main():
    postgres_dsn = environ['POSTGRES_DSN']
    print "All builds:"
    stats(postgres_dsn, start_of_last_week())


def start_of_last_week():
    today = datetime.utcnow().date()
    dow = today.weekday() + 1 # shift the mapping so mon is 1 and sun 7
    sun = today - timedelta(days=dow)
    return sun - timedelta(days=7)


def stats(postgres_dsn, start):
    """Prints stats for the week starting at start.
    """
    end = start + timedelta(days=7)
    conn = psycopg2.connect(postgres_dsn)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    test_sql = ('select * from builds '
                'where job IN (%s, %s) and timestamp_utc >= %s and timestamp_utc < %s '
                'order by timestamp_utc asc')
    other_sql = ('select * from builds '
                 'where job = %s and timestamp_utc >= %s '
                 'order by timestamp_utc asc')
    cur.execute(test_sql, ('dogweb-ci', 'dogweb-to-staging', start, end))
    tests = cur.fetchall()
    cur.execute(other_sql, ('build-dogweb-staging', start))
    builds = cur.fetchall()
    cur.execute(other_sql, ('deploy-dogweb-staging', start))
    deploys = cur.fetchall()

    iteration_times = []
    for test in tests:
        if test['result'] != 'SUCCESS':
            continue
        ci_end = test['timestamp_utc'] + timedelta(seconds=test['duration'])
        bld = first_success_from(builds, ci_end)
        if not bld:
            print "Didn't find any successful builds after test %r." % test['id']
            continue
        bld_end = bld['timestamp_utc'] + timedelta(seconds=bld['duration'])
        deploy = first_success_from(deploys, bld_end)
        if not deploy:
            print "Didn't find any successful deploys after build %r." % bld['id']
            continue
        deploy_end = deploy['timestamp_utc'] + timedelta(seconds=deploy['duration'])
        total = deploy_end - test['timestamp_utc']
        iteration_times.append(total.total_seconds())
        print "%s %s at %sZ took %s to get onto staging." % (
            test['job'], test['jenkins_id'], test['timestamp_utc'],
            pretty_elapsed(total.total_seconds()))

    print '\n-----------------------------\n'

    print "%d test builds (%d iterations) from %s to %s" % (
        len(tests), len(iteration_times), start, end)
    iteration_times.sort()
    p50 = percentile(iteration_times,  0.5)
    p95 = percentile(iteration_times, 0.95)
    p99 = percentile(iteration_times, 0.99)
    print "Median: %s" % pretty_elapsed(p50)
    print "p95: %s" % pretty_elapsed(p95)
    print "p99: %s" % pretty_elapsed(p99)
    print "CSVs for plopping into a spreadsheet:"
    print "week of, test builds, iterations, median iteration speed, p95, p99"
    # The 0:0:secs format does the right thing when pasted into a duration col
    # in google docs.
    print "%s, %d, %d, 0:0:%d, 0:0:%d, 0:0:%d" % (
        start, len(tests), len(iteration_times), p50, p95, p99)


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


if __name__ == '__main__':
    main()
