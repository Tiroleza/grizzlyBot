import os
import time
from datetime import datetime
import logging
import json
import matplotlib.pyplot as plt
import pandas as pd
import requests

from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv

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

        for chat_id in self.authorized_ids:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML"
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
        
        # Configurações
        self.symbol = "SOLBRL"
        self.interval = Client.KLINE_INTERVAL_1MINUTE
        self.risk_per_trade = 0.04  # 4% do capital por trade
        
        # Estado da simulação
        self.balance = 30000  # Saldo inicial em BRL
        self.position = 0  # Quantidade de cripto
        self.entry_price = 0  # Preço médio de entrada
        self.trade_history = []
        self.current_price = 0
        
        # Teste de conexão inicial
        self.test_connection()
        
        self.telegram.send_message(
            f"🚀 <b>Iniciando Simulação</b>\n"
            f"Par: {self.symbol}\n"
            f"Saldo inicial: BRL {self.balance:.2f}\n"
            f"Intervalo: {self.interval}\n"
            f"Risco por trade: {self.risk_per_trade*100}%\n"
            f"Modo: Consulta Real + Operação Simulada"
        )
        
        # Debug inicial
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

    def get_real_market_data(self):
        """Obtém dados reais da Binance"""
        try:
            print("📡 Obtendo dados do mercado...")
            candles = self.client.get_klines(
                symbol=self.symbol,
                interval=self.interval,
                limit=100
            )
            
            df = pd.DataFrame(candles, columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades",
                "taker_buy_volume", "taker_quote_volume", "ignore"
            ])
            
            # Convertendo tipos
            numeric_cols = ["open", "high", "low", "close", "volume"]
            df[numeric_cols] = df[numeric_cols].astype(float)
            
            self.current_price = df["close"].iloc[-1]
            print(f"✅ Dados recebidos | Preço atual: {self.current_price:.2f}")
            return df
            
        except Exception as e:
            error_msg = f"⚠️ Falha na consulta: {e}"
            print(error_msg)
            self.telegram.send_message(error_msg)
            raise

    def moving_average_strategy(self, df):
        """Estratégia com médias móveis e filtros adicionais"""
        # Configuração dos indicadores
        df["ma_fast"] = df["close"].rolling(12).mean()  # Média rápida (12 períodos)
        df["ma_slow"] = df["close"].rolling(50).mean()  # Média lenta (50 períodos)
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()  # EMA para tendência
    
        # Cálculo de condições
        price_above_ema200 = df["close"].iloc[-1] > df["ema_200"].iloc[-1]
        trend_up_now = df["ma_fast"].iloc[-1] > df["ma_slow"].iloc[-1]
        trend_up_prev = df["ma_fast"].iloc[-2] > df["ma_slow"].iloc[-2]
        cross_now = not trend_up_prev and trend_up_now
    
        # Cálculos adicionais
        distance_pct = 100 * abs(df["ma_fast"].iloc[-1] - df["ma_slow"].iloc[-1]) / df["ma_slow"].iloc[-1]
        min_distance_pct = 0.5
        volume_avg = df["volume"].rolling(5).mean().iloc[-1] #volume de 5 candles 
        volume_ok = df["volume"].iloc[-1] > volume_avg * 1.1 # volume maior que 10% da media dos 5 candles
    
        # Sinal de compra
        buy_signal = (trend_up_now and cross_now and distance_pct > min_distance_pct 
                     and price_above_ema200 and volume_ok)
    
        # Sinal de venda
        sell_signal = (not trend_up_now) or (self.position > 0 and df["close"].iloc[-1] < df["ma_slow"].iloc[-1])
    
        # Preparar mensagem detalhada para o Telegram
        signal_details = (
            f"📊 <b>ANÁLISE DO MERCADO</b>\n"
            f"▪️ Par: {self.symbol}\n"
            f"▪️ Preço Atual: BRL {self.current_price:.2f}\n"
            f"▪️ MA Fast (12): BRL {df['ma_fast'].iloc[-1]:.2f}\n"
            f"▪️ MA Slow (50): BRL {df['ma_slow'].iloc[-1]:.2f}\n"
            f"▪️ EMA 200: BRL {df['ema_200'].iloc[-1]:.2f}\n"
            f"▪️ Distância: {distance_pct:.2f}% (Mín: {min_distance_pct}%)\n"
            f"▪️ Volume: {df['volume'].iloc[-1]:.2f} vs Média {volume_avg:.2f}\n\n"
            f"📈 <b>SINAIS</b>\n"
            f"▪️ Tendência de Alta: {'✅ SIM' if trend_up_now else '❌ NÃO'}\n"
            f"▪️ Cruzamento: {'✅ CONFIRMADO' if cross_now else '❌ NÃO CONFIRMADO'}\n"
            f"▪️ Acima EMA200: {'✅ SIM' if price_above_ema200 else '❌ NÃO'}\n"
            f"▪️ Volume OK: {'✅ SIM' if volume_ok else '❌ NÃO'}\n"
            f"▪️ Sinal de COMPRA: {'✅ ATIVADO' if buy_signal else '❌ NÃO ATIVADO'}\n"
            f"▪️ Sinal de VENDA: {'✅ ATIVADO' if sell_signal else '❌ NÃO ATIVADO'}"
        )
    
        # Enviar análise para o Telegram
        self.telegram.send_message(signal_details)
    
        return buy_signal, sell_signal, distance_pct, df

    def plot_chart(self, df):
        """Gera um gráfico dos últimos 50 candles com indicadores"""
        subset = df.tail(50)
        plt.figure(figsize=(12, 6))
        
        # Preço e médias
        plt.plot(subset.index, subset["close"], label="Preço", color="blue", linewidth=1.5)
        plt.plot(subset.index, subset["ma_fast"], label="Média Rápida (12)", color="green", linestyle="--", linewidth=1)
        plt.plot(subset.index, subset["ma_slow"], label="Média Lenta (50)", color="red", linestyle="--", linewidth=1)
        plt.plot(subset.index, subset["ema_200"], label="EMA 200", color="purple", linestyle=":", linewidth=1)
        
        # Destaque para a posição atual
        if self.position > 0:
            plt.axhline(y=self.entry_price, color='orange', linestyle='-', linewidth=1, label='Preço de Entrada')
            stop_loss_price = self.entry_price * 0.98
            plt.axhline(y=stop_loss_price, color='red', linestyle=':', linewidth=1, label='Stop Loss (2%)')
        
        plt.title(f"{self.symbol} - Últimos 50 Candles")
        plt.xlabel("Candles")
        plt.ylabel("Preço (BRL)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig("grafico.png")
        plt.close()

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
        """Executa uma operação simulada com taxa real da Binance"""
        try:
            print(f"🎮 Simulando {action}...")
            fee_rate = 0.00075  # Taxa real da Binance para makers (0.075%)

            if action == "BUY":
                # Calcula tamanho da posição dinamicamente
                trade_amount = self.calculate_position_size()
                cost = trade_amount * self.current_price
                fee = cost * fee_rate
                total_cost = cost + fee

                if total_cost > self.balance:
                    msg = (
                        f"⚠️ Saldo insuficiente\n"
                        f"• Preço: {self.current_price:.2f}\n"
                        f"• Custo: {cost:.2f}\n"
                        f"• Taxa: {fee:.2f}\n"
                        f"• Total: {total_cost:.2f}\n"
                        f"• Saldo: {self.balance:.2f}"
                    )
                    print(msg)
                    self.telegram.send_message(msg)
                    return False

                # Executa a compra
                self.balance -= total_cost
                self.position += trade_amount
                self.entry_price = self.current_price  # Atualiza preço de entrada

                self.trade_history.append({
                    "type": "BUY",
                    "amount": trade_amount,
                    "price": self.current_price,
                    "time": datetime.now().strftime("%d/%m %H:%M"),
                    "fee": fee
                })

                logger.info(f"TRADE BUY - Qtd: {trade_amount} | Preço: {self.current_price:.2f} | Taxa: {fee:.2f}")
                
                msg = (
                    f"🟢 <b>COMPRA Simulada</b>\n"
                    f"▪️ Par: {self.symbol}\n"
                    f"▪️ Quantidade: {trade_amount:.4f} SOL\n"
                    f"▪️ Preço: BRL {self.current_price:.2f}\n"
                    f"▪️ Custo: BRL {cost:.2f}\n"
                    f"▪️ Taxa: BRL {fee:.2f}\n"
                    f"▪️ Total: BRL {total_cost:.2f}\n"
                    f"▪️ Saldo: BRL {self.balance:.2f}\n"
                    f"🛑 Stop Loss: BRL {self.entry_price * 0.98:.2f} (2%)"
                )

            elif action == "SELL":
                if self.position <= 0:
                    msg = "⚠️ Sem posição para vender"
                    print(msg)
                    self.telegram.send_message(msg)
                    return False

                # Executa a venda
                gross_revenue = self.position * self.current_price
                fee = gross_revenue * fee_rate
                net_revenue = gross_revenue - fee

                self.balance += net_revenue
                
                # Calcula resultado da operação
                profit = net_revenue - (self.position * self.entry_price)
                profit_pct = (profit / (self.position * self.entry_price)) * 100

                self.trade_history.append({
                    "type": "SELL",
                    "amount": self.position,
                    "price": self.current_price,
                    "time": datetime.now().strftime("%d/%m %H:%M"),
                    "fee": fee,
                    "profit": profit,
                    "profit_pct": profit_pct
                })

                logger.info(f"TRADE SELL - Qtd: {self.position} | Preço: {self.current_price:.2f} | Taxa: {fee:.2f} | Lucro: {profit:.2f} ({profit_pct:.2f}%)")

                # Relatório completo da carteira após venda
                portfolio_value = self.balance  # Agora só temos saldo em BRL
                initial_balance = 3000  # Saldo inicial
                pl_percent = ((portfolio_value - initial_balance) / initial_balance) * 100
                
                msg = (
                    f"🔴 <b>VENDA Simulada</b>\n"
                    f"▪️ Par: {self.symbol}\n"
                    f"▪️ Quantidade: {self.position:.4f} SOL\n"
                    f"▪️ Preço: BRL {self.current_price:.2f}\n"
                    f"▪️ Receita bruta: BRL {gross_revenue:.2f}\n"
                    f"▪️ Taxa: BRL {fee:.2f}\n"
                    f"▪️ Receita líquida: BRL {net_revenue:.2f}\n\n"
                    f"💰 <b>RELATÓRIO DA CARTEIRA</b>\n"
                    f"▪️ Saldo BRL: {self.balance:.2f}\n"
                    f"▪️ Posição SOL: 0.0000 (zerada)\n"
                    f"▪️ Valor Total: BRL {portfolio_value:.2f}\n"
                    f"▪️ P/L Total: {pl_percent:.2f}%\n\n"
                    f"📈 Lucro da Operação: BRL {profit:.2f} ({profit_pct:.2f}%)"
                )

                # Reseta a posição
                self.position = 0
                self.entry_price = 0

            print(msg.replace('<b>', '').replace('</b>', ''))
            self.telegram.send_message(msg)
            return True

        except Exception as e:
            error_msg = f"⚠️ Erro na simulação: {e}"
            print(error_msg)
            self.telegram.send_message(error_msg)
            raise

    def run(self):
        """Loop principal do simulador"""
        while True:
            try:
                print("\n" + "="*50)
                print(f"⏰ Ciclo iniciado em {datetime.now().strftime('%H:%M:%S')}")
            
                # 1. Obter dados
                market_data = self.get_real_market_data()
            
                # 2. Verificar stop-loss
                if self.position > 0 and self.check_stop_loss():
                    print("⚠️ Stop-loss atingido, vendendo posição...")
                    self.simulate_trade("SELL")
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