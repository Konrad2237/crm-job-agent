"use client";
import { useState } from "react";

type FormData = {
  name: string;
  url: string;
  what_they_do: string;
  position: string;
  salary_expectation: string;
  contact_email: string;
  notes: string;
};

type Props = {
  onSubmit: (data: FormData) => Promise<void>;
  onClose: () => void;
  loading: boolean;
};

export default function ManualEntryModal({ onSubmit, onClose, loading }: Props) {
  const [form, setForm] = useState<FormData>({
    name: "",
    url: "",
    what_they_do: "",
    position: "",
    salary_expectation: "",
    contact_email: "",
    notes: "",
  });
  const [error, setError] = useState<string | null>(null);

  const set =
    (field: keyof FormData) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));

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
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Dodaj firmę ręcznie</h2>
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

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">Nazwa firmy</span>
            <input
              type="text"
              placeholder="np. Acme AI sp. z o.o."
              value={form.name}
              onChange={set("name")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">URL strony</span>
            <input
              type="url"
              placeholder="https://acme.ai"
              value={form.url}
              onChange={set("url")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">Czym się zajmuje</span>
            <input
              type="text"
              placeholder="np. automatyzacje procesów biznesowych z AI"
              value={form.what_they_do}
              onChange={set("what_they_do")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-900 font-medium">Stanowisko</span>
            <input
              type="text"
              placeholder="np. AI Engineer"
              value={form.position}
              onChange={set("position")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-900 font-medium">Oczekiwania finansowe</span>
            <input
              type="text"
              placeholder="np. 15 000 PLN netto"
              value={form.salary_expectation}
              onChange={set("salary_expectation")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">E-mail kontaktowy</span>
            <input
              type="email"
              placeholder="np. hr@acme.ai"
              value={form.contact_email}
              onChange={set("contact_email")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400"
            />
          </label>

          <label className="block sm:col-span-2">
            <span className="text-sm text-gray-900 font-medium">Notatki</span>
            <textarea
              rows={3}
              placeholder="Skąd firma, co wiesz, link do ogłoszenia..."
              value={form.notes}
              onChange={set("notes")}
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
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
            {loading ? "Dodaję..." : "Dodaj firmę"}
          </button>
        </div>
      </div>
    </div>
  );
}
