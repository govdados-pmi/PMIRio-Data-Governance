import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import hashlib
from typing import Optional, Union, Any, Dict

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

class DatabaseManager:
    def __init__(self, connection_string: Optional[str] = None):
        """
        Inicializa o gerenciador de banco de dados.
        Suporta o banco PostgreSQL hospedado no Supabase nativamente via:
        - SUPABASE_DB_URL / DATABASE_URL / POSTGRES_URL
        - Variáveis individuais (SUPABASE_PROJECT_REF, SUPABASE_DB_PASSWORD, PGHOST, etc.)
        - Fallback resiliente para SQLite ('voluntariado.db') se sem credenciais ativas.
        """
        # 1. Tenta pegar de parâmetro explícito ou variáveis de ambiente
        self.connection_string = connection_string or os.getenv("SUPABASE_DB_URL") or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
        
        # 2. Tenta pegar de st.secrets do Streamlit (Streamlit Cloud ou .streamlit/secrets.toml)
        if not self.connection_string:
            try:
                import streamlit as st
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

        self.is_postgres = False
        
        # Verifica se forneceu URL direta do Supabase/Postgres
        if self.connection_string and ("postgresql" in self.connection_string or "postgres" in self.connection_string or "supabase" in self.connection_string):
            self.is_postgres = True
        else:
            # Verifica se possui variáveis do Supabase
            supabase_ref = os.getenv("SUPABASE_PROJECT_REF")
            supabase_pass = os.getenv("SUPABASE_DB_PASSWORD") or os.getenv("PGPASSWORD")
            pghost = os.getenv("PGHOST") or (f"db.{supabase_ref}.supabase.co" if supabase_ref else None)
            pgdb = os.getenv("PGDATABASE", "postgres")
            pguser = os.getenv("PGUSER", "postgres")
            pgport = os.getenv("PGPORT", "5432")
            
            if pghost and supabase_pass:
                self.connection_string = f"postgresql://{pguser}:{supabase_pass}@{pghost}:{pgport}/{pgdb}"
                self.is_postgres = True
            else:
                self.db_file = os.getenv("SQLITE_DB_PATH", "voluntariado.db")
                self.is_postgres = False

    def update_connection(self, connection_string: str):
        """
        Permite atualizar a string de conexão em tempo de execução (ex: via UI do Streamlit).
        """
        self.connection_string = connection_string
        if "postgresql" in connection_string or "postgres" in connection_string or "supabase" in connection_string:
            self.is_postgres = True
        else:
            self.is_postgres = False

    def get_connection(self):
        if self.is_postgres:
            return psycopg2.connect(self.connection_string)
        else:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            return conn

    @staticmethod
    def hash_password(password: str) -> str:
        """Gera hash SHA-256 com salt estático para armazenamento seguro de senhas."""
        salt = "pmi_rio_gov_dados_salt_2026"
        return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

    def init_db(self, schema_file: str = "schema.sql"):
        """
        Executa o DDL de criação das tabelas se elas não existirem e insere os usuários padrão.
        """
        with open(schema_file, "r", encoding="utf-8") as f:
            sql_script = f.read()

        conn = self.get_connection()
        try:
            cur = conn.cursor()
            if self.is_postgres:
                # Garante CREATE TABLE IF NOT EXISTS no Postgres
                pg_script = sql_script.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
                cur.execute(pg_script)
                conn.commit()
            else:
                # Para SQLite, converte os tipos SERIAL -> INTEGER PRIMARY KEY AUTOINCREMENT
                sqlite_script = sql_script.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
                sqlite_script = sqlite_script.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
                cur.executescript(sqlite_script)
                conn.commit()
            cur.close()

            # Migração graciosa de colunas/tabelas novas para bancos já existentes
            conn_mig = self.get_connection()
            cur_mig = conn_mig.cursor()
            try:
                # 1. Adiciona colunas novas se não existirem
                for alter_sql in [
                    "ALTER TABLE membership ADD COLUMN tenureinyears NUMERIC;",
                    "ALTER TABLE person ADD COLUMN alternativeemail VARCHAR;",
                    "ALTER TABLE app_user ADD COLUMN allowed_reports VARCHAR;",
                    "ALTER TABLE app_user ADD COLUMN is_active BOOLEAN DEFAULT TRUE;"
                ]:
                    try:
                        cur_mig.execute(alter_sql)
                        conn_mig.commit()
                    except Exception:
                        conn_mig.rollback()

                # 2. Cria person_history se não existir
                ph_sql = """
                CREATE TABLE IF NOT EXISTS person_history (
                    history_id SERIAL PRIMARY KEY,
                    personid BIGINT REFERENCES person (personid),
                    field_changed VARCHAR NOT NULL,
                    old_value VARCHAR,
                    new_value VARCHAR,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """ if self.is_postgres else """
                CREATE TABLE IF NOT EXISTS person_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    personid BIGINT REFERENCES person (personid),
                    field_changed VARCHAR NOT NULL,
                    old_value VARCHAR,
                    new_value VARCHAR,
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
                cur_mig.execute(ph_sql)
                conn_mig.commit()

                # 3. Cria custom_report se não existir
                cr_sql = """
                CREATE TABLE IF NOT EXISTS custom_report (
                    report_id SERIAL PRIMARY KEY,
                    report_name VARCHAR NOT NULL,
                    sql_query TEXT NOT NULL,
                    description VARCHAR,
                    created_by VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """ if self.is_postgres else """
                CREATE TABLE IF NOT EXISTS custom_report (
                    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_name VARCHAR NOT NULL,
                    sql_query TEXT NOT NULL,
                    description VARCHAR,
                    created_by VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
                cur_mig.execute(cr_sql)
                conn_mig.commit()
            finally:
                conn_mig.close()
        finally:
            conn.close()

        self.seed_default_users()

    def seed_default_users(self):
        """Insere ou atualiza os usuários padrão de cada diretoria."""
        placeholder = "%s" if self.is_postgres else "?"
        
        # Atualiza admin@pmirio.org.br para govdados@pmirio.org.br se existir
        try:
            self.execute_non_query(
                f"UPDATE app_user SET email = {placeholder} WHERE LOWER(email) = {placeholder};",
                ("govdados@pmirio.org.br", "admin@pmirio.org.br")
            )
        except Exception:
            pass

        default_users = [
            ("govdados@pmirio.org.br", self.hash_password("admin123"), "Administrador de Dados", "admin"),
            ("filiacao@pmirio.org.br", self.hash_password("filiacao123"), "Diretoria de Filiação", "view"),
            ("voluntariado@pmirio.org.br", self.hash_password("voluntarios123"), "Diretoria de Voluntariado", "view"),
            ("certificacao@pmirio.org.br", self.hash_password("certificacao123"), "Diretoria de Certificação", "view")
        ]
        
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            for email, pwd_hash, name, role in default_users:
                # Verifica se o e-mail já existe
                cur.execute(f"SELECT 1 FROM app_user WHERE LOWER(email) = LOWER({placeholder});", (email,))
                if not cur.fetchone():
                    sql = f"""
                    INSERT INTO app_user (email, password_hash, full_name, role)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder});
                    """
                    cur.execute(sql, (email, pwd_hash, name, role))
            conn.commit()
            cur.close()
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

    # =========================================================================
    # RELATÓRIOS PERSONALIZADOS SALVOS VIA CONSOLE SQL
    # =========================================================================
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
        Garante que nomes de colunas duplicados (oriundos de JOINs com SELECT *) sejam tratados com segurança.
        """
        conn = self.get_connection()
        try:
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

# Instância padrão global
db_manager = DatabaseManager()

