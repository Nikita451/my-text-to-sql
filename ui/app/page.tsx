import Link from 'next/link';
import { Plus } from 'lucide-react';
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
    <main className="max-w-6xl mx-auto px-4 py-12">    
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-10 border-b border-slate-200 pb-6 bg-white">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-slate-900 mb-2">
            Мои проекты
          </h1>
          <p className="text-sm text-slate-600 leading-relaxed max-w-xl">
            Выберите рабочий проект, чтобы начать диалог со своими данными через ИИ-ассистента.
          </p>
        </div>
        <Link
          href="/create"
          className="bg-slate-900 hover:bg-slate-800 text-white font-medium px-4 py-2.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 whitespace-nowrap active:scale-[0.98] shadow-sm shadow-slate-900/5"
        >
          <Plus className="w-4 h-4 text-slate-400" />
          <span>Создать проект</span>
        </Link>
      </div>
      <WorkspaceList initialWorkspaces={workspaces} />
    </main>
  );
}
