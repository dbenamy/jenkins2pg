from datetime import datetime
from os import environ
import re

import psycopg2
import requests


def main():
    jenkins_url = environ['JENKINS_URL']
    conn = psycopg2.connect("dbname=postgres")
    for b in get_builds(jenkins_url, 'dogweb-ci'):
        upsert(conn, 'dogweb-ci', b)
    for b in get_builds(jenkins_url, 'build-dogweb-staging'):
        upsert(conn, 'build-dogweb-staging', b)
    for b in get_builds(jenkins_url, 'deploy-dogweb-staging'):
        upsert(conn, 'deploy-dogweb-staging', b)


def get_builds(jenkins_url, job):
    url = '%s/job/%s/api/json?depth=1&tree=allBuilds' % (jenkins_url, job)
    resp = requests.get(url).json()
    builds = []
    for build in resp['builds']:
        builds.append({
            'id': int(build['id']),
            'timestamp': datetime.utcfromtimestamp(float(build['timestamp']) / 1000),  # ms to sec
            'duration': float(build['duration']) / 1000,  # ms to sec
            'result': build['result'],
            'triggers': set([c['shortDescription'] for a in build['actions'] for c in a.get('causes', [])]),
        })
    return builds


def upsert(conn, job, build):
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
    main()
