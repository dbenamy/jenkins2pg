from datetime import datetime
import json
import logging
from os import environ
import re

import psycopg2
import requests


log = logging.getLogger()


def main():
    logging.basicConfig()
    jenkins_url = environ['JENKINS_URL']
    conn = psycopg2.connect(environ['POSTGRES_DSN'])
    skip = set(environ['SKIP_JOBS'].split(','))
    errors = False
    for job in get_jobs(jenkins_url):
        if job in skip:
            print "Skipping %r" % job
            continue
        print "Downloading info for last 100 builds of %r" % job
        try:
            for build in get_builds(jenkins_url, job):
                save_build(conn, job, build)
        except Exception:
            log.exception("Error saving builds for %r", job)
            errors = True
    return errors


def get_jobs(jenkins_url):
    url = '%s/api/json' % jenkins_url
    # decode/encode to skip invalid chars
    resp = requests.get(url).text
    resp = json.loads(resp)
    if 'jobs' not in resp:
        print "Error:\n" + json.dumps(resp, sort_keys=True, indent=4)
        raise Exception
    return [job['name'] for job in resp['jobs']]


def get_builds(jenkins_url, job):
    url = '%s/job/%s/api/json?depth=1' % (jenkins_url, job)
    # decode/encode to skip invalid chars
    resp = requests.get(url).text
    resp = json.loads(resp)
    if 'builds' not in resp:
        print "Error:\n" + json.dumps(resp, sort_keys=True, indent=4)
        raise Exception
    builds = []
    for build in resp['builds']:
        if not build['result']:
            # it's in progress
            continue
        builds.append({
            'id': int(build['id']),
            'timestamp': datetime.utcfromtimestamp(float(build['timestamp']) / 1000),  # ms to sec
            'duration': float(build['duration']) / 1000,  # ms to sec
            'result': build['result'],
            'triggers': set([c['shortDescription'] for a in build['actions'] for c in a.get('causes', [])]),
        })
    return builds


def save_build(conn, job, build):
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO builds (job, jenkins_id, timestamp_utc, duration, result)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
        ''', (job, build['id'], build['timestamp'], build['duration'], build['result'])
    )
    id = cur.fetchone()
    if not id:
        # this record already existed in the db
        return
    conn.commit()
    for t in build['triggers']:
        try:
            cur.execute('''
                INSERT INTO build_triggers (build_id, trigger)
                VALUES (%s, %s)
                ''', (id, t)
            )
            conn.commit()
        except psycopg2.IntegrityError as error:
            dupe_trigger_msg = ('duplicate key value violates unique '
                                'constraint "unique_triggers_idx"')
            if dupe_trigger_msg not in error.message:
                raise
            conn.rollback()


if __name__ == '__main__':
    exit(main())
