import os
import time
from datetime import datetime
import logging
import json
import matplotlib.pyplot as plt
import pandas as pd
import requests
import html

from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv

KLINE_COLUMNS = [
    "time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_volume", "taker_quote_volume", "ignore"
]

NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume"]

# Configuração inicial
load_dotenv()
logging.basicConfig(
    filename='trading_simulation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        def load_authorized_ids():
            try:
                with open("authorized_ids.json", "r") as f:
                    return json.load(f)
            except:
                return []
        self.authorized_ids = load_authorized_ids()
    
    def send_message(self, message):
        if not self.token or not self.authorized_ids:
            return
        sanitized_message = html.escape(message)  # Escapa caracteres especiais do HTML
        for chat_id in self.authorized_ids:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": sanitized_message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True
                    }
                )
            except Exception as e:
                logger.error(f"Erro ao enviar para {chat_id}: {e}")
    
    def send_photo(self, caption, image_path="grafico.png"):
        if not self.token or not self.authorized_ids:
            return

        for chat_id in self.authorized_ids:
            try:
                with open(image_path, "rb") as photo:
                    requests.post(
                        f"https://api.telegram.org/bot{self.token}/sendPhoto",
                        data={
                            "chat_id": chat_id, 
                            "caption": caption, 
                            "parse_mode": "HTML"
                        },
                        files={"photo": photo}
                    )
            except Exception as e:
                logger.error(f"Erro ao enviar imagem para {chat_id}: {e}")

