import React, { useState, useEffect, useCallback } from "react";
import Chat from './components/Chart';
import Dropdowns from "./components/Dropdowns";
import TradeInfo from "./components/TradeInfo";
import { MarketAnalyzer } from "../bot/analyzer";
import { DecisionEngine } from "../bot/decisionEngine";
import { TradeSignal, MarketData } from "./types";
import { subscribeToMarketUpdates } from "../services/marketData";
import { TradeDecision } from "./types";
import Chart from "chart.js";

const App: React.FC = () => {
    const [MarketData, setMarketData] = useState<MarketData | null>(null);
    const [tradeSignal, setTradeSignal] = useState<TradeSignal | null>(null);
    const [tradeDecision, setTradeDecision] = useState<TradeDecision | null>(null);
    const [selectedOption, setSelectedOption] = useState<string>('EUR/USD');
    const [error, setError] = useState<string | null>(null);

    const currencyPairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD'];

    const generateTradeSignal = useCallback((currencyPair: string): TradeSignal | null => {
        if (!MarketData) return null;

        const analyzer = new MarketAnalyzer(MarketData);
        return analyzer.getTradeSignals();
    }, [MarketData]);

    const DecisionEngine = new DecisionEngine(2, 10000); //2% requestIdleCallback, $10k balance 

    useEffect(() => {
        if (!selectedOption) return;

        const unsubscribe = subscribeToMarketUpdates(
            selectedOption,
            (data: MarketData) => {
                setMarketData(data);
                setError(null);

                // Generate new trade signal on data update
                const signal = generateTradeSignal(selectedOption);
                setTradeSignal(signal);

                if (signal) {
                    const decision = DecisionEngine.makeTradeDecision(signal);
                    setTradeDecision(decision);
                }
            },
            (err: Error) => {
                setError(`Market data error: ${err.message}`);
                console.error('WebSocket error:', err);
            }
        );

        return () => unsubscribe();
    }, [selectedOption, generateTradeSignal]);

    return (
        <div>
            <h1>Forex Trade Helper Bot</h1>
            {error && <div className="error">{error}</div>}

            <Dropdowns
                options={currencyPairs}
                selectedOption={selectedOption}
                onOptionChange={setSelectedOption}

                generateTradeSignal={generateTradeSignal}
                setTradeSignal={setTradeSignal}
            />

            {MarketData && (
                <Chart data={MarketData.prices} />
            )}

            {tradeSignal && <TradeInfo trade={tradeSignal} />}
            {tradeDecision && (
                <div className="trade-decision">
                    <h2>Trade Decision</h2>
                    <p>Action: {tradeDecision.action}</p>
                    <p>Lot Size: {tradeDecision.lotSize.toFixed(2)}</p>
                </div>
            )}
        </div>
    );
}