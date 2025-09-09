import React from 'react';
import type { TradeSignal } from '../types';

interface TradeInfoProps {
    trade: TradeSignal;
}

const TradeInfo: React.FC<TradeInfoProps> = ({ trade }) => (
    <div className="trade-info">
        <h2>Trade Information</h2>
        <p>Symbol: {trade.symbol}</p>
        <p>Entry Point: {trade.entryPoint}</p>
        <p>Exit Point: {trade.exitPoint}</p>
    </div>
);

export default TradeInfo;