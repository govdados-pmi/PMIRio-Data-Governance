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

    def format_report_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        renames = {
            'isreceiveelectronicnotifications': 'Aceita Notificações Eletrônicas'
        }
        df = df.rename(columns=renames)
        if 'Aceita Notificações Eletrônicas' in df.columns:
            df['Aceita Notificações Eletrônicas'] = df['Aceita Notificações Eletrônicas'].map({True: 'Sim', False: 'Não', 1: 'Sim', 0: 'Não', '1': 'Sim', '0': 'Não'}).fillna('Não')
        return df

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
        WHERE m.startdateforterm <= %s AND m.enddateforterm >= %s
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
        WHERE m.startdateforterm <= ? AND m.enddateforterm >= ?
        ORDER BY m.enddateforterm DESC;
        """
        
        ref_str = dt_ref.strftime("%Y-%m-%d")
        df = db_manager.execute_query(query, (ref_str, ref_str))
        return self.format_report_df(df)

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
        return self.format_report_df(df)

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
        return self.format_report_df(df)

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
        return self.format_report_df(df)

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
        return self.format_report_df(df)

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
        return self.format_report_df(df_filtered.sort_values(by='originaljoindate', ignore_index=True))

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
        return self.format_report_df(df_filtered.sort_values(by='originaljoindate', ignore_index=True))

    def get_aniversariantes_filiacao(self, ref_date: str = None) -> pd.DataFrame:
        """
        Aniversariantes de filiação ativos (startdateforterm <= ref_date <= enddateforterm) 
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
            p.primaryphone
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.startdateforterm <= %s AND m.enddateforterm >= %s AND m.originaljoindate IS NOT NULL;
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
            p.primaryphone
        FROM membership m
        JOIN person p ON p.personid = m.personid
        WHERE m.startdateforterm <= ? AND m.enddateforterm >= ? AND m.originaljoindate IS NOT NULL;
        """
        
        df = db_manager.execute_query(query, (ref_str, ref_str))
        if df.empty:
            return df
        
        df['originaljoindate_dt'] = pd.to_datetime(df['originaljoindate'], errors='coerce')
        df['aniversario_de_filiacao'] = dt_ref.year - df['originaljoindate_dt'].dt.year
        lista_marcos = [1, 3, 5, 10, 15, 20, 25]
        
        # Filtra filiados ativos no mês de aniversário e completando marcos de anos
        df_filtered = df[
            (df['originaljoindate_dt'].dt.month == dt_ref.month) &
            (df['aniversario_de_filiacao'].isin(lista_marcos))
        ].copy()
        
        df_filtered = df_filtered.drop(columns=['originaljoindate_dt'])
        return self.format_report_df(df_filtered.sort_values(by='originaljoindate', ignore_index=True))

    def get_aniversariantes_renovados(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        Relatório de Reconhecimento: Filiados que completaram aniversário de filiação no período selecionado
        (start_date até end_date) e cuja filiação foi renovada pós-aniversário.
        """
        dt_start = self.get_ref_date(start_date) if start_date else datetime.now() - timedelta(days=30)
        dt_end = self.get_ref_date(end_date) if end_date else datetime.now()
        
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
        WHERE m.originaljoindate IS NOT NULL AND m.startdateforterm IS NOT NULL;
        """
        
        df = db_manager.execute_query(query)
        if df.empty:
            return df
        
        df['join_dt'] = pd.to_datetime(df['originaljoindate'], errors='coerce')
        df['start_dt'] = pd.to_datetime(df['startdateforterm'], errors='coerce')
        df['end_dt'] = pd.to_datetime(df['enddateforterm'], errors='coerce')
        
        df = df.dropna(subset=['join_dt', 'start_dt']).copy()
        if df.empty:
            return df
            
        def is_anniversary_in_range(row):
            j_dt = row['join_dt']
            for yr in range(dt_start.year, dt_end.year + 1):
                try:
                    anniv = datetime(yr, j_dt.month, min(j_dt.day, 28 if j_dt.month == 2 else (30 if j_dt.month in [4,6,9,11] else 31)))
                    if dt_start.date() <= anniv.date() <= dt_end.date():
                        return True, anniv, yr - j_dt.year
                except Exception:
                    pass
            return False, None, 0

        res_rows = []
        for _, row in df.iterrows():
            in_range, anniv_dt, tenure_calc = is_anniversary_in_range(row)
            if in_range:
                if row['start_dt'] > row['join_dt'] and row['end_dt'] >= anniv_dt:
                    row_dict = row.to_dict()
                    row_dict['Anos de Filiação'] = max(1, tenure_calc)
                    row_dict['Data do Aniversário no Período'] = anniv_dt.strftime("%Y-%m-%d")
                    row_dict['Status da Renovação'] = "Renovado com Sucesso ✅"
                    res_rows.append(row_dict)
                    
        if not res_rows:
            return pd.DataFrame()
            
        res_df = pd.DataFrame(res_rows)
        res_df = res_df.drop(columns=['join_dt', 'start_dt', 'end_dt'])
        return self.format_report_df(res_df.sort_values(by='originaljoindate', ignore_index=True))

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
        return self.format_report_df(df)

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
        return self.format_report_df(df)

    def get_filiados_renovados_90_dias(self, ref_date: str = None) -> pd.DataFrame:
        """
        Filiados com início do mandato atual (startdateforterm) nos últimos 90 dias 
        cujo ano de originaljoindate é diferente de startdateforterm (renovações efetivas).
        """
        dt_ref = self.get_ref_date(ref_date)
        dt_start = dt_ref - timedelta(days=90)
        
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
        WHERE m.startdateforterm >= %s AND m.startdateforterm <= %s
          AND m.originaljoindate IS NOT NULL
        ORDER BY m.startdateforterm DESC;
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
        WHERE m.startdateforterm >= ? AND m.startdateforterm <= ?
          AND m.originaljoindate IS NOT NULL
        ORDER BY m.startdateforterm DESC;
        """
        
        df = db_manager.execute_query(query, (dt_start.strftime("%Y-%m-%d"), dt_ref.strftime("%Y-%m-%d")))
        if df.empty:
            return df
        
        start_year = pd.to_datetime(df['startdateforterm'], errors='coerce').dt.year
        join_year = pd.to_datetime(df['originaljoindate'], errors='coerce').dt.year
        
        df_filtered = df[start_year != join_year].copy()
        return self.format_report_df(df_filtered.reset_index(drop=True))

    def get_certificacoes_expirando_mes(self, ref_date: str = None) -> pd.DataFrame:
        """
        Certificações ativas cuja data de expiração (effectiveenddate) ocorre no mês da data de referência.
        """
        dt_ref = self.get_ref_date(ref_date)
        
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
        WHERE c.effectiveenddate IS NOT NULL
        ORDER BY c.effectiveenddate ASC;
        """
        
        df = db_manager.execute_query(query)
        if df.empty:
            return df
        
        end_dates = pd.to_datetime(df['effectiveenddate'], errors='coerce')
        df_filtered = df[
            (end_dates.dt.month == dt_ref.month) & 
            (end_dates.dt.year == dt_ref.year)
        ].copy()
        
        return self.format_report_df(df_filtered.reset_index(drop=True))



    def export_all_to_excel(self, ref_date: str = None, user_role: str = "admin", allowed_keys: list = None) -> bytes:
        """
        Gera uma planilha Excel (.xlsx) contendo todas as abas de relatórios autorizadas para o usuário.
        """
        output = io.BytesIO()
        sheets_added = 0
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            all_reports = {
                'Filiados_Ativos': lambda: self.get_filiados_ativos(ref_date),
                'Novos_Filiados_30D': lambda: self.get_novos_filiados_30_dias(ref_date),
                'Renovados_90D': lambda: self.get_filiados_renovados_90_dias(ref_date),
                'Desfiliados_30D': lambda: self.get_desfiliados_30_dias(ref_date),
                'Desfilia_Prox_30D': lambda: self.get_desfiliacao_prox_30_dias(ref_date),
                'Desfilia_Prox_90D': lambda: self.get_desfiliacao_prox_90_dias(ref_date),
                'Filiados_1_Trimestre': lambda: self.get_filiados_1_trimestre(ref_date),
                'Filiados_1_Semestre': lambda: self.get_filiados_1_semestre(ref_date),
                'Aniversariantes_Filiacao': lambda: self.get_aniversariantes_filiacao(ref_date),
                'Certificados_3_Meses': lambda: self.get_certificados_ultimos_3_meses(ref_date),
                'Certificacoes_Expirando_Mes': lambda: self.get_certificacoes_expirando_mes(ref_date),
                'Voluntarios_Ativos': lambda: self.get_voluntarios_filtrados()
            }
            
            for key, fn in all_reports.items():
                if user_role == "admin" or allowed_keys is None or key in allowed_keys:
                    try:
                        df = fn()
                        if df is not None and not df.empty:
                            df.to_excel(writer, sheet_name=key[:31], index=False)
                            sheets_added += 1
                    except Exception:
                        pass
            
            if sheets_added == 0:
                pd.DataFrame({"Aviso": ["Nenhum dado encontrado para os relatórios autorizados nesta data."]}).to_excel(writer, sheet_name="Sem_Dados", index=False)
        output.seek(0)
        return output.getvalue()

report_manager = ReportManager()
