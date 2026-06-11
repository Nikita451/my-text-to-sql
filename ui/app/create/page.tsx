'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Database, FileText, UploadCloud, ChevronLeft, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import Link from 'next/link';
import {getBaseApiUrl} from '@/utils/api'

export default function CreateWorkspace() {
  const router = useRouter();
  
  // Состояния из вашей логики формы + новые для UX
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
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 font-sans antialiased py-12 px-4 selection:bg-blue-500/30">
      <div className="max-w-xl mx-auto">
        
        {/* Кнопка назад */}
        <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-white mb-6 group transition">
          <ChevronLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
          <span>Назад к пространствам</span>
        </Link>

        {/* Заголовок */}
        <div className="mb-8">
          <h1 className="text-2xl font-extrabold tracking-tight text-white mb-1.5">
            Новое рабочее пространство
          </h1>
          <p className="text-xs text-slate-400 leading-relaxed">
            Загрузите схему данных и примеры вопросов. Система развернет изолированную векторную коллекцию в Qdrant дляFew-Shot генерации.
          </p>
        </div>

        {/* Системные уведомления */}
        {status && (
          <div className={`p-3.5 rounded-xl border mb-6 text-xs flex items-start gap-2.5 animate-in fade-in duration-200 ${
            status.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
          }`}>
            {status.type === 'success' ? <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
            <span>{status.msg}</span>
          </div>
        )}

        {/* Красивая форма */}
        <form onSubmit={handleSubmit} className="space-y-5 bg-[#070A13] border border-slate-800/80 rounded-2xl p-6 shadow-2xl">
          
          {/* Пункт 1: Название воркспейса (для UI главной) */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Название проекта</label>
            <input 
              type="text" 
              required
              placeholder="Например: Аналитика интернет-магазина" 
              value={wsName} 
              onChange={e => setWsName(e.target.value)}
              className="w-full bg-[#0F1524] border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none focus:border-blue-500/80 transition-all"
            />
          </div>

          {/* Пункт 2: Описание (для UI главной) */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Описание контекста (необязательно)</label>
            <textarea 
              placeholder="Какие таблицы здесь лежат, за что они отвечают..." 
              value={description} 
              onChange={e => setDescription(e.target.value)}
              className="w-full bg-[#0F1524] border border-slate-800 rounded-xl px-3.5 py-2.5 text-sm text-slate-200 placeholder-slate-600 outline-none focus:border-blue-500/80 transition-all h-16 resize-none"
            />
          </div>

          {/* Пункт 4: Схема данных (.sql) */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Файл структуры данных (.sql)</label>
            <div className={`relative border-2 border-dashed rounded-xl p-4 text-center transition group ${
              sqlFile ? 'border-blue-500/40 bg-blue-500/[0.02]' : 'border-slate-800 hover:border-slate-700 bg-[#0F1524]/50'
            }`}>
              <input 
                type="file" 
                required
                accept=".sql" 
                onChange={e => setSqlFile(e.target.files?.[0] || null)}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <div className="flex flex-col items-center justify-center gap-1.5">
                <UploadCloud className={`w-6 h-6 ${sqlFile ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-400'}`} />
                {sqlFile ? (
                  <p className="text-xs font-medium text-blue-300 font-mono flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> {sqlFile.name}
                  </p>
                ) : (
                  <>
                    <p className="text-xs font-medium text-slate-300">Перетащите или выберите .sql файл</p>
                    <p className="text-[10px] text-slate-500">Экспорт схемы вашей БД (DDL таблицы)</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Пункт 4: Примеры Few-Shot (.json) */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Примеры запросов для Qdrant (.json)</label>
            <div className={`relative border-2 border-dashed rounded-xl p-4 text-center transition group ${
              jsonFile ? 'border-indigo-500/40 bg-indigo-500/[0.02]' : 'border-slate-800 hover:border-slate-700 bg-[#0F1524]/50'
            }`}>
              <input 
                type="file" 
                required
                accept=".json" 
                onChange={e => setJsonFile(e.target.files?.[0] || null)}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              <div className="flex flex-col items-center justify-center gap-1.5">
                <UploadCloud className={`w-6 h-6 ${jsonFile ? 'text-indigo-400' : 'text-slate-500 group-hover:text-slate-400'}`} />
                {jsonFile ? (
                  <p className="text-xs font-medium text-indigo-300 font-mono flex items-center gap-1">
                    <FileText className="w-3.5 h-3.5" /> {jsonFile.name}
                  </p>
                ) : (
                  <>
                    <p className="text-xs font-medium text-slate-300">Перетащите или выберите `.json` файл</p>
                    <p className="text-[10px] text-slate-500">Массив пар {"{ text, sql }"} для контекстного обучения ИИ</p>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Кнопка отправки */}
          <button 
            type="submit" 
            disabled={isLoading || !sqlFile || !jsonFile || !wsName || !description}
            className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white font-medium py-2.5 rounded-xl text-sm transition shadow-lg shadow-blue-600/10 flex items-center justify-center gap-2 mt-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Создание окружения...</span>
              </>
            ) : (
              <span>Инициализировать воркспейс</span>
            )}
          </button>
        </form>

      </div>
    </div>
  );
}
