export function calculatePips(entryPrice: number, exitPrice: number): number {
    return (exitPrice - entryPrice) * 10000; // Assuming the price is in a format where 1 pip = 0.0001
}

export function formatTradeData(tradeData: any): string {
    return `Trade Info: 
    Entry Price: ${tradeData.entryPrice}, 
    Exit Price: ${tradeData.exitPrice}, 
    Lot Size: ${tradeData.lotSize}, 
    Pips: ${calculatePips(tradeData.entryPrice, tradeData.exitPrice)}`;
}