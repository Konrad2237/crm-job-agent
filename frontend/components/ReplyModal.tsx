"use client";
import { useState } from "react";
import { Company } from "@/lib/api";

export const REPLY_STATUS_OPTIONS = [
  { value: "", label: "Brak odpowiedzi" },
  { value: "rejected", label: "Odrzucono" },
  { value: "interview", label: "Zaproszono na rozmowę" },
  { value: "offer", label: "Oferta pracy" },
];

type ReplyData = {
  reply_status: string;
  reply_received: string;
};

type Props = {
  company: Company;
  onSubmit: (data: ReplyData) => Promise<void>;
  onClose: () => void;
  loading: boolean;
};

export default function ReplyModal({ company, onSubmit, onClose, loading }: Props) {
  const [form, setForm] = useState<ReplyData>({
    reply_status: company.reply_status ?? "",
    reply_received: company.reply_received ?? "",
  });
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    try {
      await onSubmit(form);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nieznany błąd. Spróbuj ponownie.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Odpowiedź od firmy</h2>
            <p className="text-sm text-gray-500 mt-0.5">{company.name}</p>
          </div>
          <button
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600 disabled:opacity-50 text-xl leading-none"
          >
            ✕
          </button>
        </div>

        {error && (
          <p className="rounded-lg bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-gray-600">Status odpowiedzi</span>
            <select
              value={form.reply_status}
              onChange={(e) => setForm((prev) => ({ ...prev, reply_status: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            >
              {REPLY_STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-gray-600">Kiedy / jak</span>
            <input
              type="text"
              placeholder="np. email 22 maja, rejection po 2 tygodniach"
              value={form.reply_received}
              onChange={(e) => setForm((prev) => ({ ...prev, reply_received: e.target.value }))}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>
        </div>

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            Anuluj
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Zapisuję..." : "Zapisz"}
          </button>
        </div>
      </div>
    </div>
  );
}
