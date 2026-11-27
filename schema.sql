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
    primarystate VARCHAR,
    primarycountryname VARCHAR,
    primaryaddress_full TEXT,
    primaryaddress_map TEXT,
    primaryaddress_full_map TEXT,
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

-- 2.2. Tabela de Status Mensal de Filiados (Snapshots oficiais do ThoughtSpot)
CREATE TABLE member_monthly_status (
    personid BIGINT NOT NULL REFERENCES person (personid),
    memberdatayearmonth DATE NOT NULL,
    iscurrentrenew BOOLEAN,
    iscurrentexpiration BOOLEAN,
    isrenew BOOLEAN,
    isnonrenew BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (personid, memberdatayearmonth)
);
CREATE INDEX IF NOT EXISTS idx_member_monthly_status_lookup 
    ON member_monthly_status (personid, memberdatayearmonth); 

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
    application_service_end_date DATE,
    termo_assinado BOOLEAN DEFAULT FALSE,
    termo_status VARCHAR DEFAULT 'Não Consta'
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

CREATE INDEX IF NOT EXISTS idx_membership_person_term 
    ON membership (personid, startdateforterm);

DROP VIEW IF EXISTS vw_looker_filiacoes;

CREATE VIEW vw_looker_filiacoes AS
SELECT 
    ms.memberdatayearmonth::date AS "Memberdatayearmonth_dateformat",
    ms.memberdatayearmonth::date AS "Memberdatayearmonth",
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
          AND (c.effectiveenddate >= ms.memberdatayearmonth OR c.certificationstatusname = 'Certified')
    ) AS "Certificationlist",
    p.primaryphone AS "Primaryphone",
    p.primaryaddress AS "Primaryaddress_Detalhado",
    COALESCE(p.primaryaddress_map, p.primaryaddress) AS "Primaryaddress1",
    p.primarycity AS "Primarycity",
    p.primarystate AS "Primarystate",
    p.primarycountryname AS "Primarycountryname",
    p.primaryzip AS "Primaryzip",
    COALESCE(p.primaryaddress_full_map, p.primaryaddress_full) AS "Endereco_Mapa",
    COALESCE(p.primaryaddress_full_map, p.primaryaddress_full) AS "Endereco_Completo",
    p.primaryaddress_full AS "Endereco_Detalhado",
    'yes'::text AS "Isactive",
    m.isreceiveelectronicnotifications AS "Isreceiveelectronicnotifications",
    CASE WHEN ms.iscurrentexpiration IS TRUE THEN 'yes' ELSE 'no' END AS "IsCurrentExpiration",
    CASE WHEN ms.iscurrentrenew IS TRUE THEN 'yes' ELSE 'no' END AS "Iscurrentrenew",
    CASE WHEN EXISTS (
        SELECT 1 FROM certification c 
        WHERE c.personid = p.personid 
          AND (c.effectiveenddate >= ms.memberdatayearmonth OR c.certificationstatusname = 'Certified')
    ) THEN 'Certificado' ELSE 'Não Certificado' END AS "Iscurrentlycertified",
    CASE WHEN m.originaljoindate IS NOT NULL AND ms.memberdatayearmonth = DATE_TRUNC('month', m.originaljoindate)::date THEN 'yes' ELSE 'no' END AS "Isfirstmonth",
    CASE WHEN m.originaljoindate IS NOT NULL AND ms.memberdatayearmonth < (m.originaljoindate + INTERVAL '1 year') THEN 'yes' ELSE 'no' END AS "Isfirstyear",
    CASE WHEN ms.isnonrenew IS TRUE THEN 'yes' ELSE 'no' END AS "Isnonrenew",
    CASE WHEN ms.isrenew IS TRUE THEN 'yes' ELSE 'no' END AS "Isrenew",
    COALESCE(m.tenureinyears, 1) AS "Qtd_renew"
FROM member_monthly_status ms
JOIN person p ON p.personid = ms.personid
LEFT JOIN LATERAL (
    SELECT m.membership_id, m.originaljoindate, m.startdateforterm, m.enddateforterm, 
           m.plannameforchapters, m.issinglemembership, m.autorenewstatus, 
           m.isreceiveelectronicnotifications, m.tenureinyears
    FROM membership m
    WHERE m.personid = ms.personid
    ORDER BY 
        CASE 
            WHEN ms.memberdatayearmonth BETWEEN DATE_TRUNC('month', m.startdateforterm) AND DATE_TRUNC('month', m.enddateforterm) THEN 0
            WHEN ms.memberdatayearmonth < DATE_TRUNC('month', m.startdateforterm) THEN 1
            ELSE 2
        END,
        m.startdateforterm DESC
    LIMIT 1
) m ON TRUE;

-- 10. View Leve de Última Atualização para Google Looker Studio (Data Studio)
CREATE OR REPLACE VIEW vw_looker_ultima_atualizacao AS
SELECT 
    data_type AS "Tipo_Dado",
    filename AS "Ultimo_Arquivo",
    (created_at - INTERVAL '3 hours') AS "Data_Hora_Atualizacao",
    TO_CHAR(created_at - INTERVAL '3 hours', 'DD/MM/YYYY "às" HH24:MI') AS "Ultima_Atualizacao_Formatada",
    record_count AS "Registros_Processados",
    source AS "Origem"
FROM (
    SELECT DISTINCT ON (data_type) 
        data_type, filename, created_at, record_count, source
    FROM datalake_raw_files
    ORDER BY data_type, created_at DESC
) sub;

-- 11. Tabela de Requisições de Dados e Inteligência (Governança e Autoatendimento)
CREATE TABLE IF NOT EXISTS data_request (
    id SERIAL PRIMARY KEY,
    requester_name VARCHAR(255) NOT NULL,
    requester_email VARCHAR(255) NOT NULL,
    directorate VARCHAR(100) NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    strategic_objective TEXT NOT NULL,
    request_type VARCHAR(100) NOT NULL,
    data_elements TEXT NOT NULL,
    urgency VARCHAR(50) DEFAULT 'Média',
    deadline VARCHAR(50),
    status VARCHAR(50) DEFAULT 'Em Análise',
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 12. Tabela de Solicitações de Cadastro de Novos Usuários
CREATE TABLE IF NOT EXISTS user_registration_request (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    directorate VARCHAR(100) NOT NULL,
    justification TEXT NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- 13. Tabela de Solicitações de Recuperação / Redefinição de Senha
CREATE TABLE IF NOT EXISTS password_reset_request (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    reason TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    admin_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- 14. Tabela de Ativos da Biblioteca de Conhecimento & Estudos Estratégicos
CREATE TABLE IF NOT EXISTS knowledge_asset (
    asset_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'Estudos',
    directorate VARCHAR(100) NOT NULL,
    author_name VARCHAR(150) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'Homologado',
    is_featured BOOLEAN DEFAULT FALSE,
    summary TEXT NOT NULL,
    decision_supported TEXT,
    data_sources TEXT,
    file_path VARCHAR(500),
    file_type VARCHAR(20) DEFAULT 'pptx',
    slide_count INT DEFAULT 0,
    view_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);