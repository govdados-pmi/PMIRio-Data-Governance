import pandas as pd
import numpy as np
import os
import re
import warnings
import unicodedata
from datetime import datetime
from database import db_manager
try:
    from psycopg2.extras import execute_values
except ImportError:
    execute_values = None

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

def fast_batch_insert(cur, sql_postgres, sql_sqlite, data_tuples, page_size=5000):
    if not data_tuples:
        return
    if db_manager.is_postgres and execute_values:
        execute_values(cur, sql_postgres, data_tuples, page_size=page_size)
    else:
        placeholder = get_param_placeholder()
        sql = sql_sqlite.replace("%s", placeholder)
        for i in range(0, len(data_tuples), page_size):
            cur.executemany(sql, data_tuples[i:i + page_size])


def normalize_col_name(s) -> str:
    """Normaliza o nome de colunas removendo acentos, espaços e caracteres especiais."""
    if not s or pd.isna(s):
        return ""
    n = unicodedata.normalize('NFKD', str(s))
    n = "".join([c for c in n if not unicodedata.combining(c)])
    return n.lower().replace(" ", "").replace("_", "").replace("-", "").replace(".", "")

def auto_read_excel(file_path: str) -> pd.DataFrame:
    """
    Lê um arquivo Excel do ThoughtSpot tentando encontrar a linha de cabeçalho correta (header).
    O ThoughtSpot costuma inserir linhas de título no início dos exports.
    """
    for h in range(15):
        try:
            df = pd.read_excel(file_path, header=h)
            named_cols = [c for c in df.columns if not str(c).startswith("Unnamed")]
            if len(named_cols) >= 3:
                cols_str = " ".join([normalize_col_name(c) for c in named_cols])
                if any(k in cols_str for k in ["personid", "email", "applicants", "certification", "certificacao", "originaljoindate", "startdateforterm"]):
                    return df
        except Exception:
            pass
    return pd.read_excel(file_path)



def montar_nome_completo(first, middle, last) -> str:
    """
    Concatena nome, sobrenome e nome do meio limpando espaços extras e aplicando Title Case.
    """
    parts = []
    if pd.notna(first) and str(first).strip() and str(first).strip() != 'nan':
        parts.append(str(first).strip())
    if pd.notna(middle) and str(middle).strip() and str(middle).strip() != 'nan':
        parts.append(str(middle).strip())
    if pd.notna(last) and str(last).strip() and str(last).strip() != 'nan':
        parts.append(str(last).strip())
    
    full_name = " ".join(parts)
    return full_name.title() if full_name else ""

def clean_date(val):
    if pd.isna(val) or str(val).strip() == "" or str(val).strip() == "nan":
        return None
    try:
        dt = pd.to_datetime(val, errors="coerce")
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None

def clean_bool(val):
    if pd.isna(val):
        return None
    if isinstance(val, bool):
        return val
    try:
        if isinstance(val, (int, float)):
            if val == 1 or val == 1.0:
                return True
            if val == 0 or val == 0.0:
                return False
    except Exception:
        pass
    
    val_str = str(val).strip().lower()
    if val_str.endswith('.0'):
        val_str = val_str[:-2]
    
    if val_str in ["true", "1", "yes", "sim", "t", "y", "s", "receive", "enabled"]:
        return True
    if val_str in ["false", "0", "no", "não", "nao", "f", "n", "disabled"]:
        return False
    return None

def clean_str(val):
    if pd.isna(val) or str(val).strip() == "" or str(val).strip() == "nan":
        return None
    return str(val).strip()

def clean_int(val):
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except Exception:
        return None

def clean_float(val):
    if pd.isna(val) or str(val).strip() == "" or str(val).strip() == "nan":
        return None
    try:
        return float(val)
    except Exception:
        return None

def get_param_placeholder():
    return "%s" if db_manager.is_postgres else "?"