class BinanceSimulator:
    def __init__(self):
        self.telegram = TelegramNotifier()
        self.client = Client(
            os.getenv("BINANCE_API_KEY"),
            os.getenv("BINANCE_SECRET_KEY")
        )
        self._setup_config()
        self._setup_state()
        self.test_connection()
        self.initialize_cross_analysis()
        self._log_start()

    def _setup_config(self):
        self.symbol = "BNBUSDT"
        self.interval = Client.KLINE_INTERVAL_1MINUTE
        self.risk_per_trade = 0.04
        self.min_distance_pct = 0.2
        self.min_volume_pct = 0.45

    def _setup_state(self):
        self.balance = 30000
        self.position = 0
        self.entry_price = 0
        self.trade_history = []
        self.current_price = 0
        self.initial_candles_to_load = 200
        self.cross_status = False
        self.stop_loss_cooldown = 0
        self.force_cross = True

    def _log_start(self):
        self.telegram.send_message(
            f"🚀 Iniciando Simulação\n"
            f"Par: {self.symbol}\n"
            f"Saldo inicial: BRL {self.balance:.2f}\n"
            f"Intervalo: {self.interval}\n"
            f"Risco por trade: {self.risk_per_trade*100}%\n"
            f"Modo: Consulta Real + Operação Simulada"
        )
        print("\n🔍 Modo Debug Ativo")
        print(f"Par: {self.symbol}")
        print(f"Intervalo: {self.interval}")
        print(f"Saldo inicial: BRL {self.balance:.2f}")
        print(f"Risco por trade: {self.risk_per_trade*100}%\n")

    def test_connection(self):
        """Testa a conexão com a API da Binance"""
        try:
            print("🔌 Testando conexão com Binance...")
            self.client.get_server_time()
            print("✅ Conexão OK")
        except Exception as e:
            print(f"❌ Falha na conexão: {e}")
            raise

    def build_dataframe(self, candles):
        df = pd.DataFrame(candles, columns=KLINE_COLUMNS)
        df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].astype(float)
        return df

    def initialize_cross_analysis(self):
        """Carrega dados históricos e analisa cruzamentos prévios"""
        try:
            print("🔍 Analisando cruzamentos históricos...")
            candles = self.client.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=self.initial_candles_to_load
            )
        
            df = self.build_dataframe(candles)
        
            # Calcula médias
            df["ma_fast"] = df["close"].rolling(12).mean()
            df["ma_slow"] = df["close"].rolling(50).mean()
        
            # Analisa os últimos candles para determinar estado inicial
            self.cross_status =  True # df["ma_fast"].iloc[-1] > df["ma_slow"].iloc[-1]
        
            print(f"✅ Estado inicial do cruzamento: {'MA12 acima da MA50' if self.cross_status else 'MA12 abaixo da MA50'}")
        
        except Exception as e:
            print(f"⚠️ Erro na análise inicial: {e}")
            raise

    def get_real_market_data(self):
        """Obtém e processa dados de mercado da Binance"""
        try:
            # Requisição dos dados + construção do DataFrame
            df = self.build_dataframe(
                self.client.get_klines(
                    symbol=self.symbol,    # Par de negociação (ex: BNBUSDT)
                    interval=self.interval, # Intervalo (ex: 1m, 5m)
                    limit=100              # Quantidade de candles
                )
            )
            # Atualiza preço atual (último fechamento)
            self.current_price = df["close"].iat[-1] 
            
            print(f"✅ Dados recebidos | Preço: {self.current_price:.2f}")
            return df
            
        except Exception as e:
            error_msg = f"⚠️ Falha na consulta: {str(e)}"[:4000]  # Limite de 4000 caracteres no erro do Telegram
            print(error_msg)
            self.telegram.send_message(error_msg)
            raise 

    def moving_average_strategy(self, df):
        """Estratégia com médias móveis"""
        # 1. Configuração dos indicadores
        df["ma_fast"] = df["close"].rolling(12).mean()
        df["ma_slow"] = df["close"].rolling(50).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

        # 2. Obter valores atuais e anteriores (evita múltiplos iloc)
        current_close = df["close"].iloc[-1]
        current_ma_fast = df["ma_fast"].iloc[-1]
        current_ma_slow = df["ma_slow"].iloc[-1]
        prev_ma_fast = df["ma_fast"].iloc[-2]
        prev_ma_slow = df["ma_slow"].iloc[-2]
        
        # 3. Cálculo de volume (penúltimo candle)
        current_volume = df["volume"].iloc[-2]
        volume_ma5 = df["volume"].rolling(5).mean().iloc[-2]

        # 4. Condições de análise (organizadas por relevância)
        price_above_ema = current_close > df["ema_200"].iloc[-1]
        trend_up_now = current_ma_fast > current_ma_slow
        trend_up_prev = prev_ma_fast > prev_ma_slow
        ma_fast_rising = current_ma_fast > prev_ma_fast
        
        # 5. Cálculo de distância com print (mantido igual)
        distance_pct = abs((current_ma_fast - current_ma_slow) / current_ma_slow * 100)
        print(f'Distancia percentual MA12/MA50: {distance_pct:.2f}%')

        # 6. Definição de sinais (lógica inalterada)
        cross_now = True if self.force_cross else not trend_up_prev and trend_up_now
        volume_ok = current_volume > volume_ma5 * self.min_volume_pct
        
        buy_signal = (trend_up_now and cross_now and 
                    distance_pct >= self.min_distance_pct and
                    price_above_ema and volume_ok and ma_fast_rising)
        
        sell_signal = ((not trend_up_now) or 
                    (self.position > 0 and current_close < current_ma_slow) or
                    (self.position > 0 and self.check_stop_loss()))

        # 7. Notificações (mesmo formato original)
        log_msg = self.format_log_message(df, buy_signal, sell_signal, distance_pct, volume_ma5, current_volume)
        self.telegram.send_message(log_msg)

        terminal_summary = (
            f"[{datetime.now().strftime('%H:%M:%S')}] {self.symbol} | "
            f"Preço: R${self.current_price:.2f} | "
            f"{'📈 Sinal de COMPRA' if buy_signal else '📉 Sinal de VENDA' if sell_signal else '⏸️ Nenhum sinal'}"
        )
        print(terminal_summary)

        return buy_signal, sell_signal, distance_pct, df

    def format_log_message(self, df, buy_signal, sell_signal, distance_pct, volume_ma5, current_volume):
        """Formata a mensagem de log no padrão"""
        # Dados básicos
        current_time = datetime.now().strftime('[%H:%M:%S]')
        ma_fast = df['ma_fast'].iloc[-1]
        ma_slow = df['ma_slow'].iloc[-1]
        ema200 = df['ema_200'].iloc[-1]
        ma_fast_prev = df['ma_fast'].iloc[-2]
        ma_slow_prev = df['ma_slow'].iloc[-2]
        
        # Cálculos
        def calc_pct_change(price, reference):
            return (price - reference) / reference * 100
            
        price_change_fast = calc_pct_change(self.current_price, ma_fast)
        price_change_slow = calc_pct_change(self.current_price, ma_slow)
        price_change_ema = calc_pct_change(self.current_price, ema200)
        
        # Formatações
        trend = "Alta ▲" if ma_fast > ma_slow else "Baixa ▼"
        result = ("📈 SINAL DE COMPRA" if buy_signal else 
                "📉 SINAL DE VENDA" if sell_signal else 
                "⏸️ NENHUM SINAL")
        
        def format_volume(vol):
            return f"{vol/1000:.1f}K" if vol >= 1000 else f"{vol:.2f}"
        
        # Condições reutilizadas
        price_above_ema = self.current_price > ema200
        ma_cross = (ma_fast > ma_slow) and not (ma_fast_prev > ma_slow_prev)
        volume_ok = current_volume > volume_ma5 * self.min_volume_pct
        distance_ok = distance_pct > self.min_distance_pct
        stop_loss_triggered = self.position > 0 and self.check_stop_loss()
        price_below_ma50 = self.current_price < ma_slow
        ma12_below_ma50 = ma_fast < ma_slow
        
        # Construção da mensagem (mantendo exatamente o mesmo formato)
        log_msg = (
            f"📊 {current_time} {self.symbol} @ R${self.current_price:.2f}\n"
            f"▪️ MA12: R${ma_fast:.2f} ({'▲' if price_change_fast >= 0 else '▼'} {abs(price_change_fast):.1f}%)\n"
            f"▪️ MA50: R${ma_slow:.2f} ({'▲' if price_change_slow >= 0 else '▼'} {abs(price_change_slow):.1f}%)\n"
            f"▪️ EMA200: R${ema200:.2f} ( {'▲' if price_change_ema >= 0 else '▼'} {abs(price_change_ema):.1f}%)\n"
            f"▪️ Volume: {format_volume(current_volume)} vs Média {format_volume(volume_ma5)}\n"
            f"▪️ Distância MAs: {distance_pct:.1f}% (Mínimo: 0.2%)\n"
            f"▪️ Tendência: {trend}\n"
            f"▪️ Posição: {result}\n\n"
            f"BUY\n"
            f"├─ {'✅' if price_above_ema else '❌'} Preço > EMA200\n"
            f"├─ {'✅' if self.force_cross or ma_cross else '❌'} MA12 cruzou MA50 ▲\n"
            f"├─ {'✅' if volume_ok else '❌'} Volume (45%)> Média\n"
            f"└─ {'✅' if distance_ok else '❌'} Distância MAs > 0.2%\n\n"
            f"SELL\n"
            f"├─ {'✅' if stop_loss_triggered else '❌'} Stop-Loss 2%\n"
            f"├─ {'✅' if price_below_ma50 else '❌'} Valor < MA50\n"
            f"└─ {'✅' if ma12_below_ma50 else '❌'} MA12 < MA50"
        )
        return log_msg

    def print_terminal_log(self, execution_time, api_status, buy_signal, sell_signal):
        """Exibe o log formatado no terminal"""
        current_time = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        position_status = "Neutro" if self.position == 0 else f"Posição Aberta ({self.position:.4f} ({self.symbol}))"
        
        if buy_signal:
            result = "📈 SINAL DE COMPRA"
        elif sell_signal:
            result = "📉 SINAL DE VENDA"
        else:
            result = "⏸️ NENHUM SINAL"
        
        # Formatação do log
        log = f"""
            ────────────────────────────────────────────
            ▶️ Consulta realizada em: {current_time}
            ⚡ Tempo de execução: {execution_time:.2f}s
            🔌 API Status: {api_status}
            💰 Preço atual: R$ {self.current_price:.2f}
            📊 Posição atual: {position_status}
            🧭 Resultado: {result}
            ────────────────────────────────────────────

            DIAGNÓSTICO
            🔧 Conexão: OK
            🔁 Dados completos: True
            ⏱️ Latência: {execution_time:.2f}s
            ✅ Análise concluída com sucesso
            ────────────────────────────────────────────
            """
        print(log)

    def plot_chart(self, df):
        """Gera e salva gráfico dos últimos 50 candles com indicadores técnicos"""
        # Pré-processamento dos dados
        subset = df.tail(50).copy()  # Evita SettingWithCopyWarning
        colors = np.where(subset['close'] >= subset['open'], 'green', 'red')  # Vetorizado
        
        # Configuração do layout
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), 
                                    gridspec_kw={'height_ratios': [2, 1]},
                                    sharex=True)
        
        # Gráfico de preço
        price_lines = [
            ('Preço', 'blue', '-', subset['close'], 1.5),
            ('MA12', 'green', '--', subset['ma_fast'], 1),
            ('MA50', 'red', '--', subset['ma_slow'], 1),
            ('EMA200', 'yellow', ':', subset['ema_200'], 1)
        ]
        for label, color, linestyle, values, lw in price_lines:
            ax1.plot(subset.index, values, label=label, color=color, 
                    linestyle=linestyle, linewidth=lw)
        
        # Marcadores de posição (se houver)
        if self.position > 0:
            ax1.axhline(self.entry_price, color='orange', label='Entrada')
            ax1.axhline(self.entry_price * 0.98, color='red', 
                    linestyle=':', label='Stop 2%')

        # Gráfico de volume (vetorizado)
        ax2.bar(subset.index, subset['volume'], color=colors, alpha=0.4)
        ax2.plot(subset.index, subset['volume'].rolling(5).mean(), 
                color='blue', label='Média 5')

        # Configurações 
        ax1.set_title(f"{self.symbol} - 50 Candles")
        ax1.grid(True)
        ax1.legend()
        ax2.legend()
        
        plt.tight_layout()  
        plt.savefig("grafico.png", dpi=100, bbox_inches='tight') # Salva a figura em arquivo PNG com configurações otimizadas
        plt.close(fig)  # Libera memória explicitamente

    def check_stop_loss(self):
        """Verifica se atingiu stop-loss de 2% abaixo do preço de entrada"""
        if self.position <= 0:
            return False
            
        stop_loss_price = self.entry_price * 0.98
        return self.current_price <= stop_loss_price

    def calculate_position_size(self):
        """Calcula o tamanho da posição baseado no risco por trade"""
        position_size = (self.balance * self.risk_per_trade) / self.current_price
        return round(position_size, 4)  # Arredonda para 4 casas decimais
    
    def simulate_trade(self, action):
        """Executa operação simulada de compra/venda com taxas reais"""
        try:
            print(f"🎮 Simulando {action}...")
            fee_rate = 0.00075  # Taxa maker da Binance (0.075%)

            if action == "BUY":
                return self._execute_buy(fee_rate)
            elif action == "SELL":
                return self._execute_sell(fee_rate)
            else:
                raise ValueError(f"Ação inválida: {action}")

        except Exception as e:
            error_msg = f"⚠️ Erro na simulação: {str(e)}"
            print(error_msg)
            self.telegram.send_message(error_msg[:4000])  # Limita tamanho para Telegram
            raise

    def _execute_buy(self, fee_rate):
        """Lógica dedicada para operações de COMPRA"""
        # Cálculos iniciais
        trade_amount = self.calculate_position_size()
        cost = trade_amount * self.current_price
        fee = cost * fee_rate
        total_cost = cost + fee

        # Validação de saldo
        if total_cost > self.balance:
            msg = (f"⚠️ Saldo insuficiente\n• Preço: {self.current_price:.2f}\n"
                f"• Custo: {cost:.2f}\n• Taxa: {fee:.2f}\n• Total: {total_cost:.2f}\n"
                f"• Saldo: {self.balance:.2f}")
            print(msg)
            self.telegram.send_message(msg)
            return False

        # Execução da compra
        self.balance -= total_cost
        self.position += trade_amount
        self.entry_price = self.current_price

        # Registro no histórico
        self.trade_history.append({
            "type": "BUY",
            "amount": trade_amount,
            "price": self.current_price,
            "time": datetime.now().strftime("%d/%m %H:%M"),
            "fee": fee
        })

        # Notificação
        msg = (f"🟢 <b>COMPRA Simulada</b>\n▪️ Par: {self.symbol}\n"
            f"▪️ Qtd: {trade_amount:.4f}\n▪️ Preço: {self.current_price:.2f}\n"
            f"▪️ Custo: {cost:.2f}\n▪️ Taxa: {fee:.2f}\n▪️ Total: {total_cost:.2f}\n"
            f"▪️ Saldo: {self.balance:.2f}\n🛑 Stop: {self.entry_price * 0.98:.2f} (2%)")
        
        print(msg.replace('<b>', '').replace('</b>', ''))
        self.telegram.send_message(msg)
        return True

    def _execute_sell(self, fee_rate):
        """Lógica dedicada para operações de VENDA"""
        # Validação de posição
        if self.position <= 0:
            msg = "⚠️ Sem posição para vender"
            print(msg)
            self.telegram.send_message(msg)
            return False

        # Cálculos da venda
        gross_revenue = self.position * self.current_price
        fee = gross_revenue * fee_rate
        net_revenue = gross_revenue - fee
        profit = net_revenue - (self.position * self.entry_price)
        profit_pct = (profit / (self.position * self.entry_price)) * 100
        pl_total = ((self.balance + net_revenue - 30000) / 30000) * 100

        # Execução da venda
        self.balance += net_revenue
        
        # Registro no histórico
        self.trade_history.append({
            "type": "SELL",
            "amount": self.position,
            "price": self.current_price,
            "time": datetime.now().strftime("%d/%m %H:%M"),
            "fee": fee,
            "profit": profit,
            "profit_pct": profit_pct
        })

        # Notificação
        msg = (f"🔴 <b>VENDA Simulada</b>\n▪️ Par: {self.symbol}\n"
            f"▪️ Qtd: {self.position:.4f}\n▪️ Preço: {self.current_price:.2f}\n"
            f"▪️ Receita: {gross_revenue:.2f}\n▪️ Taxa: {fee:.2f}\n"
            f"▪️ Liquido: {net_revenue:.2f}\n\n💰 <b>RELATÓRIO</b>\n"
            f"▪️ Saldo: {self.balance:.2f}\n▪️ P/L: {pl_total:.2f}%\n"
            f"📈 Lucro: {profit:.2f} ({profit_pct:.2f}%)")
        
        print(msg.replace('<b>', '').replace('</b>', ''))
        self.telegram.send_message(msg)

        # Reset de posição
        self.position = 0
        self.entry_price = 0
        return True

    def run(self):
        """Loop principal do simulador"""
        while True:
            try:
                print("\n" + "="*50)
                print(f"⏰ Ciclo iniciado em {datetime.now().strftime('%H:%M:%S')}")
            
                # 1. Obter dados
                market_data = self.get_real_market_data()
                api_status = "OK"
                start_time = time.time()

            
                # 2. Verificar stop-loss
                if self.position > 0 and self.check_stop_loss():
                    print("⚠️ Stop-loss atingido, vendendo posição...")
                    self.simulate_trade("SELL")
                    self.stop_loss_cooldown = 3  # cooldown após stop
                    self.plot_chart(market_data)  # Gráfico na venda por stop
                    self.telegram.send_photo(
                        caption=f"🛑 <b>STOP-LOSS ATINGIDO</b>\n"
                           f"▪️ Par: {self.symbol}\n"
                           f"▪️ Preço: BRL {self.current_price:.2f}\n"
                           f"▪️ Preço Entrada: BRL {self.entry_price:.2f}\n"
                           f"▪️ Perda: {100*(self.current_price/self.entry_price-1):.2f}%",
                        image_path="grafico.png"
                    )
            
                # 3. Aplicar estratégia
                buy_signal, sell_signal, distance, market_data = self.moving_average_strategy(market_data)

                 # Mostra o log formatado no terminal
                execution_time = time.time() - start_time
                self.print_terminal_log(execution_time, api_status, buy_signal, sell_signal)
                
                # 4. Executar operações com relatórios detalhados
                if buy_signal and self.balance > 10:
                    if self.simulate_trade("BUY"):
                        self.plot_chart(market_data)
                        self.telegram.send_photo(
                            caption=(
                                f"📈 <b>GRÁFICO DE COMPRA</b>\n"
                                f"▪️ Par: {self.symbol}\n"
                                f"▪️ Preço: BRL {self.current_price:.2f}\n"
                                f"▪️ Distância Médias: {distance:.2f}%\n"
                                f"▪️ Stop Loss: BRL {self.entry_price*0.98:.2f}\n"
                                f"▪️ Alvo Inicial: BRL {self.entry_price*1.05:.2f} (+5%)"
                            ),
                            image_path="grafico.png"
                        )
            
                elif sell_signal and self.position > 0:
                    profit_pct = 100 * (self.current_price - self.entry_price) / self.entry_price
                    self.simulate_trade("SELL")
                    self.plot_chart(market_data)  # Gráfico na venda também
                    self.telegram.send_photo(
                        caption=(
                            f"📉 <b>GRÁFICO DE VENDA</b>\n"
                            f"▪️ Par: {self.symbol}\n"
                            f"▪️ Preço: BRL {self.current_price:.2f}\n"
                            f"▪️ Preço Entrada: BRL {self.entry_price:.2f}\n"
                            f"▪️ Resultado: {profit_pct:.2f}%\n"
                            f"▪️ Motivo: {'Tendência revertida' if not trend_up_now else 'Stop dinâmico'}"
                        ),
                        image_path="grafico.png"
                    )   

                if self.stop_loss_cooldown > 0:
                    self.stop_loss_cooldown -= 1
                time.sleep(30)
            
            except Exception as e:
                error_msg = f"⚠️ Erro: {str(e)}"
                print(error_msg)
                self.telegram.send_message(error_msg)
                time.sleep(60)  # Espera 1 minuto antes de tentar novamente

if __name__ == "__main__":
    print("⏳ Iniciando o bot...")
    try:
        bot = BinanceSimulator()
        bot.run()
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        raise
