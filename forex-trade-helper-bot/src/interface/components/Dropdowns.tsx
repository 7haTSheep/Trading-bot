import React, { Dispatch, SetStateAction } from 'react';
import { TradeSignal } from '../../types';

interface DropdownsProps {
    options: string[];
    selectedOption: string;
    onOptionChange: (value: string) => void;
    generateTradeSignal: (currencyPair: string) => TradeSignal | null;
    setTradeSignal: Dispatch<SetStateAction<TradeSignal | null>>;
}

const Dropdowns: React.FC<DropdownsProps> = ({
    options,
    selectedOption,
    onOptionChange,
    generateTradeSignal,
    setTradeSignal
}) => (
    <div>
        <label htmlFor="trade-options">Select Currency Pair:</label>
        <select
            id="trade-options"
            value={selectedOption}
            onChange={(e) => {
                const value = e.target.value;
                onOptionChange(value);
                const signal = generateTradeSignal(value);
                setTradeSignal(signal);
            }}
        >
            {options.map((option) => (
                <option key={option} value={option}>
                    {option}
                </option>
            ))}
        </select>
    </div>
);

export default Dropdowns;

