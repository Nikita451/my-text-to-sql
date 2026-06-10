'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Plus, Database, Cpu, ArrowRight, Layers, Search, Loader2, MessageSquare } from 'lucide-react';

// Чистые данные без утечки инфраструктурных названий
const initialWorkspaces = [
  { 
    id: '1', 
    name: 'Аналитика продаж', 
    description: 'Контекст основного интернет-магазина. Анализ выручки, заказов и поведения покупателей.',
    updatedAt: '2 часа назад' 
  },
  { 
    id: '2', 
    name: 'Маркетинговая CRM', 
    description: 'Данные рекламных кампаний, лидов и профилей клиентов из сквозной аналитики.',
    updatedAt: 'Вчера' 
  },
  { 
    id: '3', 
    name: 'Тестовая песочница', 
    description: 'Изолированное окружение со сгенерированными данными для проверки сложных SQL-запросов.',
    updatedAt: '3 дня назад' 
  },
];

interface Workspace {
  id: string;
  name: string;
  description: string | null;
  internal_db_name: string;
  internal_col_name: string;
  created_at: string;
}

export default function WorkspacesDashboard() {
  const [workspaces, setWorkspaces] = useState(initialWorkspaces);
  const [searchTerm, setSearchTerm] = useState('');

  const filteredWorkspaces = workspaces.filter(ws => 
    ws.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    ws.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 font-sans antialiased selection:bg-blue-500/30">
      
      {/* Верхняя навигация */}
      <header className="border-b border-slate-800/60 bg-[#070A13]/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="bg-blue-600 p-2 rounded-xl shadow-lg shadow-blue-600/20">
              <Layers className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              SQL.ai
            </span>
          </div>
          <div className="text-sm text-slate-500 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Сервер активен
          </div>
        </div>
      </header>

      {/* Основной блок */}
      <main className="max-w-6xl mx-auto px-4 py-12">
        
        {/* Заголовок и кнопка */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white mb-1">
              Рабочие пространства
            </h1>
            <p className="text-sm text-slate-400">
              Выберите проект, чтобы начать диалог со своими данными через ИИ-ассистента.
            </p>
          </div>
          
          <Link
            href="/create"
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium px-4 py-2.5 rounded-xl text-sm transition-all shadow-lg shadow-blue-600/10 flex items-center justify-center gap-2 whitespace-nowrap"
          >
            <Plus className="w-4 h-4" />
            <span>Создать проект</span>
          </Link>
        </div>

        {/* Поиск */}
        <div className="relative mb-8 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Поиск по названию или описанию..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#070A13] border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-blue-500/80 transition-all"
          />
        </div>

        {/* Сетка элементов */}
        {filteredWorkspaces.length === 0 ? (
          <div className="border border-dashed border-slate-800 rounded-2xl p-12 text-center max-w-md mx-auto mt-12">
            <Layers className="w-8 h-8 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-400 font-medium mb-1">Ничего не найдено</p>
            <p className="text-xs text-slate-500">Попробуйте изменить поисковый запрос.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filteredWorkspaces.map((ws) => (
              <Link 
                key={ws.id} 
                href={`/chat/${ws.id}`}
                className="group relative bg-[#070A13] border border-slate-800/80 rounded-2xl p-5 hover:border-slate-700/80 hover:bg-[#090D1A] transition-all duration-300 flex flex-col justify-between shadow-sm hover:shadow-xl hover:shadow-blue-600/[0.01]"
              >
                <div>
                  {/* Заголовок карточки */}
                  <div className="flex items-start justify-between gap-4 mb-2">
                    <h3 className="font-semibold text-slate-200 group-hover:text-blue-400 transition-colors truncate">
                      {ws.name}
                    </h3>
                    <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-blue-400 group-hover:translate-x-1 transition-all opacity-0 group-hover:opacity-100 flex-shrink-0" />
                  </div>

                  {/* Безопасное описание */}
                  <p className="text-xs text-slate-400 leading-relaxed mb-6 line-clamp-3 group-hover:text-slate-300 transition-colors">
                    {ws.description}
                  </p>
                </div>

                {/* Безопасный футер: статус подключения инфраструктуры без раскрытия имен */}
                <div className="flex items-center justify-between pt-3 border-t border-slate-800/40 text-[11px]">
                  <div className="flex items-center gap-3 text-slate-500">
                    <span className="flex items-center gap-1" title="База данных PostgreSQL подключена">
                      <Database className="w-3 h-3 text-blue-500/70" />
                      <span className="text-[10px]">SQL</span>
                    </span>
                    <span className="flex items-center gap-1" title="Векторная коллекция Qdrant активна">
                      <Cpu className="w-3 h-3 text-indigo-500/70" />
                      <span className="text-[10px]">Vector</span>
                    </span>
                  </div>
                  <span className="text-slate-500 flex items-center gap-1">
                    <MessageSquare className="w-3 h-3 opacity-60" />
                    {ws.updatedAt}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
