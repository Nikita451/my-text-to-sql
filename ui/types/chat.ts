export interface DataPoint {
  argument: string; // Поле 'argument' из Pydantic
  value: number;    // Поле 'value' из Pydantic
}

export interface ChartData {
  label: string;
  type: 'bar' | 'line' | 'pie';
  data: DataPoint[];
}

export interface Message {
  // id: string;
  role: 'user' | 'assistant';
  content: string;
  chart?: ChartData | null; // График привязан к конкретному сообщению
}
