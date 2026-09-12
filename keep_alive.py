import os
import sys
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

DEFAULT_URL = "https://pmirio-govdados.streamlit.app/"

def main():
    target_url = os.getenv("APP_URL", DEFAULT_URL).strip()
    if not target_url:
        target_url = DEFAULT_URL

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando verificação de Keep-Alive para:")
    print(f"URL Alvo: {target_url}")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        start_time = time.time()
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(60)

        print("Navegando para o sistema...")
        driver.get(target_url)

        # Aguarda a página carregar (container do Streamlit ou elemento raiz HTML)
        wait = WebDriverWait(driver, 45)
        print("Aguardando carregamento da interface (Streamlit)...")

        # Verifica se o container do Streamlit ou a tag body carregou
        try:
            wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='stAppViewContainer'], div#root, body"))
            )
        except Exception as e:
            print(f"Aviso ao aguardar elemento específico do Streamlit: {e}")

        # Aguarda um tempo adicional para garantir que qualquer cold-start do Streamlit seja concluído
        time.sleep(5)

        title = driver.title
        elapsed = round(time.time() - start_time, 2)

        print("--------------------------------------------------")
        print(f"SUCESSO: Aplicação acessada com sucesso!")
        print(f"Título da Página: {title}")
        print(f"Tempo total de carregamento: {elapsed} segundos")
        print("--------------------------------------------------")

    except Exception as err:
        print(f"ERRO ao acessar a aplicação ({target_url}): {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        if driver:
            driver.quit()
            print("Sessão do Selenium finalizada.")

if __name__ == "__main__":
    main()
