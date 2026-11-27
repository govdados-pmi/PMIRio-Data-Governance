import os
import glob
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
import streamlit as st
import pandas as pd
try:
    import pptx
except ImportError:
    pptx = None

try:
    from docx import Document
except ImportError:
    Document = None


from database import db_manager

# Categorias oficiais de documentação e ativos do PMI Rio
CATEGORIES_LIST = [
    "Todos",
    "Canvas & Modelos de Projeto",
    "Apresentações Executivas",
    "Estudos & Inteligência de Dados",
    "Planilhas, Modelos & Censo",
    "Diretrizes, Políticas & Governança",
    "Termos de Abertura & Planejamento (TAP)",
    "Outros Documentos do Capítulo"
]


def natural_sort_key(s: str):
    """Ordenação natural para arquivos gerados como slide-1.png, slide-2.png, slide-10.png."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


@st.cache_data(show_spinner=False)
def get_or_generate_slide_images(file_path: str) -> List[str]:
    """
    Retorna a lista ordenada de imagens PNG em alta resolução geradas a partir dos slides da apresentação PPTX ou páginas de PDF (Canvas/Documento).
    Caso as imagens ainda não existam em cache, converte automaticamente via pdftoppm (e LibreOffice se for PPTX).
    """
    if not file_path or not os.path.exists(file_path):
        return []
    base_name = os.path.splitext(os.path.basename(file_path))[0].replace(" ", "_")
    cache_dir = os.path.abspath(os.path.join(".slide_cache", base_name))
    os.makedirs(cache_dir, exist_ok=True)

    # Verifica se os slides PNG já estão gerados no cache
    existing_slides = sorted(glob.glob(os.path.join(cache_dir, "slide-*.png")), key=natural_sort_key)
    if existing_slides:
        return existing_slides

    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            pdf_path = os.path.abspath(file_path)
        else:
            pdf_path = os.path.join(cache_dir, base_name + ".pdf")
            # Converte PPTX para PDF usando LibreOffice headless
            cmd_pdf = ["libreoffice", "--headless", "--convert-to", "pdf", os.path.abspath(file_path), "--outdir", cache_dir]
            subprocess.run(cmd_pdf, capture_output=True, check=True)

        # Converte as páginas do PDF em imagens PNG nítidas (150 DPI)
        cmd_ppm = ["pdftoppm", "-png", "-r", "150", pdf_path, os.path.join(cache_dir, "slide")]
        subprocess.run(cmd_ppm, capture_output=True, check=True)

        return sorted(glob.glob(os.path.join(cache_dir, "slide-*.png")), key=natural_sort_key)
    except Exception:
        return []


def get_asset_thumbnail(file_path: str, file_type: str = "pptx") -> Optional[str]:
    """Retorna o caminho da imagem de capa (primeiro slide ou página do Canvas) do ativo."""
    if file_type.lower() in ["pptx", "pdf"] and file_path and os.path.exists(file_path):
        slides = get_or_generate_slide_images(file_path)
        if slides:
            return slides[0]
    return None


@st.cache_data(show_spinner=False)
def load_study_pptx(file_path: str):
    """Extrai com segurança os textos e tópicos de cada slide da apresentação para acessibilidade e busca."""
    if not file_path or not os.path.exists(file_path) or pptx is None:
        return []
    try:
        prs = pptx.Presentation(file_path)
        slides_data = []
        for idx, slide in enumerate(list(prs.slides)):
            texts = []
            title = ""
            for shape in slide.shapes:
                if shape.has_text_frame:
                    t = shape.text_frame.text.strip()
                    if not t:
                        continue
                    if not title and len(t) < 90 and "\n" not in t:
                        title = t
                    else:
                        texts.append(t)
            if not title:
                title = f"Slide {idx + 1}"
            slides_data.append({
                "slide_num": idx + 1,
                "title": title,
                "body": "\n\n".join(texts)
            })
        return slides_data
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def load_study_docx(file_path: str):
    """Extrai os parágrafos e critérios do documento de texto DOCX."""
    if not file_path or not os.path.exists(file_path) or Document is None:
        return []
    try:
        doc = Document(file_path)
        return [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    except Exception:
        return []


def render_knowledge_library(user: Optional[Dict[str, Any]] = None, role: str = "view"):
    """
    Renderiza a interface corporativa da Biblioteca de Conhecimento do PMI Rio,
    com suporte integral a todas as categorias documentais (Canvases, Apresentações, TAP,
    Estudos, Diretrizes), status exclusivos (Publicado e Em Revisão),
    ranking dos mais populares e leitor visual governado.
    """
    # Inicializa estados de navegação na sessão
    if "library_viewing_asset_id" not in st.session_state:
        st.session_state["library_viewing_asset_id"] = None
    if "library_show_publish" not in st.session_state:
        st.session_state["library_show_publish"] = False
    if "library_selected_category" not in st.session_state:
        st.session_state["library_selected_category"] = "Todos"

    # Se um ativo específico estiver selecionado para leitura, exibe a tela do leitor
    if st.session_state["library_viewing_asset_id"] is not None:
        render_study_reader(st.session_state["library_viewing_asset_id"], role=role)
        return

    # Garante que as tabelas e dados iniciais da biblioteca existam
    try:
        db_manager.init_db()
    except Exception:
        pass

    # Carrega todos os ativos de conhecimento do banco
    df_all = db_manager.list_knowledge_assets()
    total_docs = len(df_all) if not df_all.empty else 0
    total_views = int(df_all["view_count"].sum()) if not df_all.empty and "view_count" in df_all.columns else 0
    publicados_count = len(df_all[df_all["status"] == "Publicado"]) if not df_all.empty else 0
    revisao_count = len(df_all[df_all["status"] == "Em Revisão"]) if not df_all.empty else 0

    # Determina saudação dinâmica com base na hora
    current_hour = datetime.now().hour
    greeting = "Bom dia" if current_hour < 12 else "Boa tarde" if current_hour < 18 else "Boa noite"
    user_name = user.get("full_name", "Líder PMI Rio") if user else "Líder PMI Rio"
    first_name = user_name.split()[0]

    # ==========================================================================
    # CABEÇALHO & BARRA DE AÇÃO
    # ==========================================================================
    col_greet, col_actions = st.columns([3, 2])
    with col_greet:
        st.markdown(
            f"""
            <div style="margin-bottom: 4px;">
                <h1 style="color: #0F172A; font-size: 1.85rem; font-weight: 700; margin: 0; padding: 0;">
                    {greeting}, {first_name}.
                </h1>
                <p style="color: #64748B; font-size: 0.95rem; margin-top: 4px; margin-bottom: 12px;">
                    <span style="background-color: #F1F5F9; color: #475569; padding: 3px 8px; border-radius: 12px; font-weight: 600; font-size: 0.82rem;">{total_docs} documentos no acervo</span>
                    &nbsp;•&nbsp;
                    <span style="color: #166534; font-weight: 600; font-size: 0.85rem;">{publicados_count} publicados</span>
                    &nbsp;•&nbsp;
                    <span style="color: #92400E; font-weight: 600; font-size: 0.85rem;">{revisao_count} em revisão</span>
                    &nbsp;•&nbsp;
                    <span style="color: #461DA3; font-weight: 600; font-size: 0.85rem;">{total_views} consultas registradas</span>
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_actions:
        col_btn1, col_btn2 = st.columns([2, 1.2])
        with col_btn1:
            search_query = st.text_input(
                "Buscar",
                placeholder="Buscar por título, diretoria, tag...",
                label_visibility="collapsed",
                key="lib_search_input"
            )
        with col_btn2:
            publish_label = "Fechar Publicação" if st.session_state["library_show_publish"] else "+ Publicar"
            if st.button(publish_label, type="primary", use_container_width=True, key="btn_toggle_publish"):
                st.session_state["library_show_publish"] = not st.session_state["library_show_publish"]
                st.rerun()

    # ==========================================================================
    # GAVETA DE PUBLICAÇÃO DE NOVO DOCUMENTO (+ Publicar)
    # ==========================================================================
    if st.session_state["library_show_publish"]:
        with st.container():
            st.markdown("""
            <div style="background-color: #FAF5FF; border: 1px solid #D8B4FE; border-left: 5px solid #461DA3; border-radius: 8px; padding: 18px 24px; margin-bottom: 24px;">
                <h3 style="color: #461DA3; font-size: 1.25rem; font-weight: 700; margin: 0 0 6px 0;">Publicar Novo Documento no Repositório do Capítulo</h3>
                <p style="color: #6B21A8; font-size: 0.9rem; margin: 0;">
                    Adicione Canvases de Projeto (.pdf/.pptx), apresentações executivas (.pptx), especificações metodológicas (.docx) ou planilhas analíticas com indexação corporativa.
                </p>
            </div>
            """, unsafe_allow_html=True)

            with st.form("form_publish_knowledge_asset", clear_on_submit=True):
                uploaded_file = st.file_uploader(
                    "Selecione o Arquivo (.pdf, .pptx, .docx, .xlsx):",
                    type=["pdf", "pptx", "docx", "xlsx"],
                    key="upload_lib_file"
                )

                c_p1, c_p2 = st.columns(2)
                with c_p1:
                    pub_title = st.text_input("Título do Documento / Ativo:", placeholder="Ex: Canvas do Projeto Observatório 2026")
                    pub_category = st.selectbox(
                        "Categoria do Ativo:",
                        options=CATEGORIES_LIST[1:],
                        index=0
                    )
                    pub_directorate = st.selectbox(
                        "Diretoria Responsável:",
                        options=[
                            "Diretoria de Filiação & Relacionamento",
                            "Diretoria de Voluntariado",
                            "Diretoria de Relacionamento & Certificação",
                            "Diretoria de Governança de Dados",
                            "Diretoria Executiva / Board",
                            "Diretoria de Operações & Eventos",
                            "Diretoria de Comunicação & Marketing"
                        ]
                    )
                with c_p2:
                    pub_author = st.text_input("Autor / Responsável Técnico:", value=user_name)
                    if role == "admin":
                        pub_status = st.selectbox(
                            "Status de Publicação:",
                            options=["Publicado", "Em Revisão"],
                            index=0
                        )
                    else:
                        st.text_input(
                            "Status de Publicação:",
                            value="Em Revisão",
                            disabled=True,
                            help="Envios de voluntários e usuários comuns entram compulsoriamente como 'Em Revisão' para homologação pela Governança de Dados."
                        )
                        pub_status = "Em Revisão"

                pub_summary = st.text_area(
                    "Resumo Executivo / Descrição do Ativo:",
                    placeholder="Descreva o objetivo do documento, principais entregas e público-alvo..."
                )
                pub_decision = st.text_input(
                    "Decisão de Gestão / Impacto Apoiado:",
                    placeholder="Ex: Alinhamento de escopo aprovado pelo Board para o ano corrente."
                )
                pub_sources = st.text_input(
                    "Fontes de Dados / Referências Utilizadas:",
                    placeholder="Ex: Planejamento Estratégico, ThoughtSpot, Atas da Diretoria."
                )

                c_sub1, c_sub2 = st.columns([1, 4])
                with c_sub1:
                    btn_save_asset = st.form_submit_button("Publicar Documento", type="primary", use_container_width=True)
                with c_sub2:
                    st.caption("O arquivo será arquivado de forma segura e disponibilizado para consulta em tela com controle de acessos.")

                if btn_save_asset:
                    if not pub_title or not pub_summary:
                        st.error("Informe ao menos o Título e o Resumo Executivo.")
                    elif not uploaded_file:
                        st.error("Faça o upload do arquivo correspondente.")
                    else:
                        file_ext = uploaded_file.name.split(".")[-1].lower()
                        cat_folder = "CANVAS PROJETOS" if "Canvas" in pub_category else "Estudos"
                        save_dir = os.path.join(cat_folder, pub_category.replace(" ", "_"))
                        os.makedirs(save_dir, exist_ok=True)
                        dest_file_path = os.path.join(save_dir, uploaded_file.name)
                        
                        with open(dest_file_path, "wb") as f_out:
                            f_out.write(uploaded_file.getbuffer())

                        # Converte slides/páginas em imagens em cache se for PPTX ou PDF
                        slide_count = 1
                        if file_ext in ["pptx", "pdf"]:
                            try:
                                slides = get_or_generate_slide_images(dest_file_path)
                                slide_count = len(slides) if slides else 1
                            except Exception:
                                pass

                        if db_manager.create_knowledge_asset(
                            title=pub_title,
                            category=pub_category,
                            directorate=pub_directorate,
                            author_name=pub_author,
                            status=pub_status,
                            summary=pub_summary,
                            decision_supported=pub_decision,
                            data_sources=pub_sources,
                            file_path=dest_file_path,
                            file_type=file_ext,
                            slide_count=slide_count,
                            is_featured=False
                        ):
                            st.session_state["library_show_publish"] = False
                            st.cache_data.clear()
                            if role == "admin":
                                st.success(f"Ativo '{pub_title}' cadastrado com sucesso com status '{pub_status}'!")
                            else:
                                st.success(f"Ativo '{pub_title}' submetido com sucesso! O documento foi registrado com status 'Em Revisão' e será homologado pelo Comitê de Governança de Dados.")
                            st.rerun()
                        else:
                            st.error("Erro ao registrar o ativo no banco de dados.")

        st.markdown("<hr style='margin: 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # ==========================================================================
    # SEÇÃO: MAIS POPULARES DA SEMANA (Ranking 1, 2, 3 - Em Alta)
    # ==========================================================================
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 18px; margin-bottom: 6px;">
        <div>
            <h3 style="color: #0F172A; font-size: 1.35rem; font-weight: 700; margin: 0;">Mais populares da semana</h3>
            <p style="color: #64748B; font-size: 0.88rem; margin: 2px 0 0 0;">Documentos e canvases mais visualizados e acessados pela Diretoria e voluntários.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    popular_df = df_all.sort_values(by="view_count", ascending=False).head(3) if not df_all.empty else pd.DataFrame()
    
    if not popular_df.empty:
        cols_pop = st.columns(len(popular_df))
        rank_colors = ["#D97706", "#475569", "#78350F"]
        
        for p_idx, (_, prow) in enumerate(popular_df.iterrows()):
            with cols_pop[p_idx]:
                p_id = int(prow["asset_id"])
                p_title = str(prow["title"])
                p_dir = str(prow["directorate"])
                p_status = str(prow["status"])
                p_views = int(prow.get("view_count", 0))
                p_slides = int(prow.get("slide_count", 1))
                p_file = str(prow.get("file_path", ""))
                p_type = str(prow.get("file_type", "pptx")).upper()
                p_thumb = get_asset_thumbnail(p_file, prow.get("file_type", "pptx"))

                # Status apenas Publicado (verde) ou Em Revisão (âmbar)
                status_bg = "#DCFCE7" if p_status == "Publicado" else "#FEF3C7"
                status_fg = "#166534" if p_status == "Publicado" else "#92400E"

                unit_label = "PÁGINAS" if p_type == "PDF" else "SLIDES"

                # Moldura de Card Corporativo com Imagem de Capa
                st.markdown(f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; overflow: hidden; box-shadow: 0 3px 10px rgba(0,0,0,0.05); margin-bottom: 8px;">
                    <div style="background-color: #0F172A; color: #FFFFFF; padding: 6px 12px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="background-color: {rank_colors[p_idx]}; color: #FFFFFF; font-weight: 700; border-radius: 50%; width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.85rem;">{p_idx + 1}</span>
                        <span style="font-size: 0.75rem; color: #CBD5E1; font-weight: 600;">{p_type} • {p_slides} {unit_label}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if p_thumb and os.path.exists(p_thumb):
                    st.image(p_thumb, use_container_width=True)
                else:
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #461DA3 0%, #36177B 100%); height: 130px; display: flex; align-items: center; justify-content: center; color: #FFFFFF; font-size: 1.05rem; font-weight: 700; border-radius: 4px; margin-bottom: 8px;">
                        PMI Rio • Documentação
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown(f"""
                <div style="padding: 4px 6px;">
                    <div style="margin-bottom: 6px;">
                        <span style="background-color: {status_bg}; color: {status_fg}; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;">{p_status}</span>
                    </div>
                    <h4 style="color: #0F172A; font-size: 0.98rem; font-weight: 700; margin: 0 0 6px 0; line-height: 1.35; min-height: 42px;">{p_title}</h4>
                    <p style="color: #64748B; font-size: 0.8rem; margin: 0 0 8px 0;">{p_dir}</p>
                    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #F1F5F9; padding-top: 6px; margin-bottom: 8px; font-size: 0.8rem; color: #475569;">
                        <span>{p_views} visualizações</span>
                        <span style="color: #461DA3; font-weight: 600;">Acesso Livre</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("Visualizar Documento", key=f"btn_open_pop_{p_id}", type="primary", use_container_width=True):
                    st.session_state["library_viewing_asset_id"] = p_id
                    st.rerun()

    # ==========================================================================
    # SEÇÃO: HISTÓRICO & ACERVO COMPLETO DE DOCUMENTOS DO CAPÍTULO
    # ==========================================================================
    st.markdown("<hr style='margin: 28px 0 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    
    col_rec_hdr, col_rec_filter = st.columns([3, 2])
    with col_rec_hdr:
        st.markdown("""
        <h3 style="color: #0F172A; font-size: 1.35rem; font-weight: 700; margin: 0;">Repositório Documental do Capítulo</h3>
        <p style="color: #64748B; font-size: 0.88rem; margin: 2px 0 0 0;">Canvases, especificações metodológicas, relatórios e apresentações organizados por eixo temático.</p>
        """, unsafe_allow_html=True)
    with col_rec_filter:
        c_sort1, c_sort2 = st.columns(2)
        with c_sort1:
            cat_choice = st.selectbox(
                "Filtrar Categoria:",
                options=CATEGORIES_LIST,
                key="lib_cat_filter"
            )
        with c_sort2:
            sort_choice = st.selectbox(
                "Ordenar por:",
                options=["Mais Populares", "Mais Recentes", "Título"],
                key="lib_sort_filter"
            )

    # Aplica os filtros na listagem
    sort_code = "popular" if sort_choice == "Mais Populares" else "recent" if sort_choice == "Mais Recentes" else "title"
    filtered_df = db_manager.list_knowledge_assets(
        category=cat_choice if cat_choice != "Todos" else None,
        sort_by=sort_code,
        search=search_query if search_query else None
    )

    if filtered_df.empty:
        st.info("Nenhum documento encontrado com os filtros aplicados.")
    else:
        st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
        for _, row in filtered_df.iterrows():
            a_id = int(row["asset_id"])
            a_title = str(row["title"])
            a_cat = str(row["category"])
            a_dir = str(row["directorate"])
            a_author = str(row["author_name"])
            a_status = str(row["status"])
            a_views = int(row.get("view_count", 0))
            a_summary = str(row.get("summary", ""))[:145] + ("..." if len(str(row.get("summary", ""))) > 145 else "")
            a_date = str(row.get("created_at", ""))[:10]
            a_file = str(row.get("file_path", ""))
            a_type = str(row.get("file_type", "pptx")).upper()

            status_bg = "#DCFCE7" if a_status == "Publicado" else "#FEF3C7"
            status_fg = "#166534" if a_status == "Publicado" else "#92400E"

            with st.container():
                c_row1, c_row2, c_row3 = st.columns([1, 4, 1.2])
                with c_row1:
                    a_thumb = get_asset_thumbnail(a_file, row.get("file_type", "pptx"))
                    if a_thumb and os.path.exists(a_thumb):
                        st.image(a_thumb, use_container_width=True)
                    else:
                        st.markdown(f"""
                        <div style="background-color: #F1F5F9; border-radius: 6px; height: 75px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #461DA3; font-size: 0.85rem;">
                            {a_type}
                        </div>
                        """, unsafe_allow_html=True)

                with c_row2:
                    st.markdown(f"""
                    <div style="padding-left: 6px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <span style="color: #0F172A; font-weight: 700; font-size: 1.05rem;">{a_title}</span>
                            <span style="background-color: {status_bg}; color: {status_fg}; font-size: 0.72rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;">{a_status}</span>
                        </div>
                        <p style="color: #475569; font-size: 0.85rem; line-height: 1.4; margin: 0 0 4px 0;">{a_summary}</p>
                        <p style="color: #64748B; font-size: 0.78rem; margin: 0;">
                            <span style="color: #461DA3; font-weight: 600;">{a_cat}</span> &nbsp;•&nbsp; <strong>{a_dir}</strong> &nbsp;•&nbsp; Autor: {a_author} &nbsp;•&nbsp; Cadastrado em: {a_date}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

                with c_row3:
                    st.markdown(f"""
                    <div style="text-align: right; margin-bottom: 8px; color: #64748B; font-size: 0.85rem;">
                        <strong>{a_views}</strong> visualizações
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("Abrir Documento", key=f"btn_open_row_{a_id}", use_container_width=True):
                        st.session_state["library_viewing_asset_id"] = a_id
                        st.rerun()

                st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px solid #F1F5F9;'>", unsafe_allow_html=True)


def render_study_reader(asset_id: int, role: str = "view"):
    """
    Renderiza o leitor governado em tela do estudo ou documento selecionado,
    incluindo visualizador de lâminas de alta resolução (para Canvas/PPTX/PDF),
    resumo de decisão, metodologia e fontes de dados.
    """
    # Incrementa as visualizações do documento no banco
    db_manager.increment_asset_views(asset_id)

    asset = db_manager.get_knowledge_asset(asset_id)
    if not asset:
        st.error("Documento não encontrado no acervo.")
        if st.button("◀ Voltar para a Biblioteca"):
            st.session_state["library_viewing_asset_id"] = None
            st.rerun()
        return

    # Botão de retorno ao catálogo
    col_b1, col_b2 = st.columns([1, 4])
    with col_b1:
        if st.button("◀ Voltar ao Acervo", type="secondary", use_container_width=True, key="btn_back_to_catalog"):
            st.session_state["library_viewing_asset_id"] = None
            st.rerun()

    # Cabeçalho do Estudo
    status_bg = "#DCFCE7" if asset['status'] == "Publicado" else "#FEF3C7"
    status_fg = "#166534" if asset['status'] == "Publicado" else "#92400E"

    st.markdown(f"""
    <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-top: 4px solid #461DA3; border-radius: 8px; padding: 20px 24px; box-shadow: 0 3px 10px rgba(0,0,0,0.04); margin-bottom: 20px; margin-top: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div>
                <span style="background-color: {status_bg}; color: {status_fg}; font-size: 0.78rem; font-weight: 700; padding: 3px 10px; border-radius: 4px;">{asset['status']}</span>
                <span style="color: #64748B; font-size: 0.85rem; margin-left: 8px; font-weight: 600;">{asset['category']}</span>
            </div>
            <span style="color: #64748B; font-size: 0.85rem; font-weight: 600;">👁 {asset['view_count']} consultas</span>
        </div>
        <h2 style="color: #0F172A; font-size: 1.45rem; font-weight: 700; margin: 4px 0 10px 0;">{asset['title']}</h2>
        <div style="display: flex; gap: 24px; font-size: 0.88rem; color: #475569; border-top: 1px solid #F1F5F9; padding-top: 10px;">
            <span><strong>Diretoria:</strong> {asset['directorate']}</span>
            <span><strong>Responsável:</strong> {asset['author_name']}</span>
            <span><strong>Cadastrado em:</strong> {str(asset['created_at'])[:10]}</span>
            <span><strong>Formato:</strong> {str(asset.get('file_type', '')).upper()} (Consulta em Tela)</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Banner de Governança e Ações Administrativas
    if role == "admin":
        st.markdown(f"""
        <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-left: 4px solid #461DA3; padding: 12px 18px; border-radius: 6px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 0.88rem; color: #334155;">
                <strong>Painel de Homologação (Admin):</strong> Status atual: <strong>{asset['status']}</strong>.
            </div>
        </div>
        """, unsafe_allow_html=True)
        col_adm1, col_adm2 = st.columns([2, 1])
        with col_adm2:
            if asset['status'] == "Em Revisão":
                if st.button("✓ Homologar & Publicar", type="primary", use_container_width=True, key=f"btn_approve_{asset_id}"):
                    if db_manager.update_knowledge_asset_status(asset_id, "Publicado"):
                        st.success("Documento homologado e publicado com sucesso no acervo oficial!")
                        st.cache_data.clear()
                        st.rerun()
            elif asset['status'] == "Publicado":
                if st.button("Mover para Revisão", type="secondary", use_container_width=True, key=f"btn_revert_{asset_id}"):
                    if db_manager.update_knowledge_asset_status(asset_id, "Em Revisão"):
                        st.info("Documento alterado para status 'Em Revisão'.")
                        st.cache_data.clear()
                        st.rerun()

    st.markdown("""
    <div style="background-color: #F8FAFC; border-left: 4px solid #44789B; padding: 10px 16px; border-radius: 4px; margin-bottom: 18px; font-size: 0.86rem; color: #475569;">
        <strong>Governança Documental PMI Rio:</strong> Documento corporativo disponibilizado estritamente para visualização e consulta estratégica. O download do arquivo bruto está desabilitado para conformidade com a LGPD e preservação dos ativos de conhecimento do capítulo.
    </div>
    """, unsafe_allow_html=True)

    file_path = asset.get("file_path", "")
    file_type = str(asset.get("file_type", "pptx")).lower()

    # Abas do Leitor
    r_tabs = st.tabs([
        "Visualização em Tela (Lâminas / Canvas)",
        "Resumo Executivo & Decisão",
        "Metodologia & Critérios",
        "Fontes de Dados & Rastreabilidade"
    ])

    # 1. Visualização em Tela
    with r_tabs[0]:
        if file_path and os.path.exists(file_path):
            if file_type in ["pptx", "pdf"]:
                slide_images = get_or_generate_slide_images(file_path)
                slides_text = load_study_pptx(file_path) if file_type == "pptx" else []
                total_slides = max(len(slide_images), len(slides_text), 1)

                if slide_images:
                    unit_name = "Página" if file_type == "pdf" else "Slide"

                    if total_slides > 1:
                        col_m1, col_m2 = st.columns([3, 1])
                        with col_m1:
                            mode = st.radio(
                                "Modo de Visualização:",
                                options=[f"{unit_name} a {unit_name}", f"Mural Completo (Todas as {unit_name}s)"],
                                horizontal=True,
                                key=f"reader_mode_{asset_id}"
                            )
                    else:
                        mode = f"{unit_name} a {unit_name}"

                    if mode.startswith(f"{unit_name} a {unit_name}"):
                        nav_key = f"reader_slide_idx_{asset_id}"
                        if nav_key not in st.session_state:
                            st.session_state[nav_key] = 1

                        if total_slides > 1:
                            c_prev, c_sel, c_next = st.columns([1, 4, 1])
                            with c_prev:
                                if st.button("◀ Anterior", key=f"btn_r_prev_{asset_id}", use_container_width=True):
                                    if st.session_state[nav_key] > 1:
                                        st.session_state[nav_key] -= 1
                                        st.rerun()
                            with c_next:
                                if st.button("Próximo ▶", key=f"btn_r_next_{asset_id}", use_container_width=True):
                                    if st.session_state[nav_key] < total_slides:
                                        st.session_state[nav_key] += 1
                                        st.rerun()
                            with c_sel:
                                def slide_label(s_idx):
                                    hint = ""
                                    if s_idx - 1 < len(slides_text):
                                        t = slides_text[s_idx - 1]["title"]
                                        if t and t != f"Slide {s_idx}":
                                            hint = f" — {t[:40]}"
                                    return f"{unit_name} {s_idx} de {total_slides}{hint}"

                                selected_s = st.selectbox(
                                    unit_name,
                                    options=list(range(1, total_slides + 1)),
                                    index=st.session_state[nav_key] - 1,
                                    format_func=slide_label,
                                    label_visibility="collapsed",
                                    key=f"reader_select_{asset_id}"
                                )
                                st.session_state[nav_key] = selected_s

                        curr = st.session_state[nav_key]
                        if curr <= len(slide_images):
                            st.markdown(f"""
                            <div style="background-color: #0F172A; padding: 10px; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.12); margin-top: 10px; margin-bottom: 12px; text-align: center;">
                                <div style="color: #94A3B8; font-size: 0.85rem; font-weight: 600; text-align: right;">
                                    {asset['category']} — {unit_name} {curr} de {total_slides}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.image(slide_images[curr - 1], use_container_width=True)

                        if slides_text and curr <= len(slides_text):
                            c_txt = slides_text[curr - 1]
                            if c_txt.get("body"):
                                with st.expander("Transcrição & Notas do Apresentador (Acessibilidade & Busca)", expanded=False):
                                    st.markdown(f"**Título:** {c_txt['title']}")
                                    st.text(c_txt["body"])
                    else:
                        st.markdown(f"#### Mural Completo — Visão Sequencial ({total_slides} {unit_name}s)")
                        for s_num, img_p in enumerate(slide_images, start=1):
                            st.markdown(f"<div style='margin-top: 16px; margin-bottom: 4px; font-weight: 600; color: #461DA3;'>{unit_name} {s_num} de {total_slides}</div>", unsafe_allow_html=True)
                            st.image(img_p, use_container_width=True)
                            st.markdown("<hr style='margin: 10px 0; border: none; border-top: 1px dashed #CBD5E1;'>", unsafe_allow_html=True)
                else:
                    st.info("Não foi possível processar as páginas visuais deste arquivo.")
            elif file_type == "docx":
                paragraphs = load_study_docx(file_path)
                if paragraphs:
                    st.markdown("### Documento de Especificação & Metodologia")
                    for p in paragraphs:
                        st.markdown(f"<p style='color: #1E293B; line-height: 1.6;'>{p}</p>", unsafe_allow_html=True)
                else:
                    st.info("Documento sem conteúdo textual localizado.")
            else:
                st.info(f"Visualizador em tela habilitado para formato {file_type.upper()}.")
        else:
            st.info("Arquivo correspondente a este ativo não localizado no diretório correspondente.")

    # 2. Resumo Executivo & Decisão
    with r_tabs[1]:
        st.markdown("### Resumo do Documento / Ativo")
        st.markdown(f"<div style='font-size: 1.02rem; line-height: 1.6; color: #1E293B;'>{asset['summary']}</div>", unsafe_allow_html=True)

        if asset.get("decision_supported"):
            st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
            st.markdown("### Decisão de Gestão Apoiada")
            st.markdown(f"""
            <div style="background-color: #F0F4F8; border-left: 4px solid #44789B; padding: 14px 18px; border-radius: 6px;">
                <strong style="color: #270F53;">Impacto na Governança do Capítulo:</strong><br>
                <span style="color: #334155;">{asset['decision_supported']}</span>
            </div>
            """, unsafe_allow_html=True)

    # 3. Metodologia & Critérios
    with r_tabs[2]:
        st.markdown("### Framework de Governança & Padrões do PMI Rio")
        st.markdown("""
        <p style="color: #475569; line-height: 1.6;">
            A documentação oficial do PMI Rio (incluindo Canvases de Projeto, Termos de Abertura, Planilhas de Censo e Decks de Gestão) 
            segue os preceitos de sustentabilidade, rastreabilidade e boas práticas globais de gerenciamento de projetos.
        </p>
        """, unsafe_allow_html=True)

    # 4. Fontes de Dados & Rastreabilidade
    with r_tabs[3]:
        st.markdown("### Rastreabilidade & Referências do Documento")
        st.markdown("<p style='color: #64748B;'>Bases, normas e origens documentais auditadas pelo Comitê de Dados:</p>", unsafe_allow_html=True)
        sources = asset.get("data_sources", "")
        if sources:
            for s in sources.split(","):
                st.markdown(f"<div style='padding: 8px 12px; margin-bottom: 6px; background-color: #F1F5F9; border-radius: 6px; color: #1E293B;'>✓ {s.strip()}</div>", unsafe_allow_html=True)
        else:
            st.caption("Documento corporativo aprovado e auditado pelo capítulo.")
