export interface TradeSignal {
    includes(arg0: string): unknown;
    symbol: string;
    currencyPair: string;
    entryPrice: number;
    exitPrice: number;
    stopLoss: number;
    takeProfit: number;
    direction: 'buy' | 'sell';
    timestamp: Date;
}

export interface MarketData {
    [x: string]: any;
    currencyPair: string;
    bidPrice: number;
    askPrice: number;
    lastPrice: number;
    volume: number;
    timestamp: Date;
}

export interface TradeDecision {
    symbol: string;
    entryPrice: number;
    exitPrice: number;
    signal: TradeSignal;
    lotSize: number;
    decision: 'enter' | 'exit';
    timestamp: Date;
}