-- 1. Criação da Tabela Principal (PERSON)
CREATE TABLE person ( 
    personid BIGINT PRIMARY KEY,  
    fullname VARCHAR,  
    primaryemail VARCHAR,  
    primaryphone VARCHAR, -- Alterado de INT para VARCHAR
    primaryaddress VARCHAR,  
    industry VARCHAR,  
    jobtittle VARCHAR,  
    primaryzip VARCHAR,  
    primarycity VARCHAR,  
    alternativeemail VARCHAR 
); 

-- 2. Criação da Tabela MEMBERSHIP
CREATE TABLE membership ( 
    membership_id SERIAL PRIMARY KEY, -- Chave primária adicionada
    personid BIGINT REFERENCES person (personid), -- FK inline
    originaljoindate DATE,  
    startdateforterm DATE,  
    enddateforterm DATE, -- Alterado de INT para DATE
    plannameforchapters VARCHAR,  
    autorenewstatus VARCHAR,  
    issinglemembership BOOLEAN,  
    isreceiveelectronicnotifications BOOLEAN,  
    tenureinyears NUMERIC
); 

-- 2.1. Tabela de Histórico de Alterações Cadastrais de Pessoas (Audit)
CREATE TABLE person_history (
    history_id SERIAL PRIMARY KEY,
    personid BIGINT REFERENCES person (personid),
    field_changed VARCHAR NOT NULL,
    old_value VARCHAR,
    new_value VARCHAR,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
); 

-- 3. Criação da Tabela CERTIFICATION
CREATE TABLE certification ( 
    certification_id SERIAL PRIMARY KEY, -- Chave primária auto-incremental
    certificationid BIGINT,  
    personid BIGINT REFERENCES person (personid), -- FK inline
    certificationtypename VARCHAR,  
    originalgrantdate DATE,  
    effectivestartdate DATE,  
    effectiveenddate DATE,  
    certificationstatusname VARCHAR,  
    total_cycleseqno INT
); 

-- 4. Criação da Tabela VOLUNTARY
CREATE TABLE voluntary ( 
    voluntary_id SERIAL PRIMARY KEY, -- Chave primária adicionada
    personid BIGINT REFERENCES person (personid), -- FK inline
    applicants VARCHAR,  
    opportunity_name VARCHAR, -- Espaços removidos
    application_status VARCHAR,  
    opportunity_description VARCHAR,  
    email_address VARCHAR,  
    application_service_start_date DATE,  
    application_service_end_date DATE
);

