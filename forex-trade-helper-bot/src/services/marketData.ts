import axios from 'axios';

const API_URL = 'https://api.forex.com/v1/marketdata'; // Example API URL

export const fetchMarketData = async (currencyPair: string) => {
    try {
        const response = await axios.get(`${API_URL}/${currencyPair}`);
        return response.data;
    } catch (error) {
        console.error('Error fetching market data:', error);
        throw error;
    }
};

export const subscribeToMarketUpdates = (currencyPair: string, callback: (data: any) => void, p0: (err: Error) => void) => {
    const socket = new WebSocket(`wss://api.forex.com/v1/marketdata/${currencyPair}`);

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        callback(data);
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    return () => {
        socket.close();
    };
};