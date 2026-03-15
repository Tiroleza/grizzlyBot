# 🐻 grizzly-bot

Bot de trading automatizado para criptomoedas na Binance com notificações via Telegram.  
Opera em modo **simulado** — consulta dados reais do mercado e executa operações fictícias para validação de estratégias sem risco financeiro.

---

## 📋 Visão Geral

O grizzlyBot é um simulador de trading que consome dados em tempo real da API da Binance, aplica uma estratégia baseada em cruzamento de médias móveis com filtros de volume e tendência, e reporta cada decisão via Telegram com gráficos e métricas detalhadas.

**Modo de operação:** dados reais, trades simulados.

---

## ⚙️ Stack

| Componente        | Tecnologia                          |
|-------------------|-------------------------------------|
| Linguagem         | Python 3.10+                        |
| Exchange API      | Binance (via `python-binance`)      |
| Notificações      | Telegram Bot API                    |
| Análise de dados  | Pandas                              |
| Gráficos          | Matplotlib                          |
| Variáveis de ambiente | python-dotenv                   |

---

## 🧠 Estratégia

O bot utiliza uma estratégia de **cruzamento de médias móveis** com múltiplos filtros para reduzir falsos sinais:

| Indicador           | Configuração       | Função                        |
|---------------------|---------------------|-------------------------------|
| MA Rápida           | 12 períodos         | Detecção de momentum          |
| MA Lenta            | 50 períodos         | Confirmação de tendência      |
| EMA 200             | 200 períodos (exp.) | Filtro de tendência macro     |
| Volume              | Média de 5 candles  | Confirmação de liquidez       |

### Condições de Entrada (BUY)
- Cruzamento da MA rápida acima da MA lenta (golden cross)
- Distância mínima de 0.5% entre as médias
- Preço acima da EMA 200
- Volume do candle atual > 110% da média dos últimos 5 candles

### Condições de Saída (SELL)
- Reversão de tendência (MA rápida abaixo da MA lenta)
- Preço abaixo da MA lenta com posição aberta
- **Stop-loss automático:** -2% abaixo do preço de entrada

### Gestão de Risco
- **Risco por trade:** 4% do capital total
- **Stop-loss fixo:** 2%
- **Taxa simulada:** 0.075% (taxa maker real da Binance)

---

## 🚀 Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/Tiroleza/grizzlyBot.git
cd grizzlyBot
```

### 2. Crie e ative o ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
BINANCE_API_KEY=sua_api_key_aqui
BINANCE_SECRET_KEY=sua_secret_key_aqui
TELEGRAM_BOT_TOKEN=seu_token_do_bot_aqui
```

> ⚠️ **Nunca commite o arquivo `.env`.** Ele já está listado no `.gitignore`.

### 5. Configure o acesso Telegram

Execute o script de autorização para registrar os IDs de chat autorizados a receber notificações:

```bash
python3 src/telegram_auth.py
```

Envie o comando `/robbery4` para o bot no Telegram para autorizar seu chat.

---

## ▶️ Uso

```bash
python3 src/trading_bot.py
```

O bot irá:
1. Conectar-se à API da Binance e validar a conexão
2. Consultar dados de mercado a cada 30 segundos
3. Calcular indicadores técnicos (MA 12, MA 50, EMA 200)
4. Gerar sinais de compra/venda com base na estratégia
5. Executar trades simulados e enviar relatórios via Telegram
6. Gerar gráficos com indicadores a cada operação

---

## 📂 Estrutura do Projeto

```
grizzlyBot/
├── src/
│   ├── trading_bot.py         # Bot principal — loop de simulação
│   ├── telegram_auth.py       # Autorização de usuários via Telegram
│   └── strategies/
│       └── moving_average.py  # Classe de estratégia (módulo extensível)
├── .env                       # Variáveis de ambiente (não versionado)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 📊 Notificações Telegram

O bot envia mensagens detalhadas a cada ciclo de análise:

- **📊 Análise do Mercado** — indicadores, sinais ativos, volume
- **🟢 Compra Simulada** — quantidade, preço, taxa, stop-loss
- **🔴 Venda Simulada** — receita, P/L da operação, relatório da carteira
- **🛑 Stop-Loss Atingido** — preço de entrada, perda percentual
- **📈📉 Gráficos** — chart com preço, médias móveis e linhas de entrada/stop

---

## 🔐 Segurança

- Chaves de API são carregadas exclusivamente via variáveis de ambiente (`.env`)
- Nenhuma credencial é hardcoded no código-fonte
- O arquivo `authorized_ids.json` é gerado localmente e ignorado pelo Git
- O bot **não executa ordens reais** — opera exclusivamente em modo simulado

---

## 📄 Licença

Este projeto é distribuído sob a licença MIT. Consulte o arquivo `LICENSE` para mais detalhes.
