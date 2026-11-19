"""Version 1 PostgreSQL evidence model; original payload bytes remain authoritative."""
OWNER='dragonhydra.postgresql/1'
DDL='''
CREATE SCHEMA __S__;
CREATE TABLE __S__.ownership(owner TEXT PRIMARY KEY,version INTEGER NOT NULL CHECK(version=1));
CREATE TABLE __S__.providers(id TEXT PRIMARY KEY,payload JSONB NOT NULL);
CREATE TABLE __S__.raw_evidence(hash TEXT PRIMARY KEY,original_json TEXT NOT NULL,content BYTEA,content_sha256 TEXT);
CREATE TABLE __S__.observations(
 id TEXT PRIMARY KEY,source TEXT NOT NULL REFERENCES __S__.providers(id),series TEXT NOT NULL,kind TEXT NOT NULL,origin TEXT NOT NULL,unit TEXT NOT NULL,
 observed_at TIMESTAMPTZ, collected_at TIMESTAMPTZ NOT NULL,event_date DATE,issue_at TIMESTAMPTZ,valid_at TIMESTAMPTZ,
 value NUMERIC,identity_key TEXT NOT NULL,raw_hash TEXT NOT NULL REFERENCES __S__.raw_evidence(hash),payload JSONB NOT NULL,payload_text TEXT NOT NULL,payload_sha256 TEXT NOT NULL);
CREATE INDEX observation_scope ON __S__.observations(source,series,unit,origin);
CREATE INDEX observation_identity ON __S__.observations(source,identity_key,series,origin);
CREATE INDEX observation_time ON __S__.observations(observed_at,collected_at);
CREATE INDEX observation_kind ON __S__.observations(kind,origin);
CREATE TABLE __S__.competitions(id TEXT PRIMARY KEY,provider_id TEXT NOT NULL REFERENCES __S__.providers(id),source_identity TEXT NOT NULL,name TEXT,UNIQUE(provider_id,source_identity));
CREATE TABLE __S__.seasons(id TEXT PRIMARY KEY,provider_id TEXT NOT NULL REFERENCES __S__.providers(id),label TEXT NOT NULL,UNIQUE(provider_id,label));
CREATE TABLE __S__.teams(id TEXT PRIMARY KEY,provider_id TEXT NOT NULL REFERENCES __S__.providers(id),source_identity TEXT NOT NULL,name TEXT,UNIQUE(provider_id,source_identity));
CREATE TABLE __S__.fixtures(id TEXT PRIMARY KEY,provider_id TEXT NOT NULL REFERENCES __S__.providers(id),provider_event_id TEXT NOT NULL,competition_id TEXT REFERENCES __S__.competitions(id),season_id TEXT REFERENCES __S__.seasons(id),home_team_id TEXT REFERENCES __S__.teams(id),away_team_id TEXT REFERENCES __S__.teams(id),event_date DATE,scheduled_at TIMESTAMPTZ,status TEXT,UNIQUE(provider_id,provider_event_id));
CREATE TABLE __S__.match_results(observation_id TEXT PRIMARY KEY REFERENCES __S__.observations(id),fixture_id TEXT REFERENCES __S__.fixtures(id),home_goals INTEGER,away_goals INTEGER,classification TEXT NOT NULL);
CREATE TABLE __S__.bookmakers(id TEXT PRIMARY KEY,provider_id TEXT NOT NULL REFERENCES __S__.providers(id),name TEXT NOT NULL,UNIQUE(provider_id,name));
CREATE TABLE __S__.odds_markets(id TEXT PRIMARY KEY,provider_id TEXT NOT NULL REFERENCES __S__.providers(id),name TEXT NOT NULL,UNIQUE(provider_id,name));
CREATE TABLE __S__.odds_quotes(observation_id TEXT PRIMARY KEY REFERENCES __S__.observations(id),fixture_id TEXT REFERENCES __S__.fixtures(id),bookmaker_id TEXT REFERENCES __S__.bookmakers(id),market_id TEXT REFERENCES __S__.odds_markets(id),outcome TEXT,decimal_odds NUMERIC NOT NULL CHECK(decimal_odds>1),quoted_at TIMESTAMPTZ,classification TEXT NOT NULL);
CREATE TABLE __S__.import_receipts(id TEXT PRIMARY KEY,payload JSONB NOT NULL,payload_text TEXT NOT NULL);
CREATE TABLE __S__.acquisition_tasks(id TEXT PRIMARY KEY,state TEXT NOT NULL,payload JSONB NOT NULL);
CREATE TABLE __S__.analysis_results(id TEXT PRIMARY KEY,payload JSONB NOT NULL);
CREATE TABLE __S__.provider_connections(id TEXT PRIMARY KEY,payload JSONB NOT NULL);
CREATE TABLE __S__.data_lineage(observation_id TEXT NOT NULL REFERENCES __S__.observations(id),snapshot_sha256 TEXT NOT NULL,original_id TEXT NOT NULL,payload_sha256 TEXT NOT NULL,PRIMARY KEY(observation_id,snapshot_sha256));
CREATE TABLE __S__.migration_history(id UUID PRIMARY KEY,at TIMESTAMPTZ NOT NULL,snapshot_sha256 TEXT UNIQUE NOT NULL,rows_read BIGINT NOT NULL,inserted BIGINT NOT NULL,duplicates BIGINT NOT NULL,identities_sha256 TEXT NOT NULL,status TEXT NOT NULL,payload JSONB NOT NULL);
CREATE TABLE __S__.workspace_evidence(snapshot_sha256 TEXT NOT NULL,table_name TEXT NOT NULL,row_number BIGINT NOT NULL,original_row JSONB NOT NULL,PRIMARY KEY(snapshot_sha256,table_name,row_number));
CREATE VIEW __S__.match_events AS SELECT id,source,origin,payload FROM __S__.observations WHERE payload->'metadata'->>'contract'='football.event/1';
CREATE VIEW __S__.player_statistics AS SELECT id,source,origin,payload FROM __S__.observations WHERE payload->'metadata'->>'contract'='football.player.statistic/1';
CREATE VIEW __S__.team_statistics AS SELECT id,source,origin,payload FROM __S__.observations WHERE payload->'metadata'->>'contract'='football.team.statistic/1';
CREATE FUNCTION __S__.immutable_observation() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'Original observations are immutable'; END$$;
CREATE TRIGGER immutable_original BEFORE UPDATE OR DELETE ON __S__.observations FOR EACH ROW EXECUTE FUNCTION __S__.immutable_observation();
'''
