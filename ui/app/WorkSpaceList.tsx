'use client';
import { useState } from 'react';
import {Workspace} from './types';
import Link from 'next/link';
import { Database, Cpu, ArrowRight, Layers, Search, MessageSquare } from 'lucide-react';

interface WorkspaceListProps {
  initialWorkspaces: Workspace[];
}

export default function WorkspaceList({ initialWorkspaces }: WorkspaceListProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const filteredWorkspaces = initialWorkspaces.filter(ws => 
    ws.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (ws.description || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div>
        <div className="relative mb-8 max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Поиск по названию или описанию..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-[#f4f4f4] border border-slate-200 rounded-lg py-2.5 pl-10 pr-4 text-sm text-slate-900 placeholder-slate-400 outline-none hover:border-slate-300 focus:bg-white focus:border-slate-900 focus:ring-1 focus:ring-slate-900 transition-all"
          />
        </div>
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
                href={`/chat?workspace_id=${ws.id}`}
                className="group relative bg-[#f4f4f4] border border-slate-200/80 rounded-xl p-6 hover:border-blue-500 hover:shadow-[0_8px_30px_rgb(0,0,0,0.04)] transition-all duration-200 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <h3 className="font-bold text-base text-slate-900 group-hover:text-blue-600 transition-colors truncate">
                      {ws.name}
                    </h3>
                    <div className="bg-slate-50 group-hover:bg-blue-50 p-1.5 rounded-md transition-colors flex-shrink-0">
                      <ArrowRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 group-hover:translate-x-0.5 transition-all" />
                    </div>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed mb-6 line-clamp-3">
                    {ws.description || "Описание проекта отсутствует."}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-100 text-[11px]">
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-50/70 text-blue-700 font-medium">
                      <Database className="w-3.5 h-3.5" />
                      <span>SQL</span>
                    </span>
                    <span className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-indigo-50/70 text-indigo-700 font-medium">
                      <Cpu className="w-3.5 h-3.5" />
                      <span>Vector</span>
                    </span>
                  </div>
                  
                  <span className="text-slate-900 flex items-center gap-1.5 font-medium">
                    <MessageSquare className="w-3.5 h-3.5 text-slate-900" />
                    {new Intl.DateTimeFormat('ru-RU', {
                      day: 'numeric',
                      month: 'long', // 'long' выведет "июня", 'numeric' выведет "06"
                      year: 'numeric'
                    }).format(new Date(ws.created_at))}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
    </div>
  );
}