# PMI Rio — Portal de Governança, Ingestão ETL & Autoatendimento de Dados 📊

Solução completa de autoatendimento seguro de dados, pipeline de ETL incremental e governança relacional baseada no **PMI Brand Guidelines (2024)** para o **PMI Rio Chapter**.

---

## 📌 Principais Recursos

- **Identidade Visual Oficial PMI**: Interface desenvolvida no Streamlit utilizando as cores oficiais da marca (`#461DA3`, `#44789B`, `#6CBEDE`, `#E0611F`, `#B29478`) e tipografia institucional.
- **Controle de Acessos & RBAC**:
  - **👑 Acesso Total (admin)**: Gestão de usuários, Ingestão de planilhas (ETL), Console SQL Live e Central de Relatórios.
  - **👁️ Acesso de Visualização (view)**: Acesso restrito e granular exclusivamente aos relatórios autorizados pelo administrador.
- **Pipeline de Ingestão ETL Incremental**:
  - **Processamento de Filiados**: Deduplicação por `(personid, startdateforterm)`, rastreabilidade de histórico em `person_history` (e-mail, telefone, endereço), armazenamento de e-mail anterior em `alternativeemail` e cálculo de fallback de `tenureinyears`.
  - **Certificações**: Filtro estrito de registros com concessão válida (`originalgrantdate`) e deduplicação por `(certificationid, certificationtypename, effectivestartdate)`.
  - **Voluntários**: Deduplicação e filtragem de candidaturas ativas.
- **Console SQL Live & Gerador de Relatórios Customizados**: Execução de consultas SQL no banco e salvamento direto de consultas como novos relatórios dinâmicos na Central de Relatórios.
- **Central de Relatórios Executivos**:
  - **Filiados Ativos** (`enddateforterm >= data_referencia`)
  - **Aniversariantes** (ativos e completando marcos de 1, 3, 5, 10, 15, 20 ou 25 anos)
  - **Voluntários Ativos**
  - **Novos Filiados (30D)**, **Desfiliados (30D)**, **A Vencer (30/90D)**, **Certificados (3M)**
  - Downloads em **Excel (.xlsx)** e **CSV** posicionados estrategicamente acima das tabelas.

---

## 🏗️ Estrutura do Projeto

```text
Voluntariado/
├── app.py                # Aplicação Principal Streamlit (UI, RBAC & Console SQL)
├── database.py           # Gerenciador de Banco de Dados (PostgreSQL Supabase / SQLite)
├── etl.py                # Pipeline de ETL Incremental (Processamento de 80k+ registros)
├── reports.py            # Gerenciador da Central de Relatórios & Exportações
├── schema.sql            # Script DDL de Modelo Relacional do Banco
├── .streamlit/
│   └── config.toml       # Configuração de Tema com a Paleta Oficial do PMI
├── .gitignore            # Proteção contra commit de dados sensíveis e planilhas (LGPD)
├── .env.example          # Modelo de configuração de variáveis de ambiente
└── requirements.txt      # Dependências Python para execução e deployment
```

---

## 🚀 Como Executar o Projeto Localmente

### 1. Clonar o Repositório
```bash
git clone https://github.com/SEU_USUARIO/PMIRio-Data-Governance.git
cd PMIRio-Data-Governance
```

### 2. Criar Ambiente Virtual e Instalar Dependências
```bash
python3 -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar Conexão com o Banco de Dados (Opcional)
Se desejar conectar diretamente ao **Supabase (PostgreSQL)**, crie um arquivo `.env` baseado no `.env.example`:
```bash
cp .env.example .env
```
Preencha a variável `SUPABASE_DB_URL`. Se não configurado, a aplicação utilizará o banco SQLite local (`voluntariado.db`) como fallback resiliente automaticamente.

### 4. Iniciar a Aplicação
```bash
streamlit run app.py
```

Acesse em seu navegador em `http://localhost:8501`.

---

## 🛡️ Segurança & LGPD (Importante)

Por questões de segurança e conformidade com a LGPD:
- Arquivos `.xlsx`, `.csv`, `.db` e diretórios com planilhas reais da diretoria estão **estritamente ignorados no `.gitignore`** e não devem ser enviados para o repositório público.
- Credenciais e strings de conexão de banco de dados devem ser mantidas em Variáveis de Ambiente ou configuradas no **Streamlit Secrets**.
