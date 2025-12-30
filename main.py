from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import openpyxl
import time

service = Service()
options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=service, options=options)

url = "https://www.circulo.com.br/receitas?termo=&dificuldade=&categoria=&tecnica=&peca=&produto=2286"
driver.get(url)

wait = WebDriverWait(driver, 10)

links = wait.until(
    EC.presence_of_all_elements_located(
        (By.XPATH, "//a[contains(@href, '/receitas/') and not(contains(@href, '?'))]")
    )
)

urls_receitas = [
    link.get_attribute("href")
    for link in links
    if link.is_displayed()
]

urls_receitas = list(set(urls_receitas))

df_receitas = pd.DataFrame(columns=['titulo','url','materiais', 'receita'])

for url_receita in urls_receitas:
    driver.get(url_receita)

    titulo = wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "h2"))
    ).text


    try:
        materiais_detalhe = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "receita-detalhe__conteudo"))
        ).text
    except:
        materiais_detalhe = ""
        
    try:
        receita_detalhe = wait.until(
            EC.presence_of_element_located((By.CLASS_NAME, "receita-detalhe__execucao"))
        ).text
    except:
        receita_detalhe = ""
    df_receitas.loc[len(df_receitas)]=[titulo, url_receita, materiais_detalhe, receita_detalhe]
    time.sleep(1)


df_receitas.to_csv('dados.csv', sep=';', encoding='utf8')

driver.quit()
