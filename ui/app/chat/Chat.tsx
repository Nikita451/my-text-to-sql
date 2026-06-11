'use client';

import { useState, useRef, useEffect } from 'react';
import { Workspace } from '../types';
import {getBaseApiUrl} from '@/utils/api'

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatProps {
  workspace: Workspace;
}

export default function Home({workspace}: ChatProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState<string>(''); // Сюда пишем текущего агента
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Автопрокрутка чата вниз при новых сообщениях
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }]);
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
                  { role: 'assistant', content: data.content },
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
    <div>
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

      {/* Форма отправки */}
      <footer className="bg-white border-t border-slate-200 p-4 shadow-lg">
        <form onSubmit={handleSubmit} className="max-w-4xl w-full mx-auto flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Например: Сколько заказов сделал самый активный пользователь?"
            disabled={isLoading}
            className="flex-1 p-3 border border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 text-sm"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-6 py-3 rounded-xl transition disabled:bg-slate-300 text-sm"
          >
            Отправить
          </button>
        </form>
      </footer>
    </div>
  );
}
