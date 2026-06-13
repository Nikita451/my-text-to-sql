'use client';

import { Bar, BarChart, Line, LineChart, Pie, PieChart, XAxis, YAxis, CartesianGrid } from 'recharts';
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'; // Путь к shadcn компонентам
import { ChartData } from '@/types/chat';

const formatCurrency = (value: number) => {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return value.toString();
};

export function ChatChart({ chartData }: { chartData: ChartData }) {
  const chartConfig = {
    value: {
      label: chartData.label,
      color: 'hsl(var(--primary))',
    },
  } satisfies ChartConfig;

  return (
    <div className="w-full mt-4 p-4 border rounded-xl bg-background shadow-sm">
      <h4 className="text-sm font-medium mb-4 text-muted-foreground">{chartData.label}</h4>
      
      <ChartContainer config={chartConfig} className="min-h-[200px] max-h-[300px] w-full">
        {chartData.type === 'bar' && (
          <BarChart data={chartData.data} margin={{ left: -20, right: 10 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" opacity={0.3} />
            {/* Исползуем 'name' для оси X */}
            <XAxis dataKey="name" tickLine={false} tickMargin={10} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={70} tickFormatter={formatCurrency} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}

        {chartData.type === 'line' && (
          <LineChart data={chartData.data} margin={{ left: -20, right: 10 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" opacity={0.3} />
            {/* Исползуем 'name' для оси X */}
            <XAxis dataKey="name" tickLine={false} tickMargin={10} axisLine={false} />
            <YAxis tickLine={false} axisLine={false} width={70} tickFormatter={formatCurrency} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Line type="monotone" dataKey="value" stroke="#4f46e5" strokeWidth={2.5} dot={{ fill: '#4f46e5', r: 4 }} />

          </LineChart>
        )}

        {chartData.type === 'pie' && (
          <PieChart>
            <ChartTooltip content={<ChartTooltipContent hideLabel />} />
            <Pie
              data={chartData.data}
              dataKey="value"
              nameKey="name" // Связываем сегменты пирога с именами категорий
              innerRadius={60}
              strokeWidth={5}
              fill="#4f46e5"
            />
          </PieChart>
        )}
      </ChartContainer>
    </div>
  );
}