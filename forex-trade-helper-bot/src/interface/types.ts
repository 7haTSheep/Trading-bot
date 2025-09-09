export interface TradeSignal {
    symbol: string;
    currencyPair: string;
    entryPoint: number;
    exitPoint: number;
    stopLoss: number;
    takeProfit: number;
    direction: 'buy' | 'sell';
    timestamp: Date;
}

export interface TradeDecision {
    symbol: string;
    entryprice: number;
    exitprice: number;
    lotSize: number;
    action: 'enter' | 'exit' | 'hold';
    timestamp: Date;
}

export interface MarketDataPoint {
    time: string;
    price: number;
}

export interface MarketData {
    currencyPair: string;
    bidPrice: number;
    askPrice: number;
    lastPrice: number;
    volume: number;
    timestamp: Date;
    prices: MarketDataPoint[];
}

export interface TradeSignalWithDecision extends TradeSignal {
    decision: TradeDecision;
}

export interface TradeInfo {
    trade: TradeSignal;
    entryPoint: number;
    exitPoint: number;
    lotSize: number;
}