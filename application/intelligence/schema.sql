-- Version 1: exclusively inside the ownership-marked intelligence database.
SET XACT_ABORT ON;
IF DB_NAME()<>N'DRAGONHYDRA_SCRAPP_INTELLIGENCE' THROW 51100,'Wrong application database',1;
IF NOT EXISTS(SELECT 1 FROM sys.extended_properties WHERE class=0 AND name=N'DragonhydraOwner' AND CONVERT(nvarchar(128),value)=N'scrapp-intelligence/mission-002') THROW 51101,'Ownership marker missing',1;
IF SCHEMA_ID(N'scrapp') IS NULL THROW 51102,'Provision scrapp schema first',1;
BEGIN TRANSACTION;
IF OBJECT_ID(N'scrapp.SchemaMigrations',N'U') IS NULL
CREATE TABLE scrapp.SchemaMigrations(version int PRIMARY KEY,applied_at_utc datetime2(6) NOT NULL DEFAULT SYSUTCDATETIME());
IF NOT EXISTS(SELECT 1 FROM scrapp.SchemaMigrations WHERE version=1)
BEGIN
CREATE TABLE scrapp.DataSources(source_id nvarchar(100) PRIMARY KEY,source_url nvarchar(2000) NOT NULL,category varchar(40) NOT NULL,enabled bit NOT NULL DEFAULT 0,refresh_seconds int NOT NULL DEFAULT 600 CHECK(refresh_seconds>=10),config_json nvarchar(max) NOT NULL DEFAULT N'{}' CHECK(ISJSON(config_json)=1));
CREATE TABLE scrapp.AcquisitionJobs(job_id varchar(64) PRIMARY KEY,source_id nvarchar(100) NOT NULL REFERENCES scrapp.DataSources(source_id),started_at_utc datetime2(6) NOT NULL,finished_at_utc datetime2(6),status varchar(24) NOT NULL,error_code nvarchar(120));
CREATE TABLE scrapp.FetchResults(fetch_id varchar(64) PRIMARY KEY,job_id varchar(64) REFERENCES scrapp.AcquisitionJobs(job_id),source_id nvarchar(100) NOT NULL REFERENCES scrapp.DataSources(source_id),received_at_utc datetime2(6) NOT NULL,http_status int,content_hash varchar(64) NOT NULL,byte_count bigint NOT NULL CHECK(byte_count>=0));
CREATE TABLE scrapp.RawObservations(observation_id varchar(64) PRIMARY KEY,source_id nvarchar(100) NOT NULL REFERENCES scrapp.DataSources(source_id),series_key nvarchar(160) NOT NULL,kind varchar(40) NOT NULL,origin varchar(16) NOT NULL CHECK(origin IN ('synthetic','imported','observed')),verification varchar(40) NOT NULL,received_at_utc datetime2(6) NOT NULL,observed_at_utc datetime2(6),published_at_utc datetime2(6),issue_at_utc datetime2(6),valid_at_utc datetime2(6),content_hash varchar(64) NOT NULL,raw_json nvarchar(max) NOT NULL CHECK(ISJSON(raw_json)=1),normalized_json nvarchar(max) NOT NULL CHECK(ISJSON(normalized_json)=1),engine_version varchar(64) NOT NULL);
CREATE INDEX IX_ObservationSeriesTime ON scrapp.RawObservations(source_id,series_key,received_at_utc DESC) INCLUDE(kind,origin,observed_at_utc);
CREATE INDEX IX_ObservationOriginTime ON scrapp.RawObservations(origin,received_at_utc DESC) INCLUDE(source_id,kind,series_key);
CREATE TABLE scrapp.NumericalObservations(observation_id varchar(64) PRIMARY KEY REFERENCES scrapp.RawObservations(observation_id),value decimal(28,10) NOT NULL,original_value nvarchar(100) NOT NULL,unit nvarchar(32) NOT NULL);
CREATE TABLE scrapp.PublicTextObservations(observation_id varchar(64) PRIMARY KEY REFERENCES scrapp.RawObservations(observation_id),text nvarchar(4000) NOT NULL,language varchar(12) NOT NULL DEFAULT 'unknown');
CREATE TABLE scrapp.SentimentResults(result_id varchar(64) PRIMARY KEY,observation_id varchar(64) NOT NULL REFERENCES scrapp.RawObservations(observation_id),label varchar(24) NOT NULL,strength decimal(8,6),interpretation_json nvarchar(max) NOT NULL CHECK(ISJSON(interpretation_json)=1),engine_version varchar(64) NOT NULL,interpreted_at_utc datetime2(6) NOT NULL);
CREATE TABLE scrapp.WeatherObservations(observation_id varchar(64) PRIMARY KEY REFERENCES scrapp.NumericalObservations(observation_id),observed_at_utc datetime2(6) NOT NULL,latitude decimal(9,6),longitude decimal(9,6));
CREATE TABLE scrapp.WeatherForecasts(observation_id varchar(64) PRIMARY KEY REFERENCES scrapp.NumericalObservations(observation_id),issue_at_utc datetime2(6),valid_at_utc datetime2(6) NOT NULL,model nvarchar(100),issue_status varchar(24) NOT NULL);
CREATE INDEX IX_ForecastValidIssue ON scrapp.WeatherForecasts(valid_at_utc,issue_at_utc);
CREATE TABLE scrapp.SportsEvents(event_id varchar(64) PRIMARY KEY,definition_json nvarchar(max) NOT NULL CHECK(ISJSON(definition_json)=1));
CREATE TABLE scrapp.SportsOdds(observation_id varchar(64) PRIMARY KEY REFERENCES scrapp.NumericalObservations(observation_id),event_id varchar(64) NOT NULL REFERENCES scrapp.SportsEvents(event_id),market_id varchar(64) NOT NULL,bookmaker nvarchar(180) NOT NULL,outcome nvarchar(80) NOT NULL,market_json nvarchar(max) NOT NULL CHECK(ISJSON(market_json)=1));
CREATE TABLE scrapp.SourceHealth(source_id nvarchar(100) PRIMARY KEY REFERENCES scrapp.DataSources(source_id),state varchar(24) NOT NULL,last_success_utc datetime2(6),last_attempt_utc datetime2(6),failures int NOT NULL DEFAULT 0,reason nvarchar(500));
CREATE TABLE scrapp.DataQuality(assessment_id varchar(64) PRIMARY KEY,observation_id varchar(64) NOT NULL REFERENCES scrapp.RawObservations(observation_id),status varchar(24) NOT NULL,detail_json nvarchar(max) NOT NULL CHECK(ISJSON(detail_json)=1));
CREATE TABLE scrapp.ProcessingReports(report_id varchar(64) PRIMARY KEY,created_at_utc datetime2(6) NOT NULL,kind varchar(40) NOT NULL,report_json nvarchar(max) NOT NULL CHECK(ISJSON(report_json)=1));
INSERT INTO scrapp.SchemaMigrations(version) VALUES(1);
END;
COMMIT TRANSACTION;
-- Runtime cannot rewrite raw evidence or numerical history even though it can update health/configuration.
DENY UPDATE,DELETE ON scrapp.RawObservations TO scrapp_runtime;
DENY UPDATE,DELETE ON scrapp.NumericalObservations TO scrapp_runtime;
