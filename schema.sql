create table builds (
  id serial primary key,
  job text not null,
  jenkins_id int not null,
  duration int not null,
  timestamp_utc timestamp not null,
  result text not null
);
create unique index unique_builds_idx ON builds (job, jenkins_id);

create table build_triggers (
  build_id int not null references builds(id),
  trigger text not null
);
create unique index unique_triggers_idx ON build_triggers (build_id, trigger);
