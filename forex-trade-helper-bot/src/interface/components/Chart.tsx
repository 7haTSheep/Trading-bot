import React from 'react';
import { Line } from 'react-chartjs-2';

interface ChartProps {
    data: { time: string; price: number }[];
}

const Chart: React.FC<ChartProps> = ({ data }) => {
    const chartData = {
        labels: data.map(point => point.time),
        datasets: [
            {
                label: 'Forex Price',
                data: data.map(point => point.price),
                borderColor: 'rgba(75,192,192,1)',
                borderWidth: 2,
                fill: false,
            },
        ],
    };

    return <Line data={chartData} />;
};

export default Chart;