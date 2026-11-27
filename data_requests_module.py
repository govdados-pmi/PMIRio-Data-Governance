import streamlit as st
import pandas as pd
from datetime import date, timedelta
from database import db_manager

DIRECTORATES = [
    "Diretoria de Filiação",
    "Diretoria de Voluntariado",
    "Diretoria de Certificação & Desenvolvimento",
    "Diretoria de Eventos & Parcerias",
    "Diretoria de Comunicação & Marketing",
    "Diretoria de Operações & Finanças",
    "Presidência & Diretoria Executiva",
    "Outra Área / Projeto Específico"
]

URGENCY_LEVELS = [
    "Normal (até 7 dias úteis)",
    "Alta (até 3 dias úteis)",
    "Estratégica / Urgente (prioridade institucional)"
]


def render_data_requests_hub(user: dict, role: str):
    """Renderiza a Central Corporativa de Requisições de Dados e Gestão de Demandas."""
    st.markdown('<h2 style="color: #270F53; font-weight: 700; margin-bottom: 4px;">Central de Requisição de Dados & Inteligência</h2>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color: #44789B; font-weight: 500; margin-bottom: 16px;">'
        'Canal institucional para que diretorias e gerências solicitem recortes analíticos, relatórios sob medida '
        'e cruzamento de informações para fundamentar tomadas de decisão no PMI Rio.'
        '</p>',
        unsafe_allow_html=True
    )

    req_tabs = st.tabs([
        "Nova Solicitação de Dados",
        "Acompanhamento de Demandas",
        "Indicadores de Governança"
    ])

    # -------------------------------------------------------------------------
    # ABA 1: FORMULÁRIO DE NOVA REQUISIÇÃO
    # -------------------------------------------------------------------------
    with req_tabs[0]:
        st.markdown("### Formulário de Demanda de Informação")
        st.caption("O preenchimento detalhado auxilia a equipe de Governança a priorizar e estruturar os dados com precisão.")

        with st.form("form_new_data_request", clear_on_submit=True):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                req_name = st.text_input("Nome do Solicitante", value=user.get("full_name", ""))
                req_dir = st.selectbox("Diretoria ou Programa Solicitante", options=DIRECTORATES)
            with col_f2:
                req_email = st.text_input("E-mail Institucional", value=user.get("email", ""), disabled=True)
                req_project = st.text_input("Iniciativa ou Projeto Vinculado", placeholder="Ex: Campanha de Renovação 2026, Congresso Regional, etc.")

            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            req_objective = st.text_area(
                "Objetivo de Negócio & Decisão a ser Apoiada *",
                placeholder="Qual problema prático essa informação resolverá? Que decisão será tomada a partir desses dados?",
                help="Explique a finalidade estratégica do pedido."
            )

            req_scope = st.text_area(
                "Escopo dos Dados Necessários *",
                placeholder="Descreva métricas, filtros temporais, status de filiação, certificações ou grupos específicos de voluntários requeridos.",
                help="Especifique colunas, agregações ou cruzamentos esperados."
            )

            col_u1, col_u2 = st.columns(2)
            with col_u1:
                req_urgency = st.selectbox("Nível de Urgência", options=URGENCY_LEVELS)
            with col_u2:
                default_deadline = date.today() + timedelta(days=7)
                req_deadline = st.date_input("Prazo Desejado para Recebimento", value=default_deadline)

            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
            submit_req = st.form_submit_button("Registrar Requisição no Portal", type="primary", use_container_width=True)

            if submit_req:
                if not req_name.strip() or not req_project.strip() or not req_objective.strip() or not req_scope.strip():
                    st.error("Por favor, preencha todos os campos obrigatórios (Iniciativa, Objetivo e Escopo dos Dados).")
                else:
                    success = db_manager.create_data_request(
                        requester_name=req_name,
                        requester_email=user.get("email", ""),
                        directorate=req_dir,
                        project_initiative=req_project,
                        business_objective=req_objective,
                        data_scope=req_scope,
                        urgency=req_urgency.split(" ")[0],
                        deadline=str(req_deadline)
                    )
                    if success:
                        st.success("Requisição registrada com sucesso! Ela foi integrada à fila da Governança de Dados.")
                        st.rerun()
                    else:
                        st.error("Ocorreu um erro ao registrar a solicitação no banco de dados. Tente novamente.")

    # -------------------------------------------------------------------------
    # ABA 2: ACOMPANHAMENTO DE DEMANDAS
    # -------------------------------------------------------------------------
    with req_tabs[1]:
        st.markdown("### Painel de Acompanhamento de Demandas")
        
        # Filtro: Admin vê tudo; usuário comum vê apenas suas próprias demandas
        user_filter = None if role == "admin" else user.get("email", "")
        df_requests = db_manager.list_data_requests(user_filter)

        if df_requests.empty:
            st.info("Nenhuma requisição de dados registrada até o momento.")
        else:
            # Resumo visual
            col_st1, col_st2, col_st3, col_st4 = st.columns(4)
            with col_st1:
                st.metric("Total de Solicitações", len(df_requests))
            with col_st2:
                pendentes = len(df_requests[df_requests["status"] == "Pendente"])
                st.metric("Pendentes", pendentes)
            with col_st3:
                em_andamento = len(df_requests[df_requests["status"].isin(["Em Análise", "Em Desenvolvimento"])])
                st.metric("Em Andamento", em_andamento)
            with col_st4:
                concluidas = len(df_requests[df_requests["status"] == "Concluída"])
                st.metric("Concluídas", concluidas)

            st.markdown("<hr style='margin: 14px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

            # Lista em cards estruturados
            for _, rrow in df_requests.iterrows():
                rid = int(rrow["request_id"])
                r_status = str(rrow["status"])
                r_dir = str(rrow["directorate"])
                r_proj = str(rrow["project_initiative"])
                r_obj = str(rrow["business_objective"])
                r_scope = str(rrow["data_scope"])
                r_urg = str(rrow["urgency"])
                r_dead = str(rrow["deadline"]) if pd.notna(rrow.get("deadline")) else "A definir"
                r_date = str(rrow["created_at"])[:16]
                r_admin = str(rrow["admin_notes"]) if pd.notna(rrow.get("admin_notes")) and rrow.get("admin_notes") else "Aguardando triagem técnica."

                # Status color badge
                status_bg = "#FEF3C7" if r_status == "Pendente" else "#DBEAFE" if r_status in ["Em Análise", "Em Desenvolvimento"] else "#D1FAE5"
                status_color = "#92400E" if r_status == "Pendente" else "#1E40AF" if r_status in ["Em Análise", "Em Desenvolvimento"] else "#065F46"

                with st.expander(f"Demanda #{rid} — {r_proj} ({r_dir}) | Status: {r_status}", expanded=(r_status == "Pendente")):
                    col_det1, col_det2 = st.columns([3, 2])
                    with col_det1:
                        st.markdown(f"**Solicitante:** {rrow['requester_name']} ({rrow['requester_email']})")
                        st.markdown(f"**Iniciativa / Projeto:** {r_proj}")
                        st.markdown(f"**Objetivo Estratégico:**<br><span style='color: #334155;'>{r_obj}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Escopo Solicitado:**<br><span style='color: #334155;'>{r_scope}</span>", unsafe_allow_html=True)
                    with col_det2:
                        st.markdown(f"<span style='background-color: {status_bg}; color: {status_color}; padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 0.85rem;'>{r_status}</span>", unsafe_allow_html=True)
                        st.markdown(f"**Urgência:** {r_urg}")
                        st.markdown(f"**Prazo Desejado:** {r_dead}")
                        st.markdown(f"**Data de Abertura:** {r_date}")
                        st.markdown(f"**Parecer da Governança:**<br><em style='color: #475569;'>{r_admin}</em>", unsafe_allow_html=True)

                    # Painel de gestão exclusivo para Administradores
                    if role == "admin":
                        st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                        st.markdown("**Atualização de Status (Exclusivo Administrador):**")
                        col_adm1, col_adm2, col_adm3 = st.columns([2, 4, 2])
                        with col_adm1:
                            new_st = st.selectbox(
                                "Novo Status",
                                ["Pendente", "Em Análise", "Em Desenvolvimento", "Concluída", "Cancelada"],
                                index=["Pendente", "Em Análise", "Em Desenvolvimento", "Concluída", "Cancelada"].index(r_status) if r_status in ["Pendente", "Em Análise", "Em Desenvolvimento", "Concluída", "Cancelada"] else 0,
                                key=f"sel_status_req_{rid}"
                            )
                        with col_adm2:
                            new_notes = st.text_input("Parecer Técnico / Resposta", value=rrow.get("admin_notes", "") if pd.notna(rrow.get("admin_notes")) else "", key=f"notes_req_{rid}")
                        with col_adm3:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            if st.button("Salvar Atualização", key=f"btn_upd_req_{rid}", type="primary"):
                                if db_manager.update_data_request_status(rid, new_st, new_notes):
                                    st.success("Demanda atualizada!")
                                    st.rerun()
                                else:
                                    st.error("Erro ao atualizar demanda.")

    # -------------------------------------------------------------------------
    # ABA 3: INDICADORES DE GOVERNANÇA
    # -------------------------------------------------------------------------
    with req_tabs[2]:
        st.markdown("### Métricas de Apoio da Governança de Dados ao Capítulo")
        st.caption("Indicadores quantitativos de como o programa atende às demandas estratégicas das diversas diretorias.")

        df_all = db_manager.list_data_requests()
        if df_all.empty:
            st.info("Ainda não há dados suficientes para gerar os indicadores consolidados.")
        else:
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("#### Demandas por Diretoria Solicitante")
                dir_counts = df_all["directorate"].value_counts().reset_index()
                dir_counts.columns = ["Diretoria", "Total de Demandas"]
                st.dataframe(dir_counts, use_container_width=True, hide_index=True)
            with col_m2:
                st.markdown("#### Distribuição por Status de Atendimento")
                status_counts = df_all["status"].value_counts().reset_index()
                status_counts.columns = ["Status", "Quantidade"]
                st.dataframe(status_counts, use_container_width=True, hide_index=True)
