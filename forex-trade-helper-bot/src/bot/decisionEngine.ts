import { TradeSignal, TradeDecision } from '../types';

export class DecisionEngine {
    private riskPercentage: number;
    private accountBalance: number;

    constructor(riskPercentage: number, accountBalance: number) {
        this.riskPercentage = riskPercentage;
        this.accountBalance = accountBalance;
    }

    public makeTradeDecision(tradeSignal: TradeSignal): TradeDecision {
        const lotSize = this.calculateLotSize(tradeSignal);

        return {
            symbol: tradeSignal.symbol,
            entryPrice: tradeSignal.entryPrice,
            exitPrice: tradeSignal.exitPrice,
            lotSize,
            decision: tradeSignal.direction === 'buy' ? 'enter' : 'exit',
            signal: tradeSignal,
            timestamp: new Date(),
        };
    }

    public calculateLotSize(tradeSignal: TradeSignal): number {
        const riskAmount = this.accountBalance * (this.riskPercentage / 100);
        const pipValue = this.getPipValue(tradeSignal);
        const riskPips = Math.abs(tradeSignal.entryPrice - (tradeSignal.stopLoss || 0)) * 10000; // Assuming 1 pip = 0.0001
        const lotSize = riskAmount / (riskPips * pipValue);
        return Math.max(0.01, Math.min(100, lotSize));  // Clamp between 0.01 and 100 lots

    }

    private getPipValue(tradeSymbol: TradeSignal): number {

        const isJPY = tradeSymbol.includes('JPY');
        const contractSize = 100000; // Standard contract size for forex pairs

        return isJPY ? 0.01 * contractSize : 0.0001 * contractSize; // Pip value for JPY pairs is different
    }

    public updateAccountBalance(balance: number) {
        this.accountBalance = balance;
    }
}