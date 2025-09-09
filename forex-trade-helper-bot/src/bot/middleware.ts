import { Request, Response, NextFunction } from 'express';
import axios from 'axios';

const API_URL = 'https://api.forex.com/v1/marketdata';

interface MarketDataRequest extends Request {
    marketData?: any;
}

export const fetchMarketDataMiddleware = async (req: MarketDataRequest, res: Response, next: NextFunction) => {
    try {
        const response = await axios.get(API_URL);
        req.marketData = response.data;
        next();
    } catch (error) {
        console.error('Error fetching market data:', error);
        res.status(500).send('Error fetching market data');
    }
};

export const validateTradeParameters = (req: Request, res: Response, next: NextFunction) => {
    const { entryPrice, exitPrice, lotSize } = req.body;
    if (!entryPrice || !exitPrice || !lotSize) {
        return res.status(400).send('Missing trade parameters');
    }
    next();
};