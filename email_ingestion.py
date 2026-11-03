import os
import sys
import time
import imaplib
import email
from email.header import decode_header
import hashlib
from datetime import datetime
import warnings
from typing import Optional, Dict, Any, List

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from database import db_manager
from etl import pipeline

def get_clean_env_pwd(var_name: str) -> str:
    val = os.getenv(var_name, "")
    # Remove aspas e espaços que o Google costuma gerar na senha de app
    return val.strip().strip("'\"").replace(" ", "")

def decode_mime_words(s: Optional[str]) -> str:
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    result = []
    for frag, enc in decoded_fragments:
        if isinstance(frag, bytes):
            result.append(frag.decode(enc or "utf-8", errors="ignore"))
        else:
            result.append(str(frag))
def detect_dataset_type(filename: str, file_path: str = None) -> str:
    """Detecta automaticamente se a planilha é de filiados, certificações ou voluntários."""
    fn_lower = filename.lower()
    if any(k in fn_lower for k in ["certif", "pmp", "capm", "acp", "pgmp", "pfmp"]):
        return "certificacoes"
    if any(k in fn_lower for k in ["volunt", "candidat", "opportunit"]):
        return "voluntarios"
    if any(k in fn_lower for k in ["filiad", "member", "membership"]):
        return "filiados"
    
    # Se o nome for genérico, inspeciona as colunas da planilha
    if file_path and os.path.exists(file_path):
        try:
            from etl import auto_read_excel
            sample_df = auto_read_excel(file_path)
            cols_str = " ".join([str(c).lower() for c in sample_df.columns])
            if any(k in cols_str for k in ["certification", "certificacao", "grantdate", "cycleseqno"]):
                return "certificacoes"
            if any(k in cols_str for k in ["applicant", "opportunity", "application_status"]):
                return "voluntarios"
        except Exception:
            pass
    return "filiados"