class ETLPipeline:
    def __init__(self):
        db_manager.init_db()

    def process_members(self, member_files: list[str]) -> dict:
        """
        Processa arquivos de filiados (Histórico e Mês Atual),
        atualizando as tabelas `person`, `membership` e `person_history`.
        """
        placeholder = get_param_placeholder()
        dfs = []
        for file_path in member_files:
            if os.path.exists(file_path):
                df = auto_read_excel(file_path)
                dfs.append(df)

        if not dfs:
            return {"status": "error", "message": "Nenhum arquivo de membros válido fornecido."}

        df_combined = pd.concat(dfs, ignore_index=True)
        
        # Padroniza nomes de colunas de forma ultra flexível
        cols_map = {}
        for col in df_combined.columns:
            c_clean = normalize_col_name(col)
            if "personid" in c_clean or c_clean == "id" or "person" in c_clean or "filiado" in c_clean:
                cols_map[col] = "personid"
            elif "firstname" in c_clean or "primeironome" in c_clean:
                cols_map[col] = "firstname"
            elif "middlename" in c_clean or "nomedomeio" in c_clean:
                cols_map[col] = "middlename"
            elif "lastname" in c_clean or "sobrenome" in c_clean:
                cols_map[col] = "lastname"
            elif "fullname" in c_clean or "nomecompleto" in c_clean:
                cols_map[col] = "fullname"
            elif "primaryemail" in c_clean or "email" in c_clean:
                cols_map[col] = "primaryemail"
            elif "primaryphone" in c_clean or "telefone" in c_clean or "phone" in c_clean:
                cols_map[col] = "primaryphone"
            elif "originaljoindate" in c_clean or "dataprimeirafiliacao" in c_clean or "joindate" in c_clean:
                cols_map[col] = "originaljoindate"
            elif "startdateforterm" in c_clean or "startdate" in c_clean or "inicio" in c_clean:
                cols_map[col] = "startdateforterm"
            elif "enddateforterm" in c_clean or "enddate" in c_clean or "dataexpiracao" in c_clean or "expiracao" in c_clean:
                cols_map[col] = "enddateforterm"
            elif "plannameforchapters" in c_clean or "classificacao" in c_clean or "plan" in c_clean:
                cols_map[col] = "plannameforchapters"
            elif "autorenewstatus" in c_clean or "renovacaoautomatica" in c_clean or "autorenew" in c_clean:
                cols_map[col] = "autorenewstatus"
            elif "issinglemembership" in c_clean or "singlemembership" in c_clean:
                cols_map[col] = "issinglemembership"
            elif any(k in c_clean for k in ["isreceiveelectronicnotifications", "electronicnotifications", "receiveelectronic", "electronicnotification", "notificacoeseletronicas", "notificacaoeletronica", "receiveelectronicnotif"]):
                cols_map[col] = "isreceiveelectronicnotifications"
            elif "industry" in c_clean or "industria" in c_clean:
                cols_map[col] = "industry"
            elif "jobtittle" in c_clean or "jobtitle" in c_clean or "cargo" in c_clean:
                cols_map[col] = "jobtittle"
            elif "primaryaddress" in c_clean or "address" in c_clean or "endereco" in c_clean:
                cols_map[col] = "primaryaddress"
            elif "primaryzip" in c_clean or "zip" in c_clean or "cep" in c_clean:
                cols_map[col] = "primaryzip"
            elif "primarycity" in c_clean or "city" in c_clean or "cidade" in c_clean:
                cols_map[col] = "primarycity"
            elif "tenureinyears" in c_clean or "tenure" in c_clean:
                cols_map[col] = "tenureinyears"
            elif any(k in c_clean for k in ["certificationlist", "certificacoes", "certifications", "certification"]):
                cols_map[col] = "certificationlist"


        df_combined = df_combined.rename(columns=cols_map)
        # Remove colunas duplicadas que tenham sido mapeadas com o mesmo nome
        df_combined = df_combined.loc[:, ~df_combined.columns.duplicated(keep='first')]
        
        # Validação segura da coluna personid
        if 'personid' not in df_combined.columns:
            return {
                "status": "error",
                "message": f"Coluna de identificação ('personid' ou 'Person ID') não foi encontrada no arquivo enviado. Colunas detectadas: {list(df_combined.columns)}"
            }

        # Garante personid válido
        df_combined = df_combined[df_combined['personid'].notna()]
        df_combined['personid'] = df_combined['personid'].astype(int)

        # Trata nome completo (Vetorizado para alta performance)
        if 'fullname' not in df_combined.columns:
            f_col = df_combined['firstname'].fillna('').astype(str).str.strip() if 'firstname' in df_combined.columns else ''
            m_col = df_combined['middlename'].fillna('').astype(str).str.strip() if 'middlename' in df_combined.columns else ''
            l_col = df_combined['lastname'].fillna('').astype(str).str.strip() if 'lastname' in df_combined.columns else ''
            
            combined_names = (f_col + ' ' + m_col + ' ' + l_col).str.replace(r'\s+', ' ', regex=True).str.strip()
            df_combined['fullname'] = combined_names.str.title()

        # Converte para dicionários nativos Python para performance máxima (80k+ registros)
        records = df_combined.to_dict('records')

        persons_inserted = 0
        persons_updated = 0
        history_records_created = 0
        memberships_inserted = 0
        memberships_skipped = 0

        conn = db_manager.get_connection()
        cur = conn.cursor()

        try:
            # 1. Carrega dados de pessoas existentes do banco para comparação
            cur.execute("SELECT personid, primaryemail, primaryphone, primaryaddress FROM person;")
            existing_persons = {}
            for row in cur.fetchall():
                pid, email, phone, addr = row[0], row[1], row[2], row[3]
                existing_persons[pid] = {
                    "email": email or "",
                    "phone": phone or "",
                    "address": addr or ""
                }

            # Prepara lista de pessoas únicas a partir dos registros
            unique_persons = {}
            for row in records:
                pid = clean_int(row.get('personid'))
                if not pid:
                    continue
                email = clean_str(row.get('primaryemail'))
                if email:
                    email = email.lower()
                
                p_data = {
                    "pid": pid,
                    "fullname": clean_str(row.get('fullname')),
                    "email": email,
                    "phone": clean_str(row.get('primaryphone')),
                    "address": clean_str(row.get('primaryaddress')),
                    "industry": clean_str(row.get('industry')),
                    "jobtittle": clean_str(row.get('jobtittle')),
                    "primaryzip": clean_str(row.get('primaryzip')),
                    "primarycity": clean_str(row.get('primarycity')),
                    "alternativeemail": clean_str(row.get('alternativeemail'))
                }
                unique_persons[pid] = p_data

            # Processa inserção/atualização de pessoas + histórico
            insert_person_sql = f"""
            INSERT INTO person (personid, fullname, primaryemail, primaryphone, primaryaddress, industry, jobtittle, primaryzip, primarycity, alternativeemail)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});
            """

            update_person_sql = f"""
            UPDATE person 
            SET fullname = COALESCE({placeholder}, fullname),
                primaryemail = COALESCE({placeholder}, primaryemail),
                primaryphone = COALESCE({placeholder}, primaryphone),
                primaryaddress = COALESCE({placeholder}, primaryaddress),
                industry = COALESCE({placeholder}, industry),
                jobtittle = COALESCE({placeholder}, jobtittle),
                primaryzip = COALESCE({placeholder}, primaryzip),
                primarycity = COALESCE({placeholder}, primarycity),
                alternativeemail = COALESCE({placeholder}, alternativeemail)
            WHERE personid = {placeholder};
            """

            insert_history_sql = f"""
            INSERT INTO person_history (personid, field_changed, old_value, new_value)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder});
            """

            new_persons_batch = []
            history_batch = []
            update_persons_batch = []

            for pid, p in unique_persons.items():
                if pid not in existing_persons:
                    p_tuple = (
                        pid, p["fullname"], p["email"], p["phone"], p["address"],
                        p["industry"], p["jobtittle"], p["primaryzip"], p["primarycity"], p["alternativeemail"]
                    )
                    new_persons_batch.append(p_tuple)
                    existing_persons[pid] = {
                        "email": p["email"] or "",
                        "phone": p["phone"] or "",
                        "address": p["address"] or ""
                    }
                else:
                    old_p = existing_persons[pid]
                    changed = False
                    alt_email_to_save = None

                    field_checks = [
                        ("primaryemail", old_p["email"], p["email"]),
                        ("primaryphone", old_p["phone"], p["phone"]),
                        ("primaryaddress", old_p["address"], p["address"])
                    ]

                    for field_name, old_val, new_val in field_checks:
                        if new_val and old_val != new_val:
                            history_batch.append((pid, field_name, old_val, new_val))
                            changed = True
                            if field_name == "primaryemail":
                                alt_email_to_save = old_val

                    if not alt_email_to_save:
                        alt_email_to_save = p["alternativeemail"]

                    if changed:
                        update_persons_batch.append((
                            p["fullname"], p["email"], p["phone"], p["address"],
                            p["industry"], p["jobtittle"], p["primaryzip"], p["primarycity"], alt_email_to_save, pid
                        ))
                        existing_persons[pid] = {
                            "email": p["email"] if p["email"] else old_p["email"],
                            "phone": p["phone"] if p["phone"] else old_p["phone"],
                            "address": p["address"] if p["address"] else old_p["address"]
                        }

            # Executa inserções e atualizações em lote (chunking para performance na nuvem)
            batch_size = 1000
            if new_persons_batch:
                for i in range(0, len(new_persons_batch), batch_size):
                    cur.executemany(insert_person_sql, new_persons_batch[i:i + batch_size])
                persons_inserted = len(new_persons_batch)

            if history_batch:
                for i in range(0, len(history_batch), batch_size):
                    cur.executemany(insert_history_sql, history_batch[i:i + batch_size])
                history_records_created = len(history_batch)

            if update_persons_batch:
                for i in range(0, len(update_persons_batch), batch_size):
                    cur.executemany(update_person_sql, update_persons_batch[i:i + batch_size])
                persons_updated = len(update_persons_batch)

            # 2. Processa tabela MEMBERSHIP em lote (Incremental por personid + startdateforterm)
            cur.execute("SELECT personid, startdateforterm FROM membership WHERE startdateforterm IS NOT NULL;")
            existing_memberships = set((row[0], str(row[1])) for row in cur.fetchall())

            insert_membership_sql = f"""
            INSERT INTO membership (personid, originaljoindate, startdateforterm, enddateforterm, plannameforchapters, autorenewstatus, issinglemembership, isreceiveelectronicnotifications, tenureinyears)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});
            """

            new_memberships_batch = []

            for row in records:
                pid = clean_int(row.get('personid'))
                if not pid:
                    continue
                
                orig_dt_str = clean_date(row.get('originaljoindate'))
                start_dt_str = clean_date(row.get('startdateforterm'))
                end_dt_str = clean_date(row.get('enddateforterm'))
                
                m_key = (pid, str(start_dt_str)) if start_dt_str else None

                if m_key and m_key in existing_memberships:
                    memberships_skipped += 1
                    continue

                # Trata tenureinyears: se não vier preenchido no Excel, calcula com base em startdateforterm e originaljoindate
                tenure_val = clean_float(row.get('tenureinyears'))
                if tenure_val is None:
                    try:
                        d_orig = pd.to_datetime(orig_dt_str) if orig_dt_str else None
                        d_start = pd.to_datetime(start_dt_str) if start_dt_str else None
                        d_end = pd.to_datetime(end_dt_str) if end_dt_str else None
                        
                        if d_start and d_orig and d_start >= d_orig:
                            days_diff = (d_start - d_orig).days
                            tenure_val = round(days_diff / 365.25, 2)
                        elif d_end and d_orig and d_end >= d_orig:
                            days_diff = (d_end - d_orig).days
                            tenure_val = round(days_diff / 365.25, 2)
                        elif d_orig:
                            days_diff = (datetime.now() - d_orig).days
                            tenure_val = round(days_diff / 365.25, 2)
                    except Exception:
                        tenure_val = None

                m_tuple = (
                    pid,
                    orig_dt_str,
                    start_dt_str,
                    end_dt_str,
                    clean_str(row.get('plannameforchapters')),
                    clean_str(row.get('autorenewstatus')),
                    clean_bool(row.get('issinglemembership')),
                    clean_bool(row.get('isreceiveelectronicnotifications')),
                    tenure_val
                )
                new_memberships_batch.append(m_tuple)

                if m_key:
                    existing_memberships.add(m_key)

            if new_memberships_batch:
                batch_size = 1000
                for i in range(0, len(new_memberships_batch), batch_size):
                    cur.executemany(insert_membership_sql, new_memberships_batch[i:i + batch_size])
                memberships_inserted = len(new_memberships_batch)

            conn.commit()

            return {
                "status": "success",
                "persons_inserted": persons_inserted,
                "persons_updated": persons_updated,
                "history_records_created": history_records_created,
                "memberships_inserted": memberships_inserted,
                "memberships_skipped": memberships_skipped
            }


        except Exception as e:
            conn.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def process_certifications(self, cert_files: list[str]) -> dict:
        """
        Processa planilhas de certificações, atualizando `person` e `certification`.
        """
        placeholder = get_param_placeholder()
        dfs = []
        for file_path in cert_files:
            if os.path.exists(file_path):
                df = auto_read_excel(file_path)
                dfs.append(df)

        if not dfs:
            return {"status": "error", "message": "Nenhum arquivo de certificação fornecido."}

        df_combined = pd.concat(dfs, ignore_index=True)
        
        # Mapeamento de colunas ultra flexível
        cols_map = {}
        for col in df_combined.columns:
            c_clean = normalize_col_name(col)
            if "personid" in c_clean or c_clean == "id" or "person" in c_clean or "filiado" in c_clean or "memberid" in c_clean:
                cols_map[col] = "personid"
            elif "certificationid" in c_clean or "idcertificacao" in c_clean or "certificacaoid" in c_clean:
                cols_map[col] = "certificationid"
            elif any(k in c_clean for k in ["certificationtypename", "certificacao", "type", "nomecertificacao", "tipocertificacao"]):
                cols_map[col] = "certificationtypename"
            elif any(k in c_clean for k in ["originalgrantdate", "grantdate", "dataconcessao", "concessao", "dataoutorga", "outorga", "dategranted"]):
                cols_map[col] = "originalgrantdate"
            elif any(k in c_clean for k in ["effectivestartdate", "startdate", "datainicio", "inicio"]):
                cols_map[col] = "effectivestartdate"
            elif any(k in c_clean for k in ["effectiveenddate", "enddate", "dataexpiracao", "expiracao", "datafim", "fim"]):
                cols_map[col] = "effectiveenddate"
            elif any(k in c_clean for k in ["certificationstatusname", "statuscertificacao", "status"]):
                cols_map[col] = "certificationstatusname"
            elif any(k in c_clean for k in ["totalcycleseqno", "cycleseqno", "qtdeciclos", "ciclos"]):
                cols_map[col] = "total_cycleseqno"
            elif "firstname" in c_clean or "primeironome" in c_clean:
                cols_map[col] = "firstname"
            elif "middlename" in c_clean or "nomedomeio" in c_clean:
                cols_map[col] = "middlename"
            elif "lastname" in c_clean or "sobrenome" in c_clean:
                cols_map[col] = "lastname"
            elif "fullname" in c_clean or "nomecompleto" in c_clean:
                cols_map[col] = "fullname"
            elif "primaryemail" in c_clean or "email" in c_clean:
                cols_map[col] = "primaryemail"
            elif "primaryphone" in c_clean or "phone" in c_clean or "telefone" in c_clean:
                cols_map[col] = "primaryphone"

        df_combined = df_combined.rename(columns=cols_map)
        df_combined = df_combined.loc[:, ~df_combined.columns.duplicated(keep='first')]

        if 'personid' not in df_combined.columns:
            return {
                "status": "error",
                "message": f"Coluna de identificação ('personid' ou 'Person ID') não foi encontrada no arquivo de certificações. Colunas detectadas: {list(df_combined.columns)}"
            }

        df_combined = df_combined[df_combined['personid'].notna()]
        df_combined['personid'] = df_combined['personid'].astype(int)

        # Garante nome completo
        if 'fullname' not in df_combined.columns:
            f_name = df_combined['firstname'] if 'firstname' in df_combined.columns else pd.Series()
            m_name = df_combined['middlename'] if 'middlename' in df_combined.columns else pd.Series()
            l_name = df_combined['lastname'] if 'lastname' in df_combined.columns else pd.Series()
            
            names = []
            for i in range(len(df_combined)):
                first = f_name.iloc[i] if not f_name.empty else ""
                mid = m_name.iloc[i] if not m_name.empty else ""
                last = l_name.iloc[i] if not l_name.empty else ""
                names.append(montar_nome_completo(first, mid, last))
            df_combined['fullname'] = names

        certs_inserted = 0
        conn = db_manager.get_connection()
        cur = conn.cursor()

        try:
            # Upsert na tabela PERSON em lote para garantir foreign key
            person_sql_pg = "INSERT INTO person (personid, fullname, primaryemail, primaryphone) VALUES %s ON CONFLICT (personid) DO UPDATE SET fullname = EXCLUDED.fullname;"
            person_sql_sqlite = "INSERT INTO person (personid, fullname, primaryemail, primaryphone) VALUES (%s, %s, %s, %s) ON CONFLICT (personid) DO UPDATE SET fullname = excluded.fullname;"

            unique_person_tuples = {}
            for idx, row in df_combined.iterrows():
                pid = clean_int(row['personid'])
                if not pid or pid in unique_person_tuples:
                    continue
                email = clean_str(row.get('primaryemail'))
                if email:
                    email = email.lower()
                unique_person_tuples[pid] = (pid, clean_str(row.get('fullname')), email, clean_str(row.get('primaryphone')))

            person_tuples = list(unique_person_tuples.values())
            if person_tuples:
                fast_batch_insert(cur, person_sql_pg, person_sql_sqlite, person_tuples, page_size=5000)


            # Inserção incremental na tabela CERTIFICATION
            cur.execute("SELECT certificationid, personid, certificationtypename FROM certification;")
            existing_certs = set(
                (clean_int(r[0]), clean_int(r[1]), clean_str(r[2]).upper() if r[2] else "") for r in cur.fetchall()
            )
            
            sql_pg = "INSERT INTO certification (certificationid, personid, certificationtypename, originalgrantdate, effectivestartdate, effectiveenddate, certificationstatusname, total_cycleseqno) VALUES %s ON CONFLICT (certificationid) DO NOTHING;"
            sql_sqlite = "INSERT INTO certification (certificationid, personid, certificationtypename, originalgrantdate, effectivestartdate, effectiveenddate, certificationstatusname, total_cycleseqno) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (certificationid) DO NOTHING;"

            new_certs_batch = []
            certs_skipped = 0

            for row in df_combined.to_dict('records'):
                pid = clean_int(row.get('personid'))
                if not pid:
                    continue

                ctype = clean_str(row.get('certificationtypename'))
                if not ctype:
                    continue

                start_dt = clean_date(row.get('effectivestartdate'))
                grant_dt = clean_date(row.get('originalgrantdate')) or start_dt or datetime.now().strftime("%Y-%m-%d")
                if not start_dt:
                    start_dt = grant_dt

                cid = clean_int(row.get('certificationid'))
                if not cid:
                    # Auto-gera ID determinístico se não vier na planilha
                    cid = abs(hash(f"{pid}_{ctype.upper()}_{grant_dt}")) % (10**12)

                c_key = (cid, pid, ctype.upper())

                if c_key in existing_certs:
                    certs_skipped += 1
                    continue

                c_tuple = (
                    cid,
                    pid,
                    ctype,
                    grant_dt,
                    start_dt,
                    clean_date(row.get('effectiveenddate')),
                    clean_str(row.get('certificationstatusname')) or 'Active',
                    clean_int(row.get('total_cycleseqno'))
                )
                new_certs_batch.append(c_tuple)
                existing_certs.add(c_key)

            if new_certs_batch:
                fast_batch_insert(cur, sql_pg, sql_sqlite, new_certs_batch, page_size=5000)
                certs_inserted = len(new_certs_batch)


            conn.commit()

            return {
                "status": "success",
                "certifications_inserted": certs_inserted,
                "certifications_skipped": certs_skipped
            }

        except Exception as e:
            conn.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

    def process_volunteers(self, vol_file: str) -> dict:
        """
        Processa a planilha Voluntarios.xlsx com a regra de negócio do notebook (célula 103):
        - Ordena por data de início descendente
        - Filtra e-mails únicos (exclui duplicados)
        - Exclui candidaturas com status 'Complete'
        """
        placeholder = get_param_placeholder()
        if not os.path.exists(vol_file):
            return {"status": "error", "message": f"Arquivo {vol_file} não encontrado."}

        df = auto_read_excel(vol_file)

        # Mapeamento de colunas
        cols_map = {}
        for col in df.columns:
            c_low = col.lower()
            if "personid" in c_low or "id" == c_low:
                cols_map[col] = "personid"
            elif "applicants" in c_low or "nome" in c_low:
                cols_map[col] = "applicants"
            elif "opportunity name" in c_low or "oportunidade" in c_low:
                cols_map[col] = "opportunity_name"
            elif "opportunity description" in c_low or "descricao" in c_low:
                cols_map[col] = "opportunity_description"
            elif "application status" in c_low or "status" in c_low:
                cols_map[col] = "application_status"
            elif "email address" in c_low or "email" in c_low:
                cols_map[col] = "email_address"
            elif "start date" in c_low:
                cols_map[col] = "application_service_start_date"
            elif "end date" in c_low:
                cols_map[col] = "application_service_end_date"

        df = df.rename(columns=cols_map)

        # Regra do Notebook (Célula 103):
        # 1) Converter data para datetime
        df['application_service_start_date'] = pd.to_datetime(df['application_service_start_date'], errors='coerce')
        # 2) Ordenar do mais novo para o mais antigo
        df = df.sort_values(by='application_service_start_date', ascending=False).reset_index(drop=True)
        # 3) Email minúsculo
        if 'email_address' in df.columns:
            df['email_address'] = df['email_address'].astype(str).str.lower().str.strip()
            # 4) Filtrar emails únicos (sem repetição)
            email_counts = df['email_address'].value_counts()
            df['email_count'] = df['email_address'].map(email_counts)
            df = df[df['email_count'] == 1]
            df = df.drop(columns=['email_count'])
        
        # 5) Excluir status 'Complete'
        if 'application_status' in df.columns:
            df = df[df['application_status'] != 'Complete']

        vols_inserted = 0
        conn = db_manager.get_connection()
        cur = conn.cursor()

        try:
            cur.execute("DELETE FROM voluntary;")

            vol_sql = f"""
            INSERT INTO voluntary (personid, applicants, opportunity_name, application_status, opportunity_description, email_address, application_service_start_date, application_service_end_date)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});
            """

            for idx, row in df.iterrows():
                pid = clean_int(row.get('personid'))
                start_dt = clean_date(row.get('application_service_start_date'))
                end_dt = clean_date(row.get('application_service_end_date'))
                
                v_tuple = (
                    pid,
                    clean_str(row.get('applicants')),
                    clean_str(row.get('opportunity_name')),
                    clean_str(row.get('application_status')),
                    clean_str(row.get('opportunity_description')),
                    clean_str(row.get('email_address')),
                    start_dt,
                    end_dt
                )
                cur.execute(vol_sql, v_tuple)
                vols_inserted += 1

            conn.commit()
            return {"status": "success", "volunteers_inserted": vols_inserted}
        except Exception as e:
            conn.rollback()
            return {"status": "error", "message": str(e)}
        finally:
            conn.close()

pipeline = ETLPipeline()
