'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { FileText, UploadCloud, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import {getBaseApiUrl} from '@/utils/api'

export default function CreateWorkspace() {
  const router = useRouter();
  const [wsName, setWsName] = useState('');
  const [description, setDescription] = useState('');
  const [sqlFile, setSqlFile] = useState<File | null>(null);
  const [jsonFile, setJsonFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sqlFile || !jsonFile || !wsName || !description) return;

    setIsLoading(true);
    setStatus(null);

    const formData = new FormData();
    formData.append('name', wsName);
    formData.append('description', description);
    formData.append('sql_file', sqlFile);
    formData.append('few_shot_file', jsonFile);

    try {
      const res = await fetch(`${getBaseApiUrl()}/api/onboard`, {
        method: 'POST',
        body: formData,
      });
      
      if (res.ok) {
        setStatus({ type: 'success', msg: 'Окружение успешно создано! Инициализируем Postgres и Qdrant...' });
        setTimeout(() => {
          router.push('/'); // Возвращаем на главную после успеха
        }, 2000);
      } else {
        setStatus({ type: 'error', msg: 'Ошибка сервера при создании окружения. Проверьте логи.' });
      }
    } catch (error) {
      setStatus({ type: 'error', msg: 'Не удалось связаться с сервером бэкенда.' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto">
      <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white mb-6 group transition">
      </Link>
      {/* Системные уведомления */}
      {status && (
        <div className={`p-3.5 rounded-xl border mb-6 text-xs flex items-start gap-2.5 animate-in fade-in duration-200 ${
          status.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
        }`}>
          {status.type === 'success' ? <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
          <span>{status.msg}</span>
        </div>
      )}

      <form 
        onSubmit={handleSubmit} 
        className="space-y-6 bg-white border border-zinc-200 rounded-2xl p-6 md:p-8 shadow-[0_10px_40px_rgba(0,0,0,0.04)] max-w-xl mx-auto"
      >
        <div>
          <h2 className="text-xl font-bold text-zinc-900 tracking-tight mb-1">Новый проект</h2>
          <p className="text-xs text-zinc-500">Настройте окружение для вашего ИИ-агента</p>
        </div>

        {/* Пункт 1: Название воркспейса */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-800 tracking-tight">Название проекта</label>
          <input 
            type="text" 
            required
            placeholder="Аналитика интернет-магазина" 
            value={wsName} 
            onChange={e => setWsName(e.target.value)}
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-3.5 py-2.5 text-sm text-zinc-900 placeholder-zinc-400 outline-none hover:bg-zinc-100/50 focus:bg-white focus:border-zinc-900 focus:ring-1 focus:ring-zinc-900 transition-all font-normal"
          />
        </div>

        {/* Пункт 2: Описание */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-800 tracking-tight">Описание контекста <span className="text-zinc-400 font-normal">(необязательно)</span></label>
          <textarea 
            placeholder="Какие таблицы здесь лежат, за что они отвечают..." 
            value={description} 
            onChange={e => setDescription(e.target.value)}
            className="w-full bg-zinc-50 border border-zinc-200 rounded-xl px-3.5 py-2.5 text-sm text-zinc-900 placeholder-zinc-400 outline-none hover:bg-zinc-100/50 focus:bg-white focus:border-zinc-900 focus:ring-1 focus:ring-zinc-900 transition-all h-20 resize-none font-normal leading-relaxed"
          />
        </div>

        {/* Пункт 3: Схема данных (.sql) */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-800 tracking-tight">Файл структуры данных (.sql)</label>
          <div className={`relative border border-dashed rounded-xl p-5 text-center transition-all ${
            sqlFile 
              ? 'border-blue-500 bg-blue-50/30' 
              : 'border-zinc-300 bg-zinc-50/50 hover:bg-zinc-50 hover:border-zinc-400'
          }`}>
            <input 
              type="file" 
              required
              accept=".sql" 
              onChange={e => setSqlFile(e.target.files?.[0] || null)}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
            <div className="flex flex-col items-center justify-center gap-1">
              <UploadCloud className={`w-5 h-5 mb-1 ${sqlFile ? 'text-blue-600' : 'text-zinc-400'}`} />
              {sqlFile ? (
                <p className="text-xs font-semibold text-blue-700 font-mono flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" /> {sqlFile.name}
                </p>
              ) : (
                <>
                  <p className="text-xs font-semibold text-zinc-800">Перетащите или выберите файл .sql</p>
                  <p className="text-[11px] text-zinc-400">Экспорт схемы вашей БД (DDL таблицы)</p>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Пункт 4: Примеры Few-Shot (.json) */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-800 tracking-tight">Примеры запросов для обучения (.json)</label>
          <div className={`relative border border-dashed rounded-xl p-5 text-center transition-all ${
            jsonFile 
              ? 'border-indigo-500 bg-indigo-50/30' 
              : 'border-zinc-300 bg-zinc-50/50 hover:bg-zinc-50 hover:border-zinc-400'
          }`}>
            <input 
              type="file" 
              required
              accept=".json" 
              onChange={e => setJsonFile(e.target.files?.[0] || null)}
              className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
            />
            <div className="flex flex-col items-center justify-center gap-1">
              <UploadCloud className={`w-5 h-5 mb-1 ${jsonFile ? 'text-indigo-600' : 'text-zinc-400'}`} />
              {jsonFile ? (
                <p className="text-xs font-semibold text-indigo-700 font-mono flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5" /> {jsonFile.name}
                </p>
              ) : (
                <>
                  <p className="text-xs font-semibold text-zinc-800">Перетащите или выберите файл .json</p>
                  <p className="text-[11px] text-zinc-400">Массив пар {"{ text, sql }"} для контекстного обучения ИИ</p>
                </>
              )}
            </div>
          </div>
        </div>
        <button 
          type="submit" 
          disabled={isLoading || !sqlFile || !jsonFile || !wsName}
          className="w-full bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-100 disabled:text-zinc-400 disabled:border-zinc-200 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-xl text-sm transition-all flex items-center justify-center gap-2 mt-4 active:scale-[0.99]"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-zinc-400" />
              <span>Создание окружения...</span>
            </>
          ) : (
            <span>Инициализировать проект</span>
          )}
        </button>
      </form>
    </div>
  );
}
