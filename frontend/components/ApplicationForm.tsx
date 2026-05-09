"use client";
import { useState } from "react";

type FormData = {
  position: string;
  salary_expectation: string;
  contact_email: string;
  notes: string;
};

type Props = {
  onSubmit: (data: FormData) => Promise<void>;
  onCancel: () => void;
  loading: boolean;
};

export default function ApplicationForm({ onSubmit, onCancel, loading }: Props) {
  const [form, setForm] = useState<FormData>({
    position: "",
    salary_expectation: "",
    contact_email: "",
    notes: "",
  });

  const set = (field: keyof FormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.value }));

  return (
    <div className="mt-4 bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <h3 className="font-semibold text-gray-700">Zapisz aplikację</h3>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-sm text-gray-600">Stanowisko</span>
          <input
            type="text"
            placeholder="np. AI Engineer"
            value={form.position}
            onChange={set("position")}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </label>

        <label className="block">
          <span className="text-sm text-gray-600">Oczekiwania finansowe</span>
          <input
            type="text"
            placeholder="np. 15 000 PLN netto"
            value={form.salary_expectation}
            onChange={set("salary_expectation")}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </label>

        <label className="block">
          <span className="text-sm text-gray-600">E-mail kontaktowy</span>
          <input
            type="email"
            placeholder="np. hr@firma.pl"
            value={form.contact_email}
            onChange={set("contact_email")}
            className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          />
        </label>
      </div>

      <label className="block">
        <span className="text-sm text-gray-600">Notatki</span>
        <textarea
          rows={3}
          placeholder="Dodatkowe informacje..."
          value={form.notes}
          onChange={set("notes")}
          className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
        />
      </label>

      <div className="flex gap-3 justify-end">
        <button
          onClick={onCancel}
          disabled={loading}
          className="px-4 py-2 text-sm rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50"
        >
          Anuluj
        </button>
        <button
          onClick={() => onSubmit(form)}
          disabled={loading}
          className="px-4 py-2 text-sm rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? "Zapisuję..." : "Zapisz i szukaj dalej"}
        </button>
      </div>
    </div>
  );
}
