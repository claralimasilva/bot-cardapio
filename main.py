import os
import requests
from bs4 import BeautifulSoup
import telebot
import schedule
import time
import threading
import logging
import re
from datetime import datetime
import holidays

# ---------------------------------------
# CONFIGURAÇÕES
# ---------------------------------------
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
bot = telebot.TeleBot(TOKEN)

cache_cardapio = {}
logging.basicConfig(level=logging.INFO)

def pega_cardapio_formatado(refeicao):
    hoje = datetime.now().date()

    if hoje in cache_cardapio:
        texto = cache_cardapio[hoje]
    else:
        url = "https://www.ufc.br/restaurante/cardapio/1-restaurante-universitario-de-fortaleza"
        response = requests.get(url)
        if response.status_code != 200:
            return "Erro ao buscar o cardápio."

        soup = BeautifulSoup(response.content, "html.parser")
        cardapio_div = soup.find("div", class_="c-cardapios")
        if not cardapio_div:
            return "Cardápio não encontrado."

        texto = cardapio_div.get_text(separator="\n", strip=True)
        cache_cardapio[hoje] = texto

    linhas = [linha.strip() for linha in texto.split("\n") if linha.strip()]
    seções = {"Desjejum": [], "Almoço": [], "Jantar": []}
    refeicao_atual = None
    categoria_atual = None
    sobremesa_ja_criada = False

    emoji_categoria = {
        "salada": "🥬",
        "suco": "🧃",
    }

    categorias_site = [
        "principal", "vegetariano", "salada", "guarnição", "acompanhamento",
        "suco", "sobremesa", "frutas", "bebidas", "pães", "especial"
    ]

    for linha in linhas:
        if linha.lower().startswith(("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")):
            continue

        if linha.lower() in ["desjejum", "almoço", "jantar"]:
            refeicao_atual = linha.capitalize()
            categoria_atual = None
            sobremesa_ja_criada = False
            continue

        if linha.lower() in categorias_site:
            categoria_atual = linha.lower()
            if categoria_atual == "sobremesa" and not sobremesa_ja_criada:
                seções[refeicao_atual].append(f"\n🍉🍬 *SOBREMESA*")
                sobremesa_ja_criada = True
            elif categoria_atual != "sobremesa":
                emoji = emoji_categoria.get(categoria_atual, "🍽️")
                seções[refeicao_atual].append(f"\n{emoji} *{linha.upper()}*")
                if categoria_atual == "salada":
                    seções[refeicao_atual].append("- Alface")
            continue

        if re.match(r"\(.*contém.*\)", linha.lower()):
            continue

        if linha.lower() == "doce":
            if not sobremesa_ja_criada:
                seções[refeicao_atual].append(f"\n🍉🍬 *SOBREMESA*")
                sobremesa_ja_criada = True
            seções[refeicao_atual].append("- Doce")
            continue

        if refeicao_atual and categoria_atual:
            seções[refeicao_atual].append(f"- {linha}")

    if refeicao.capitalize() not in seções or not seções[refeicao.capitalize()]:
        return f"Nenhum item encontrado para {refeicao}."

    return "\n".join(seções[refeicao.capitalize()])


# ---------------------------------------
# COMANDOS
# ---------------------------------------
def envia_cardapio(message, refeicao):
    texto = pega_cardapio_formatado(refeicao)
    bot.reply_to(message, texto, parse_mode="Markdown")

@bot.message_handler(commands=['desjejum'])
def cmd_desjejum(message):
    envia_cardapio(message, "Desjejum")

@bot.message_handler(commands=['almoco'])
def cmd_almoco(message):
    envia_cardapio(message, "Almoço")

@bot.message_handler(commands=['jantar'])
def cmd_jantar(message):
    envia_cardapio(message, "Jantar")

@bot.message_handler(commands=['hoje'])
def cmd_hoje(message):
    resposta = []
    for r in ["Desjejum", "Almoço", "Jantar"]:
        resposta.append(f"*{r.upper()}*\n{pega_cardapio_formatado(r)}\n")
    bot.reply_to(message, "\n".join(resposta), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def cmd_chat_id(message):
    logging.info(f"Chat ID: {message.chat.id}")
    bot.reply_to(message, f"Seu chat_id é: {message.chat.id}")

# ---------------------------------------
# AGENDAMENTO COM VERIFICAÇÃO DE FERIADO
# ---------------------------------------
def is_dia_util_sem_feriado():
    hoje = datetime.now().date()
    if hoje.weekday() >= 5:
        return False  # sábado (5) ou domingo (6)
    feriados_br = holidays.Brazil()
    return hoje not in feriados_br

def job():
    if is_dia_util_sem_feriado():
        cardapio = pega_cardapio_formatado("Almoço")
        bot.send_message(CHAT_ID, cardapio, parse_mode="Markdown")
        logging.info("Cardápio enviado!")
    else:
        logging.info("Hoje é final de semana ou feriado. Nada enviado.")

def agendador():
    schedule.every().day.at("11:00").do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=agendador).start()
bot.polling()
