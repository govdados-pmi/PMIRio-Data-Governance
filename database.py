import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import hashlib
import streamlit as st
import warnings
from typing import Optional, Union, Any, Dict

warnings.filterwarnings("ignore", category=UserWarning, message=".*pandas only supports SQLAlchemy.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*DBAPI2.*")

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

class DatabaseManager:
    def __init__(self, connection_string: Optional[str] = None):
        """
        Inicializa o gerenciador de banco de dados nativo do Supabase (PostgreSQL).
        Carrega a conexão a partir de:
        1. Parâmetro explícito ou variáveis de ambiente (SUPABASE_DB_URL, DATABASE_URL, POSTGRES_URL)
        2. Streamlit Secrets (st.secrets["SUPABASE_DB_URL"])
        3. Variáveis de ambiente individuais (PGHOST, PGPASSWORD, etc.)
        """
        self.connection_string = connection_string or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
        
        if not self.connection_string:
            try:
                if hasattr(st, "secrets"):
                    if "SUPABASE_DB_URL" in st.secrets:
                        self.connection_string = st.secrets["SUPABASE_DB_URL"]
                    elif "DATABASE_URL" in st.secrets:
                        self.connection_string = st.secrets["DATABASE_URL"]
                    elif "postgres" in st.secrets:
                        pg = st.secrets["postgres"]
                        self.connection_string = f"postgresql://{pg.get('user')}:{pg.get('password')}@{pg.get('host')}:{pg.get('port', 5432)}/{pg.get('dbname', 'postgres')}"
            except Exception:
                pass

        if not self.connection_string:
            supabase_ref = os.getenv("SUPABASE_PROJECT_REF")
            supabase_pass = os.getenv("SUPABASE_DB_PASSWORD") or os.getenv("PGPASSWORD")
            pghost = os.getenv("PGHOST") or (f"db.{supabase_ref}.supabase.co" if supabase_ref else None)
            pgdb = os.getenv("PGDATABASE", "postgres")
            pguser = os.getenv("PGUSER", "postgres")
            pgport = os.getenv("PGPORT", "5432")
            
            if pghost and supabase_pass:
                self.connection_string = f"postgresql://{pguser}:{supabase_pass}@{pghost}:{pgport}/{pgdb}"

        self.is_postgres = True

    def update_connection(self, connection_string: str):
        """Atualiza a string de conexão do Supabase em tempo de execução."""
        self.connection_string = connection_string
        self.is_postgres = True

    def get_connection(self):
        """Retorna uma conexão ativa com o banco PostgreSQL no Supabase."""
        if not self.connection_string:
            raise ValueError(
                "String de conexão com o banco de dados não configurada. "
                "Verifique se o arquivo .env contém SUPABASE_DB_URL ou se python-dotenv está instalado."
            )
        return psycopg2.connect(self.connection_string)

    @staticmethod
    def hash_password(password: str) -> str:
        """Gera hash SHA-256 para armazenamento seguro de senhas."""
        salt = os.getenv("PASSWORD_SALT", "pmi_rio_gov_dados_salt_2026")
        return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

    def init_db(self, schema_file: Optional[str] = None):
        """
        Verifica a conectividade com o banco de dados e assegura que a tabela
        report_access_request exista.
        """
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            id_type = "SERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS report_access_request (
                request_id {id_type},
                user_id INT NOT NULL,
                user_email VARCHAR NOT NULL,
                user_name VARCHAR NOT NULL,
                report_key VARCHAR NOT NULL,
                report_name VARCHAR NOT NULL,
                justification TEXT,
                status VARCHAR NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS data_request (
                request_id {id_type},
                requester_name VARCHAR NOT NULL,
                requester_email VARCHAR NOT NULL,
                directorate VARCHAR NOT NULL,
                project_initiative VARCHAR NOT NULL,
                business_objective TEXT NOT NULL,
                data_scope TEXT NOT NULL,
                urgency VARCHAR NOT NULL DEFAULT 'Normal',
                deadline VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'Pendente',
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS user_registration_request (
                reg_id {id_type},
                full_name VARCHAR NOT NULL,
                email VARCHAR NOT NULL,
                directorate VARCHAR NOT NULL,
                justification TEXT,
                password_hash VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS password_reset_request (
                reset_id {id_type},
                email VARCHAR NOT NULL,
                full_name VARCHAR,
                reason TEXT,
                status VARCHAR NOT NULL DEFAULT 'pending',
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Tabela de Ativos da Biblioteca de Conhecimento & Estudos
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS knowledge_asset (
                asset_id {id_type},
                title VARCHAR NOT NULL,
                category VARCHAR NOT NULL DEFAULT 'Estudos',
                directorate VARCHAR NOT NULL,
                author_name VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'Homologado',
                is_featured BOOLEAN DEFAULT FALSE,
                summary TEXT NOT NULL,
                decision_supported TEXT,
                data_sources TEXT,
                file_path VARCHAR,
                file_type VARCHAR DEFAULT 'pptx',
                slide_count INT DEFAULT 0,
                view_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Assegura a existência da coluna must_change_password em app_user
            try:
                if self.is_postgres:
                    cur.execute("ALTER TABLE app_user ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;")
                else:
                    cur.execute("PRAGMA table_info(app_user);")
                    cols = [col[1] for col in cur.fetchall()]
                    if "must_change_password" not in cols:
                        cur.execute("ALTER TABLE app_user ADD COLUMN must_change_password BOOLEAN DEFAULT 0;")
            except Exception:
                pass

            conn.commit()
            cur.close()
            conn.close()

            # Executa o seed de ativos de conhecimento padrão caso necessário
            self.seed_default_knowledge_assets()
        except Exception:
            pass

    def seed_default_users(self):
        """
        Cria o usuário administrador inicial apenas se as variáveis de ambiente 
        INITIAL_ADMIN_EMAIL e INITIAL_ADMIN_PASSWORD estiverem configuradas no .env.
        Sem credenciais ou senhas hardcoded no código.
        """
        admin_email = os.getenv("INITIAL_ADMIN_EMAIL")
        admin_password = os.getenv("INITIAL_ADMIN_PASSWORD")
        if not admin_email or not admin_password:
            return

        placeholder = "%s" if self.is_postgres else "?"
        pwd_hash = self.hash_password(admin_password)
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT 1 FROM app_user WHERE LOWER(email) = LOWER({placeholder});", (admin_email,))
            if not cur.fetchone():
                sql = f"""
                INSERT INTO app_user (email, password_hash, full_name, role, is_active)
                VALUES ({placeholder}, {placeholder}, {placeholder}, 'admin', TRUE);
                """
                cur.execute(sql, (admin_email, pwd_hash, "Administrador de Dados"))
                conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Valida e-mail e senha diretamente no banco (sem cache) e retorna dicionário com os dados do usuário autenticado."""
        pwd_hash = self.hash_password(password.strip())
        placeholder = "%s" if self.is_postgres else "?"
        default_bool = "FALSE" if self.is_postgres else "0"
        query = f"SELECT user_id, email, full_name, role, allowed_reports, is_active, COALESCE(must_change_password, {default_bool}) FROM app_user WHERE LOWER(email) = LOWER({placeholder}) AND password_hash = {placeholder};"
        
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, (email.strip(), pwd_hash))
            row = cur.fetchone()
            cur.close()
            if row:
                # row: user_id, email, full_name, role, allowed_reports, is_active, must_change_password
                is_active = bool(row[5])
                if is_active:
                    return {
                        "user_id": int(row[0]),
                        "email": str(row[1]),
                        "full_name": str(row[2]),
                        "role": str(row[3]),
                        "allowed_reports": str(row[4]) if row[4] else "[]",
                        "must_change_password": bool(row[6]) if len(row) > 6 and row[6] else False
                    }
        finally:
            conn.close()
        return None

    def create_user(self, email: str, password: str, full_name: str, role: str, allowed_reports: Optional[str] = "[]", must_change_password: bool = True) -> bool:
        """Cadastra um novo usuário no banco com controle de permissões de relatórios e flag de primeiro acesso."""
        pwd_hash = self.hash_password(password)
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"INSERT INTO app_user (email, password_hash, full_name, role, allowed_reports, must_change_password, is_active) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, TRUE);"
        try:
            final_reports = allowed_reports if allowed_reports is not None else "[]"
            self.execute_non_query(sql, (email.strip().lower(), pwd_hash, full_name.strip(), role.strip(), final_reports, must_change_password))
            return True
        except Exception:
            return False

    def update_user_allowed_reports(self, user_id: int, allowed_reports: Optional[str]) -> bool:
        """Atualiza a lista de relatórios autorizados para um usuário de visualização."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE app_user SET allowed_reports = {placeholder} WHERE user_id = {placeholder};"
        try:
            self.execute_non_query(sql, (allowed_reports, user_id))
            return True
        except Exception:
            return False

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        """Atualiza a senha de um usuário no banco de dados com hash seguro e reseta a obrigatoriedade de troca de senha."""
        pwd_hash = self.hash_password(new_password)
        placeholder = "%s" if self.is_postgres else "?"
        reset_val = "FALSE" if self.is_postgres else "0"
        sql = f"UPDATE app_user SET password_hash = {placeholder}, must_change_password = {reset_val} WHERE user_id = {placeholder};"
        try:
            self.execute_non_query(sql, (pwd_hash, user_id))
            return True
        except Exception:
            return False


    def list_users(self) -> pd.DataFrame:
        """Retorna lista de usuários cadastrados (sem expor o hash da senha)."""
        return self.execute_query("SELECT user_id, email, full_name, role, allowed_reports, is_active, created_at FROM app_user ORDER BY created_at DESC;")

    def toggle_user_status(self, user_id: int, current_status: bool) -> bool:
        """Ativa ou desativa o acesso de um usuário."""
        placeholder = "%s" if self.is_postgres else "?"
        new_status = not current_status
        sql = f"UPDATE app_user SET is_active = {placeholder} WHERE user_id = {placeholder};"
        try:
            self.execute_non_query(sql, (new_status, user_id))
            return True
        except Exception:
            return False

    def delete_user(self, user_id: int) -> bool:
        """Remove um usuário do cadastro de acessos."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"DELETE FROM app_user WHERE user_id = {placeholder};"
        try:
            self.execute_non_query(sql, (user_id,))
            return True
        except Exception:
            return False

    def save_custom_report(self, report_name: str, sql_query: str, description: str = "", created_by: str = "") -> bool:
        """Salva uma consulta SQL como um novo relatório personalizado dinâmico."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"INSERT INTO custom_report (report_name, sql_query, description, created_by) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder});"
        try:
            self.execute_non_query(sql, (report_name.strip(), sql_query.strip(), description.strip(), created_by.strip()))
            return True
        except Exception:
            return False

    def update_custom_report(self, report_id: int, report_name: str, sql_query: str, description: str = "") -> bool:
        """Atualiza a consulta SQL, nome e descrição de um relatório personalizado existente."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE custom_report SET report_name = {placeholder}, sql_query = {placeholder}, description = {placeholder} WHERE report_id = {placeholder};"
        try:
            self.execute_non_query(sql, (report_name.strip(), sql_query.strip(), description.strip(), report_id))
            return True
        except Exception:
            return False

    def list_custom_reports(self) -> pd.DataFrame:
        """Lista todos os relatórios personalizados salvos pelo console SQL."""
        try:
            return self.execute_query("SELECT report_id, report_name, sql_query, description, created_by, created_at FROM custom_report ORDER BY created_at DESC;")
        except Exception:
            return pd.DataFrame()

    def delete_custom_report(self, report_id: int) -> bool:
        """Exclui um relatório personalizado salvo."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"DELETE FROM custom_report WHERE report_id = {placeholder};"
        try:
            self.execute_non_query(sql, (report_id,))
            return True
        except Exception:
            return False

    def create_access_request(self, user_id: int, user_email: str, user_name: str, report_key: str, report_name: str, justification: str = "") -> bool:
        """Cria uma solicitação de acesso a um relatório."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"""
        INSERT INTO report_access_request (user_id, user_email, user_name, report_key, report_name, justification, status)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'pending');
        """
        try:
            self.execute_non_query(sql, (user_id, user_email.strip(), user_name.strip(), report_key.strip(), report_name.strip(), justification.strip()))
            return True
        except Exception:
            return False

    def get_user_access_requests(self, user_id: int) -> pd.DataFrame:
        """Retorna todas as solicitações de acesso de um determinado usuário."""
        placeholder = "%s" if self.is_postgres else "?"
        query = f"SELECT request_id, report_key, report_name, justification, status, created_at FROM report_access_request WHERE user_id = {placeholder} ORDER BY created_at DESC;"
        try:
            return self.execute_query(query, (user_id,))
        except Exception:
            return pd.DataFrame()

    def list_pending_access_requests(self) -> pd.DataFrame:
        """Retorna todas as solicitações de acesso pendentes de aprovação."""
        query = "SELECT request_id, user_id, user_email, user_name, report_key, report_name, justification, status, created_at FROM report_access_request WHERE status = 'pending' ORDER BY created_at ASC;"
        try:
            return self.execute_query(query)
        except Exception:
            return pd.DataFrame()

    def list_all_access_requests(self) -> pd.DataFrame:
        """Retorna histórico de todas as solicitações de acesso."""
        query = "SELECT request_id, user_id, user_email, user_name, report_key, report_name, justification, status, created_at FROM report_access_request ORDER BY created_at DESC;"
        try:
            return self.execute_query(query)
        except Exception:
            return pd.DataFrame()

    def approve_access_request(self, request_id: int, user_id: int, report_key: str) -> bool:
        """Aprova a solicitação de acesso e adiciona o relatório à lista do usuário."""
        import json
        placeholder = "%s" if self.is_postgres else "?"
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT allowed_reports FROM app_user WHERE user_id = {placeholder};", (user_id,))
            row = cur.fetchone()
            current_allowed = []
            if row and row[0]:
                try:
                    current_allowed = json.loads(row[0])
                except Exception:
                    current_allowed = []
            
            if report_key not in current_allowed:
                current_allowed.append(report_key)
            
            new_allowed_json = json.dumps(current_allowed)
            cur.execute(f"UPDATE app_user SET allowed_reports = {placeholder} WHERE user_id = {placeholder};", (new_allowed_json, user_id))
            cur.execute(f"UPDATE report_access_request SET status = 'approved' WHERE request_id = {placeholder};", (request_id,))
            conn.commit()
            cur.close()
            try:
                st.cache_data.clear()
            except Exception:
                pass
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def reject_access_request(self, request_id: int) -> bool:
        """Rejeita uma solicitação de acesso a relatório."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE report_access_request SET status = 'rejected' WHERE request_id = {placeholder};"
        try:
            self.execute_non_query(sql, (request_id,))
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # GESTÃO DE REQUISIÇÕES DE DADOS (DATA REQUEST HUB)
    # -------------------------------------------------------------------------
    def create_data_request(self, requester_name: str, requester_email: str, directorate: str,
                            project_initiative: str, business_objective: str, data_scope: str,
                            urgency: str = "Normal", deadline: str = "") -> bool:
        """Registra uma nova requisição formal de dados ou relatório."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"""
        INSERT INTO data_request (requester_name, requester_email, directorate, project_initiative, business_objective, data_scope, urgency, deadline, status)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'Pendente');
        """
        try:
            self.execute_non_query(sql, (requester_name.strip(), requester_email.strip().lower(),
                                        directorate.strip(), project_initiative.strip(),
                                        business_objective.strip(), data_scope.strip(),
                                        urgency.strip(), deadline.strip()))
            return True
        except Exception:
            return False

    def list_data_requests(self, requester_email: Optional[str] = None) -> pd.DataFrame:
        """Lista requisições de dados (todas para admin ou filtradas por e-mail)."""
        placeholder = "%s" if self.is_postgres else "?"
        if requester_email:
            query = f"SELECT request_id, requester_name, requester_email, directorate, project_initiative, business_objective, data_scope, urgency, deadline, status, admin_notes, created_at FROM data_request WHERE LOWER(requester_email) = LOWER({placeholder}) ORDER BY created_at DESC;"
            try:
                return self.execute_query(query, (requester_email.strip(),))
            except Exception:
                return pd.DataFrame()
        else:
            query = "SELECT request_id, requester_name, requester_email, directorate, project_initiative, business_objective, data_scope, urgency, deadline, status, admin_notes, created_at FROM data_request ORDER BY created_at DESC;"
            try:
                return self.execute_query(query)
            except Exception:
                return pd.DataFrame()

    def update_data_request_status(self, request_id: int, status: str, admin_notes: str = "") -> bool:
        """Atualiza o status e parecer técnico de uma requisição de dados."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE data_request SET status = {placeholder}, admin_notes = {placeholder} WHERE request_id = {placeholder};"
        try:
            self.execute_non_query(sql, (status.strip(), admin_notes.strip(), request_id))
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # GESTÃO DE CADASTRO E RESET DE SENHA (SELF-SERVICE GOVERNADO)
    # -------------------------------------------------------------------------
    def create_registration_request(self, full_name: str, email: str, directorate: str,
                                    justification: str, password: str) -> bool:
        """Registra pedido de criação de conta institucional."""
        placeholder = "%s" if self.is_postgres else "?"
        pwd_hash = self.hash_password(password)
        sql = f"""
        INSERT INTO user_registration_request (full_name, email, directorate, justification, password_hash, status)
        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'pending');
        """
        try:
            self.execute_non_query(sql, (full_name.strip(), email.strip().lower(), directorate.strip(), justification.strip(), pwd_hash))
            return True
        except Exception:
            return False

    def list_registration_requests(self, status: str = "pending") -> pd.DataFrame:
        """Lista pedidos de cadastro pendentes ou todos."""
        placeholder = "%s" if self.is_postgres else "?"
        if status:
            query = f"SELECT reg_id, full_name, email, directorate, justification, password_hash, status, created_at FROM user_registration_request WHERE status = {placeholder} ORDER BY created_at ASC;"
            try:
                return self.execute_query(query, (status,))
            except Exception:
                return pd.DataFrame()
        else:
            query = "SELECT reg_id, full_name, email, directorate, justification, status, created_at FROM user_registration_request ORDER BY created_at DESC;"
            try:
                return self.execute_query(query)
            except Exception:
                return pd.DataFrame()

    def approve_registration_request(self, reg_id: int, role: str = "view", allowed_reports: Optional[str] = None) -> bool:
        """Aprova pedido de cadastro e cria usuário ativo na tabela app_user."""
        placeholder = "%s" if self.is_postgres else "?"
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT full_name, email, password_hash FROM user_registration_request WHERE reg_id = {placeholder};", (reg_id,))
            row = cur.fetchone()
            if not row:
                return False
            full_name, email, pwd_hash = row[0], row[1], row[2]
            
            cur.execute(f"SELECT user_id FROM app_user WHERE LOWER(email) = LOWER({placeholder});", (email,))
            existing = cur.fetchone()
            if existing:
                cur.execute(f"UPDATE app_user SET full_name = {placeholder}, password_hash = {placeholder}, role = {placeholder}, allowed_reports = {placeholder}, is_active = TRUE WHERE user_id = {placeholder};",
                            (full_name, pwd_hash, role, allowed_reports, existing[0]))
            else:
                cur.execute(f"INSERT INTO app_user (email, password_hash, full_name, role, allowed_reports, is_active) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, TRUE);",
                            (email, pwd_hash, full_name, role, allowed_reports))
            
            cur.execute(f"UPDATE user_registration_request SET status = 'approved' WHERE reg_id = {placeholder};", (reg_id,))
            conn.commit()
            cur.close()
            try:
                st.cache_data.clear()
            except Exception:
                pass
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def reject_registration_request(self, reg_id: int) -> bool:
        """Rejeita solicitação de cadastro."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE user_registration_request SET status = 'rejected' WHERE reg_id = {placeholder};"
        try:
            self.execute_non_query(sql, (reg_id,))
            return True
        except Exception:
            return False

    def create_password_reset_request(self, email: str, full_name: str = "", reason: str = "") -> bool:
        """Registra pedido de recuperação/redefinição de senha."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"""
        INSERT INTO password_reset_request (email, full_name, reason, status)
        VALUES ({placeholder}, {placeholder}, {placeholder}, 'pending');
        """
        try:
            self.execute_non_query(sql, (email.strip().lower(), full_name.strip(), reason.strip()))
            return True
        except Exception:
            return False

    def list_password_reset_requests(self, status: str = "pending") -> pd.DataFrame:
        """Lista pedidos de recuperação de senha."""
        placeholder = "%s" if self.is_postgres else "?"
        if status:
            query = f"SELECT reset_id, email, full_name, reason, status, admin_notes, created_at FROM password_reset_request WHERE status = {placeholder} ORDER BY created_at ASC;"
            try:
                return self.execute_query(query, (status,))
            except Exception:
                return pd.DataFrame()
        else:
            query = "SELECT reset_id, email, full_name, reason, status, admin_notes, created_at FROM password_reset_request ORDER BY created_at DESC;"
            try:
                return self.execute_query(query)
            except Exception:
                return pd.DataFrame()

    def resolve_password_reset_request(self, reset_id: int, new_password: str, admin_notes: str = "") -> bool:
        """Redefine a senha do usuário correspondente e conclui o pedido de reset."""
        placeholder = "%s" if self.is_postgres else "?"
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(f"SELECT email FROM password_reset_request WHERE reset_id = {placeholder};", (reset_id,))
            row = cur.fetchone()
            if not row:
                return False
            email = row[0]
            pwd_hash = self.hash_password(new_password)
            flag_val = "TRUE" if self.is_postgres else "1"
            cur.execute(f"UPDATE app_user SET password_hash = {placeholder}, must_change_password = {flag_val} WHERE LOWER(email) = LOWER({placeholder});", (pwd_hash, email))
            cur.execute(f"UPDATE password_reset_request SET status = 'resolved', admin_notes = {placeholder} WHERE reset_id = {placeholder};", (admin_notes, reset_id))
            conn.commit()
            cur.close()
            try:
                st.cache_data.clear()
            except Exception:
                pass
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def seed_default_knowledge_assets(self):
        """Popula os 4 estudos estratégicos fundamentais caso a tabela esteja vazia."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            placeholder = "%s" if self.is_postgres else "?"
            
            # Migração: Unifica qualquer status 'Homologado' para 'Publicado'
            try:
                cur.execute(f"UPDATE knowledge_asset SET status = 'Publicado' WHERE status = 'Homologado';")
                conn.commit()
            except Exception:
                pass

            cur.execute("SELECT COUNT(*) FROM knowledge_asset;")
            count = cur.fetchone()[0]
            if count == 0:
                ph = f"({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})"
                
                initial_assets = [
                    (
                        "Jornada do Filiado: Modelo Metodológico & Score de Engajamento",
                        "Apresentações Executivas",
                        "Diretoria de Filiação & Relacionamento",
                        "Comitê de Governança de Dados",
                        "Publicado",
                        True,
                        "Estudo aprofundado que estabelece o framework metodológico da jornada de filiação no PMI Rio. Define a transição do membro em 4 fases distintas de maturidade (Descoberta, Inscrição, Ativação e Retenção), pontuando comportamentos de 0 a 100 pontos para prever o risco de churn.",
                        "Orientou a Diretoria a criar réguas de comunicação segmentadas para filiados de primeiro ano, antecipando o contato de renovação antes do período crítico de expiração.",
                        "Base histórica ThoughtSpot, voluntários ativos (VRMS), presença em eventos Sympla e pesquisas pós-evento (CSAT/NPS).",
                        "Estudos/Jornada do Filiado/Estudo - Jornada do Filiado.pptx",
                        "pptx",
                        13,
                        42
                    ),
                    (
                        "Análise Estratégica de Certificações & Evolução de Credenciais",
                        "Estudos & Inteligência de Dados",
                        "Diretoria de Relacionamento & Certificação",
                        "Comitê de Governança de Dados",
                        "Publicado",
                        True,
                        "Diagnóstico do volume, distribuição e ritmo de crescimento dos membros ativos credenciados pelo PMI no Rio de Janeiro. Identificou um salto de 17% no número de filiados com certificações válidas em 2025, com dominância de PMP, CAPM e PMI-ACP.",
                        "Apoiou o planejamento dos Grupos de Estudo preparatórios para 2026 e a criação do programa de mentoria voltado à manutenção de PDUs.",
                        "Relatórios mensais ThoughtSpot (Módulo de Certificações), OriginalGrantDate e ciclos de renovação ativa.",
                        "Estudos/Analise Relacionamento/Analise_Certificacoes_2025.pptx",
                        "pptx",
                        7,
                        28
                    ),
                    (
                        "Censo Demográfico & Classificação de Perfis de Filiados",
                        "Planilhas, Modelos & Censo",
                        "Diretoria de Filiação",
                        "Comitê de Governança de Dados",
                        "Publicado",
                        False,
                        "Mapeamento abrangente do perfil profissional dos membros do PMI Rio. Avalia indústrias preponderantes (Óleo & Gás, Tecnologia, Engenharia e Serviços Financeiros), cargos executivos e operacionais e distribuição geográfica.",
                        "Subsidou a precificação e a seleção de temas para os congressos e workshops do capítulo, alinhando com indústrias que concentram 70% da base.",
                        "Base consolidada de filiados ativos do PMI Global, campos de indústria e cargo auditados.",
                        "Estudos/Analise de Perfis/Analise dos dados de nossos filiados - Dez_24.pptx",
                        "pptx",
                        11,
                        19
                    ),
                    (
                        "Diagnóstico de Relacionamento & Saúde da Base de Membros",
                        "Apresentações Executivas",
                        "Diretoria de Filiação & Relacionamento",
                        "Comitê de Governança de Dados",
                        "Em Revisão",
                        False,
                        "Revisão executiva dos indicadores de atratividade e evasão de filiados. Analisa a correlação entre participação em eventos e taxa de renovação anual.",
                        "Recomendou a reformulação dos eventos de boas-vindas e ações conjuntas com a Diretoria de Voluntariado para retenção ativa.",
                        "Extratos de faturamento e filiação ThoughtSpot, histórico de contatos e cruzamento relacional.",
                        "Estudos/Analise Relacionamento/Analise Relacionamento.pptx",
                        "pptx",
                        20,
                        15
                    )
                ]
                
                sql_insert = f"""
                INSERT INTO knowledge_asset (
                    title, category, directorate, author_name, status, is_featured,
                    summary, decision_supported, data_sources, file_path, file_type, slide_count, view_count
                ) VALUES {ph};
                """
                for item in initial_assets:
                    cur.execute(sql_insert, item)
                conn.commit()
            cur.close()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def list_knowledge_assets(self, category: Optional[str] = None, sort_by: str = "popular", search: Optional[str] = None) -> pd.DataFrame:
        """Retorna os ativos de conhecimento com suporte a filtro de categoria, busca e ordenação."""
        conditions = []
        params = []
        placeholder = "%s" if self.is_postgres else "?"
        
        if category and category != "Todos":
            conditions.append(f"category = {placeholder}")
            params.append(category)
            
        if search:
            search_pattern = f"%{search.strip().lower()}%"
            conditions.append(f"(LOWER(title) LIKE {placeholder} OR LOWER(directorate) LIKE {placeholder} OR LOWER(summary) LIKE {placeholder} OR LOWER(author_name) LIKE {placeholder})")
            params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        if sort_by == "popular":
            order_clause = " ORDER BY view_count DESC, created_at DESC"
        elif sort_by == "title":
            order_clause = " ORDER BY title ASC"
        else:
            order_clause = " ORDER BY created_at DESC, view_count DESC"
            
        sql = f"SELECT asset_id, title, category, directorate, author_name, status, is_featured, summary, decision_supported, data_sources, file_path, file_type, slide_count, view_count, created_at, updated_at FROM knowledge_asset{where_clause}{order_clause};"
        return self.execute_query(sql, tuple(params) if params else None)

    def get_knowledge_asset(self, asset_id: int) -> Optional[Dict[str, Any]]:
        """Busca um ativo de conhecimento individual pelo ID."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"SELECT asset_id, title, category, directorate, author_name, status, is_featured, summary, decision_supported, data_sources, file_path, file_type, slide_count, view_count, created_at FROM knowledge_asset WHERE asset_id = {placeholder};"
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, (asset_id,))
            row = cur.fetchone()
            cur.close()
            if row:
                return {
                    "asset_id": row[0],
                    "title": row[1],
                    "category": row[2],
                    "directorate": row[3],
                    "author_name": row[4],
                    "status": row[5],
                    "is_featured": bool(row[6]),
                    "summary": row[7],
                    "decision_supported": row[8] or "",
                    "data_sources": row[9] or "",
                    "file_path": row[10] or "",
                    "file_type": row[11] or "pptx",
                    "slide_count": row[12] or 0,
                    "view_count": row[13] or 0,
                    "created_at": row[14]
                }
        finally:
            conn.close()
        return None

    def increment_asset_views(self, asset_id: int) -> bool:
        """Incrementa a contagem de visualizações de um documento da biblioteca."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE knowledge_asset SET view_count = view_count + 1 WHERE asset_id = {placeholder};"
        try:
            self.execute_non_query(sql, (asset_id,))
            return True
        except Exception:
            return False

    def create_knowledge_asset(self, title: str, category: str, directorate: str, author_name: str,
                               status: str, summary: str, decision_supported: str = "",
                               data_sources: str = "", file_path: str = "", file_type: str = "pptx",
                               slide_count: int = 0, is_featured: bool = False) -> bool:
        """Cadastra um novo ativo de conhecimento publicado na biblioteca."""
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"""
        INSERT INTO knowledge_asset (
            title, category, directorate, author_name, status, is_featured,
            summary, decision_supported, data_sources, file_path, file_type, slide_count, view_count
        ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 1);
        """
        try:
            self.execute_non_query(sql, (
                title.strip(), category.strip(), directorate.strip(), author_name.strip(),
                status.strip(), is_featured, summary.strip(), decision_supported.strip(),
                data_sources.strip(), file_path.strip(), file_type.strip(), slide_count
            ))
            return True
        except Exception:
            return False

    def save_datalake_file(self, filename: str, file_bytes: bytes, record_count: int = 0, source: str = "thoughtspot_email", data_type: str = "filiados") -> Optional[int]:
        """Salva uma cópia bruta imutável do arquivo no Data Lake com hash SHA-256 e tipo de dados."""
        import hashlib
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size = len(file_bytes)
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            if self.is_postgres:
                import psycopg2
                sql = """
                INSERT INTO datalake_raw_files (filename, file_hash, file_size_bytes, record_count, source, data_type, file_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING file_id;
                """
                cur.execute(sql, (filename, file_hash, file_size, record_count, source, data_type, psycopg2.Binary(file_bytes)))
                row = cur.fetchone()
                file_id = row[0] if row else None
            else:
                placeholder = "?"
                sql = f"""
                INSERT INTO datalake_raw_files (filename, file_hash, file_size_bytes, record_count, source, data_type, file_content)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});
                """
                cur.execute(sql, (filename, file_hash, file_size, record_count, source, data_type, sqlite3.Binary(file_bytes)))
                file_id = cur.lastrowid
            conn.commit()
            cur.close()
            return file_id
        except Exception:
            conn.rollback()
            return None
        finally:
            conn.close()

    def list_datalake_files(self, limit: int = 50) -> pd.DataFrame:
        """Lista os arquivos brutos armazenados no Data Lake (sem baixar os bytes do conteúdo)."""
        query = f"SELECT file_id, filename, file_hash, file_size_bytes, record_count, source, data_type, created_at FROM datalake_raw_files ORDER BY created_at DESC LIMIT {limit};"
        try:
            return self.execute_query(query)
        except Exception:
            return pd.DataFrame()

    def get_last_data_update_info(self, data_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retorna informações sobre a última atualização de acordo com o tipo:
        'filiados', 'certificacoes', 'voluntarios' ou geral se None.
        """
        try:
            placeholder = "%s" if self.is_postgres else "?"
            where_clause = f"WHERE data_type = {placeholder}" if data_type else ""
            params = (data_type,) if data_type else None
            
            df = self.execute_query(
                f"SELECT filename, created_at, record_count, source, data_type FROM datalake_raw_files {where_clause} ORDER BY created_at DESC LIMIT 1;",
                params
            )
            if not df.empty:
                row = df.iloc[0]
                dt = pd.to_datetime(row["created_at"])
                if dt.tzinfo is None:
                    dt_br = dt - pd.Timedelta(hours=3)
                else:
                    dt_br = dt.tz_convert("America/Sao_Paulo")
                
                type_labels = {
                    "filiados": "Filiados",
                    "certificacoes": "Certificações",
                    "voluntarios": "Voluntários"
                }
                curr_type = str(row.get("data_type", "filiados")).lower()
                type_label = type_labels.get(curr_type, "Base de Dados")
                
                return {
                    "timestamp": dt_br,
                    "formatted": dt_br.strftime("%d/%m/%Y às %H:%M"),
                    "filename": str(row["filename"]),
                    "source": str(row.get("source", "Data Lake")),
                    "data_type": type_label
                }
            
            # Fallbacks caso o Data Lake ainda não tenha registro para este tipo específico
            if data_type == "certificacoes":
                df_c = self.execute_query("SELECT count(*) as total, max(originalgrantdate) as max_d FROM certification;")
                if not df_c.empty and df_c.iloc[0]["total"] > 0:
                    max_d = str(df_c.iloc[0]["max_d"])
                    return {
                        "timestamp": None,
                        "formatted": f"Última concessão registrada: {max_d}",
                        "filename": "Carga de Certificações",
                        "source": "ETL",
                        "data_type": "Certificações"
                    }
            elif data_type == "voluntarios":
                df_v = self.execute_query("SELECT count(*) as total, max(application_service_start_date) as max_d FROM voluntary;")
                if not df_v.empty and df_v.iloc[0]["total"] > 0:
                    max_d = str(df_v.iloc[0]["max_d"])
                    return {
                        "timestamp": None,
                        "formatted": f"Última candidatura registrada: {max_d}",
                        "filename": "Carga de Voluntários",
                        "source": "ETL",
                        "data_type": "Voluntários"
                    }
            else:
                df_hist = self.execute_query("SELECT changed_at FROM person_history ORDER BY changed_at DESC LIMIT 1;")
                if not df_hist.empty:
                    dt = pd.to_datetime(df_hist.iloc[0]["changed_at"])
                    if dt.tzinfo is None:
                        dt_br = dt - pd.Timedelta(hours=3)
                    else:
                        dt_br = dt.tz_convert("America/Sao_Paulo")
                    return {
                        "timestamp": dt_br,
                        "formatted": dt_br.strftime("%d/%m/%Y às %H:%M"),
                        "filename": "Atualização Cadastral",
                        "source": "ETL",
                        "data_type": "Filiados"
                    }
        except Exception:
            pass
        return None

    def execute_query(self, query: str, params: Optional[Union[tuple, dict]] = None) -> pd.DataFrame:
        """
        Executa uma consulta SQL e retorna um DataFrame do Pandas.
        Utiliza cache inteligente em memória por 5 minutos (ttl=300) para máxima velocidade no Streamlit.
        """
        try:
            return _cached_query(self.connection_string or getattr(self, "db_file", "voluntariado.db"), query, params)
        except Exception:
            # Fallback direto sem cache se falhar
            conn = self.get_connection()
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    df = pd.read_sql_query(query, conn, params=params)
                if df.columns.duplicated().any():
                    df = df.loc[:, ~df.columns.duplicated(keep='first')]
                return df
            finally:
                conn.close()

    def execute_non_query(self, sql: str, params: Optional[Union[tuple, dict]] = None):
        """
        Executa comandos INSERT, UPDATE, DELETE ou DDL.
        """
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            conn.commit()
            cur.close()
            try:
                st.cache_data.clear()
            except Exception:
                pass
        finally:
            conn.close()

@st.cache_data(ttl=300, show_spinner=False)
def _cached_query(db_identifier: str, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
    conn = db_manager.get_connection()
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            df = pd.read_sql_query(query, conn, params=params)
        if df.columns.duplicated().any():
            df = df.loc[:, ~df.columns.duplicated(keep='first')]
        return df
    finally:
        conn.close()

# Instância padrão global
db_manager = DatabaseManager()