-- 5. Criação da Tabela APP_USER (Autenticação e Governança RBAC)
CREATE TABLE app_user (
    user_id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    full_name VARCHAR NOT NULL,
    role VARCHAR NOT NULL DEFAULT 'view', -- 'admin' (Acesso Total), 'view' (Acesso de Visualização)
    allowed_reports VARCHAR, -- Lista JSON/string de relatórios autorizados
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Criação da Tabela CUSTOM_REPORT (Relatórios Salvos via Console SQL)
CREATE TABLE custom_report (
    report_id SERIAL PRIMARY KEY,
    report_name VARCHAR NOT NULL,
    sql_query TEXT NOT NULL,
    description VARCHAR,
    created_by VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Criação da Tabela REPORT_ACCESS_REQUEST (Solicitações de Acesso a Relatórios)
CREATE TABLE report_access_request (
    request_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    user_email VARCHAR NOT NULL,
    user_name VARCHAR NOT NULL,
    report_key VARCHAR NOT NULL,
    report_name VARCHAR NOT NULL,
    justification TEXT,
    status VARCHAR NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Criação da Tabela DATALAKE_RAW_FILES (Histórico Bruto Imutável de Ingestões)
CREATE TABLE datalake_raw_files (
    file_id SERIAL PRIMARY KEY,
    filename VARCHAR NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    record_count INT DEFAULT 0,
    source VARCHAR DEFAULT 'thoughtspot_email',
    data_type VARCHAR DEFAULT 'filiados', -- 'filiados', 'certificacoes', 'voluntarios'
    file_content BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Views para Conexão Direta com Google Looker Studio (Data Studio)
CREATE OR REPLACE VIEW vw_looker_certificacoes AS
SELECT 
    COALESCE(c.effectivestartdate, c.originalgrantdate) AS "Mes_Referencia",
    c.personid AS "ID",
    c.certificationtypename AS "Certificacao",
    c.originalgrantdate AS "Data_Certificacao_Original",
    c.effectivestartdate AS "Data_Certificacao_Atual",
    c.effectiveenddate AS "Data_Expiracao_Certificacao",
    c.certificationstatusname AS "Status_Certificacao",
    c.total_cycleseqno AS "Qtde_Ciclos"
FROM certification c;

DROP VIEW IF EXISTS vw_looker_filiacoes;

CREATE VIEW vw_looker_filiacoes AS
SELECT 
    m_month::date AS "Memberdatayearmonth_dateformat",
    m_month::date AS "Memberdatayearmonth",
    p.personid AS "Personid",
    p.fullname AS "Fullname",
    p.industry AS "Industry",
    p.primaryemail AS "Primaryemail",
    m.originaljoindate AS "Originaljoindate",
    m.startdateforterm AS "Startdateforterm",
    m.enddateforterm AS "Enddateforterm",
    m.plannameforchapters AS "Plannameforchapters",
    m.issinglemembership AS "Issinglemembership",
    m.autorenewstatus AS "Autorenewstatus",
    (
        SELECT STRING_AGG(DISTINCT c.certificationtypename, ', ')
        FROM certification c 
        WHERE c.personid = p.personid 
          AND (c.effectiveenddate >= m_month::date OR c.certificationstatusname = 'Certified')
    ) AS "Certificationlist",
    p.primaryphone AS "Primaryphone",
    p.primaryaddress AS "Primaryaddress1",
    p.primaryzip AS "Primaryzip",
    'yes'::text AS "Isactive",
    m.isreceiveelectronicnotifications AS "Isreceiveelectronicnotifications",
    CASE WHEN m_month::date = DATE_TRUNC('month', m.enddateforterm)::date THEN 'yes' ELSE 'no' END AS "IsCurrentExpiration",
    CASE WHEN (m_month::date = DATE_TRUNC('month', m.startdateforterm)::date OR m_month::date = DATE_TRUNC('month', m.startdateforterm - INTERVAL '1 month')::date) AND m.startdateforterm > m.originaljoindate THEN 'yes' ELSE 'no' END AS "Iscurrentrenew",
    CASE WHEN EXISTS (
        SELECT 1 FROM certification c 
        WHERE c.personid = p.personid AND (c.effectiveenddate >= m_month::date OR c.certificationstatusname = 'Certified')
    ) THEN 'yes' ELSE 'no' END AS "Iscurrentlycertified",
    CASE WHEN m.originaljoindate IS NOT NULL AND m_month::date = DATE_TRUNC('month', m.originaljoindate)::date THEN 'yes' ELSE 'no' END AS "Isfirstmonth",
    CASE WHEN m.originaljoindate IS NOT NULL AND m_month::date < (m.originaljoindate + INTERVAL '1 year') THEN 'yes' ELSE 'no' END AS "Isfirstyear",
    CASE 
        WHEN m_month::date = DATE_TRUNC('month', m.enddateforterm)::date 
         AND NOT EXISTS (
             SELECT 1 FROM membership m2 
             WHERE m2.personid = m.personid 
               AND m2.startdateforterm > m.startdateforterm 
               AND m2.startdateforterm <= (m.enddateforterm + INTERVAL '60 days')
         )
        THEN 'yes' 
        ELSE 'no' 
    END AS "Isnonrenew",
    CASE WHEN m.startdateforterm > m.originaljoindate THEN 'yes' ELSE 'no' END AS "Isrenew",
    COALESCE(m.tenureinyears, 1) AS "Qtd_renew"
FROM membership m
JOIN person p ON p.personid = m.personid
CROSS JOIN LATERAL generate_series(
    CASE 
        WHEN m.originaljoindate IS NOT NULL 
         AND m.originaljoindate < m.startdateforterm 
         AND m.originaljoindate >= (m.startdateforterm - INTERVAL '35 days') 
        THEN DATE_TRUNC('month', m.originaljoindate)
        ELSE DATE_TRUNC('month', m.startdateforterm)
    END,
    LEAST(DATE_TRUNC('month', m.enddateforterm), DATE_TRUNC('month', CURRENT_DATE)),
    INTERVAL '1 month'
) AS m_month
WHERE CASE 
        WHEN m.originaljoindate IS NOT NULL 
         AND m.originaljoindate < m.startdateforterm 
         AND m.originaljoindate >= (m.startdateforterm - INTERVAL '35 days') 
        THEN DATE_TRUNC('month', m.originaljoindate)
        ELSE DATE_TRUNC('month', m.startdateforterm)
      END <= DATE_TRUNC('month', CURRENT_DATE);