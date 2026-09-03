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