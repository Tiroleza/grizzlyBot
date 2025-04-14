import pandas as pd

class MovingAverageStrategy:
    def __init__(self, fast_window=20, slow_window=40):
        self.fast_window = fast_window
        self.slow_window = slow_window
    
    def calculate(self, data):
        data["ma_fast"] = data["close"].rolling(window=self.fast_window).mean()
        data["ma_slow"] = data["close"].rolling(window=self.slow_window).mean()
        return data
    
    def decide(self, data):
        last_ma_fast = data["ma_fast"].iloc[-1]
        last_ma_slow = data["ma_slow"].iloc[-1]
        return last_ma_fast > last_ma_slow

        