class EmailDataLakeIngestion:
    def __init__(self):
        self.gmail_user = os.getenv("GMAIL_USER", "").strip()
        self.gmail_password = get_clean_env_pwd("GMAIL_APP_PASSWORD")
        self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.imap_port = int(os.getenv("IMAP_PORT", "993"))
        self.datalake_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datalake", "filiados")
        os.makedirs(self.datalake_dir, exist_ok=True)

    def connect(self) -> imaplib.IMAP4_SSL:
        if not self.gmail_user or not self.gmail_password:
            raise ValueError(
                "Credenciais do Gmail não configuradas. Verifique se GMAIL_USER e GMAIL_APP_PASSWORD "
                "estão preenchidas no arquivo .env ou nos Secrets do GitHub Actions."
            )
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Conectando a {self.imap_server}:{self.imap_port}...")
        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        mail.login(self.gmail_user, self.gmail_password)
        print(f"Autenticação estabelecida com sucesso para {self.gmail_user}!")
        return mail

    def check_already_ingested(self, file_hash: str) -> bool:
        """Verifica no Data Lake se o arquivo com esse hash já foi processado anteriormente."""
        try:
            placeholder = "%s" if db_manager.is_postgres else "?"
            query = f"SELECT file_id, filename, created_at FROM datalake_raw_files WHERE file_hash = {placeholder} LIMIT 1;"
            df = db_manager.execute_query(query, (file_hash,))
            if not df.empty:
                return True
        except Exception as e:
            print(f"Aviso ao consultar hash no Data Lake: {e}")
        return False

    def sync_latest_filiados(self, force: bool = False) -> Dict[str, Any]:
        """
        Busca e-mails enviados pelo ThoughtSpot ou contendo planilhas de filiados,
        salva no Data Lake e executa o pipeline ETL de atualização.
        """
        mail = self.connect()
        try:
            mail.select("INBOX")
            
            # 1. Estratégia de busca: primeiro e-mails não lidos, depois mais recentes do ThoughtSpot
            search_queries = [
                '(UNSEEN FROM "thoughtspot")',
                '(UNSEEN SUBJECT "ThoughtSpot")',
                '(UNSEEN SUBJECT "Liveboard")',
                '(UNSEEN SUBJECT "Filiados")',
                '(FROM "thoughtspot")',
                '(SUBJECT "Liveboard")',
                '(SUBJECT "Filiados")'
            ]
            
            candidate_ids = []
            for query in search_queries:
                status, data = mail.search(None, query)
                if status == "OK" and data[0]:
                    ids = data[0].split()
                    for mid in reversed(ids):
                        if mid not in candidate_ids:
                            candidate_ids.append(mid)
                if candidate_ids and "UNSEEN" in query:
                    # Encontrou não lidos prioritários
                    break

            if not candidate_ids:
                print("Nenhum e-mail correspondente do ThoughtSpot encontrado na caixa de entrada.")
                return {"status": "empty", "message": "Nenhum e-mail correspondente encontrado."}

            print(f"Analisando {len(candidate_ids)} e-mail(s) candidato(s)...")

            processed_count = 0
            for msg_id in candidate_ids[:10]: # Analisa até os 10 mais recentes
                status, data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not data or not data[0]:
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = decode_mime_words(msg.get("Subject"))
                sender = decode_mime_words(msg.get("From"))
                date_str = msg.get("Date")

                # Procura anexos .xlsx ou .csv
                attachments = []
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    filename = part.get_filename()
                    if filename:
                        filename = decode_mime_words(filename)
                    
                    if filename and any(filename.lower().endswith(ext) for ext in [".xlsx", ".csv"]):
                        file_bytes = part.get_payload(decode=True)
                        if file_bytes:
                            attachments.append((filename, file_bytes))

                if not attachments:
                    continue

                print(f"\n==================================================")
                print(f"E-mail Encontrado: '{subject}'")
                print(f"Remetente: {sender}")
                print(f"Data: {date_str}")
                print(f"Anexos detectados: {[att[0] for att in attachments]}")

                for filename, file_bytes in attachments:
                    file_hash = hashlib.sha256(file_bytes).hexdigest()
                    print(f"\nAnalisando anexo: {filename} ({len(file_bytes)} bytes)")
                    print(f"Hash SHA-256: {file_hash}")

                    if not force and self.check_already_ingested(file_hash):
                        print(f"ℹ️ O anexo '{filename}' (hash {file_hash[:10]}...) já foi processado anteriormente no Data Lake. Pulando duplicidade.")
                        continue

                    # 1. Salva cópia local particionada por Ano/Mês
                    today = datetime.now()
                    partition_path = os.path.join(self.datalake_dir, today.strftime("%Y"), today.strftime("%m"))
                    os.makedirs(partition_path, exist_ok=True)
                    
                    clean_filename = f"{today.strftime('%Y%m%d_%H%M%S')}_{filename}"
                    local_file_path = os.path.join(partition_path, clean_filename)
                    
                    with open(local_file_path, "wb") as f:
                        f.write(file_bytes)
                    print(f"💾 Cópia salva no Data Lake local: {local_file_path}")

                    # 2. Detecta o tipo de base e executa o Pipeline correspondente
                    detected_type = detect_dataset_type(filename, local_file_path)
                    print(f"🔍 Tipo de base detectada: {detected_type.upper()}")

                    if detected_type == "certificacoes":
                        print("🚀 Iniciando ingestão de Certificações via pipeline.process_certifications()...")
                        etl_res = pipeline.process_certifications([local_file_path])
                        record_count = etl_res.get("certifications_inserted", 0)
                    elif detected_type == "voluntarios":
                        print("🚀 Iniciando ingestão de Voluntários via pipeline.process_volunteers()...")
                        etl_res = pipeline.process_volunteers(local_file_path)
                        record_count = etl_res.get("volunteers_inserted", 0)
                    else:
                        print("🚀 Iniciando ingestão de Filiados via pipeline.process_members()...")
                        etl_res = pipeline.process_members([local_file_path])
                        record_count = etl_res.get("details", {}).get("memberships_inserted", 0) + etl_res.get("details", {}).get("memberships_updated", 0)

                    # 3. Salva cópia imutável no Data Lake do Supabase (datalake_raw_files)
                    datalake_id = db_manager.save_datalake_file(
                        filename=filename,
                        file_bytes=file_bytes,
                        record_count=record_count,
                        source="thoughtspot_email",
                        data_type=detected_type
                    )
                    print(f"✅ Arquivo registrado no Data Lake do Supabase (ID: {datalake_id}) sob categoria '{detected_type}'!")
                    print(f"Resultado do ETL: {etl_res}")

                    processed_count += 1

                # Marca mensagem como lida
                mail.store(msg_id, "+FLAGS", "\\Seen")

                if processed_count > 0 and not force:
                    # Já processou o envio mais recente
                    break

            if processed_count == 0:
                print("Todos os anexos recentes já estavam ingeridos ou nenhum novo arquivo encontrado.")
                return {"status": "up_to_date", "message": "Nenhum novo anexo pendente."}

            return {
                "status": "success",
                "processed_files": processed_count,
                "message": f"Ingestão concluída com sucesso! {processed_count} arquivo(s) processado(s)."
            }

        finally:
            try:
                mail.close()
            except Exception:
                pass
            mail.logout()

def main():
    force = "--force" in sys.argv
    syncer = EmailDataLakeIngestion()
    res = syncer.sync_latest_filiados(force=force)
    print("\nResumo da Operação:")
    print(res)

if __name__ == "__main__":
    main()
