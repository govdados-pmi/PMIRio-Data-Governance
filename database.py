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
        Verifica a conectividade com o banco de dados.
        A estrutura de tabelas (DDL) já está criada no PostgreSQL/Supabase.
        """
        try:
            conn = self.get_connection()
            conn.close()
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
        """Valida e-mail e senha e retorna dicionário com os dados do usuário autenticado."""
        pwd_hash = self.hash_password(password)
        placeholder = "%s" if self.is_postgres else "?"
        query = f"SELECT user_id, email, full_name, role, allowed_reports, is_active FROM app_user WHERE LOWER(email) = LOWER({placeholder}) AND password_hash = {placeholder};"
        
        df = self.execute_query(query, (email.strip(), pwd_hash))
        if not df.empty and df.iloc[0]["is_active"]:
            row = df.iloc[0]
            return {
                "user_id": int(row["user_id"]),
                "email": str(row["email"]),
                "full_name": str(row["full_name"]),
                "role": str(row["role"]),
                "allowed_reports": str(row["allowed_reports"]) if pd.notna(row.get("allowed_reports")) else None
            }
        return None

    def create_user(self, email: str, password: str, full_name: str, role: str, allowed_reports: Optional[str] = None) -> bool:
        """Cadastra um novo usuário no banco com controle de permissões de relatórios."""
        pwd_hash = self.hash_password(password)
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"INSERT INTO app_user (email, password_hash, full_name, role, allowed_reports) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});"
        try:
            self.execute_non_query(sql, (email.strip().lower(), pwd_hash, full_name.strip(), role.strip(), allowed_reports))
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
        """Atualiza a senha de um usuário no banco de dados com hash seguro."""
        pwd_hash = self.hash_password(new_password)
        placeholder = "%s" if self.is_postgres else "?"
        sql = f"UPDATE app_user SET password_hash = {placeholder} WHERE user_id = {placeholder};"
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


