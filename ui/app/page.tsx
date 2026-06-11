import Link from 'next/link';
import { Plus, Layers } from 'lucide-react';
import WorkspaceList from './WorkSpaceList';
import {getBaseApiUrl} from '@/utils/api'

interface Workspace {
  id: string;
  name: string;
  description: string | null;
  internal_db_name: string;
  internal_col_name: string;
  created_at: string;
}

async function getWorkspaces(): Promise<Workspace[]> {
  // cache: 'no-store' отключает агрессивное кэширование Next.js,
  // чтобы при добавлении новой БД список на главной обновлялся мгновенно
  const res = await fetch(`${getBaseApiUrl()}/api/onboard/workspaces`, {
    cache: 'no-store', 
  });

  if (!res.ok) {
    throw new Error('Не удалось загрузить список воркспейсов на сервере');
  }

  return res.json();
}

export default async function WorkspacesDashboard() {
  const workspaces = await getWorkspaces();

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

        <WorkspaceList initialWorkspaces={workspaces} />
      </main>
    </div>
  );
}
