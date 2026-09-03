import pandas as pd
import numpy as np
import warnings
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from database import db_manager
import io

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

class ReportManager:
    def __init__(self):
        pass

    def get_ref_date(self, ref_date: str = None) -> datetime:
        if ref_date:
            try:
                return pd.to_datetime(ref_date)
            except Exception:
                pass
        return datetime.now()

    def get_filiados_ativos(self, ref_date: str = None) -> pd.DataFrame:
        """
        Lista nominal de filiados ativos (enddateforterm >= data de referência).
        """
        dt_ref = self.get_ref_date(ref_date)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.issinglemembership,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= %s
        ORDER BY m.enddateforterm DESC;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.issinglemembership,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= ?
        ORDER BY m.enddateforterm DESC;
        """
        
        df = db_manager.execute_query(query, (dt_ref.strftime("%Y-%m-%d"),))
        return df

    def get_novos_filiados_30_dias(self, ref_date: str = None) -> pd.DataFrame:
        """
        Lista de novos filiados nos últimos 30 dias com colunas padrão do banco.
        """
        dt_ref = self.get_ref_date(ref_date)
        dt_start = dt_ref - timedelta(days=30)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.originaljoindate >= %s AND m.originaljoindate <= %s
        ORDER BY m.originaljoindate DESC;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.originaljoindate >= ? AND m.originaljoindate <= ?
        ORDER BY m.originaljoindate DESC;
        """
        
        df = db_manager.execute_query(query, (dt_start.strftime("%Y-%m-%d"), dt_ref.strftime("%Y-%m-%d")))
        return df

    def get_desfiliados_30_dias(self, ref_date: str = None) -> pd.DataFrame:
        """
        Lista nominal de desfiliados nos últimos 30 dias.
        """
        dt_ref = self.get_ref_date(ref_date)
        dt_start = dt_ref - timedelta(days=30)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= %s AND m.enddateforterm <= %s
        ORDER BY m.enddateforterm DESC;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= ? AND m.enddateforterm <= ?
        ORDER BY m.enddateforterm DESC;
        """
        
        df = db_manager.execute_query(query, (dt_start.strftime("%Y-%m-%d"), dt_ref.strftime("%Y-%m-%d")))
        return df

    def get_desfiliacao_prox_30_dias(self, ref_date: str = None) -> pd.DataFrame:
        """
        Filiados com expiração de filiação prevista nos próximos 30 dias.
        """
        dt_ref = self.get_ref_date(ref_date)
        dt_end = dt_ref + timedelta(days=30)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= %s AND m.enddateforterm <= %s
        ORDER BY m.enddateforterm ASC;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= ? AND m.enddateforterm <= ?
        ORDER BY m.enddateforterm ASC;
        """
        
        df = db_manager.execute_query(query, (dt_ref.strftime("%Y-%m-%d"), dt_end.strftime("%Y-%m-%d")))
        return df

    def get_desfiliacao_prox_90_dias(self, ref_date: str = None) -> pd.DataFrame:
        """
        Filiados com expiração nos próximos 90 dias (previsão trimestral de renovações).
        """
        dt_ref = self.get_ref_date(ref_date)
        dt_end = dt_ref + timedelta(days=90)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= %s AND m.enddateforterm <= %s
        ORDER BY m.enddateforterm ASC;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= ? AND m.enddateforterm <= ?
        ORDER BY m.enddateforterm ASC;
        """
        
        df = db_manager.execute_query(query, (dt_ref.strftime("%Y-%m-%d"), dt_end.strftime("%Y-%m-%d")))
        return df

    def get_filiados_1_trimestre(self, ref_date: str = None) -> pd.DataFrame:
        """
        Filiados que completam 3 meses de casa no mês de referência.
        """
        dt_ref = self.get_ref_date(ref_date)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.originaljoindate IS NOT NULL;
        """
        df = db_manager.execute_query(query)
        if df.empty:
            return df
        
        df['originaljoindate_dt'] = pd.to_datetime(df['originaljoindate'], errors='coerce')
        df['data_3_meses'] = df['originaljoindate_dt'] + pd.DateOffset(months=3)
        
        df_filtered = df[
            (df['data_3_meses'].dt.month == dt_ref.month) & 
            (df['data_3_meses'].dt.year == dt_ref.year)
        ].copy()
        
        df_filtered = df_filtered.drop(columns=['originaljoindate_dt', 'data_3_meses'])
        return df_filtered.sort_values(by='originaljoindate', ignore_index=True)

    def get_filiados_1_semestre(self, ref_date: str = None) -> pd.DataFrame:
        """
        Filiados que completam 6 meses de casa no mês de referência.
        """
        dt_ref = self.get_ref_date(ref_date)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.originaljoindate IS NOT NULL;
        """
        df = db_manager.execute_query(query)
        if df.empty:
            return df
        
        df['originaljoindate_dt'] = pd.to_datetime(df['originaljoindate'], errors='coerce')
        df['data_6_meses'] = df['originaljoindate_dt'] + pd.DateOffset(months=6)
        
        df_filtered = df[
            (df['data_6_meses'].dt.month == dt_ref.month) & 
            (df['data_6_meses'].dt.year == dt_ref.year)
        ].copy()
        
        df_filtered = df_filtered.drop(columns=['originaljoindate_dt', 'data_6_meses'])
        return df_filtered.sort_values(by='originaljoindate', ignore_index=True)

    def get_aniversariantes_filiacao(self, ref_date: str = None) -> pd.DataFrame:
        """
        Aniversariantes de filiação ativos (enddateforterm >= data de referência) 
        cujo originaljoindate faz aniversário no mês da data de extração.
        """
        dt_ref = self.get_ref_date(ref_date)
        ref_str = dt_ref.strftime("%Y-%m-%d")
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= %s AND m.originaljoindate IS NOT NULL;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            m.originaljoindate,
            m.startdateforterm,
            m.enddateforterm,
            m.plannameforchapters,
            m.autorenewstatus,
            p.primaryphone,
            m.tenureinyears
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.enddateforterm >= ? AND m.originaljoindate IS NOT NULL;
        """
        
        df = db_manager.execute_query(query, (ref_str,))
        if df.empty:
            return df
        
        df['originaljoindate_dt'] = pd.to_datetime(df['originaljoindate'], errors='coerce')
        df['idade_de_filiacao'] = dt_ref.year - df['originaljoindate_dt'].dt.year
        lista_marcos = [1, 3, 5, 10, 15, 20, 25]
        
        # Filtra filiados ativos no mês de aniversário e completando marcos de anos
        df_filtered = df[
            (df['originaljoindate_dt'].dt.month == dt_ref.month) &
            (df['idade_de_filiacao'].isin(lista_marcos))
        ].copy()
        
        df_filtered = df_filtered.drop(columns=['originaljoindate_dt', 'idade_de_filiacao'])
        return df_filtered.sort_values(by='originaljoindate', ignore_index=True)

    def get_certificados_ultimos_3_meses(self, ref_date: str = None) -> pd.DataFrame:
        """
        Membros que obtiveram certificação nos últimos 3 meses.
        """
        dt_ref = self.get_ref_date(ref_date)
        dt_start = dt_ref - relativedelta(months=3)
        
        query = """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            c.certificationtypename,
            c.originalgrantdate,
            c.effectivestartdate,
            c.effectiveenddate,
            c.certificationstatusname,
            c.total_cycleseqno
        FROM certification c
        JOIN person p ON p.personid = c.personid
        LEFT JOIN membership m ON p.personid = m.personid
        WHERE c.originalgrantdate >= %s AND c.originalgrantdate <= %s
        ORDER BY c.originalgrantdate DESC;
        """ if db_manager.is_postgres else """
        SELECT 
            p.personid,
            p.fullname,
            p.primaryemail,
            m.isreceiveelectronicnotifications,
            c.certificationtypename,
            c.originalgrantdate,
            c.effectivestartdate,
            c.effectiveenddate,
            c.certificationstatusname,
            c.total_cycleseqno
        FROM certification c
        JOIN person p ON p.personid = c.personid
        LEFT JOIN membership m ON p.personid = m.personid
        WHERE c.originalgrantdate >= ? AND c.originalgrantdate <= ?
        ORDER BY c.originalgrantdate DESC;
        """
        
        df = db_manager.execute_query(query, (dt_start.strftime("%Y-%m-%d"), dt_ref.strftime("%Y-%m-%d")))
        return df

    def get_voluntarios_filtrados(self) -> pd.DataFrame:
        """
        Lista de candidaturas de voluntários ativos (deduplicados e em andamento).
        """
        query = """
        SELECT 
            v.voluntary_id,
            v.applicants,
            v.email_address,
            m.isreceiveelectronicnotifications,
            v.opportunity_name,
            v.opportunity_description,
            v.application_status,
            v.application_service_start_date,
            v.application_service_end_date
        FROM voluntary v
        LEFT JOIN membership m ON v.personid = m.personid
        ORDER BY v.application_service_start_date DESC;
        """
        df = db_manager.execute_query(query)
        return df


    def export_all_to_excel(self, ref_date: str = None, user_role: str = "admin") -> bytes:
        """
        Gera uma planilha Excel (.xlsx) contendo as abas autorizadas para o papel do usuário.
        - admin: todas as abas
        - filiacao: abas de filiação e renovação
        - voluntariado: 1 aba de voluntários
        - certificacao: 1 aba de certificações
        """
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            if user_role in ["admin", "filiacao"]:
                self.get_filiados_ativos(ref_date).to_excel(writer, sheet_name='Filiados_Ativos', index=False)
                self.get_novos_filiados_30_dias(ref_date).to_excel(writer, sheet_name='Novos_Filiados_30D', index=False)
                self.get_desfiliados_30_dias(ref_date).to_excel(writer, sheet_name='Desfiliados_30D', index=False)
                self.get_desfiliacao_prox_30_dias(ref_date).to_excel(writer, sheet_name='Desfilia_Prox_30D', index=False)
                self.get_desfiliacao_prox_90_dias(ref_date).to_excel(writer, sheet_name='Desfilia_Prox_90D', index=False)
                self.get_filiados_1_trimestre(ref_date).to_excel(writer, sheet_name='Filiados_1_Trimestre', index=False)
                self.get_filiados_1_semestre(ref_date).to_excel(writer, sheet_name='Filiados_1_Semestre', index=False)
                self.get_aniversariantes_filiacao(ref_date).to_excel(writer, sheet_name='Aniversariantes', index=False)
            
            if user_role in ["admin", "certificacao"]:
                self.get_certificados_ultimos_3_meses(ref_date).to_excel(writer, sheet_name='Certificados_3_Meses', index=False)
                
            if user_role in ["admin", "voluntariado"]:
                self.get_voluntarios_filtrados().to_excel(writer, sheet_name='Voluntarios_Ativos', index=False)
        
        output.seek(0)
        return output.getvalue()

report_manager = ReportManager()
