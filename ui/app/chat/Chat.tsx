'use client';

import { useState, useRef, useEffect } from 'react';
import { Workspace } from '../types';
import {getBaseApiUrl} from '@/utils/api'
import { Message } from '@/types/chat';
import { ChatChart } from '@/components/chat-chart';

interface ChatProps {
  workspace: Workspace;
}

export default function Home({workspace}: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState<string>(''); // Сюда пишем текущего агента
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const projectName = workspace.name;

  // Автопрокрутка чата вниз при новых сообщениях
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage, chart: null }]);
    setIsLoading(true);
    setStatus('Инициализация агентов...');

    try {
      // Делаем POST запрос к нашему FastAPI бэкенду
      const response = await fetch(`${getBaseApiUrl()}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          db_name: workspace.internal_db_name,
          col_name: workspace.internal_col_name,
          thread_id: workspace.internal_db_name, // Общий id сессии для памяти диалога
        }),
      });

      if (!response.body) throw new Error('Поток данных пуст');

      // Начинаем построчно читать асинхронный SSE-поток
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        // Декодируем прилетевший чанк текста и добавляем в буфер
        // Опция { stream: true } склеивает обрывки бинарных данных (на уровне байт кодировки UTF-8) 
        buffer += decoder.decode(value, { stream: true });
        
        // SSE строки всегда разделяются двумя переносами строк (\n\n)
        const lines = buffer.split('\n\n');
        // Мехинака склеивает обрывки текстовых строк (на уровне букв и JSON)
        buffer = lines.pop() || ''; // Оставляем незавершенную строку в буфере

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.replace('data: ', '').trim();
            if (!jsonStr) continue;

            try {
              const data = JSON.parse(jsonStr);

              if (data.type === 'status') {
                // Изменяем статус над строкой ввода (какой агент сейчас думает)
                setStatus(data.message);
              } else if (data.type === 'final_answer') {
                // Если прилетел финальный ответ — выключаем крутилку и пушим в чат
                setMessages((prev) => [
                  ...prev,
                  { role: 'assistant', content: data.content, chart: data.chart },
                ]);
                setStatus('');
                setIsLoading(false);
              } else if (data.type === 'error') {
                setStatus(`❌ Ошибка: ${data.message}`);
                setIsLoading(false);
              }
            } catch (err) {
              console.error('Ошибка парсинга SSE строки:', err);
            }
          }
        }
      }
    } catch (error) {
      console.error('Критическая ошибка сети:', error);
      setStatus('💥 Ошибка подключения к серверу бэкенда.');
      setIsLoading(false);
    }
  };

  return (
    <div className='flex-1 flex flex-col overflow-hidden w-full'>
      {/* Окно сообщений */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-4xl w-full mx-auto">
        {messages.length === 0 && (
          <div className="text-center py-20 text-slate-400 space-y-2">
            <p className="text-lg font-medium">👋 Добро пожаловать в ИИ-аналитик!</p>
            <p className="text-sm">Задайте любой аналитический вопрос по вашей базе данных.</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-2xl p-4 rounded-2xl shadow-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-none'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-bl-none'
              }`}
            >
              <p className="text-sm">{msg.content}</p>

              {msg.role === 'assistant' && msg.chart && (
                <div className="mt-2 w-full">
                  <ChatChart chartData={msg.chart} />
                </div>
              )}
            </div>
          </div>
        ))}
        
        {/* Логгер статуса размышлений агентов */}
        {isLoading && (
          <div className="flex justify-start items-center gap-3 bg-indigo-50 border border-indigo-100 p-3 rounded-xl max-w-xl animate-pulse">
            <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-xs font-medium text-indigo-700">{status}</p>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <footer className="bg-white border-t border-slate-200 p-4 shadow-[0_-10px_40px_rgba(0,0,0,0.02)] flex-shrink-0">
        <form onSubmit={handleSubmit} className="max-w-4xl w-full mx-auto flex items-center gap-3">
          <div className="hidden sm:inline-flex items-center gap-2 px-3 py-3 h-[46px] rounded-xl bg-slate-50 border border-slate-200/80 shadow-sm whitespace-nowrap flex-shrink-0">
            {/* Пульсирующая точка активного контекста */}
            <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-pulse" />
            <span className="text-xs font-semibold text-slate-500">
              Проект: <span className="text-slate-900 font-bold">{projectName}</span>
            </span>
          </div>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Спросите меня что-нибудь на обычном языке..."
            disabled={isLoading}
            className="flex-1 p-3 h-[46px] bg-slate-50 border border-slate-200 rounded-xl outline-none hover:bg-slate-100/50 focus:bg-white focus:border-zinc-900 focus:ring-1 focus:ring-zinc-900 disabled:bg-slate-100 text-sm text-slate-900 placeholder-slate-400 transition-all"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-slate-900 hover:bg-slate-800 text-white font-medium px-5 h-[46px] rounded-xl transition-all text-sm disabled:bg-slate-100 disabled:text-slate-400 disabled:border-slate-200 disabled:cursor-not-allowed flex items-center justify-center active:scale-[0.98] flex-shrink-0"
          >
            Отправить
          </button>
        </form>
      </footer>
    </div>
  );
}
