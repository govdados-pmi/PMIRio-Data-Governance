import streamlit as st
import pandas as pd
import numpy as np
import os
import tempfile
import json
import importlib
import warnings
from datetime import datetime

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

import database
importlib.reload(database)
from database import db_manager
from etl import pipeline
import reports
importlib.reload(reports)
from reports import report_manager

# Configuração da Página
st.set_page_config(
    page_title="PMI Rio - Governança & Ingestão de Dados",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Personalizada com a Identidade Visual Oficial do PMI (2024 Brand Guidelines)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');
    
    /* Tipografia Global e Cores do PMI */
    html, body, [class*="css"] {
        font-family: 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #270F53;
    }
    
    /* Estilo do Header Principal */
    .main-title {
        font-size: 2.3rem;
        font-weight: 700;
        color: #461DA3;
        background: linear-gradient(90deg, #270F53 0%, #461DA3 50%, #6CBEDE 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        letter-spacing: -0.5px;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #44789B;
        margin-bottom: 1.5rem;
        font-weight: 500;
    }
    
    /* Card de Login */
    .login-container {
        max-width: 450px;
        margin: 2rem auto;
        padding: 2.5rem;
        background-color: #FFFFFF;
        border: 1px solid #D4C6F5;
        border-radius: 12px;
        box-shadow: 0 8px 24px rgba(70, 29, 163, 0.08);
    }
    
    /* Badges de Perfis com a Paleta Oficial do PMI */
    .role-badge {
        display: inline-block;
        padding: 0.4em 0.85em;
        font-size: 82%;
        font-weight: 700;
        line-height: 1;
        text-align: center;
        white-space: nowrap;
        vertical-align: baseline;
        border-radius: 6px;
        letter-spacing: 0.3px;
    }
    .badge-admin { background-color: #E0611F; color: #FFFFFF; border: 1px solid #B83713; }
    .badge-view { background-color: #44789B; color: #FFFFFF; border: 1px solid #233E4F; }
    .badge-filiacao { background-color: #461DA3; color: #FFFFFF; border: 1px solid #270F53; }
    .badge-voluntariado { background-color: #6CBEDE; color: #270F53; border: 1px solid #508EA6; }
    .badge-certificacao { background-color: #B29478; color: #FFFFFF; border: 1px solid #753205; }
    
    /* Botões Primários com o Roxo Principal (#461DA3) */
    div.stButton > button[kind="primary"] {
        background-color: #461DA3 !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease-in-out !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #36177B !important;
        box-shadow: 0 4px 12px rgba(70, 29, 163, 0.3) !important;
    }
    
    /* Estilização das Abas Superiores (st.tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 2px solid #D4C6F5;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre;
        border-radius: 8px 8px 0px 0px;
        color: #44789B;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #461DA3 !important;
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)

# Inicializa banco de dados
try:
    db_manager.init_db()
except Exception as e:
    st.error(f"Erro ao inicializar o banco de dados: {e}")

# Gerenciamento de Sessão de Usuário
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "user" not in st.session_state:
    st.session_state["user"] = None

# ==============================================================================
# TELA DE LOGIN (Caso não autenticado)
# ==============================================================================
if not st.session_state["logged_in"]:
    st.markdown('<h1 class="main-title" style="text-align: center;">PMI Rio — Portal de Dados & Governança</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title" style="text-align: center;">Autoatendimento Seguro e Governança de Dados da Diretoria</p>', unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.subheader("🔑 Autenticação de Acesso")
        with st.form("login_form"):
            email_input = st.text_input("E-mail Institucional", placeholder="diretoria@pmirio.org.br")
            password_input = st.text_input("Senha", type="password", placeholder="••••••••")
            submit_login = st.form_submit_button("Entrar no Portal", type="primary", width="stretch")
            
            if submit_login:
                user = db_manager.authenticate_user(email_input, password_input)
                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["user"] = user
                    st.success(f"Bem-vindo(a), {user['full_name']}!")
                    st.rerun()
                else:
                    st.error("Credenciais inválidas ou conta inativa. Tente novamente.")
    st.stop()

# ==============================================================================
# APLICAÇÃO PRINCIPAL (Usuário Autenticado)
# ==============================================================================
user = st.session_state["user"]
role = user["role"]

# Header Principal
st.markdown('<h1 class="main-title">PMI Rio — Portal de Dados & Governança</h1>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-title">Conectado como <strong>{user["full_name"]}</strong> ({user["email"]})</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚡ Usuário Autenticado")
    badge_class = f"badge-{role}" if role in ["admin", "view"] else "badge-view"
    role_desc = "Acesso Total (Admin)" if role == "admin" else "Acesso de Visualização"
    st.markdown(f'<span class="role-badge {badge_class}">{role_desc}</span>', unsafe_allow_html=True)
    st.markdown("---")
    
    if st.button("🚪 Sair (Logout)", width="stretch"):
        st.session_state["logged_in"] = False
        st.session_state["user"] = None
        st.rerun()
        
    st.markdown("---")
    db_type = "⚡ Supabase (PostgreSQL)" if db_manager.is_postgres else "SQLite (Local)"
    st.info(f"**Banco Conectado:** {db_type}")
    
    if role == "admin":
        with st.expander("🔑 Conexão Supabase (PostgreSQL)"):
            st.markdown("Cole sua **Connection String** do Supabase:")
            supabase_url_input = st.text_input(
                "URI do Supabase", 
                value=db_manager.connection_string or "",
                type="password",
                placeholder="postgresql://postgres:[SENHA]@db.[PROJECT_REF].supabase.co:5432/postgres"
            )
            if st.button("Conectar ao Supabase"):
                if supabase_url_input.strip():
                    db_manager.update_connection(supabase_url_input.strip())
                    try:
                        db_manager.init_db()
                        st.success("Conectado ao Supabase PostgreSQL com sucesso!")
                        st.rerun()
                    except Exception as err:
                        st.error(f"Erro ao conectar no Supabase: {err}")

# Dicionário de relatórios padrão do sistema (Filiados Ativos em primeiro lugar)
STANDARD_REPORTS_DICT = {
    "Filiados_Ativos": "Filiados Ativos",
    "Novos_Filiados_30D": "Novos Filiados (30D)",
    "Desfiliados_30D": "Desfiliados (30D)",
    "Desfilia_Prox_30D": "A Vencer (30D)",
    "Desfilia_Prox_90D": "A Vencer (90D)",
    "Filiados_1_Trimestre": "1º Trimestre (3M)",
    "Filiados_1_Semestre": "1º Semestre (6M)",
    "Aniversariantes_Filiacao": "Aniversariantes",
    "Certificados_3_Meses": "Certificados (3M)",
    "Voluntarios_Ativos": "Voluntários Ativos"
}

# Define Abas disponíveis de acordo com o papel (RBAC)
tabs_map = {}
if role == "admin":
    tabs_map["users"] = "🔑 Gestão de Acessos"
    tabs_map["etl"] = "📥 Ingestão & Atualização (ETL)"
    tabs_map["db"] = "🗄️ Banco de Dados & Console SQL"
    tabs_map["reports"] = "📊 Central de Relatórios"
else:
    tabs_map["reports"] = "📊 Central de Relatórios"

tab_objects = st.tabs(list(tabs_map.values()))
tab_dict = {key: tab_objects[i] for i, key in enumerate(tabs_map.keys())}

# ==============================================================================
# ABA: GESTÃO DE ACESSOS (Apenas Admin)
# ==============================================================================
if "users" in tab_dict:
    with tab_dict["users"]:
        st.subheader("🔑 Gestão de Acessos & Permissões (RBAC)")
        st.markdown("Cadastre novos usuários, ative/desative, altere permissões de relatórios ou exclua acessos.")
        
        # Carrega relatórios salvos no banco para a lista de permissões
        custom_reports_df = db_manager.list_custom_reports()
        all_report_options = dict(STANDARD_REPORTS_DICT)
        if not custom_reports_df.empty:
            for _, crow in custom_reports_df.iterrows():
                cid = str(crow["report_id"])
                all_report_options[f"custom_{cid}"] = f"📊 [Custom] {crow['report_name']}"

        # Formulário de Cadastro de Novo Acesso
        with st.form("form_add_user"):
            st.markdown("### ➕ Cadastrar Novo Acesso")
            c1, c2 = st.columns(2)
            with c1:
                new_email = st.text_input("E-mail Institucional", placeholder="nome.sobrenome@pmirio.org.br")
                new_name = st.text_input("Nome Completo", placeholder="Ex: Maria Souza")
            with c2:
                new_pass = st.text_input("Senha Inicial", type="password", placeholder="••••••••")
                new_role = st.selectbox(
                    "Perfil de Acesso", 
                    options=["admin", "view"],
                    format_func=lambda x: "👑 Acesso Total (Administrador)" if x == "admin" else "👁️ Acesso de Visualização"
                )
            
            selected_reports = []
            if new_role == "view":
                st.markdown("#### 🎯 Permissão Granular de Relatórios (Apenas para Acesso de Visualização)")
                selected_reports = st.multiselect(
                    "Selecione os Relatórios Autorizados:",
                    options=list(all_report_options.keys()),
                    format_func=lambda x: all_report_options[x],
                    default=list(all_report_options.keys())
                )
            
            submit_user = st.form_submit_button("🚀 Cadastrar Novo Acesso", type="primary", width="stretch")
            if submit_user:
                if new_email and new_name and new_pass:
                    allowed_json = json.dumps(selected_reports) if new_role == "view" else None
                    if db_manager.create_user(new_email, new_pass, new_name, new_role, allowed_json):
                        st.success(f"Acesso criado com sucesso para {new_name} ({new_email})!")
                        st.rerun()
                    else:
                        st.error("Erro ao cadastrar usuário. O e-mail já pode estar cadastrado no banco.")
                else:
                    st.warning("Preencha todos os campos obrigatórios do formulário.")
                    
        st.markdown("---")
        st.markdown("### 📋 Usuários Cadastrados no Banco de Dados")
        
        users_df = db_manager.list_users()
        if not users_df.empty:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Total de Acessos", len(users_df))
            with m2:
                st.metric("Acessos Ativos", len(users_df[users_df["is_active"] == True]))
            with m3:
                st.metric("Administradores (Total)", len(users_df[users_df["role"] == "admin"]))
            with m4:
                st.metric("Usuários de Visualização", len(users_df[users_df["role"] == "view"]))

            st.markdown("---")
            
            # Tabela Interativa de Usuários
            for idx, urow in users_df.iterrows():
                uid = int(urow["user_id"])
                uemail = str(urow["email"])
                uname = str(urow["full_name"])
                urole = str(urow["role"])
                uactive = bool(urow["is_active"])
                u_allowed_raw = urow.get("allowed_reports")
                
                # Parse allowed_reports
                u_allowed_list = []
                if pd.notna(u_allowed_raw) and u_allowed_raw:
                    try:
                        u_allowed_list = json.loads(u_allowed_raw)
                    except Exception:
                        u_allowed_list = []

                col_u1, col_u2, col_u3, col_u4, col_u5 = st.columns([3, 2, 2, 2, 2])
                with col_u1:
                    st.markdown(f"**{uname}**<br><small style='color: #64748B;'>{uemail}</small>", unsafe_allow_html=True)
                with col_u2:
                    badge_str = "👑 Admin" if urole == "admin" else "👁️ Visualização"
                    b_class = f"badge-{urole}" if urole in ["admin", "view"] else "badge-view"
                    st.markdown(f'<span class="role-badge {b_class}">{badge_str}</span>', unsafe_allow_html=True)
                    if urole == "view":
                        st.caption(f"📊 {len(u_allowed_list)} relatórios permitidos")
                with col_u3:
                    status_str = "🟢 Ativo" if uactive else "🔴 Inativo"
                    st.markdown(f"**{status_str}**")
                with col_u4:
                    toggle_btn_label = "🔴 Desativar" if uactive else "🟢 Ativar"
                    if st.button(toggle_btn_label, key=f"btn_toggle_usr_{uid}"):
                        db_manager.toggle_user_status(uid, uactive)
                        st.rerun()
                with col_u5:
                    show_edit_key = f"show_edit_{uid}"
                    if st.button("✏️ Editar", key=f"btn_edit_usr_{uid}"):
                        st.session_state[show_edit_key] = not st.session_state.get(show_edit_key, False)
                        st.rerun()

                # Container de edição de permissões/perfil ativado pelo botão 'Editar'
                if st.session_state.get(f"show_edit_{uid}", False):
                    with st.container():
                        st.markdown(f"#### ⚙️ Editar Permissões & Perfil do Usuário: **{uname}**")
                        with st.form(f"form_edit_user_perm_{uid}"):
                            edit_role = st.selectbox(
                                "Perfil de Acesso:",
                                options=["view", "admin"],
                                index=0 if urole == "view" else 1,
                                format_func=lambda x: "👁️ Acesso de Visualização" if x == "view" else "👑 Acesso Total (Admin)",
                                key=f"sel_role_{uid}"
                            )
                            current_selected = [r for r in u_allowed_list if r in all_report_options]
                            new_selected = st.multiselect(
                                "Selecione os relatórios visíveis para este usuário:",
                                options=list(all_report_options.keys()),
                                format_func=lambda x: all_report_options[x],
                                default=current_selected,
                                key=f"ms_edit_{uid}"
                            )
                            submit_edit = st.form_submit_button("💾 Salvar Alterações", type="primary")
                            if submit_edit:
                                new_json = json.dumps(new_selected) if edit_role == "view" else None
                                placeholder = "%s" if db_manager.is_postgres else "?"
                                sql_upd = f"UPDATE app_user SET role = {placeholder}, allowed_reports = {placeholder} WHERE user_id = {placeholder};"
                                db_manager.execute_non_query(sql_upd, (edit_role, new_json, uid))
                                st.session_state[f"show_edit_{uid}"] = False
                                st.success(f"Permissões atualizadas com sucesso para {uname}!")
                                st.rerun()
                st.markdown("---")

# ==============================================================================
# ABA: INGESTÃO & ATUALIZAÇÃO (ETL) — Apenas Admin
# ==============================================================================
if "etl" in tab_dict:
    with tab_dict["etl"]:
        st.subheader("Subir Planilhas do ThoughtSpot")
        st.markdown("Faça o upload dos arquivos `.xlsx` baixados do ThoughtSpot para atualizar o banco de dados PostgreSQL automaticamente.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("#### 1. Filiados (Members)")
            uploaded_members = st.file_uploader("Planilhas de Filiados", type=["xlsx"], accept_multiple_files=True, key="members_uploader")
        with col2:
            st.markdown("#### 2. Certificações")
            uploaded_certs = st.file_uploader("Planilhas de Certificação", type=["xlsx"], accept_multiple_files=True, key="certs_uploader")
        with col3:
            st.markdown("#### 3. Voluntários")
            uploaded_vol = st.file_uploader("Planilha de Voluntários", type=["xlsx"], accept_multiple_files=False, key="vol_uploader")

        st.markdown("---")
        use_sample_files = st.checkbox("Usar arquivos locais da pasta 'planilhas/' caso não faça upload manual")
        
        if st.button("🚀 Executar Pipeline ETL e Atualizar Banco de Dados", type="primary", width="stretch"):
            with st.spinner("Processando planilhas, realizando limpeza e atualizando tabelas no PostgreSQL..."):
                member_paths = []
                cert_paths = []
                vol_path = None
                temp_dir = tempfile.mkdtemp()

                if uploaded_members:
                    for uf in uploaded_members:
                        p = os.path.join(temp_dir, uf.name)
                        with open(p, "wb") as f:
                            f.write(uf.getbuffer())
                        member_paths.append(p)
                elif use_sample_files:
                    import glob
                    member_paths = glob.glob("planilhas/*Members*.xlsx")

                if uploaded_certs:
                    for uf in uploaded_certs:
                        p = os.path.join(temp_dir, uf.name)
                        with open(p, "wb") as f:
                            f.write(uf.getbuffer())
                        cert_paths.append(p)
                elif use_sample_files:
                    import glob
                    cert_paths = list(set(glob.glob("planilhas/*Certif*.xlsx") + glob.glob("planilhas/*Certification*.xlsx")))


                if uploaded_vol:
                    p = os.path.join(temp_dir, uploaded_vol.name)
                    with open(p, "wb") as f:
                        f.write(uploaded_vol.getbuffer())
                    vol_path = p
                elif use_sample_files:
                    import glob
                    vols = glob.glob("planilhas/*Volunt*.xlsx")
                    if vols:
                        vol_path = vols[0]

                res_m = pipeline.process_members(member_paths) if member_paths else {"status": "skipped"}
                res_c = pipeline.process_certifications(cert_paths) if cert_paths else {"status": "skipped"}
                res_v = pipeline.process_volunteers(vol_path) if vol_path else {"status": "skipped"}

                has_error = False
                if res_m.get("status") == "error":
                    st.error(f"❌ Erro na planilha de Filiados: {res_m.get('message')}")
                    has_error = True
                if res_c.get("status") == "error":
                    st.error(f"❌ Erro na planilha de Certificações: {res_c.get('message')}")
                    has_error = True
                if res_v.get("status") == "error":
                    st.error(f"❌ Erro na planilha de Voluntários: {res_v.get('message')}")
                    has_error = True

                if not has_error:
                    st.success("🎉 Pipeline executado com sucesso!")
                    m1, m2, m3, m4, m5, m6 = st.columns(6)
                    with m1:
                        st.metric("Pessoas Criadas", res_m.get("persons_inserted", 0))
                    with m2:
                        st.metric("Pessoas Atualizadas", res_m.get("persons_updated", 0))
                    with m3:
                        st.metric("Históricos de Alteração", res_m.get("history_records_created", 0))
                    with m4:
                        st.metric("Filiações Novas", res_m.get("memberships_inserted", 0))
                    with m5:
                        st.metric("Filiações Ignoradas (Já Existiam)", res_m.get("memberships_skipped", 0))
                    with m6:
                        st.metric("Certificações Inseridas", res_c.get("certifications_inserted", 0))



# ==============================================================================
# ABA: BANCO DE DADOS & CONSOLE SQL — Apenas Admin
# ==============================================================================
if "db" in tab_dict:
    with tab_dict["db"]:
        st.subheader("Explorador de Tabelas Relacionais")
        table_choice = st.selectbox("Selecione a Tabela para Visualizar:", ["person", "membership", "person_history", "certification", "voluntary", "custom_report", "app_user"])
        try:
            df_table = db_manager.execute_query(f"SELECT * FROM {table_choice} LIMIT 500;")
            st.markdown(f"**Registros exibidos:** {len(df_table)} linhas")
            st.dataframe(df_table, width="stretch")
        except Exception as e:
            st.error(f"Erro ao consultar tabela {table_choice}: {e}")

        st.markdown("---")
        st.subheader("Console SQL Live & Gerador de Relatórios Customizados")
        custom_sql = st.text_area("Digite sua consulta SQL:", value="SELECT p.personid, p.fullname, p.primaryemail, m.originaljoindate, m.startdateforterm, m.enddateforterm, m.plannameforchapters, m.tenureinyears FROM person p JOIN membership m ON p.personid = m.personid LIMIT 50;")
        
        if st.button("Executar Consulta SQL"):
            try:
                df_custom = db_manager.execute_query(custom_sql)
                st.session_state["last_sql_result"] = df_custom
                st.session_state["last_sql_query"] = custom_sql
                st.dataframe(df_custom, width="stretch")
            except Exception as e:
                st.error(f"Erro na execução da consulta: {e}")

        if "last_sql_result" in st.session_state and st.session_state["last_sql_result"] is not None:
            st.markdown("---")
            with st.expander("💾 Transformar esta Consulta em um Novo Relatório Personalizado"):
                with st.form("form_save_custom_report"):
                    rep_title = st.text_input("Nome do Relatório Personalizado", placeholder="Ex: Filiados Ativos da Cidade do Rio")
                    rep_desc = st.text_input("Descrição do Relatório (opcional)", placeholder="Ex: Filtro especial de filiados residentes no Rio de Janeiro")
                    
                    submit_save_rep = st.form_submit_button("💾 Salvar como Novo Relatório", type="primary")
                    if submit_save_rep:
                        if rep_title.strip():
                            query_to_save = st.session_state.get("last_sql_query", custom_sql)
                            if db_manager.save_custom_report(rep_title, query_to_save, rep_desc, user["full_name"]):
                                st.success(f"Relatório '{rep_title}' salvo com sucesso! Ele agora pode ser atribuído na Gestão de Acessos e acessado na Central de Relatórios.")
                                st.rerun()
                            else:
                                st.error("Erro ao salvar o relatório personalizado no banco.")
                        else:
                            st.warning("Informe um nome para o relatório personalizado.")

        # Lista Relatórios Personalizados Salvos
        st.markdown("---")
        st.subheader("📋 Relatórios Personalizados Criados pelo Console SQL")
        c_reports = db_manager.list_custom_reports()
        if not c_reports.empty:
            for idx, crow in c_reports.iterrows():
                cid = int(crow["report_id"])
                cname = str(crow["report_name"])
                csql = str(crow["sql_query"])
                cauthor = str(crow["created_by"]) if pd.notna(crow.get("created_by")) else "Admin"
                
                col_c1, col_c2, col_c3 = st.columns([4, 4, 2])
                with col_c1:
                    st.markdown(f"**{cname}**<br><small style='color: #64748B;'>Criado por {cauthor}</small>", unsafe_allow_html=True)
                with col_c2:
                    st.code(csql, language="sql")
                with col_c3:
                    if st.button("🗑️ Excluir Relatório", key=f"del_crep_{cid}"):
                        if db_manager.delete_custom_report(cid):
                            st.success(f"Relatório '{cname}' excluído com sucesso!")
                            st.rerun()

# ==============================================================================
# ABA: CENTRAL DE RELATÓRIOS (Visibilidade de acordo com RBAC)
# ==============================================================================
if "reports" in tab_dict:
    with tab_dict["reports"]:
        st.subheader("📊 Central de Relatórios Executivos & Personalizados")
        st.markdown("Relatórios dinâmicos filtrados conforme suas permissões de acesso.")
        
        # Filtro de Data de Referência posicionado no topo/centro da Central de Relatórios
        col_d1, col_d2, col_d3 = st.columns([1, 2, 1])
        with col_d2:
            ref_date_input = st.date_input("📅 Mês de Extração / Data de Referência", datetime.now(), key="reports_ref_date_picker")
            ref_date_str = ref_date_input.strftime("%Y-%m-%d")
        
        st.markdown("---")
        
        # Mapeamento completo de relatórios padrão do sistema (Filiados Ativos em 1º lugar)
        standard_reports_map = {
            "Filiados_Ativos": ("Filiados Ativos", "Filiados_Ativos", lambda: report_manager.get_filiados_ativos(ref_date_str)),
            "Novos_Filiados_30D": ("Novos Filiados (30D)", "Novos_Filiados_30D", lambda: report_manager.get_novos_filiados_30_dias(ref_date_str)),
            "Desfiliados_30D": ("Desfiliados (30D)", "Desfiliados_30D", lambda: report_manager.get_desfiliados_30_dias(ref_date_str)),
            "Desfilia_Prox_30D": ("A Vencer (30D)", "Desfilia_Prox_30D", lambda: report_manager.get_desfiliacao_prox_30_dias(ref_date_str)),
            "Desfilia_Prox_90D": ("A Vencer (90D)", "Desfilia_Prox_90D", lambda: report_manager.get_desfiliacao_prox_90_dias(ref_date_str)),
            "Filiados_1_Trimestre": ("1º Trimestre (3M)", "Filiados_1_Trimestre", lambda: report_manager.get_filiados_1_trimestre(ref_date_str)),
            "Filiados_1_Semestre": ("1º Semestre (6M)", "Filiados_1_Semestre", lambda: report_manager.get_filiados_1_semestre(ref_date_str)),
            "Aniversariantes_Filiacao": ("Aniversariantes", "Aniversariantes", lambda: report_manager.get_aniversariantes_filiacao(ref_date_str)),
            "Certificados_3_Meses": ("Certificados (3M)", "Certificados_3_Meses", lambda: report_manager.get_certificados_ultimos_3_meses(ref_date_str)),
            "Voluntarios_Ativos": ("Voluntários Ativos", "Voluntarios_Ativos", lambda: report_manager.get_voluntarios_filtrados())
        }

        # Carrega relatórios customizados salvos no banco
        custom_reports_df = db_manager.list_custom_reports()
        custom_reports_map = {}
        if not custom_reports_df.empty:
            for _, crow in custom_reports_df.iterrows():
                cid = str(crow["report_id"])
                cname = str(crow["report_name"])
                csql = str(crow["sql_query"])
                c_key = f"custom_{cid}"
                
                def make_custom_func(sql):
                    return lambda: db_manager.execute_query(sql)
                
                custom_reports_map[c_key] = (f"📊 {cname}", f"Custom_{cname.replace(' ', '_')}", make_custom_func(csql))

        # Une todos os relatórios disponíveis
        all_available_reports_map = {**standard_reports_map, **custom_reports_map}

        # Filtra relatórios com base nas permissões do usuário
        user_allowed_keys = []
        if role == "admin":
            user_allowed_keys = list(all_available_reports_map.keys())
        else:
            raw_allowed = user.get("allowed_reports")
            if raw_allowed:
                try:
                    user_allowed_keys = json.loads(raw_allowed)
                except Exception:
                    user_allowed_keys = []
            else:
                user_allowed_keys = list(all_available_reports_map.keys())

        # Filtra tuplas ativas
        active_reports = [all_available_reports_map[k] for k in user_allowed_keys if k in all_available_reports_map]

        if not active_reports:
            st.warning("⚠️ Seu usuário ainda não possui relatórios autorizados. Entre em contato com o Administrador do sistema.")
        else:
            rep_tabs = st.tabs([r[0] for r in active_reports])
            
            for idx, (title, filename, func) in enumerate(active_reports):
                with rep_tabs[idx]:
                    try:
                        df = func()
                        
                        col_hdr1, col_hdr2 = st.columns([2, 1])
                        with col_hdr1:
                            st.markdown(f"### {title}")
                            st.markdown(f"**Total de registros:** {len(df)}")
                        
                        # Botões de Download acima da tabela de dados
                        c1, c2 = st.columns(2)
                        with c1:
                            st.download_button(
                                f"⬇️ Baixar CSV - {filename}",
                                data=df.to_csv(index=False).encode('utf-8'),
                                file_name=f"{filename}_{ref_date_str}.csv",
                                mime="text/csv",
                                type="primary",
                                key=f"dl_csv_{idx}_{filename}"
                            )
                        with c2:
                            bio = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
                            df.to_excel(bio.name, index=False)
                            with open(bio.name, "rb") as f:
                                st.download_button(
                                    f"⬇️ Baixar Excel - {filename}",
                                    data=f.read(),
                                    file_name=f"{filename}_{ref_date_str}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    type="primary",
                                    key=f"dl_xlsx_{idx}_{filename}"
                                )
                        
                        st.markdown("---")
                        st.dataframe(df, width="stretch")
                    except Exception as err:
                        st.error(f"Erro ao carregar o relatório '{title}': {err}")
