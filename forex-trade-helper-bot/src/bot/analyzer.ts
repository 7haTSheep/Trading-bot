import { MarketData } from '../interface/types';
import { TradeSignal } from '../interface/types';


export class MarketAnalyzer {
    private marketData: MarketData;

    constructor(marketData: MarketData) {
        this.marketData = marketData;
    }

    analyzeMarket() {
        const prices = this.marketData.prices.map(p => p.price);
        const shortMA = this.calculateMA(prices, 5);
        const longMA = this.calculateMA(prices, 20);

        return { shortMA, longMA, lastPrice: this.marketData.lastPrice };
    }

    getTradeSignals(): TradeSignal | null {
        const { shortMA, longMA } = this.analyzeMarket();
        const lastPrice = this.marketData.lastPrice;

        if (shortMA[shortMA.length - 1] > longMA[longMA.length - 1] &&
            shortMA[shortMA.length - 2] <= longMA[longMA.length - 2]) {
            // Buy signal (short MA crosses above long MA)

            return {
                symbol: this.marketData.currencyPair,
                currencyPair: this.marketData.currencyPair,
                entryPoint: lastPrice,
                exitPoint: lastPrice * 1.02, // 1% target
                stopLoss: lastPrice * 0.98, // 1% stop loss
                takeProfit: lastPrice * 1.05, // 1% take profit
                direction: 'buy',
                timestamp: new Date(),
            };
        }

        if (shortMA[shortMA.length - 1] < longMA[longMA.length - 1] &&
            shortMA[shortMA.length - 2] >= longMA[longMA.length - 2]) {
            // Sell signal (short MA crosses below long MA)

            return {
                symbol: this.marketData.currencyPair,
                currencyPair: this.marketData.currencyPair,
                entryPoint: lastPrice,
                exitPoint: lastPrice * 0.98, // 1% target
                stopLoss: lastPrice * 1.02, // 1% stop loss
                takeProfit: lastPrice * 0.95, // 1% take profit
                direction: 'sell',
                timestamp: new Date(),
            };
        }

        return null; // No trade signal
    }

    private calculateMA(prices: number[], period: number): number[] {
        const ma: number[] = [];
        for (let i = period - 1; i < prices.length; i++) {
            const slice = prices.slice(i - period + 1, i + 1);
            const avg = slice.reduce((sum, val) => sum + val, 0) / period;
            ma.push(avg);
        }
        return ma;
    }
}