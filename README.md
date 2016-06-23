# Setup

Go to https://<your-jenkins>/user/<you>/configure and get an api key.

```
export JENKINS_URL='https://<you>:<api-key>@<your-jenkins>' # don't include a trailing slash
export POSTGRES_DSN='dbname=postgres' # see psycopg2 connect() docs for details
pip install -r requirements.txt
psql < schema.sql
```

# Run

```
python jenkins2pg.py # this is safe to re-run
python iterationspeed.py
```
