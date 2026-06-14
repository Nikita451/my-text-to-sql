import { Workspace } from '../types';
import Link from 'next/link';
import Chat from './Chat';
import {getBaseApiUrl} from '@/utils/api';

interface ChatPageProps {
  // Next.js автоматически передает параметры строки поиска сюда
  searchParams: Promise<{ workspace_id?: string }>;
}

async function getWorkspaceDetails(workspaceId: string): Promise<Workspace> {
  console.log(workspaceId)
  const res = await fetch(`${getBaseApiUrl()}/api/onboard/workspace/${workspaceId}`, {
    cache: 'no-store'
  });
  if (!res.ok) throw new Error('Воркспейс не найден');
  return res.json();
}

export default async function Home({ searchParams }: ChatPageProps) {
  const { workspace_id } = await searchParams;
  if (!workspace_id) {
    return (
      <div className="p-6 text-center">
        <p className="text-red-500 font-semibold">Ошибка: Рабочее пространство не выбрано.</p>
        <Link href="/" className="text-blue-600 underline mt-2 inline-block">
          Вернуться на дашборд
        </Link>
      </div>
    );
  }

  const workspace = await getWorkspaceDetails(workspace_id);
  
  return (
    <main className="flex flex-col h-screen w-screen overflow-hidden bg-slate-50 text-slate-800">
      <Chat workspace={workspace} />
    </main>
  );
}
